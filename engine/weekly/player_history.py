"""Per-player game logs and past seasons from files already on disk.

  weekly(): this season week by week — opponent, snaps, carries, targets,
      share, red-zone/end-zone looks, yards, TDs, usage-based expected
      points and actual points in the chosen scoring.
  seasons(): regular-season totals per year from nflverse box scores
      (2021 on), with the position rank by nflverse fantasy points.

Kickers and anyone without a usage row come from the box scores alone.
League-scored points (this ESPN league's exact rules) are in
league_points.py; nflverse fantasy points use standard rules and match
this league only approximately.
"""
from __future__ import annotations

import re

from common import CACHE, DATA

FIRST_SEASON = 2021


def norm(name: str) -> str:
    n = re.sub(r"[.'’]", "", (name or "").lower())
    return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())


def _stats(seasons: list[int]):
    import polars as pl
    frames = [pl.scan_parquet(p) for y in seasons
              if (p := CACHE / f"player_stats_{y}.parquet").exists()]
    if not frames:
        return None
    return (pl.concat(frames, how="diagonal_relaxed")
            .filter(pl.col("season_type") == "REG")
            .with_columns(pl.col("player_display_name")
                          .map_elements(norm, return_dtype=pl.Utf8).alias("_norm")))


def find(name: str, season: int) -> list[dict]:
    """Players whose box-score name matches, newest season first:
    [{player_id, name, pos, team, season}]. Exact normalized match wins."""
    import polars as pl
    lf = _stats(list(range(FIRST_SEASON, season + 1)))
    if lf is None:
        return []
    n = norm(name)
    hits = (lf.filter(pl.col("_norm").str.contains(n, literal=True))
            .group_by("player_id")
            .agg(pl.col("player_display_name").last().alias("name"),
                 pl.col("position").last().alias("pos"), pl.col("team").last().alias("team"),
                 pl.col("season").max().alias("season"), pl.col("_norm").last().alias("_norm"))
            .sort("season", descending=True).collect().to_dicts())
    exact = [h for h in hits if h["_norm"] == n]
    return exact or hits


def _read_csv(path):
    import csv
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _n(v, fmt="{:.0f}") -> str:
    return "-" if v is None else fmt.format(v)


def kicker_points(b: dict) -> float:
    """ESPN standard kicker rules (FG 0-39 3, 40-49 4, 50+ 5, XP 1, missed FG
    or XP -1). nflverse leaves kickers at 0 fantasy points; this is an
    approximation of league scoring, league_points has the exact number."""
    g = lambda k: b.get(k) or 0  # noqa: E731
    short = g("fg_made_0_19") + g("fg_made_20_29") + g("fg_made_30_39")
    return (3 * short + 4 * g("fg_made_40_49") + 5 * (g("fg_made_50_59") + g("fg_made_60_"))
            + g("pat_made") - g("fg_missed") - g("pat_missed"))


def weekly(season: int, player_id: str, fmt: str = "std") -> list[str]:
    """Game log lines for one player this season (empty if no games on file)."""
    import polars as pl
    opp = {int(r["week"]): r for r in _read_csv(DATA / f"opportunity_{season}_weekly.csv")
           if r["player_id"] == player_id}
    use = {int(r["week"]): r for r in _read_csv(DATA / f"advanced_usage_{season}_weekly.csv")
           if r["player_id"] == player_id}
    box = {}
    p = CACHE / f"player_stats_{season}.parquet"
    if p.exists():
        for r in (pl.scan_parquet(p).filter((pl.col("player_id") == player_id)
                                            & (pl.col("season_type") == "REG")).collect().to_dicts()):
            box[int(r["week"])] = r
    weeks = sorted(set(opp) | set(use) | set(box))
    if not weeks:
        return []
    kicker = all((box.get(w) or {}).get("position") == "K" for w in weeks)
    if kicker:
        out = ["  wk opp   FG made/att (0-39 40-49 50+)   XP   approx std pts"]
        for w in weeks:
            b = box[w]
            short = sum(b.get(k) or 0 for k in ("fg_made_0_19", "fg_made_20_29", "fg_made_30_39"))
            out.append(f"  {w:>2} {b.get('opponent_team') or '?':4}  {_n(b.get('fg_made'))}/{_n(b.get('fg_att'))} "
                       f"({short} {_n(b.get('fg_made_40_49'))} "
                       f"{(b.get('fg_made_50_59') or 0) + (b.get('fg_made_60_') or 0)})"
                       f"   {_n(b.get('pat_made'))}/{_n(b.get('pat_att'))}   {kicker_points(b):.0f}")
        return out
    if all((box.get(w) or {}).get("position") == "QB" for w in weeks):
        out = [f"  wk opp  cmp/att pass yds td int  car rush yds td   EP {fmt:>4} pts"]
        for w in weeks:
            o, b = opp.get(w, {}), box.get(w, {})
            out.append(f"  {w:>2} {b.get('opponent_team') or '?':4} {_n(b.get('completions')):>3}/{_n(b.get('attempts')):<3} "
                       f"{_n(b.get('passing_yards')):>8} {_n(b.get('passing_tds')):>2} {_n(b.get('passing_interceptions')):>3} "
                       f"{_n(b.get('carries')):>4} {_n(b.get('rushing_yards')):>8} {_n(b.get('rushing_tds')):>2} "
                       f"{_n(_f(o.get(f'ep_{fmt}')), '{:.1f}'):>5} {_n(_f(o.get(f'pts_{fmt}')), '{:.1f}'):>8}")
        return out
    out = [f"  wk opp  snap%  car  tgt share rz ez  rec  yds  td   EP {fmt:>4} pts"]
    for w in weeks:
        o, u, b = opp.get(w, {}), use.get(w, {}), box.get(w, {})
        rz = (_f(o.get("rush_rz")) or 0) + (_f(o.get("tgt_rz")) or 0) if o else None
        yds = (b.get("rushing_yards") or 0) + (b.get("receiving_yards") or 0) if b else None
        td = (b.get("rushing_tds") or 0) + (b.get("receiving_tds") or 0) if b else None
        snap = _f(u.get("snap_share"))
        share = _f(u.get("target_share"))
        out.append(f"  {w:>2} {b.get('opponent_team') or '?':4} {_n(snap * 100 if snap is not None else None):>4}  "
                   f"{_n(_f(o.get('rush_att')) if o else b.get('carries')):>3} "
                   f"{_n(_f(o.get('tgt')) if o else b.get('targets')):>4} "
                   f"{('-' if share is None else f'{share:.2f}'):>5} {_n(rz):>2} {_n(_f(o.get('tgt_ez'))):>2} "
                   f"{_n(b.get('receptions')):>4} {_n(yds):>4} {_n(td):>3} "
                   f"{_n(_f(o.get(f'ep_{fmt}')), '{:.1f}'):>5} {_n(_f(o.get(f'pts_{fmt}')), '{:.1f}'):>8}")
    return out


def seasons(player_id: str, years: list[int]) -> list[str]:
    """Regular-season totals per year with position rank by nflverse points."""
    import polars as pl
    lf = _stats(years)
    if lf is None:
        return ["  no box scores cached for those seasons"]
    have = set(lf.collect_schema().names())

    def total(c):   # a season file without a column (older nflverse) counts it as 0
        return (pl.col(c).fill_null(0).sum() if c in have else pl.lit(0)).alias(c)
    agg = [pl.len().alias("g"), pl.col("team").last(), pl.col("position").last(),
           *(total(c) for c in (
               "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions",
               "carries", "rushing_yards", "rushing_tds", "targets", "receptions",
               "receiving_yards", "receiving_tds", "fg_made", "fg_att", "fg_made_40_49",
               "fg_made_50_59", "fg_made_60_", "pat_made", "pat_att", "fg_missed", "pat_missed",
               "fg_made_0_19", "fg_made_20_29", "fg_made_30_39",
               "fantasy_points", "fantasy_points_ppr"))]
    table = lf.group_by("season", "player_id").agg(*agg).collect()
    # nflverse scores kickers 0; rank them by the approximate standard points.
    c = pl.col
    k_pts = (3 * (c("fg_made_0_19") + c("fg_made_20_29") + c("fg_made_30_39"))
             + 4 * c("fg_made_40_49") + 5 * (c("fg_made_50_59") + c("fg_made_60_"))
             + c("pat_made") - c("fg_missed") - c("pat_missed")).cast(pl.Float64)
    table = table.with_columns(pl.when(c("position") == "K").then(k_pts)
                               .otherwise(c("fantasy_points")).alias("fantasy_points"))
    table = table.with_columns(
        pl.col("fantasy_points").rank("ordinal", descending=True)
        .over("season", "position").alias("pos_rank"))
    rows = table.filter(pl.col("player_id") == player_id).sort("season").to_dicts()
    if not rows:
        return ["  no regular-season games in " + ", ".join(map(str, years))]
    out = []
    for r in rows:
        pos = r["position"]
        head = f"  {r['season']} {r['team']:3} {r['g']:>2} g"
        if pos == "K":
            body = (f"FG {r['fg_made']}/{r['fg_att']} (40-49 {r['fg_made_40_49']}, "
                    f"50+ {r['fg_made_50_59'] + r['fg_made_60_']}), XP {r['pat_made']}/{r['pat_att']}")
        elif pos == "QB":
            body = (f"{r['completions']}/{r['attempts']} {r['passing_yards']:.0f} yds {r['passing_tds']} td "
                    f"{r['passing_interceptions']} int; rush {r['carries']}-{r['rushing_yards']:.0f}-{r['rushing_tds']}")
        else:
            body = (f"rush {r['carries']}-{r['rushing_yards']:.0f}-{r['rushing_tds']} td; "
                    f"tgt {r['targets']} rec {r['receptions']} {r['receiving_yards']:.0f} yds {r['receiving_tds']} td")
        g = r["g"] or 1
        pts = (f"approx std {r['fantasy_points'] / g:.1f}/g" if pos == "K" else
               f"nflverse std {r['fantasy_points'] / g:.1f}/g (ppr {r['fantasy_points_ppr'] / g:.1f}/g)")
        out.append(f"{head}  {body}  | {pts}, {pos}{r['pos_rank']} by total")
    return out


def parse_seasons(spec: str, current: int) -> list[int]:
    """'2025', '2023-2025', 'last3' or 'all' -> sorted years (capped to the cache)."""
    spec = (spec or "").strip().lower()
    if not spec:
        return []
    if spec == "all":
        return list(range(FIRST_SEASON, current + 1))
    m = re.fullmatch(r"last\s*(\d+)", spec)
    if m:
        n = int(m.group(1))
        return list(range(max(FIRST_SEASON, current - n), current))
    years = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
            years |= set(range(min(a, b), max(a, b) + 1))
        elif part.isdigit():
            years.add(int(part))
    return sorted(y for y in years if FIRST_SEASON <= y <= current)
