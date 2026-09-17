"""League power rankings: every roster scored the same way, no judgment.

    .venv-league-sim/bin/python engine/weekly/power_rankings.py [--week N] [--json]

For each team the script takes the ESPN roster, attaches the engine's
projection and value to every player (advisor.project, the recipe the
ff-weekly tools use), and reports:

  strength   best lineup by season value: the exact lineup optimiser run
             over `value` (mean of ESPN projection and usage-based expected
             points, no matchup or injury term) with IR-slot, IR-status and
             suspended players excluded. This is the ranking key.
  opp EP     the same lineup's usage-based expected points (the finding 39
             opportunity score, EWMA), skill positions only. `strength`
             is half ESPN projection; this column is what the roster's
             own snaps, carries and targets earned, with no ESPN input.
  bench      the three most valuable RB/WR/TE the strength lineup left on
             the bench, summed: depth that survives a bye or an injury.
             Backup QBs are deliberately excluded -- one starts, the rest
             never play, and a QB out-scores every other position, so
             counting them ranks a roster by a player who cannot help it.
  QB2        the best backup QB's value anyway, in its own column, since
             it is worth knowing who can cover a bye or a benching.
  week proj  the optimiser over this week's `proj` (matchup, injury, bye
             applied): how good the roster is *this* week.
  record / PF  what ESPN says happened so far.

rank_teams() is pure and unit-tested; league_rankings() does the fetch.
"""
from __future__ import annotations

import argparse
import json
import sys

import advisor
from common import SKILL

SEASON_ENDING = ("INJURY_RESERVE", "SUSPENSION")
BENCH_DEPTH = 3
# What counts as bench depth. QB is absent on purpose (see the docstring):
# only one starts, and QB scoring is on a different scale from everyone else.
BENCH_POS = ("RB", "WR", "TE")


def _unlocked(p: dict, key: str) -> dict:
    """A copy the optimiser can place anywhere, scored by `key`."""
    return dict(p, proj=p.get(key) or 0.0, locked=False, slot=None)


def _ewma(p: dict) -> float | None:
    """The player's opportunity score (usage-based expected points)."""
    return (p.get("sources") or {}).get("ewma_ep")


def team_strength(players: list[dict], slots: dict[int, int]) -> dict:
    """Strength, opportunity score, depth and this-week projection for one roster."""
    healthy = [p for p in players if p.get("slot") != 21
               and p.get("injury", "ACTIVE") not in SEASON_ENDING]
    by_value = advisor.optimal_lineup([_unlocked(p, "value") for p in healthy], slots)
    started = [p for _, p in by_value["starters"] if p]
    bench = sorted((p["proj"] for p in by_value["bench"] if p["pos"] in BENCH_POS), reverse=True)
    backup_qb = max((p["proj"] for p in by_value["bench"] if p["pos"] == "QB"), default=None)
    this_week = advisor.optimal_lineup([_unlocked(p, "proj") for p in healthy], slots)
    return {
        "strength": by_value["total"],
        "opp_ep": round(sum(_ewma(p) or 0.0 for p in started if p["pos"] in SKILL), 2),
        "bench": round(sum(bench[:BENCH_DEPTH]), 2),
        "backup_qb": round(backup_qb, 2) if backup_qb is not None else None,
        "week_proj": this_week["total"],
        "starters": [(slot, p["name"], p["pos"], p["proj"], _ewma(p)) for slot, p in by_value["starters"] if p],
        "sidelined": [p["name"] for p in players if p not in healthy],
    }


def rank_teams(rosters: dict[int, list[dict]], slots: dict[int, int],
               teams: list[dict], results: dict[int, dict] | None = None,
               my_team_id: int | None = None) -> list[dict]:
    """Rows sorted strongest first. `results[team_id]` = {wins, losses, pf}."""
    results = results or {}
    names = {t["id"]: t["name"] for t in teams}
    rows = []
    for tid, players in rosters.items():
        st = team_strength(players, slots)
        r = results.get(tid, {})
        rows.append({"team_id": tid, "name": names.get(tid, str(tid)), "mine": tid == my_team_id,
                     "wins": r.get("wins", 0), "losses": r.get("losses", 0),
                     "pf": round(r.get("pf", 0.0), 1), **st})
    rows.sort(key=lambda r: (-r["strength"], -r["bench"], -r["pf"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def league_rankings(season: int, week: int) -> dict:
    """Fetch every roster and the scoreboard, score them, return the rows."""
    import mcp_server
    lg, s, attach = mcp_server.projector(season, week)
    rosters = {tid: [attach(p) for p in ps] for tid, ps in lg.rosters(week).items()}
    results = {t["id"]: {"wins": t["record"].get("wins", 0), "losses": t["record"].get("losses", 0), "pf": 0.0}
               for t in s["teams"]}
    played = (s.get("matchup_period") or week) - 1
    for period in range(1, played + 1):
        for m in lg.scoreboard(period):
            results[m["home_id"]]["pf"] += m["home_pts"] or 0.0
            if m["away_id"] in results:
                results[m["away_id"]]["pf"] += m["away_pts"] or 0.0
    rows = rank_teams(rosters, s["slots"], s["teams"], results, s["my_team_id"])
    return {"league": s["league"], "season": season, "week": week, "scoring": s["scoring_format"],
            "weeks_played": played, "rows": rows}


def report(res: dict) -> str:
    out = [f"{res['league']} {res['season']} power rankings before week {res['week']} "
           f"({res['scoring']}; {res['weeks_played']} week(s) played)",
           f"  {'#':>2} {'team':30} {'rec':>5} {'PF':>6} {'strength':>8} {'opp EP':>7} "
           f"{'bench':>6} {'QB2':>5} {'wk proj':>7}"]
    for r in res["rows"]:
        qb2 = f"{r['backup_qb']:.1f}" if r["backup_qb"] is not None else "-"
        out.append(f"  {r['rank']:>2} {r['name']:30} {r['wins']}-{r['losses']:<3} {r['pf']:>6.1f} "
                   f"{r['strength']:>8.1f} {r['opp_ep']:>7.1f} {r['bench']:>6.1f} {qb2:>5} "
                   f"{r['week_proj']:>7.1f}{'  <- you' if r['mine'] else ''}")
    out += ["strength = best lineup by season value (mean of ESPN projection and usage EP, "
            "no matchup/injury)",
            "opp EP   = that lineup's usage-based expected points only (skill positions; no ESPN input)",
            "bench    = top 3 RB/WR/TE left over (backup QBs excluded: only one QB starts and QBs "
            "score on their own scale)",
            "QB2      = best backup QB's value, for bye cover",
            "wk proj  = this week's optimal lineup (matchup, injury and byes applied)"]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--week", type=int, default=0, help="decision week (default: current)")
    ap.add_argument("--json", action="store_true", help="print the rows as JSON")
    ap.add_argument("--starters", action="store_true", help="also list each team's strength lineup")
    a = ap.parse_args(argv)
    import mcp_server
    season, week = mcp_server._week(a.week)
    res = league_rankings(season, week)
    if a.json:
        print(json.dumps(res, indent=1))
        return 0
    print(report(res))
    if a.starters:
        for r in res["rows"]:
            print(f"\n{r['rank']}. {r['name']} ({r['strength']:.1f})")
            for slot, name, pos, v, ep in r["starters"]:
                print(f"   {pos:3} {name:24} value {v:5.1f}  opp EP {ep if ep is not None else '-':>5}")
            if r["sidelined"]:
                print(f"   sidelined: {', '.join(r['sidelined'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
