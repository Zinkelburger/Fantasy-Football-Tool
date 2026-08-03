"""What does a GOOD team actually get off the waiver wire?

Not "what was on the wire" — what we ended up holding, after eleven
rivals claimed for their own reasons and reverse-standings priority put
us at the back of the queue for winning.

Everything is the live simulator: rivals claim when they have an injured
or underperforming player (keep_value / PointsChaser), season-ending
injuries free roster spots, drops return bodies to the pool, real Friday
injury reports drive start/sit. We read the actual transaction log and
score the players the hero really acquired.

Startable = that week's points land in the position's top 12 (QB/TE) or
top 24 (RB/WR).

Run:  venv/bin/python analysis/wire_got.py
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
SEED = 13
HERO = "pick_value"          # a team that actually wins, so it drafts late
POS = ("QB", "RB", "WR", "TE")
STARTABLE_RANK = {"QB": 12, "TE": 12, "RB": 24, "WR": 24}
LAST_WEEK = 14


def thresholds(pool, week):
    out = {}
    for pos in POS:
        pts = sorted((p.points(week) for p in pool
                      if p.pos == pos and p.played(week)), reverse=True)
        n = STARTABLE_RANK[pos]
        out[pos] = pts[n - 1] if len(pts) >= n else 0.0
    return out


def main():
    adds = defaultdict(list)          # pos -> startable weeks delivered
    got_any = defaultdict(int)
    by_queue = defaultdict(list)      # queue bucket -> startable weeks
    queue_seen = []
    claims_per_season = []
    win_pct = []

    for year in SEASONS:
        pool, table = get_pool(year)
        thr = {w: thresholds(pool, w) for w in range(1, LAST_WEEK + 1)}
        for i in range(N_SIMS):
            rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
            seat = i % LG.n_teams
            strat = [make("family") for _ in range(LG.n_teams)]
            strat[seat] = make(HERO)
            for s in strat:
                s.bind_year(year)
            res = run_season(pool, strat, LG, table, rng, track_wire=True)
            hero = res.teams[seat]
            win_pct.append(hero.all_play_pct)

            n_claims = 0
            for (wk, team, add, drop) in res.transactions:
                if team is not hero or add.pos not in POS:
                    continue
                n_claims += 1
                # He is ours from week wk+1 on.
                weeks = range(wk + 1, LAST_WEEK + 1)
                good = sum(1 for k in weeks
                           if add.played(k) and add.points(k) >= thr[k][add.pos])
                adds[add.pos].append(good)
                got_any[add.pos] += good > 0
                order = res.waiver_order.get(wk + 1, [])
                if seat in order:
                    q = order.index(seat) + 1
                    bucket = ("front (1-4)" if q <= 4 else
                              "middle (5-8)" if q <= 8 else "back (9-12)")
                    by_queue[bucket].append(good)
                    queue_seen.append(q)
            claims_per_season.append(n_claims)

    print(f"Hero = {HERO}; {N_SIMS} sims x {len(SEASONS)} seasons.")
    print(f"Hero all-play {st.mean(win_pct):.3f} "
          f"(a genuinely good team), waiver queue slot "
          f"{st.mean(queue_seen):.1f} of 12 on average, "
          f"{st.mean(claims_per_season):.1f} claims/season.\n")

    print("=" * 60)
    print("WHAT WE ACTUALLY GOT: startable weeks delivered per claim")
    print("=" * 60 + "\n")
    print(f"{'pos':6s}{'claims':>9s}{'mean':>8s}{'P(>=1)':>9s}{'P(>=2)':>9s}{'P(>=3)':>9s}")
    for pos in POS:
        d = adds[pos]
        if not d:
            continue
        print(f"{pos:6s}{len(d):9d}{st.mean(d):8.2f}"
              f"{st.mean([x >= 1 for x in d]):8.0%} "
              f"{st.mean([x >= 2 for x in d]):8.0%} "
              f"{st.mean([x >= 3 for x in d]):8.0%}")

    print("\n" + "=" * 60)
    print("DOES BEING GOOD COST US? by our slot in the priority queue")
    print("=" * 60 + "\n")
    print(f"{'queue':16s}{'claims':>9s}{'mean startable wks':>21s}{'P(>=1)':>9s}")
    for b in ("front (1-4)", "middle (5-8)", "back (9-12)"):
        d = by_queue[b]
        if not d:
            continue
        print(f"{b:16s}{len(d):9d}{st.mean(d):21.2f}"
              f"{st.mean([x >= 1 for x in d]):8.0%}")


if __name__ == "__main__":
    main()
