"""The bench-lottery question: does a late-round RB become a weekly
starter more often than a late-round WR?

'Startable week' = that week's points rank in the positional top-24
(enough to crack a 12-team starting lineup + flex). We measure how
often bench-round picks (ADP 96-180, ~rounds 8-15) produce startable
weeks and sustained startable runs.

Run:  venv/bin/python scripts/bench_lottery.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simfl.config import DEFAULT_SCORING
from simfl.pool import build_pool

BAND = (96, 180)
TOP = 24


def weekly_top(pool, pos):
    """set of (week, pid) that were positional top-24 that week."""
    out = set()
    by_week = {}
    for p in pool:
        if p.pos != pos:
            continue
        for w, pts in p.week_pts.items():
            by_week.setdefault(w, []).append((pts, p.pid))
    for w, lst in by_week.items():
        lst.sort(reverse=True)
        out.update((w, pid) for _, pid in lst[:TOP])
    return out


def longest_run(weeks):
    ws, best, cur = sorted(weeks), 0, 0
    for i, w in enumerate(ws):
        cur = cur + 1 if i and ws[i - 1] == w - 1 else 1
        best = max(best, cur)
    return best


if __name__ == "__main__":
    stats = {"RB": [], "WR": []}
    for year in range(2020, 2026):
        pool = build_pool(year, DEFAULT_SCORING)
        for pos in ("RB", "WR"):
            top = weekly_top(pool, pos)
            for p in pool:
                if p.pos != pos or p.adp is None or not (BAND[0] <= p.adp <= BAND[1]):
                    continue
                good = [w for w in p.week_pts if (w, p.pid) in top]
                stats[pos].append({"year": year, "name": p.name,
                                   "weeks": len(good), "run": longest_run(good)})
    print(f"Bench-round picks (ADP {BAND[0]}-{BAND[1]}), 2020-2025:")
    print(f"how often they produced positional top-{TOP} weeks\n")
    for pos in ("RB", "WR"):
        c = stats[pos]
        n = len(c)
        avg = sum(r["weeks"] for r in c) / n
        p4 = sum(r["weeks"] >= 4 for r in c) / n
        p8 = sum(r["weeks"] >= 8 for r in c) / n
        run3 = sum(r["run"] >= 3 for r in c) / n
        dud = sum(r["weeks"] <= 1 for r in c) / n
        print(f"{pos}: n={n}  startable wks avg {avg:.1f}  P(>=4wks) {p4:.0%}  "
              f"P(>=8wks) {p8:.0%}  P(3+wk consecutive run) {run3:.0%}  "
              f"P(dud <=1wk) {dud:.0%}")
    print("\nBiggest bench-round lottery hits:")
    for pos in ("RB", "WR"):
        top5 = sorted(stats[pos], key=lambda r: -r["weeks"])[:5]
        print(f"  {pos}: " + "; ".join(f"{r['year']} {r['name']} ({r['weeks']}w)"
                                       for r in top5))
