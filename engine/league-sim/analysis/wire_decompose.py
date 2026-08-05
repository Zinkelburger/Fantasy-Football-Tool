"""Decompose the waiver wire: hole-patching vs bench churn.

Finding 22 priced the whole wire in one number. This splits it into
the two things a manager actually does, plus the naive human loop:

  nowire      never touches the wire at all (finding-22 baseline);
              still starts the best of its own 15 every week
  holes_only  claims/grabs a body ONLY when a starting slot would
              otherwise be EMPTY (QB bye with no QB2, all RBs out)
              -- pure roster maintenance, zero bench churn
  naive_wk6   holes_only PLUS, every third week from week 6 on,
              offers the worst bench spots to the wire for ANY
              projected upgrade at all ("swap my deadwood for the
              hot guy; if he pans out keep him, else try again")
  full_policy the default: holes first, then any 3+ ppg projected
              upgrade over the worst bench spot, checked weekly

All arms share drafter (pick_value), field, schedule and seeds; the
only difference is wire permission. Deltas are paired on nowire.

Run:  venv/bin/python analysis/wire_decompose.py
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

N_SIMS = 60
SEED = 17          # matches wire_worth.py: same seasons, same drafts
HERO = "pick_value"
SLOTS = ("QB", "RB", "WR", "TE", "FLEX", "K")


class HolesOnly(WaiverPolicy):
    """Roster maintenance only: fill a starting slot that would sit
    empty, never claim an upgrade."""

    def desired_claims(self, team, week, table, fa_by_pos, league, rng):
        claims: list[tuple] = []
        self._fix_holes(team, week, table, fa_by_pos, league, claims)
        return claims[:MAX_CLAIMS]


class NaiveChurn(WaiverPolicy):
    """The patient-human loop: from week 6, every third week, shop the
    worst bench spots for any projected upgrade (no 3-ppg hurdle)."""

    upgrade_threshold = 0.5

    def desired_claims(self, team, week, table, fa_by_pos, league, rng):
        claims: list[tuple] = []
        self._fix_holes(team, week, table, fa_by_pos, league, claims)
        if week >= 6 and (week - 6) % 3 == 0:
            claims += self.upgrades(team, week, table, fa_by_pos, league)
        return claims[:MAX_CLAIMS]


ARMS = [("nowire", NoClaims), ("holes_only", HolesOnly),
        ("naive_wk6", NaiveChurn), ("full_policy", WaiverPolicy)]


def run_one(year, policy_cls, seat, i, pool, table):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    hero = make(HERO)
    hero.waiver_policy = policy_cls()
    strat[seat] = hero
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng)


def main():
    print(f"{N_SIMS} sims x {len(SEASONS)} seasons per arm, paired on seed.")
    print(f"Hero drafter: {HERO}; arms differ only in waiver policy.\n")

    results = {}
    for name, cls in ARMS:
        keyed, ap, mv = {}, [], []
        addpos: dict[str, int] = defaultdict(int)
        for year in SEASONS:
            pool, table = get_pool(year)
            for i in range(N_SIMS):
                seat = i % LG.n_teams
                r = run_one(year, cls, seat, i, pool, table)
                t = r.teams[seat]
                keyed[(year, i)] = (t.points_for, r.slot_points[seat])
                ap.append(t.all_play_pct)
                mv.append(t.moves)
                for (_wk, team, add, _drop) in r.transactions:
                    if team is t:
                        addpos[add.pos] += 1
        results[name] = (keyed, ap, mv, addpos)

    n_runs = len(SEASONS) * N_SIMS
    base, base_ap = results["nowire"][0], results["nowire"][1]
    print(f"{'arm':13s}{'PF':>7s}{'vs nowire':>11s}{'±95%':>7s}"
          f"{'all-play Δ':>12s}{'adds/yr':>9s}   adds by pos")
    for name, (keyed, ap, mv, addpos) in results.items():
        pf = st.mean(v[0] for v in keyed.values())
        d = [keyed[k][0] - base[k][0] for k in keyed]
        ci = 1.96 * st.stdev(d) / len(d) ** 0.5
        dap = st.mean(ap) - st.mean(base_ap)
        mix = " ".join(f"{p}:{addpos.get(p, 0) / n_runs:.1f}"
                       for p in ("QB", "RB", "WR", "TE", "K") if addpos.get(p))
        print(f"{name:13s}{pf:7.0f}{st.mean(d):+11.1f}{ci:7.1f}"
              f"{dap:+12.3f}{st.mean(mv):9.1f}   {mix}")

    print("\nSeason points by lineup slot, arm minus nowire:\n")
    print(f"{'arm':13s}" + "".join(f"{s:>8s}" for s in SLOTS))
    for name, (keyed, *_rest) in results.items():
        if name == "nowire":
            continue
        row = ""
        for s in SLOTS:
            d = st.mean(keyed[k][1].get(s, 0.0) - base[k][1].get(s, 0.0)
                        for k in keyed)
            row += f"{d:+8.1f}"
        print(f"{name:13s}" + row)


if __name__ == "__main__":
    main()
