"""What is the right ROSTER SHAPE — how many QB/RB/WR/TE to draft?

Fixes exact position counts for all 15 rounds (a template) on top of
the pick_value drafter: within the template it still takes the best
values at the best times, it just can't deviate from the shape. The
wire stays live for everyone (default policy), so a thin position can
be patched the way a real manager would patch it — this is the
"depth vs the wire" question asked properly.

Templates sum to 15 (8 starters + 7 bench). One QB / one TE / one K
unless the template says otherwise; the swing is the RB/WR bench mix,
per the 'WRs don't get hurt, RBs are scarce' theory.

Scoring formats: std is the family league. half/ppr rescore every
player week and rebuild projections, but the DRAFT BOARD stays the
std-market ADP (no PPR ADP in the data) — cross-format rows say how
the same market prices a shape when receptions score, not what a
PPR-native room would do.

Run:  venv/bin/python analysis/roster_shape.py [--formats std,half,ppr]
"""

import random
import statistics as st
import sys

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG, ScoringConfig
from simfl.draft import POS_CAPS
from simfl.lineup import ProjectionTable
from simfl.pool import build_pool
from simfl.season import run_season
from simfl.strategies import PickValue, make

N_SIMS = 60
SEED = 17

# Templates: (QB, RB, WR, TE, K), all sum to 15.
SHAPES = {
    "pv_free":  None,               # pick_value unconstrained (baseline)
    "rb9_wr3":  (1, 9, 3, 1, 1),    # the user's guess: max RB depth
    "rb8_wr4":  (1, 8, 4, 1, 1),
    "rb7_wr5":  (1, 7, 5, 1, 1),
    "rb6_wr6":  (1, 6, 6, 1, 1),
    "rb5_wr7":  (1, 5, 7, 1, 1),    # WR-heavy mirror
    "qb2":      (2, 6, 5, 1, 1),    # second QB instead of a bench body
    "te2":      (1, 6, 5, 2, 1),    # second TE instead of a bench body
}
FORMATS = {"std": 0, "half": 0.5, "ppr": 1}
CROSS_FORMAT_SHAPES = ("pv_free", "rb8_wr4", "rb6_wr6", "rb5_wr7")

POS_CAPS["RB"] = 9   # engine sanity cap is 8; rb9_wr3 needs one more


def template_class(counts):
    q, r, w, t, k = counts
    caps = {"QB": q, "RB": r, "WR": w, "TE": t, "K": k}

    class Shaped(PickValue):
        name = "shaped"

        def banned(self, p, rnd, team, state):
            if team.count_pos(p.pos) >= caps[p.pos]:
                return True
            return super().banned(p, rnd, team, state)

    return Shaped


def get_format_pool(year, ppr, cache={}):
    if (year, ppr) not in cache:
        sc = ScoringConfig(reception=ppr) if ppr else ScoringConfig()
        pool = build_pool(year, sc)
        cache[(year, ppr)] = (pool, ProjectionTable(pool))
    return cache[(year, ppr)]


NOWIRE = False   # --nowire: hero may not touch the waiver wire, so the
                 # drafted shape is the ONLY thing covering byes/injuries


def run_one(year, strat_factory, seat, i, pool, table):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    hero = strat_factory()
    if NOWIRE:
        from simfl.waivers import NoClaims
        hero.waiver_policy = NoClaims()
    strat[seat] = hero
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng)


def factory(shape):
    counts = SHAPES[shape]
    if counts is None:
        return lambda: make("pick_value")
    cls = template_class(counts)
    return lambda: cls()


def sweep(fmt, shapes):
    ppr = FORMATS[fmt]
    print(f"\n===== {fmt} scoring =====")
    print(f"{'shape':10s}{'QB-RB-WR-TE-K':>15s}{'PF':>7s}{'vs free':>9s}"
          f"{'±95%':>7s}{'all-play':>10s}{'Δ':>8s}")
    base = None
    for shape in shapes:
        keyed, ap = {}, []
        for year in SEASONS:
            pool, table = get_format_pool(year, ppr)
            for i in range(N_SIMS):
                seat = i % LG.n_teams
                res = run_one(year, factory(shape), seat, i, pool, table)
                t = res.teams[seat]
                keyed[(year, i)] = t.points_for
                ap.append(t.all_play_pct)
        if base is None:
            base, base_ap = keyed, ap
        d = [keyed[k] - base[k] for k in keyed]
        ci = 1.96 * st.stdev(d) / len(d) ** 0.5 if any(d) else 0.0
        counts = SHAPES[shape]
        label = "-".join(map(str, counts)) if counts else "(free)"
        print(f"{shape:10s}{label:>15s}{st.mean(keyed.values()):7.0f}"
              f"{st.mean(d):+9.1f}{ci:7.1f}"
              f"{st.mean(ap):10.3f}{st.mean(ap) - st.mean(base_ap):+8.3f}")


def main():
    global NOWIRE, N_SIMS
    fmts = ["std"]
    if "--formats" in sys.argv:
        fmts = sys.argv[sys.argv.index("--formats") + 1].split(",")
    if "--nsims" in sys.argv:
        N_SIMS = int(sys.argv[sys.argv.index("--nsims") + 1])
    if "--nowire" in sys.argv:
        NOWIRE = True
        print("HERO CANNOT USE THE WAIVER WIRE: the drafted shape is the")
        print("only thing covering byes and injuries.")
    for fmt in fmts:
        shapes = list(SHAPES) if fmt == "std" else list(CROSS_FORMAT_SHAPES)
        sweep(fmt, shapes)


if __name__ == "__main__":
    main()
