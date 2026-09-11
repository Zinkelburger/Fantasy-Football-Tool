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

from common import DATA, TEAMS
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
        live = nfl_data.espn_scoreboard_odds(season, current_week)
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
