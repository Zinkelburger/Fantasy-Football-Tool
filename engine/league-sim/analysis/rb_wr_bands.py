"""Pure-data RB vs WR: what does an early pick at each position actually
buy, 2020-25? Distributions (not just means), availability, bust type,
and what replacement looks like if the pick dies."""
import statistics as st
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from collections import defaultdict
from common import SEASONS
from simfl.montecarlo import get_pool

WKS = range(1, 15)
BANDS = [(1, 12), (13, 24), (25, 36), (37, 72)]


def pts14(p):
    return sum(p.points(w) for w in WKS if p.played(w))


def games(p):
    return sum(1 for w in WKS if p.played(w))


rows = defaultdict(list)   # (pos, band) -> [(pts, games, ppg, repl)]
repl30 = {}
for year in SEASONS:
    pool, _ = get_pool(year)
    for pos in ("RB", "WR"):
        ranked = sorted((pts14(p) for p in pool if p.pos == pos), reverse=True)
        repl30[(year, pos)] = ranked[29] if len(ranked) > 29 else 0.0
    for p in pool:
        if p.pos not in ("RB", "WR") or not p.adp:
            continue
        for lo, hi in BANDS:
            if lo <= p.adp <= hi:
                g = games(p)
                rows[(p.pos, (lo, hi))].append(
                    (pts14(p), g, pts14(p) / g if g else 0.0,
                     repl30[(year, p.pos)]))

print("what an ADP band buys, 14 weeks, STD (2020-25):")
print(f"{'band':>6s} {'pos':>4s} {'n':>4s} {'mean':>6s} {'p25':>6s} "
      f"{'p50':>6s} {'p75':>6s} {'ppg':>6s} {'missed':>7s} "
      f"{'inj-bust':>9s} {'perf-bust':>10s}")
for lo, hi in BANDS:
    for pos in ("RB", "WR"):
        r = rows[(pos, (lo, hi))]
        pts = sorted(x[0] for x in r)
        n = len(pts)
        q = lambda f: pts[min(int(f * n), n - 1)]
        missed = st.mean(max(0, 13 - x[1]) for x in r)
        inj = sum(1 for x in r if x[1] <= 8) / n
        perf = sum(1 for x in r if x[1] >= 10 and x[0] < x[3]) / n
        ppg = st.mean(x[2] for x in r if x[1] >= 4)
        print(f"{lo:>3d}-{hi:<3d} {pos:>3s} {n:>4d} {st.mean(pts):>6.0f} "
              f"{q(.25):>6.0f} {q(.50):>6.0f} {q(.75):>6.0f} {ppg:>6.1f} "
              f"{missed:>7.1f} {inj:>9.0%} {perf:>10.0%}")

# ppg while active, same bands — separates talent from availability
print("\nper-game while active (>=4 games), same bands:")
for lo, hi in BANDS:
    rb = [x[2] for x in rows[("RB", (lo, hi))] if x[1] >= 4]
    wr = [x[2] for x in rows[("WR", (lo, hi))] if x[1] >= 4]
    print(f"  {lo:>3d}-{hi:<3d}: RB {st.mean(rb):5.1f} ppg   "
          f"WR {st.mean(wr):5.1f} ppg")

# replacement if the pick dies: best realistically-available wire body
print("\nwire replacement, weeks 1-14 pooled 2020-25:")
for topn in (24, 36):
    for pos in ("RB", "WR"):
        tot = und = 0
        for year in SEASONS:
            pool, _ = get_pool(year)
            for w in WKS:
                wk = sorted(((p.points(w), p) for p in pool
                             if p.pos == pos and p.played(w)),
                            key=lambda t: -t[0])[:topn]
                tot += len(wk)
                und += sum(1 for _, p in wk
                           if p.adp is None or p.adp > 180)
        print(f"  top-{topn} weekly {pos} scorers who went undrafted: "
              f"{und/tot:.0%}")
