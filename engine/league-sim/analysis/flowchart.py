"""Draft rules as an explicit flowchart, A/B tested.

The question this answers: can a small set of IF-THEN rules beat the
value drafter, and should any of those rules be CONDITIONAL on how the
early rounds went?

A flowchart here is four knobs on top of the `pick_value` drafter,
which otherwise keeps deciding *who* to take:

  qb1_at   earliest round the starting QB may be drafted
  te1_at   earliest round the starting TE may be drafted
  qb2      may a backup QB ever be drafted (rounds 10+)
  te2      may a backup TE ever be drafted (rounds 11+)

Nothing here caps RB/WR counts. That was the flaw in roster_shape.py:
templates that pinned QB=1 and TE=1 were secretly testing "no backup
QB/TE" while appearing to test the RB/WR split, and they cost ~10 pts
of drafted talent doing it. Timing windows constrain *when*, not *how
many*, so the drafter is never forced to take a player it does not
want.

CONDITIONAL arms recompute qb1_at at pick time from the early build,
which is the "if I open RB-RB, then X" shape the flowchart wants.

Run:  venv/bin/python analysis/flowchart.py [--sims 60]
"""

import random
import statistics as st
import sys

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import PickValue, make

N_SIMS = 60
SEED = 17


class Flowchart(PickValue):
    """PickValue plus explicit timing windows for QB and TE."""
    name = "flow"
    qb1_at = 1
    te1_at = 1
    qb2 = True
    te2 = True

    def _qb1_target(self, team, state):
        return self.qb1_at

    def banned(self, p, rnd, team, state):
        if p.pos == "QB":
            n = team.count_pos("QB")
            if n == 0 and rnd < self._qb1_target(team, state):
                return True
            if n >= 1 and (not self.qb2 or rnd < 10):
                return True
            return False
        if p.pos == "TE":
            n = team.count_pos("TE")
            if n == 0 and rnd < self.te1_at:
                return True
            if n >= 1 and (not self.te2 or rnd < 11):
                return True
            return False
        return super().banned(p, rnd, team, state)


class CondQB(Flowchart):
    """IF the early rounds went RB-heavy THEN take the QB sooner, ELSE
    wait. Tests whether QB timing should depend on the early build at
    all, or whether one fixed round is as good."""
    name = "cond_qb"
    early_rb_threshold = 2
    if_rb_heavy = 5
    else_round = 8

    def _qb1_target(self, team, state):
        # Mid-draft, team.roster IS the drafted roster.
        early_rb = sum(1 for p in team.roster if p.pos == "RB"
                       and team.drafted_round.get(p.pid, 99) <= 3)
        return (self.if_rb_heavy if early_rb >= self.early_rb_threshold
                else self.else_round)


def arm(name, label, **kw):
    base = CondQB if kw.pop("cond", False) else Flowchart
    return name, label, type(f"F_{name}", (base,), {"name": name, **kw})


ARMS = [
    ("pv_free", "pick_value (baseline)", None),
    arm("qb4", "QB1 by r4, QB2+TE2 on", qb1_at=4),
    arm("qb6", "QB1 by r6, QB2+TE2 on", qb1_at=6),
    arm("qb8", "QB1 by r8, QB2+TE2 on", qb1_at=8),
    arm("qb10", "QB1 by r10 (late), QB2+TE2 on", qb1_at=10),
    arm("qb6_noqb2", "QB1 by r6, NO QB2", qb1_at=6, qb2=False),
    arm("qb6_note2", "QB1 by r6, NO TE2", qb1_at=6, te2=False),
    arm("qb6_neither", "QB1 by r6, no QB2, no TE2", qb1_at=6,
        qb2=False, te2=False),
    arm("qb10_noqb2", "QB1 by r10, NO QB2 (the real late-QB punt)",
        qb1_at=10, qb2=False),
    arm("cond", "CONDITIONAL: RB-heavy start -> QB r5, else r8",
        cond=True),
]


def run_one(year, cls, seat, i, pool, table):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    strat[seat] = make("pick_value") if cls is None else cls()
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng)


def main():
    n = N_SIMS
    if "--sims" in sys.argv:
        n = int(sys.argv[sys.argv.index("--sims") + 1])
    print(f"{n} sims x {len(SEASONS)} seasons per arm, paired on seed.")
    print("Timing windows only -- no positional count caps, so no arm is")
    print("ever forced to draft a player it does not want.\n")
    print(f"{'arm':14s}{'rule':42s}{'PF':>7s}{'vs base':>9s}"
          f"{'±95%':>7s}{'all-play':>10s}")
    base = None
    for name, label, cls in ARMS:
        keyed, ap = {}, []
        for year in SEASONS:
            pool, table = get_pool(year)
            for i in range(n):
                seat = i % LG.n_teams
                res = run_one(year, cls, seat, i, pool, table)
                t = res.teams[seat]
                keyed[(year, i)] = t.points_for
                ap.append(t.all_play_pct)
        if base is None:
            base = keyed
        d = [keyed[k] - base[k] for k in keyed]
        ci = 1.96 * st.stdev(d) / len(d) ** 0.5 if any(d) else 0.0
        print(f"{name:14s}{label:42s}{st.mean(keyed.values()):7.0f}"
              f"{st.mean(d):+9.1f}{ci:7.1f}{st.mean(ap):10.3f}")


if __name__ == "__main__":
    main()
