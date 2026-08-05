"""What is ONE patched hole actually worth, in points, that week?

Finding 22 prices the wire per season. This prices the individual
event a manager actually experiences: "my QB is on bye / hurt and I
have no backup — what does going to get one buy me *this week*?"

Method: run the same team paired (same seed) under `nowire` and
`holes_only`. For every team-week where the NO-WIRE arm has an empty
starting slot at position P, record what the HOLES-ONLY arm scored at
that same slot that same week. The difference is the value of that
single patch — no season-long aggregation, no attribution guesswork.

Run:  venv/bin/python analysis/wire_hole_value.py
"""

import random
import statistics as st
from collections import defaultdict

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import make
from simfl.waivers import MAX_CLAIMS, NoClaims, WaiverPolicy

N_SIMS = 30
SEED = 17
HERO = "pick_value"
WEEKS = range(1, 15)


class HolesOnly(WaiverPolicy):
    def desired_claims(self, team, week, table, fa_by_pos, league, rng):
        claims: list[tuple] = []
        self._fix_holes(team, week, table, fa_by_pos, league, claims)
        return claims[:MAX_CLAIMS]


def run_one(year, policy_cls, seat, i, pool, table):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    hero = make(HERO)
    hero.waiver_policy = policy_cls()
    strat[seat] = hero
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng, track_weekly=True)


def main():
    print("Value of ONE patched hole: paired nowire vs holes_only.")
    print(f"{N_SIMS} sims x {len(SEASONS)} seasons, hero={HERO}.\n")
    print("For each team-week where the NO-WIRE roster had an empty slot,")
    print("what did the same team score there once allowed to patch it?\n")

    gained = defaultdict(list)
    for year in SEASONS:
        pool, table = get_pool(year)
        for i in range(N_SIMS):
            seat = i % LG.n_teams
            a = run_one(year, NoClaims, seat, i, pool, table)
            b = run_one(year, HolesOnly, seat, i, pool, table)
            # Rosters evolve week to week, so the season records the
            # lineup as it actually stood each week for each arm.
            for wk in WEEKS:
                holes = a.weekly_holes[seat].get(wk, [])
                if not holes:
                    continue
                pa = a.weekly_slot_pts[seat].get(wk, {})
                pb = b.weekly_slot_pts[seat].get(wk, {})
                for pos in set(holes):
                    gained[pos].append(pb.get(pos, 0.0) - pa.get(pos, 0.0))

    print(f"{'slot':6s}{'hole-weeks':>13s}{'pts gained':>13s}"
          f"{'median':>9s}{'p90':>7s}")
    for pos in ("QB", "RB", "WR", "TE", "K"):
        v = gained.get(pos)
        if not v:
            continue
        sv = sorted(v)
        print(f"{pos:6s}{len(v):13d}{st.mean(v):13.1f}"
              f"{st.median(v):9.1f}{sv[int(0.9 * len(sv))]:7.1f}")


if __name__ == "__main__":
    main()
