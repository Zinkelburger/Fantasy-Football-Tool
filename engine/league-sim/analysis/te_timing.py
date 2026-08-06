"""When do you take the TE — and can you just stream one off the wire?

QB timing was swept in flowchart.py (answer: rounds 4-6). This does the
same for TE, holding QB at round 5, and adds the punt arms: never draft
a TE before round 12/14 and live off the waiver wire.

Streaming is a real option here, not an assumption: the free-agent pool
is whatever no simulated team rosters, and the hero's waiver policy will
go get a TE when the slot would otherwise be empty. So `te14` genuinely
plays the season with a wire TE.

Also reported: the WR question by subtraction. Nothing bans WRs — they
are what fills every round the QB/TE rules leave alone — so the arm that
wins tells you where WRs actually belong.

Run:  venv/bin/python analysis/te_timing.py [--sims 60]
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
from flowchart import Flowchart

N_SIMS = 60
SEED = 19
QB_AT = 5

ARMS = [
    ("free", "pick_value baseline (no rules)", None),
    ("te4", "QB r5 · TE from r4", 4),
    ("te6", "QB r5 · TE from r6", 6),
    ("te8", "QB r5 · TE from r8", 8),
    ("te10", "QB r5 · TE from r10", 10),
    ("te12", "QB r5 · TE from r12 (near-punt)", 12),
    ("te14", "QB r5 · TE from r14 (punt, stream off wire)", 14),
]


def run_one(year, te_at, seat, i, pool, table):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    if te_at is None:
        strat[seat] = make("pick_value")
    else:
        strat[seat] = type(f"T{te_at}", (Flowchart,),
                           {"name": f"te{te_at}", "qb1_at": QB_AT,
                            "te1_at": te_at, "qb2": True, "te2": True})()
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng)


def main():
    n = N_SIMS
    if "--sims" in sys.argv:
        n = int(sys.argv[sys.argv.index("--sims") + 1])
    print(f"{n} sims x {len(SEASONS)} seasons per arm, paired on seed.")
    print(f"QB held at round {QB_AT}; only the TE rule moves.")
    print("WRs are never banned - they fill whatever the rules leave.\n")
    print(f"{'arm':7s}{'rule':46s}{'PF':>7s}{'vs free':>9s}{'±95%':>7s}"
          f"{'all-play':>10s}{'TE pts':>8s}{'WR rnds':>9s}")
    base = None
    for name, label, te_at in ARMS:
        keyed, ap, tepts, wrrnd = {}, [], [], []
        for year in SEASONS:
            pool, table = get_pool(year)
            for i in range(n):
                seat = i % LG.n_teams
                res = run_one(year, te_at, seat, i, pool, table)
                t = res.teams[seat]
                keyed[(year, i)] = t.points_for
                ap.append(t.all_play_pct)
                tepts.append(res.slot_points[t.idx].get("TE", 0.0))
                wr = [r for pid, r in t.drafted_round.items()
                      if table.by_pid[pid].pos == "WR"]
                if wr:
                    wrrnd.append(st.mean(wr))
        if base is None:
            base = keyed
        d = [keyed[k] - base[k] for k in keyed]
        ci = 1.96 * st.stdev(d) / len(d) ** 0.5 if any(d) else 0.0
        print(f"{name:7s}{label:46s}{st.mean(keyed.values()):7.0f}"
              f"{st.mean(d):+9.1f}{ci:7.1f}{st.mean(ap):10.3f}"
              f"{st.mean(tepts):8.0f}{st.mean(wrrnd):9.1f}")
    print("\nTE pts = season points scored in the TE starting slot.")
    print("WR rnds = mean round at which this arm's WRs were drafted")
    print("(lower = WRs bought earlier).")


if __name__ == "__main__":
    main()
