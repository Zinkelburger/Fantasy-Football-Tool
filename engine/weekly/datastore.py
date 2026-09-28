"""Read-only SQL over the saved weekly data, so an agent can ask for the
rows it needs instead of loading whole files into its context.

Every table is a lazy polars frame over files already on disk (no
network). `query()` accepts one SELECT (or WITH ... SELECT), runs it
through polars' SQL engine, which has no statement that writes files,
and returns at most `limit` rows as compact text.

Tables are season-scoped by default; `stats` and `pbp_<year>` cover
every cached season so history questions need no scratch script.
"""
from __future__ import annotations

import re
from pathlib import Path

from common import CACHE, DATA

MAX_ROWS = 200
MAX_CHARS = 12_000
FIRST_STATS_SEASON = 2021

# name -> (description, loader(season) -> LazyFrame | None, example)
_DESCRIPTIONS = {
    "usage": ("one row per player-game with a carry, target or pass: targets, team_targets, "
              "target_share, rush_att, receptions, yards, air_yds, tgt_rz, tgt_ez, snaps_off, snap_share",
              "SELECT week, name, tgt, team_targets, target_share, snap_share FROM usage "
              "WHERE team = 'PIT' AND position = 'TE' ORDER BY week"),
    "targets": ("target share per team/player/week with that week's injury report status "
                "(report_status, report_injury); share = targets / team_targets",
                "SELECT week, name, pos, targets, share, snap_pct, report_status FROM targets "
                "WHERE team = 'LA' ORDER BY week, targets DESC"),
    "vacated": ("players with a real role (>=10% share when active) who had no usage in their "
                "team's latest week or are Out/Doubtful on the latest report, with their share",
                "SELECT * FROM vacated WHERE pos = 'WR' ORDER BY share_when_active DESC"),
    "opportunity_weekly": ("usage-based expected points (ep_std/half/ppr) and actual points "
                           "(pts_std/half/ppr) per player-week, with carries, targets and red-zone usage",
                           "SELECT week, name, ep_std, pts_std, rush_att, tgt, tgt_rz FROM opportunity_weekly "
                           "WHERE name = 'AJ Barner' ORDER BY week"),
    "opportunity": ("season-to-date opportunity row per player: games, EP/g, pts/g, EWMA, per-game usage",
                    "SELECT name, team, pos, games, ewma_ep_std, tgt_pg FROM opportunity "
                    "WHERE pos = 'TE' ORDER BY ewma_ep_std DESC LIMIT 15"),
    "stats": ("nflverse weekly box scores for every cached season (2021 on), all positions "
              "including K (fg_made_40_49, pat_made ...); fantasy_points is standard-ish nflverse "
              "scoring, not this league's; season_type REG/POST",
              "SELECT season, COUNT(*) g, SUM(targets) tgt, SUM(receiving_yards) yds, "
              "SUM(receiving_tds) td FROM stats WHERE player_display_name = 'Darnell Washington' "
              "AND season_type = 'REG' GROUP BY season ORDER BY season"),
    "schedule": ("every game this season: week, gameday, weekday, gametime (ET), away/home team and "
                 "score (null until played), spread_line, total_line, roof, stadium, starting QBs",
                 "SELECT week, away_team, home_team, away_score, home_score FROM schedule "
                 "WHERE away_team = 'MIA' OR home_team = 'MIA' ORDER BY week"),
    "lines": ("per team-week betting context: opp, home, imp_own, imp_opp, spread, total, dome, "
              "kickoff, played (weeks with a posted line only)",
              "SELECT week, team, opp, imp_opp FROM lines WHERE week = 4 ORDER BY imp_opp"),
    "depth": ("latest saved ESPN depth chart (dt = snapshot time): team, player_name, pos_abb, pos_rank",
              "SELECT pos_abb, pos_rank, player_name FROM depth WHERE team = 'PIT' ORDER BY pos_abb, pos_rank"),
    "injuries": ("nflverse weekly injury reports (report_status, practice_status); not current status",
                 "SELECT week, full_name, report_status, report_primary_injury FROM injuries "
                 "WHERE team = 'BAL' AND week = 3"),
    "snaps": ("PFR snap counts per player-game, offense/defense/special teams",
              "SELECT week, player, offense_pct FROM snaps WHERE team = 'NYJ' AND position = 'WR'"),
    "team_context": ("per team-week offence: plays, PROE, EPA, success rates, CPOE, sack rate, "
                     "with <metric>_pctl and <metric>_rk",
                     "SELECT week, team, epa_pass, proe FROM team_context WHERE team = 'CIN'"),
    "players": ("nflverse id crosswalk: gsis_id, espn_id, display_name, position, latest_team, status",
                "SELECT * FROM players WHERE display_name = 'Tre Tucker'"),
    "pbp": ("this season's nflverse play-by-play (~370 columns; use data_tables('pbp', match=...) "
            "to find columns). pbp_<year> holds earlier seasons",
            "SELECT passer_player_name, receiver_player_name, COUNT(*) tgt FROM pbp "
            "WHERE posteam = 'NYG' AND pass_attempt = 1 AND receiver_player_name IS NOT NULL "
            "GROUP BY 1, 2 ORDER BY 1, 3 DESC"),
}


def _csv(path: Path):
    import polars as pl
    return pl.scan_csv(path, infer_schema_length=10_000) if path.exists() else None


def _parquet(path: Path):
    import polars as pl
    return pl.scan_parquet(path) if path.exists() else None


def _targets(season: int):
    """Long target-share table; built from the same inputs as target_share."""
    import polars as pl
    import target_share as ts
    usage = ts._read(DATA / f"advanced_usage_{season}_weekly.csv")
    if not usage:
        return None
    reports = {(r["gsis_id"], int(r["week"])): r
               for r in ts._read(DATA / f"injuries_{season}.csv")}
    rows = []
    for r in usage:
        w, team_t, tgt = int(r["week"]), ts._f(r["team_targets"]), ts._f(r["tgt"])
        rep = reports.get((r["player_id"], w), {})
        rows.append({"season": season, "week": w, "team": r["team"], "player_id": r["player_id"],
                     "name": r["name"], "pos": r["position"], "targets": tgt,
                     "team_targets": team_t, "share": round(tgt / team_t, 3) if team_t else None,
                     "snap_pct": (round(ts._f(r["snap_share"]), 2)
                                  if r.get("snap_share") not in ("", None) else None),
                     "report_status": rep.get("report_status") or None,
                     "report_injury": rep.get("report_primary_injury") or None})
    return pl.DataFrame(rows, infer_schema_length=None).lazy()


def _vacated(season: int):
    import polars as pl
    import target_share as ts
    result = ts.load(DATA, season)
    rows = [{"team": team, "name": f["name"], "pos": f["pos"],
             "share_when_active": f["share_when_active"], "reasons": "; ".join(f["reasons"]),
             "latest_week": t["weeks"][-1]}
            for team, t in result["teams"].items() for f in t["flagged"]]
    schema = {"team": pl.Utf8, "name": pl.Utf8, "pos": pl.Utf8, "share_when_active": pl.Float64,
              "reasons": pl.Utf8, "latest_week": pl.Int64}
    return pl.DataFrame(rows, schema=schema).lazy()


def _stats(season: int):
    import polars as pl
    frames = [pl.scan_parquet(p) for y in range(FIRST_STATS_SEASON, season + 1)
              if (p := CACHE / f"player_stats_{y}.parquet").exists()]
    return pl.concat(frames, how="diagonal_relaxed") if frames else None


def _depth(season: int):
    import polars as pl
    lf = _csv(DATA / f"depth_{season}.csv")
    if lf is None:
        return None
    return lf.filter(pl.col("dt") == pl.col("dt").max())


def _schedule(season: int):
    import polars as pl
    lf = _parquet(CACHE / f"schedules_{season}.parquet")
    if lf is None:
        return None
    return lf.filter(pl.col("game_type") == "REG").select(
        "game_id", "week", "gameday", "weekday", "gametime", "away_team", "home_team",
        "away_score", "home_score", "spread_line", "total_line", "roof", "stadium",
        "away_qb_name", "home_qb_name", "div_game")


def loaders(season: int) -> dict:
    tables = {
        "usage": lambda: _csv(DATA / f"advanced_usage_{season}_weekly.csv"),
        "targets": lambda: _targets(season),
        "vacated": lambda: _vacated(season),
        "opportunity_weekly": lambda: _csv(DATA / f"opportunity_{season}_weekly.csv"),
        "opportunity": lambda: _csv(DATA / f"opportunity_{season}.csv"),
        "stats": lambda: _stats(season),
        "schedule": lambda: _schedule(season),
        "lines": lambda: _csv(DATA / f"lines_{season}.csv"),
        "depth": lambda: _depth(season),
        "injuries": lambda: _csv(DATA / f"injuries_{season}.csv"),
        "snaps": lambda: _parquet(CACHE / f"snaps_{season}.parquet"),
        "team_context": lambda: _csv(DATA / f"team_context_{season}.csv"),
        "players": lambda: _parquet(CACHE / "players.parquet"),
        "pbp": lambda: _parquet(CACHE / f"pbp_{season}.parquet"),
    }
    for p in sorted(CACHE.glob("pbp_*.parquet")):
        year = p.stem.split("_")[1]
        if year.isdigit() and int(year) != season:
            tables[f"pbp_{year}"] = lambda p=p: _parquet(p)
    return tables


def _referenced(sql: str, names) -> list[str]:
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sql.lower()))
    return [n for n in names if n in words]


def describe(season: int, table: str = "", match: str = "") -> str:
    """Table list, or one table's columns (optionally filtered by `match`)."""
    tables = loaders(season)
    if not table:
        out = [f"Tables for season {season} (query with query_data; each is a file already on disk):"]
        for name in tables:
            desc = _DESCRIPTIONS.get(name) or _DESCRIPTIONS["pbp"]
            label = desc[0] if name in _DESCRIPTIONS else f"play-by-play for {name[4:]}, same columns as pbp"
            out.append(f"  {name:18} {label}")
        out.append("Call data_tables(table=NAME) for its columns and an example query.")
        return "\n".join(out)
    key = table.lower()
    if key not in tables:
        return f"unknown table {table!r}; tables: {', '.join(tables)}"
    lf = tables[key]()
    if lf is None:
        return f"{key}: no file on disk for season {season}"
    schema = lf.collect_schema()
    cols = [(c, str(t)) for c, t in schema.items() if match.lower() in c.lower()]
    base = key if key in _DESCRIPTIONS else "pbp"
    out = [f"{key}: {_DESCRIPTIONS[base][0]}",
           f"columns ({len(cols)} of {len(schema)}{f' matching {match!r}' if match else ''}):",
           "  " + ", ".join(f"{c} {t}" for c, t in cols)]
    if base == key:
        out.append(f"example: {_DESCRIPTIONS[key][1]}")
    return "\n".join(out)


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if v == v else "NaN"
    if isinstance(v, (list, tuple)):
        v = "|".join(map(str, v))
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def query(season: int, sql: str, limit: int = 50) -> str:
    """Run one read-only SELECT and return up to `limit` rows as text."""
    import polars as pl
    text = sql.strip().rstrip(";").strip()
    if ";" in text:
        return "one statement only (no ';' inside the query)"
    if not re.match(r"(?is)^(select|with)\b", text):
        return "only SELECT (or WITH ... SELECT) queries are allowed"
    limit = max(1, min(int(limit or 50), MAX_ROWS))
    tables = loaders(season)
    used = _referenced(text, tables)
    if not used:
        return ("the query names no known table; tables: " + ", ".join(tables)
                + " (data_tables() describes them)")
    ctx = pl.SQLContext()
    for name in used:
        lf = tables[name]()
        if lf is None:
            return f"table {name} has no file on disk for season {season}"
        ctx.register(name, lf)
    try:
        df = ctx.execute(text, eager=False).head(limit + 1).collect()
    except Exception as e:  # noqa: BLE001 - return the engine's message to the caller
        msg = str(e).strip().splitlines()[0][:400]
        return f"query failed: {type(e).__name__}: {msg}\n(data_tables(table=...) lists column names)"
    more = df.height > limit
    df = df.head(limit)
    lines = [",".join(df.columns)]
    lines += [",".join(_cell(v) for v in row) for row in df.iter_rows()]
    out, size = [], 0
    for i, line in enumerate(lines):
        size += len(line) + 1
        if size > MAX_CHARS:
            out.append(f"... output cut at {MAX_CHARS} characters after {i - 1} rows; "
                       "select fewer columns or aggregate")
            break
        out.append(line)
    else:
        out.append(f"({df.height} rows{', more exist: raise limit or narrow the WHERE' if more else ''})")
    return "\n".join(out)
