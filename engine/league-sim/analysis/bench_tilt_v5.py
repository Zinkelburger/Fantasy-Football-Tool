"""Late-round bench policy, CONTROLLED — late RB vs late WR.

Two sources disagree:

  finding 19 (sim v3, mild tilt)  bench RB vs bench WR = +0.2 all-play,
                                  inside the noise
  draft_shape_bands.py (v5, observational)  teams that took 4 RBs in
                                  rounds 9-15 beat teams that took 0 by
                                  ~5 points of all-play, in every
                                  early-round stratum

The observational gap is big but endogenous: a team ends up with four
late RBs partly because late RBs kept looking like the best available
player, which is itself information. This settles it with a forced
rule, where the drafter has no such discretion.

Arms restrict ONLY rounds 9-15, and only once every starting slot is
already covered, so no arm can field an illegal roster. `late_rb` and
`late_wr` reach equally hard, so the head-to-head between THEM is the
clean comparison; both may sit below `free`, which is just the cost of
being told what to do.

Run:  venv/bin/python analysis/bench_tilt_v5.py [--sims 100]
"""

import random
import statistics as st
import sys

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import PickValue, make

N_SIMS = 100
SEED = 41
LATE_FROM = 9


class LateOnly(PickValue):
    """From round LATE_FROM on, draft only `keep` (plus the kicker, and
    plus anything still needed to cover a starting slot)."""
    keep = "RB"
    name = "late"

    def banned(self, p, rnd, team, state):
        if rnd >= LATE_FROM and p.pos not in (self.keep, "K"):
            if not state.unfilled_starters(team):
                return True
        return super().banned(p, rnd, team, state)


ARMS = [
    ("free", "pick_value, no late-round rule", None),
    ("late_rb", "rounds 9-15: RBs only", "RB"),
    ("late_wr", "rounds 9-15: WRs only", "WR"),
]


def run_one(year, keep, seat, i, pool, table):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    if keep is None:
        strat[seat] = make("pick_value")
    else:
        strat[seat] = type(f"L_{keep}", (LateOnly,),
                           {"keep": keep, "name": f"late_{keep}"})()
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng)


def main():
    n = N_SIMS
    if "--sims" in sys.argv:
        n = int(sys.argv[sys.argv.index("--sims") + 1])
    print(f"{n} sims x {len(SEASONS)} seasons per arm, paired on seed.")
    print(f"Rule applies from round {LATE_FROM} and only once every")
    print("starting slot is covered.\n")
    print(f"{'arm':10s}{'rule':32s}{'PF':>7s}{'vs free':>9s}{'±95%':>7s}"
          f"{'all-play':>10s}{'titles':>8s}")
    keyed_all = {}
    for name, label, keep in ARMS:
        keyed, ap, ti = {}, [], []
        for year in SEASONS:
            pool, table = get_pool(year)
            for i in range(n):
                seat = i % LG.n_teams
                res = run_one(year, keep, seat, i, pool, table)
                t = res.teams[seat]
                keyed[(year, i)] = t.points_for
                ap.append(t.all_play_pct)
                ti.append(res.champion is t)
        keyed_all[name] = (keyed, ap, ti)
        base = keyed_all["free"][0]
        d = [keyed[k] - base[k] for k in keyed]
        ci = 1.96 * st.stdev(d) / len(d) ** 0.5 if any(d) else 0.0
        print(f"{name:10s}{label:32s}{st.mean(keyed.values()):7.0f}"
              f"{st.mean(d):+9.1f}{ci:7.1f}{st.mean(ap):10.3f}"
              f"{sum(ti)/len(ti):8.1%}")

    a = keyed_all["late_rb"][0]
    b = keyed_all["late_wr"][0]
    d = [a[k] - b[k] for k in a]
    ci = 1.96 * st.stdev(d) / len(d) ** 0.5
    apa = st.mean(keyed_all["late_rb"][1])
    apb = st.mean(keyed_all["late_wr"][1])
    print(f"\nHEAD-TO-HEAD, late RB minus late WR (both equally forced):")
    print(f"  points  {st.mean(d):+.1f} ± {ci:.1f}")
    print(f"  all-play {apa - apb:+.3f}")


if __name__ == "__main__":
    main()
