"""WHEN you draft a position, not just how many — the actionable version.

shape_observed.py showed RB-heavy teams win, but that is confounded:
a team with 8 RBs is usually a team that took RBs in round 1-3, and we
already know early RB wins (findings 01, 23). Counting bodies cannot
tell "3 elite RBs + 5 scrubs" from "8 mediocre RBs".

So split the draft into bands and ask the two questions separately:

  EARLY (rounds 1-4)  how many RBs to open with -- the "3 RB start"
  LATE  (rounds 9-15) what to do with the bench, HOLDING the early
                      build fixed (stratified, not regressed)

Stratifying beats a talent covariate here: sum(prior_ppg) is itself
composition-dependent (QBs score more per game than RBs, so any roster
with a QB2 scores higher on it regardless of quality). Comparing late
choices *within* an identical early build needs no such control.

Run:  venv/bin/python analysis/draft_shape_bands.py [--sims 250]
"""

import random
import statistics as st
import sys
from collections import defaultdict

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import make

N_SIMS = 250
SEED = 31
EARLY = (1, 4)
LATE = (9, 15)


def run_all(n_sims):
    rows = []
    for year in SEASONS:
        pool, table = get_pool(year)
        for i in range(n_sims):
            rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
            strat = [make("family") for _ in range(LG.n_teams)]
            strat[i % LG.n_teams] = make("pick_value")
            for s in strat:
                s.bind_year(year)
            res = run_season(pool, strat, LG, table, rng)
            for t in res.teams:
                band = defaultdict(int)
                for pid, rnd in t.drafted_round.items():
                    p = table.by_pid[pid]
                    if EARLY[0] <= rnd <= EARLY[1]:
                        band["e" + p.pos] += 1
                    elif LATE[0] <= rnd <= LATE[1]:
                        band["l" + p.pos] += 1
                rows.append({"pf": t.points_for, "ap": t.all_play_pct,
                             **band})
    return rows


def show(rows, key, title, lo, hi, minn=120):
    by = defaultdict(list)
    for r in rows:
        by[r.get(key, 0)].append(r)
    print(f"\n{title}")
    print(f"{key:>6s}{'teams':>8s}{'PF':>8s}{'all-play':>10s}")
    for k in sorted(by):
        if k < lo or k > hi or len(by[k]) < minn:
            continue
        v = by[k]
        print(f"{k:>6d}{len(v):>8d}{st.mean(r['pf'] for r in v):>8.0f}"
              f"{st.mean(r['ap'] for r in v):>10.3f}")


def main():
    n = N_SIMS
    if "--sims" in sys.argv:
        n = int(sys.argv[sys.argv.index("--sims") + 1])
    rows = run_all(n)
    print(f"{len(rows)} team-seasons. Nobody told what to draft.")
    print(f"EARLY = rounds {EARLY[0]}-{EARLY[1]}, "
          f"LATE = rounds {LATE[0]}-{LATE[1]}.")

    print("\n" + "=" * 58)
    print("QUESTION 1: how many RBs to OPEN with (rounds 1-4)")
    print("=" * 58)
    show(rows, "eRB", "By RBs drafted in rounds 1-4:", 0, 4)
    show(rows, "eWR", "By WRs drafted in rounds 1-4:", 0, 4)

    print("\n" + "=" * 58)
    print("QUESTION 2: the bench, HOLDING the early build fixed")
    print("=" * 58)
    print("Within each early-RB count, does a late RB or a late WR win?")
    for erb in (1, 2, 3):
        sub = [r for r in rows if r.get("eRB", 0) == erb]
        if len(sub) < 400:
            continue
        print(f"\n--- teams that opened with {erb} RB(s) in rounds 1-4 "
              f"(n={len(sub)}) ---")
        show(sub, "lRB", f"  by RBs taken in rounds {LATE[0]}-{LATE[1]}:",
             0, 6, minn=100)
        show(sub, "lWR", f"  by WRs taken in rounds {LATE[0]}-{LATE[1]}:",
             0, 6, minn=100)
        show(sub, "lQB", f"  by QBs taken in rounds {LATE[0]}-{LATE[1]}:",
             0, 2, minn=100)
        show(sub, "lTE", f"  by TEs taken in rounds {LATE[0]}-{LATE[1]}:",
             0, 2, minn=100)


if __name__ == "__main__":
    main()
