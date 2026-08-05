"""Does forcing a roster template cost TALENT at the draft table?

The objection to finding 34: a template makes the drafter pass on
better players to satisfy a quota, so its measured penalty mixes
"this shape is bad" with "reaching is bad". This isolates the second
half. Draft only, no season simulated.

`prior` = sum of the drafted roster's leak-free preseason ppg
expectation. If a template drafts systematically less `prior` than the
unconstrained drafter, its season-points penalty in finding 34 is at
least partly a reaching artifact, not a verdict on the shape.

Run:  venv/bin/python analysis/shape_reach_cost.py [--sims 25]
"""

import random
import statistics as st
import sys

from common import SEASONS
from roster_shape import SHAPES, factory

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.draft import run_draft
from simfl.models import Team
from simfl.montecarlo import get_pool
from simfl.strategies import make

N_SIMS = 25
SEED = 17


def main():
    n = N_SIMS
    if "--sims" in sys.argv:
        n = int(sys.argv[sys.argv.index("--sims") + 1])
    print("Does a forced template cost TALENT at the draft table?")
    print("prior = sum of drafted roster's preseason ppg expectation.")
    print("Draft only; no season simulated.\n")
    print(f"{'shape':10s}{'prior':>8s}{'vs free':>9s}{'±95%':>7s}"
          f"{'realized QB-RB-WR-TE-K':>26s}")
    base = None
    for shape in SHAPES:
        vals, comp = {}, []
        for year in SEASONS:
            pool, _ = get_pool(year)
            for i in range(n):
                seat = i % LG.n_teams
                rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
                strat = [make("family") for _ in range(LG.n_teams)]
                strat[seat] = factory(shape)()
                for s in strat:
                    s.bind_year(year)
                teams = [Team(idx=j, name=f"t{j}", strategy=strat[j])
                         for j in range(LG.n_teams)]
                run_draft(pool, teams, LG, rng)
                r = teams[seat].roster
                vals[(year, i)] = sum(p.prior_ppg for p in r)
                comp.append(tuple(sum(1 for p in r if p.pos == q)
                                  for q in ("QB", "RB", "WR", "TE", "K")))
        if base is None:
            base = vals
        d = [vals[k] - base[k] for k in vals]
        ci = 1.96 * st.stdev(d) / len(d) ** 0.5 if any(d) else 0.0
        avg = "-".join(f"{st.mean(c[j] for c in comp):.1f}" for j in range(5))
        print(f"{shape:10s}{st.mean(vals.values()):8.1f}{st.mean(d):+9.1f}"
              f"{ci:7.1f}{avg:>26s}")


if __name__ == "__main__":
    main()
