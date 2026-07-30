"""Review the Methuen Jackels' real drafts (2024-2025) against what
actually happened, and replay each draft with perfect hindsight.

Reads the ESPN league exports in league-sim/data/espn/.
Run:  venv/bin/python scripts/jackels_review.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nflreadpy as nfl
import polars as pl

from simfl.config import DEFAULT_SCORING
from simfl.data import norm_name
from simfl.pool import build_pool

ESPN_DIR = Path(__file__).resolve().parent.parent / "data" / "espn"
TEAM_ID = 1  # Methuen Jackels
BOLD, DIM, END = "\033[1m", "\033[2m", "\033[0m"

# espn player id -> (name, pos)
_ids = nfl.load_ff_playerids().filter(pl.col("espn_id").is_not_null())
ESPN_MAP = {int(r["espn_id"]): (r["name"], r["position"], r["gsis_id"])
            for r in _ids.select(["espn_id", "name", "position", "gsis_id"])
            .iter_rows(named=True)}

STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1}  # + FLEX RB/WR


def load_year(year):
    d = json.load(open(ESPN_DIR / f"league_{year}.json"))
    if isinstance(d, list):
        d = d[0]
    return d


def resolve(pick, pool_by_gsis, pool_by_name):
    pid = pick["playerId"]
    if pid < 0:
        return None, ("D/ST", "DST")
    name, pos, gsis = ESPN_MAP.get(pid, (f"espn:{pid}", "?", None))
    ps = pool_by_gsis.get(gsis)
    if ps is None:
        ps = pool_by_name.get((norm_name(name), pos))
    return ps, (name, pos)


def optimal_weekly_points(roster, weeks=range(1, 18)):
    """Perfect-lineup points a roster would deliver (upper bound on
    what a manager could extract)."""
    total = 0.0
    for w in weeks:
        active = sorted([p for p in roster if p.played(w)],
                        key=lambda p: -p.points(w))
        used, got = set(), []
        for pos, n in STARTERS.items():
            picks = [p for p in active if p.pos == pos and p.pid not in used][:n]
            used.update(p.pid for p in picks)
            got += picks
        flex = [p for p in active if p.pos in ("RB", "WR") and p.pid not in used][:1]
        got += flex
        total += sum(p.points(w) for p in got)
    return total


def legal_hindsight_pick(cands, have, picks_left):
    """Best-by-total pick that keeps the starting lineup fillable."""
    need = []
    for pos, n in STARTERS.items():
        need += [pos] * max(0, n - sum(1 for q in have if q.pos == pos))
    flexible = sum(1 for q in have if q.pos in ("RB", "WR"))
    if flexible < 5 and not any(p in ("RB", "WR") for p in need):
        need.append("RB")
    forced = len(need) >= picks_left
    caps = {"QB": 2, "TE": 2, "K": 1}
    for p in cands:
        if forced and p.pos not in need and not (
                "RB" in need and p.pos == "WR") and not (
                "WR" in need and p.pos == "RB"):
            continue
        if p.pos in caps and sum(1 for q in have if q.pos == p.pos) >= caps[p.pos]:
            continue
        if p.pos == "K" and picks_left > 2 and "K" not in (need if forced else []):
            continue
        return p
    return cands[0]


def review(year):
    d = load_year(year)
    pool = build_pool(year, DEFAULT_SCORING)
    by_gsis = {p.pid: p for p in pool}
    by_name = {(norm_name(p.name), p.pos): p for p in pool}
    totals = {p.pid: sum(p.week_pts.values()) for p in pool}
    pos_rank = {}
    for pos in ("QB", "RB", "WR", "TE", "K"):
        ranked = sorted([p for p in pool if p.pos == pos],
                        key=lambda p: -totals[p.pid])
        for i, p in enumerate(ranked):
            pos_rank[p.pid] = i + 1

    picks = sorted(d["draftDetail"]["picks"], key=lambda p: p["overallPickNumber"])
    team_names = {t["id"]: t["name"] for t in d["teams"]}

    print(f"\n{BOLD}=== {year} draft — Methuen Jackels (seat "
          f"{[p['teamId'] for p in picks[:12]].index(TEAM_ID)+1}) ==={END}")
    mine, taken_before = [], {}
    pos_counter = {}
    for pk in picks:
        ps, (name, pos) = resolve(pk, by_gsis, by_name)
        pos_counter[pos] = pos_counter.get(pos, 0) + 1
        if pk["teamId"] != TEAM_ID:
            if ps:
                taken_before[ps.pid] = pk["overallPickNumber"]
            continue
        n_at_pos = pos_counter[pos]
        if ps is None:
            print(f"  R{pk['roundId']:>2} (#{pk['overallPickNumber']:>3}) "
                  f"{name:24s} {pos:3s}  [not modeled]")
            continue
        mine.append(ps)
        taken_before[ps.pid] = pk["overallPickNumber"]
        tot = totals[ps.pid]
        adp = f"{ps.adp:.0f}" if ps.adp else "--"
        delta = (f"{pk['overallPickNumber'] - ps.adp:+.0f}" if ps.adp else "  ")
        print(f"  R{pk['roundId']:>2} (#{pk['overallPickNumber']:>3}) "
              f"{ps.name:24s} {pos:3s} {n_at_pos}th {pos} taken · ADP {adp:>3} ({delta})"
              f" → {tot:4.0f} pts, finished {pos}{pos_rank.get(ps.pid, '?')}")

    actual_haul = optimal_weekly_points(mine)
    print(f"\n  actual draft haul (perfect lineups all year): "
          f"{BOLD}{actual_haul:.0f} pts{END}")

    # Hindsight replay: at each of our picks, take the best
    # season-total player still on the board at that moment.
    my_pick_numbers = [pk["overallPickNumber"] for pk in picks
                       if pk["teamId"] == TEAM_ID and pk["playerId"] > 0]
    taken, dream = set(), []
    for pk in picks:
        if pk["playerId"] < 0:
            continue
        if pk["teamId"] != TEAM_ID:
            ps, _ = resolve(pk, by_gsis, by_name)
            if ps:
                taken.add(ps.pid)
            continue
        picks_left = len(my_pick_numbers) - len(dream)
        cands = sorted([p for p in pool if p.pid not in taken
                        and all(q.pid != p.pid for q in dream)],
                       key=lambda p: -totals[p.pid])
        best = legal_hindsight_pick(cands, dream, picks_left)
        dream.append(best)
        print(f"  {DIM}hindsight R{pk['roundId']:>2}: {best.name:22s} {best.pos:3s}"
              f" {totals[best.pid]:4.0f} pts{END}")
    dream_haul = optimal_weekly_points(dream)
    print(f"  perfect-hindsight haul from same seat: {BOLD}{dream_haul:.0f} pts{END}"
          f"  (you captured {actual_haul/dream_haul:.0%})")
    return mine, dream


if __name__ == "__main__":
    for year in (2024, 2025):
        review(year)
