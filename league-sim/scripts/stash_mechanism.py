"""Why a 2nd QB/TE does or doesn't pay: the mechanism behind the
stash sweep (scripts/stash_sweep.py).

Two views, both leak-free:

1. **Slot decomposition** (full seasons, waivers live). Where do the
   points move? `SeasonResult.slot_points` gives regular-season points
   by lineup slot, so a forced 2nd TE that works should show up as TE
   slot gain and RB/WR/FLEX slot loss.

2. **Frozen-roster view** (draft only, no waivers). Isolates the draft
   decision: across weeks 1-14, how often does the backup outproject
   the starter, what does best-of-two add over starter-alone, and how
   many weeks does a one-deep roster leave the slot empty? Uses the
   same leak-free projections the sim starts lineups with.

Run:  venv/bin/python scripts/stash_mechanism.py
"""

import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.draft import run_draft
from simfl.models import Team
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import make

YEARS = range(2020, 2026)
N = 60          # descriptive: 60 x 6 seasons x 14 weeks is ample here
SEED = 7
SLOTS = ("QB", "RB", "WR", "TE", "FLEX", "K")


def _seeded(year, i):
    return random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)


def slot_decomposition(heroes):
    """Regular-season points by lineup slot, paired across arms."""
    out = {h: {s: [] for s in SLOTS} for h in heroes}
    for year in YEARS:
        pool, table = get_pool(year)
        for hero in heroes:
            for i in range(N):
                rng = _seeded(year, i)
                seat = i % LG.n_teams
                strat = [make("family") for _ in range(LG.n_teams)]
                strat[seat] = make(hero)
                for s in strat:
                    s.bind_year(year)
                res = run_season(pool, strat, LG, table, rng)
                sp = res.slot_points[seat]
                for s in SLOTS:
                    out[hero][s].append(sp.get(s, 0.0))
    return out


def frozen_roster(hero, pos):
    """Draft-only: what the 2nd `pos` is worth before any waiver move."""
    starts, gain, empty1, empty2, n = 0, [], 0, 0, 0
    weeks = range(1, LG.regular_season_weeks + 1)
    for year in YEARS:
        pool, table = get_pool(year)
        for i in range(N):
            rng = _seeded(year, i)
            seat = i % LG.n_teams
            strat = [make("family") for _ in range(LG.n_teams)]
            strat[seat] = make(hero)
            for s in strat:
                s.bind_year(year)
            teams = [Team(idx=j, name=str(j), strategy=s)
                     for j, s in enumerate(strat)]
            run_draft(pool, teams, LG, rng)
            team = teams[seat]
            guys = sorted((p for p in team.roster if p.pos == pos),
                          key=lambda p: team.drafted_round[p.pid])
            if len(guys) < 2:
                continue
            n += 1
            first, second = guys[0], guys[1]
            both = one = 0.0
            for w in weeks:
                act = [p for p in guys if p.played(w)]
                if act:
                    pick = max(act, key=lambda p: table.proj(p, w))
                    both += pick.points(w)
                    starts += pick is second
                else:
                    empty2 += 1
                if first.played(w):
                    one += first.points(w)
                else:
                    empty1 += 1
            gain.append(both - one)
    wk = n * len(weeks)
    return {"n": n, "start_share": starts / wk if wk else 0,
            "gain_mean": statistics.mean(gain) if gain else 0,
            "gain_median": statistics.median(gain) if gain else 0,
            "gain_p90": (sorted(gain)[int(0.9 * len(gain))] if gain else 0),
            "empty_1deep": empty1 / wk if wk else 0,
            "empty_2deep": empty2 / wk if wk else 0}


if __name__ == "__main__":
    print("=" * 68)
    print("1. SLOT DECOMPOSITION — reg-season points by lineup slot")
    print("=" * 68)
    heroes = ["bpa", "te2_r12", "te2_never", "qb2_r12", "qb2_never"]
    dec = slot_decomposition(heroes)
    hdr = "".join(f"{s:>9s}" for s in SLOTS)
    print(f"{'arm':14s}{hdr}{'total':>9s}")
    base = {s: statistics.mean(dec["bpa"][s]) for s in SLOTS}
    for h in heroes:
        m = {s: statistics.mean(dec[h][s]) for s in SLOTS}
        row = "".join(f"{m[s]:9.1f}" for s in SLOTS)
        print(f"{h:14s}{row}{sum(m.values()):9.1f}")
    print(f"\n{'vs bpa (delta)':14s}")
    for h in heroes[1:]:
        m = {s: statistics.mean(dec[h][s]) - base[s] for s in SLOTS}
        row = "".join(f"{m[s]:+9.1f}" for s in SLOTS)
        print(f"{h:14s}{row}{sum(m.values()):+9.1f}")

    print("\n" + "=" * 68)
    print("2. FROZEN ROSTER — the drafted pair, before any waiver move")
    print("=" * 68)
    print(f"{'':22s}{'weeks':>8s}{'season pts added':>20s}{'empty slot wks':>18s}")
    print(f"{'arm':14s}{'n':>8s}{'started':>8s}"
          f"{'mean':>7s}{'med':>7s}{'p90':>6s}{'1-deep':>11s}{'2-deep':>8s}")
    for hero, pos in (("te2_r12", "TE"), ("te_darts", "TE"),
                      ("qb2_r12", "QB"), ("bpa", "QB"), ("bpa", "TE")):
        r = frozen_roster(hero, pos)
        print(f"{hero + '/' + pos:14s}{r['n']:8d}{r['start_share']:8.1%}"
              f"{r['gain_mean']:7.1f}{r['gain_median']:7.1f}{r['gain_p90']:6.1f}"
              f"{r['empty_1deep']:11.1%}{r['empty_2deep']:8.1%}")
