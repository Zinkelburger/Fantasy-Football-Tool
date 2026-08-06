"""Is a drafted backup QB ever actually useful? And does it win TITLES?

The objection: points on my bench are worth zero. A QB2 only earns his
roster spot if he STARTS — covering a bye or injury, or taking the job
outright when QB1 busts. And if I only care about the championship,
points-for is the wrong scoreboard anyway.

So this measures exactly that:

  1. How many weeks does the drafted QB2 actually appear in the
     starting lineup? How often does he never start at all?
  2. How often does he become the PRIMARY starter (more starts than
     the QB drafted before him) — the "my QB1 busted and the backup
     saved me" case?
  3. Championship rate, playoff rate and all-play for a drafter
     allowed a QB2 vs the same drafter forbidden one, paired on seed.

Titles are noisy (1-in-12 base rate), so arm 3 runs many more sims and
reports a CI on the title rate itself. If the CI covers zero, that is
reported as "no detectable effect", not as a null.

Run:  venv/bin/python analysis/qb2_usefulness.py [--sims 150]
"""

import random
import statistics as st
import sys
from collections import defaultdict

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import PickValue, make

N_SIMS = 150
SEED = 23
REG_WEEKS = 14


class NoQB2(PickValue):
    """Same drafter, may never take a second QB. The bench spot goes to
    whatever it wants instead."""
    name = "noqb2"

    def banned(self, p, rnd, team, state):
        if p.pos == "QB" and team.count_pos("QB") >= 1:
            return True
        return super().banned(p, rnd, team, state)


def run_one(year, cls, seat, i, pool, table, track=False):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    strat[seat] = make("pick_value") if cls is None else cls()
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng, track_weekly=track)


def usage(n_sims):
    """How often does the drafted QB2 start?"""
    starts2, never, primary, teams_seen = [], 0, 0, 0
    pts_as_starter = []
    for year in SEASONS:
        pool, table = get_pool(year)
        for i in range(n_sims):
            seat = i % LG.n_teams
            res = run_one(year, None, seat, i, pool, table, track=True)
            for t in res.teams:
                qbs = [(r, pid) for pid, r in t.drafted_round.items()
                       if table.by_pid[pid].pos == "QB"]
                if len(qbs) < 2:
                    continue
                qbs.sort()
                qb1, qb2 = qbs[0][1], qbs[1][1]
                s1 = s2 = 0
                pts = 0.0
                for wk in range(1, REG_WEEKS + 1):
                    st_ = res.weekly_starters[t.idx].get(wk, [])
                    if qb1 in st_:
                        s1 += 1
                    if qb2 in st_:
                        s2 += 1
                        pts += table.by_pid[qb2].points(wk)
                teams_seen += 1
                starts2.append(s2)
                never += (s2 == 0)
                primary += (s2 > s1)
                if s2:
                    pts_as_starter.append(pts / s2)
    print(f"Teams that drafted a QB2: {teams_seen}")
    print(f"  weeks the QB2 actually started: mean {st.mean(starts2):.1f} "
          f"of {REG_WEEKS}, median {st.median(starts2):.0f}")
    print(f"  NEVER started a single week:    {never/teams_seen:.0%}")
    print(f"  started 3+ weeks:               "
          f"{sum(1 for s in starts2 if s >= 3)/teams_seen:.0%}")
    print(f"  became the PRIMARY starter:     {primary/teams_seen:.0%}")
    if pts_as_starter:
        print(f"  ppg in the weeks he did start:  "
              f"{st.mean(pts_as_starter):.1f}")


def titles(n_sims):
    """QB2 allowed vs forbidden -- on the scoreboard that matters."""
    print(f"\n{'arm':10s}{'PF':>7s}{'all-play':>10s}{'playoffs':>10s}"
          f"{'titles':>9s}{'±95%':>7s}")
    out = {}
    for name, cls in (("qb2_ok", None), ("no_qb2", NoQB2)):
        pf, ap, po, ti = [], [], [], []
        for year in SEASONS:
            pool, table = get_pool(year)
            for i in range(n_sims):
                seat = i % LG.n_teams
                res = run_one(year, cls, seat, i, pool, table)
                t = res.teams[seat]
                pf.append(t.points_for)
                ap.append(t.all_play_pct)
                po.append(t in res.playoff_seeds)
                ti.append(res.champion is t)
        n = len(ti)
        rate = sum(ti) / n
        ci = 1.96 * (rate * (1 - rate) / n) ** 0.5
        out[name] = (ti, rate)
        print(f"{name:10s}{st.mean(pf):7.0f}{st.mean(ap):10.3f}"
              f"{sum(po)/n:10.1%}{rate:9.1%}{ci:7.1%}")
    a, b = out["qb2_ok"][0], out["no_qb2"][0]
    d = [x - y for x, y in zip(a, b)]
    dci = 1.96 * st.stdev(d) / len(d) ** 0.5
    print(f"\nPaired title-rate difference (QB2 minus no-QB2): "
          f"{st.mean(d):+.1%} ± {dci:.1%}")
    print(f"n = {len(d)} paired seasons per arm. A 1-in-12 base rate is")
    print("noisy; treat a CI that spans 0 as 'not detectable at this n'.")


def main():
    n = N_SIMS
    if "--sims" in sys.argv:
        n = int(sys.argv[sys.argv.index("--sims") + 1])
    print("=" * 60)
    print("DOES THE BACKUP QB EVER ACTUALLY START?")
    print("=" * 60)
    usage(max(20, n // 4))
    print("\n" + "=" * 60)
    print("DOES ALLOWING A QB2 WIN CHAMPIONSHIPS?")
    print("=" * 60)
    titles(n)


if __name__ == "__main__":
    main()
