"""What can I actually GET off this league's waiver wire?

Supersedes analysis/wire_contention.py, which hand-rolled its own
depletion model and never put dropped players back. This one measures
the wire *inside the full simulator*, so every mechanism is live:

  - the FA pool is emergent (whatever 12 drafting bots didn't roster)
  - every claim hands the dropped player back to the pool
  - season-ending injuries free the roster spot (`done_for_season`)
  - bad performers get cut (keep_value: EWMA x DNP discount)
  - real Friday injury-report status drives lineups (Q_DISCOUNT)
  - 11 rival bots claim first, at per-seat activity rates calibrated
    to the league's real ESPN transaction counts
  - reverse-standings priority, rebuilt weekly

The question is not "what's the average FA worth" — that averages a
pile of junk with the occasional real starter and tells you nothing.
It is: **how often is there someone on the wire I'd actually start?**
And for the endgame: **if I throw a dart at the best available RB in
November, how often does it stick?**

Startable = that week's points land in the position's top 12 (QB/TE)
or top 24 (RB/WR) — i.e. a legitimate starter in a 12-team league
with a FLEX.

Run:  venv/bin/python analysis/wire_sim.py
"""

import random
import statistics as st
from collections import defaultdict

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import make

N_SIMS = 40
SEED = 11
POS = ("QB", "RB", "WR", "TE")
STARTABLE_RANK = {"QB": 12, "TE": 12, "RB": 24, "WR": 24}
WEEKS = range(2, 15)          # wire snapshots exist from week 2 on
BUCKETS = [("wk 2-5", range(2, 6)), ("wk 6-10", range(6, 11)),
           ("wk 11-14", range(11, 15))]


def thresholds(pool, week: int) -> dict[str, float]:
    """Points needed that week to be a top-12/24 player at the position."""
    out = {}
    for pos in POS:
        pts = sorted((p.points(week) for p in pool
                      if p.pos == pos and p.played(week)), reverse=True)
        n = STARTABLE_RANK[pos]
        out[pos] = pts[n - 1] if len(pts) >= n else 0.0
    return out


def run(year: int):
    pool, table = get_pool(year)
    thr = {w: thresholds(pool, w) for w in WEEKS}
    by_pid = {p.pid: p for p in pool}
    # pos -> bucket -> list of (best_pts, any_of_top3_startable)
    hits = defaultdict(lambda: defaultdict(list))
    depth_hits = defaultdict(lambda: defaultdict(list))
    darts = defaultdict(list)

    for i in range(N_SIMS):
        rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
        strat = [make("family") for _ in range(LG.n_teams)]
        for s in strat:
            s.bind_year(year)
        res = run_season(pool, strat, LG, table, rng, track_wire=True)
        for w in WEEKS:
            pre = res.wire_pre.get(w, {})
            for pos in POS:
                vals = pre.get(pos)
                if not vals:
                    continue
                t = thr[w][pos]
                for label, rng_wk in BUCKETS:
                    if w in rng_wk:
                        hits[pos][label].append(vals[0] >= t)
                        depth_hits[pos][label].append(any(v >= t for v in vals))
                        break
        # Dart throw: claim the best available at week 11, then see how
        # many startable weeks he delivers over the rest of the season.
        for w in (11, 12):
            for pos in POS:
                pid = res.wire_picks.get(w, {}).get(pos)
                if not pid:
                    continue
                p = by_pid[pid]
                got = sum(1 for k in range(w, 18)
                          if p.played(k) and p.points(k) >= thr.get(
                              min(k, 14), thr[14])[pos])
                darts[pos].append(got)
    return hits, depth_hits, darts


def main():
    all_hits = defaultdict(lambda: defaultdict(list))
    all_depth = defaultdict(lambda: defaultdict(list))
    all_darts = defaultdict(list)
    for y in SEASONS:
        h, d, k = run(y)
        for pos in POS:
            for label, _ in BUCKETS:
                all_hits[pos][label] += h[pos][label]
                all_depth[pos][label] += d[pos][label]
            all_darts[pos] += k[pos]

    print("=" * 66)
    print("HOW OFTEN IS THERE SOMEONE STARTABLE ON THE WIRE?")
    print("P(the FA I'd claim posts a top-12/24 week at his position)")
    print("=" * 66 + "\n")
    print(f"{'pos':6s}" + "".join(f"{b:>12s}" for b, _ in BUCKETS)
          + f"{'season':>10s}")
    for pos in POS:
        cells = [st.mean(all_hits[pos][b]) for b, _ in BUCKETS]
        tot = st.mean([v for b, _ in BUCKETS for v in all_hits[pos][b]])
        print(f"{pos:6s}" + "".join(f"{c:11.0%} " for c in cells)
              + f"{tot:9.0%}")

    print("\nSame, but allowing the top THREE claimable names (you get one")
    print("of them — this is the number that matters if you're not last")
    print("in the priority queue):\n")
    print(f"{'pos':6s}" + "".join(f"{b:>12s}" for b, _ in BUCKETS)
          + f"{'season':>10s}")
    for pos in POS:
        cells = [st.mean(all_depth[pos][b]) for b, _ in BUCKETS]
        tot = st.mean([v for b, _ in BUCKETS for v in all_depth[pos][b]])
        print(f"{pos:6s}" + "".join(f"{c:11.0%} " for c in cells)
              + f"{tot:9.0%}")

    print("\n" + "=" * 66)
    print("THE NOVEMBER DART THROW")
    print("Claim the best available at wk 11-12; startable weeks after:")
    print("=" * 66 + "\n")
    print(f"{'pos':6s}{'n':>7s}{'mean':>8s}{'P(>=1)':>9s}{'P(>=2)':>9s}{'P(>=3)':>9s}")
    for pos in POS:
        d = all_darts[pos]
        if not d:
            continue
        print(f"{pos:6s}{len(d):7d}{st.mean(d):8.2f}"
              f"{st.mean([x >= 1 for x in d]):8.0%} "
              f"{st.mean([x >= 2 for x in d]):8.0%} "
              f"{st.mean([x >= 3 for x in d]):8.0%}")


if __name__ == "__main__":
    main()
