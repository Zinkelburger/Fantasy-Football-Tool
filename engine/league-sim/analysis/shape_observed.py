"""Which roster shapes WIN, observed rather than imposed.

Finding 34 forced templates on the drafter. That confounds two things:
the shape itself, and the cost of reaching past better players to hit
a quota. This script removes the intervention entirely.

Method: run ordinary leagues. Nobody is told what to draft. Record
every team's REALIZED composition (how many RB/WR/TE/QB it happened to
end up with) alongside what it scored. Then ask which naturally
occurring shapes did best.

The obvious confound in the other direction: composition is endogenous
(a team ends up RB-heavy partly because good RBs fell to it). So every
comparison also carries `prior` — the sum of the roster's leak-free
PRESEASON expectation, i.e. how much raw talent the draft delivered.
Comparing shapes at equal `prior` is comparing shape, not luck.

Run:  venv/bin/python analysis/shape_observed.py [--sims 200]
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

N_SIMS = 200
SEED = 31


def run_all(n_sims):
    """Every team in every league becomes one observation."""
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
                # Composition AS DRAFTED. NOT the end-of-season roster:
                # waivers churn bodies off it, so filtering t.roster would
                # silently drop everyone who was cut and undercount the
                # draft. drafted_round holds every pid the team drafted.
                drafted = [table.by_pid[pid] for pid in t.drafted_round]
                c = {pos: sum(1 for p in drafted if p.pos == pos)
                     for pos in ("QB", "RB", "WR", "TE", "K")}
                rows.append({
                    "year": year, "sim": i, "seat": t.idx,
                    "strat": t.strategy.name,
                    "pf": t.points_for, "ap": t.all_play_pct,
                    "prior": sum(p.prior_ppg for p in drafted),
                    **c,
                })
    return rows


def bucket_table(rows, key, label, lo=None, hi=None):
    """Mean outcome by a composition count, plus the talent control."""
    by = defaultdict(list)
    for r in rows:
        by[r[key]].append(r)
    print(f"\n{label}")
    print(f"{key:>5s}{'teams':>8s}{'PF':>9s}{'all-play':>10s}"
          f"{'prior':>9s}{'PF|talent':>11s}")
    # Residualize PF on prior (linear) so shapes are compared at equal
    # drafted talent.
    xs = [r["prior"] for r in rows]
    ys = [r["pf"] for r in rows]
    mx, my = st.mean(xs), st.mean(ys)
    var = sum((x - mx) ** 2 for x in xs)
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var if var else 0.0
    for k in sorted(by):
        if lo is not None and (k < lo or k > hi):
            continue
        v = by[k]
        if len(v) < 40:
            continue
        adj = st.mean(r["pf"] - beta * (r["prior"] - mx) for r in v)
        print(f"{k:>5d}{len(v):>8d}{st.mean(r['pf'] for r in v):>9.0f}"
              f"{st.mean(r['ap'] for r in v):>10.3f}"
              f"{st.mean(r['prior'] for r in v):>9.1f}{adj:>11.0f}")


def main():
    n = N_SIMS
    if "--sims" in sys.argv:
        n = int(sys.argv[sys.argv.index("--sims") + 1])
    rows = run_all(n)
    print(f"{len(rows)} team-seasons observed "
          f"({n} sims x {len(SEASONS)} seasons x {LG.n_teams} teams).")
    print("Nobody was told what to draft; these are the shapes that happened.\n")
    print("'prior' = sum of the drafted roster's leak-free preseason ppg")
    print("expectation (how much talent the draft delivered).")
    print("'PF|talent' = points for, adjusted to equal prior — this is the")
    print("column that isolates SHAPE from draft luck.")

    print("\n" + "=" * 62)
    print("NATURAL SHAPE DISTRIBUTION")
    print("=" * 62)
    for pos in ("QB", "RB", "WR", "TE"):
        cnt = defaultdict(int)
        for r in rows:
            cnt[r[pos]] += 1
        tot = len(rows)
        dist = "  ".join(f"{k}:{100*v/tot:.0f}%"
                         for k, v in sorted(cnt.items()) if v / tot >= 0.01)
        print(f"{pos:3s} {dist}")

    print("\n" + "=" * 62)
    print("OUTCOME BY REALIZED COMPOSITION")
    print("=" * 62)
    bucket_table(rows, "RB", "By number of RBs drafted:")
    bucket_table(rows, "WR", "By number of WRs drafted:")
    bucket_table(rows, "TE", "By number of TEs drafted:")
    bucket_table(rows, "QB", "By number of QBs drafted:")

    print("\n" + "=" * 62)
    print("RB/WR SPLIT AT EQUAL TALENT (the actual question)")
    print("=" * 62)
    print("rows = RBs drafted, cols = WRs drafted; cell = PF|talent")
    print("(blank = fewer than 40 teams landed there)\n")
    xs = [r["prior"] for r in rows]
    ys = [r["pf"] for r in rows]
    mx, my = st.mean(xs), st.mean(ys)
    var = sum((x - mx) ** 2 for x in xs)
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var if var else 0.0
    grid = defaultdict(list)
    for r in rows:
        grid[(r["RB"], r["WR"])].append(r["pf"] - beta * (r["prior"] - mx))
    rbs = sorted({r["RB"] for r in rows})
    wrs = sorted({r["WR"] for r in rows})
    print("      " + "".join(f"WR{w:<5d}" for w in wrs))
    for rb in rbs:
        line = f"RB{rb:<4d}"
        for wr in wrs:
            v = grid.get((rb, wr), [])
            line += f"{st.mean(v):<7.0f}" if len(v) >= 40 else "  .    "
        print(line)


if __name__ == "__main__":
    main()
