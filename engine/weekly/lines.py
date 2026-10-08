"""Vegas lines -> team implied totals -> D/ST and K weekly rankings.

Sources, freshest first:
  1. ESPN's public scoreboard (DraftKings line, moves all week)
  2. nflverse schedules (lookahead lines for every week of the season)

Implied totals from the home spread s (home margin) and total t:
  home = t/2 + s/2,   away = t/2 - s/2

D/ST rank: ascending by the OPPONENT's implied total (finding 27: the
market's number for the offence a defence faces is the whole signal;
Spearman .30 vs .13 for last-week's points). K rank: descending by the
kicker's OWN offence implied total, +0.7 for a dome (finding 28).

Output: data/weekly/lines_<season>.csv, one row per team-week with a
line, refreshed in place every run.
"""
from __future__ import annotations

import sys

import polars as pl

from common import CACHE, DATA, TEAMS, now_iso
import nfl_data

DOME_BONUS = 0.7


def team_rows_from_schedule(season: int, refresh: bool) -> list[dict]:
    s = nfl_data.schedules(season, refresh).filter(
        (pl.col("game_type") == "REG") & pl.col("total_line").is_not_null())
    rows = []
    for g in s.iter_rows(named=True):
        rows += _split(g["week"], g["home_team"], g["away_team"],
                       g["spread_line"], g["total_line"], g["roof"],
                       f"{g['gameday']}T{g['gametime'] or '00:00'}", "nflverse",
                       g.get("home_score"), g.get("away_score"))
    return rows


def _split(week, home, away, spread_home, total, roof, kickoff, provider,
           home_score=None, away_score=None) -> list[dict]:
    imp_h = total / 2 + spread_home / 2
    imp_a = total / 2 - spread_home / 2
    dome = roof in ("dome", "closed")
    played = home_score is not None and away_score is not None
    return [
        dict(week=week, team=home, opp=away, home=True, imp_own=round(imp_h, 1),
             imp_opp=round(imp_a, 1), spread=round(-spread_home, 1), total=total,
             dome=dome, kickoff=kickoff, provider=provider, played=played),
        dict(week=week, team=away, opp=home, home=False, imp_own=round(imp_a, 1),
             imp_opp=round(imp_h, 1), spread=round(spread_home, 1), total=total,
             dome=dome, kickoff=kickoff, provider=provider, played=played),
    ]


def build(season: int, current_week: int, refresh: bool = True) -> pl.DataFrame:
    rows = team_rows_from_schedule(season, refresh)
    roofs = {}
    for r in rows:
        roofs[(r["week"], r["team"])] = r["dome"]
    # Overlay the live ESPN line for the current week where it exists.
    try:
        live = nfl_data.espn_scoreboard_odds(season, current_week) if refresh else []
    except Exception as e:  # noqa: BLE001 - keep the schedule line
        print(f"  espn scoreboard unavailable: {e}", file=sys.stderr)
        live = []
    live_rows = []
    for g in live:
        if g["total"] is None or g["spread_home"] is None:
            continue
        dome = roofs.get((current_week, g["home"]), False)
        live_rows += _split(current_week, g["home"], g["away"], g["spread_home"],
                            g["total"], "dome" if dome else "outdoors", g["kickoff"],
                            g["provider"] or "ESPN", g["home_score"], g["away_score"])
    if live_rows:
        have = {(r["week"], r["team"]) for r in live_rows}
        rows = [r for r in rows if (r["week"], r["team"]) not in have] + live_rows
    df = pl.DataFrame(rows).sort(["week", "team"])
    df.write_csv(DATA / f"lines_{season}.csv")
    return df


LIVE_DIR = CACHE / "lines_live"
ESPN_TTL = 30 * 60          # the free scoreboard: cheap, re-read every half hour
ODDS_API_TTL = 3 * 3600     # two credits a call on the free tier


def _age_seconds(stamp: str | None) -> float | None:
    from datetime import datetime, timezone
    if not stamp:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp.replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        return None


def _cached_fetch(path, ttl: int, fetch, refresh: bool) -> dict:
    """{games, fetched_at, status, note}. A failed fetch falls back to the
    last good copy, labelled stale; it never pretends to be current."""
    import json
    old = json.loads(path.read_text()) if path.exists() else None
    age = _age_seconds(old.get("fetched_at")) if old else None
    if old and not refresh and age is not None and age < ttl:
        return {**old, "status": "cached"}
    try:
        games, extra = fetch()
        new = {"games": games, "fetched_at": now_iso(), **extra}
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(new))
        return {**new, "status": "fresh"}
    except Exception as e:  # noqa: BLE001 - report, fall back to the last copy
        note = f"fetch failed ({type(e).__name__}: {str(e)[:80]})"
        if old:
            return {**old, "status": "stale", "note": note}
        return {"games": [], "fetched_at": None, "status": "unavailable", "note": note}


def live_week(season: int, week: int, refresh: bool = False) -> dict:
    """This week's lines from every source we have, each with its own
    retrieval time, plus one chosen line per team.

      espn     ESPN's public scoreboard (one book, DraftKings), cached 30 min
      oddsapi  The Odds API median across US books (ODDS_API_KEY), cached 3 h
      saved    data/weekly/lines_<season>.csv from the last weekly build

    The chosen line is the Odds API median when it is under 3 hours old
    (several books beat one), else the ESPN line, else the saved file.
    Returns {"teams": {team: row}, "sources": [...]} where each row has
    opp, home, kickoff, total, spread (own, negative = favoured),
    imp_own, imp_opp, source, retrieved_at, plus `by_source`.
    """
    from common import load_env
    sched = {}
    try:
        s = nfl_data.schedules(season).filter(
            (pl.col("game_type") == "REG") & (pl.col("week") == week))
        sched = {(g["away_team"], g["home_team"]): g for g in s.iter_rows(named=True)}
    except Exception:  # noqa: BLE001 - schedule only filters the Odds API feed
        pass
    espn = _cached_fetch(LIVE_DIR / f"espn_{season}_wk{week:02d}.json", ESPN_TTL,
                         lambda: (nfl_data.espn_scoreboard_odds(season, week), {}), refresh)
    key = load_env().get("ODDS_API_KEY")
    if key:
        def odds():
            games, quota = nfl_data.odds_api_lines(key)
            return games, {"quota": quota}
        oapi = _cached_fetch(LIVE_DIR / f"oddsapi_{season}.json", ODDS_API_TTL, odds, refresh)
        oapi["games"] = [g for g in oapi["games"] if (g["away"], g["home"]) in sched] if sched else []
        if not sched:
            oapi["note"] = "schedule unavailable, so Odds API games could not be matched to this week"
    else:
        oapi = {"games": [], "fetched_at": None, "status": "no key",
                "note": "ODDS_API_KEY not set in the environment or an engine .env"}
    saved_path = DATA / f"lines_{season}.csv"
    saved_rows = []
    saved_at = None
    if saved_path.exists():
        from datetime import datetime, timezone
        saved_at = datetime.fromtimestamp(saved_path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        saved_rows = load(season).filter(pl.col("week") == week).to_dicts()

    by_team: dict[str, dict] = {}

    def put(name, team, opp, home, spread_home, total, kickoff, provider, fetched):
        if total is None or spread_home is None:
            return
        own = total / 2 + (spread_home if home else -spread_home) / 2
        row = by_team.setdefault(team, {"team": team, "opp": opp, "home": home,
                                        "kickoff": kickoff, "by_source": {}})
        row["by_source"][name] = {"total": total, "spread": round(-spread_home if home else spread_home, 1),
                                  "imp_own": round(own, 1), "imp_opp": round(total - own, 1),
                                  "provider": provider, "retrieved_at": fetched}
        if kickoff and name != "saved":
            row["kickoff"] = kickoff

    for name, feed in (("espn", espn), ("oddsapi", oapi)):
        for g in feed["games"]:
            for team, opp, home in ((g["home"], g["away"], True), (g["away"], g["home"], False)):
                put(name, team, opp, home, g["spread_home"], g["total"], g["kickoff"],
                    g.get("provider") or name, feed["fetched_at"])
    for r in saved_rows:
        spread_home = -r["spread"] if r["home"] else r["spread"]
        put("saved", r["team"], r["opp"], r["home"], spread_home, r["total"], r["kickoff"],
            f"{r['provider']} (saved file)", saved_at)

    status = {"oddsapi": oapi["status"], "espn": espn["status"], "saved": "file"}
    current = {n for n, st in status.items() if st in ("fresh", "cached")}
    order = [n for n in ("oddsapi", "espn") if n in current] + ["oddsapi", "espn", "saved"]
    for row in by_team.values():
        pick = next(n for n in order if n in row["by_source"])
        row.update(row["by_source"][pick], source=pick, stale=pick not in current)
    sources = [
        {"source": "oddsapi", "what": "median of US books (The Odds API)", "status": oapi["status"],
         "retrieved_at": oapi["fetched_at"], "games": len(oapi["games"]), "note": oapi.get("note"),
         "quota_remaining": (oapi.get("quota") or {}).get("requests_remaining")},
        {"source": "espn", "what": "ESPN public scoreboard (one book)", "status": espn["status"],
         "retrieved_at": espn["fetched_at"], "games": len(espn["games"]), "note": espn.get("note")},
        {"source": "saved", "what": f"data/weekly/lines_{season}.csv (weekly build)", "status": "file",
         "retrieved_at": saved_at, "games": len(saved_rows) // 2, "note": None},
    ]
    return {"season": season, "week": week, "teams": by_team, "sources": sources}


def load(season: int) -> pl.DataFrame:
    return pl.read_csv(DATA / f"lines_{season}.csv")


def rankings(lines: pl.DataFrame, week: int) -> dict:
    """{'dst': [...], 'k': [...]} for the site and the advisor."""
    w = lines.filter(pl.col("week") == week)
    dst = [dict(team=TEAMS.get(r["team"], r["team"]), abbr=r["team"],
                opp=TEAMS.get(r["opp"], r["opp"]), imp=r["imp_opp"], home=r["home"],
                played=r["played"])
           for r in w.iter_rows(named=True)]
    k = [dict(team=TEAMS.get(r["team"], r["team"]), abbr=r["team"],
              opp=TEAMS.get(r["opp"], r["opp"]), imp=r["imp_own"], dome=r["dome"],
              home=r["home"], played=r["played"])
         for r in w.iter_rows(named=True)]
    dst.sort(key=lambda d: (d["imp"], d["abbr"]))
    k.sort(key=lambda d: (-(d["imp"] + (DOME_BONUS if d["dome"] else 0)), d["abbr"]))
    return {"dst": dst, "k": k}


if __name__ == "__main__":
    from common import nfl_state
    st = nfl_state()
    df = build(st["season"], st["week"])
    print(df.filter(pl.col("week") == st["week"]))
