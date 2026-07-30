"""Draft strategies.

Every strategy sees the same board and the same legality rules (from
draft.DraftState); they differ only in *priorities*. Deterministic
strategies score candidates as rank multipliers on the ADP board; the
family model instead samples a noisy 'perceived rank' per player using
each player's real draft-position stdev from thousands of live drafts.

A strategy also carries its in-season personality: a lineup projection
is shared by everyone, but waiver policies differ (streamers stream,
the family chases last week's points).
"""

import json
import math
import random
from pathlib import Path

from .draft import DraftState
from .models import PlayerSeason, Team
from .waivers import PointsChaser, Streamer, WaiverPolicy

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class DraftStrategy:
    name = "base"
    label = "Base"
    window = 40   # names actually considered off the top of the board

    def __init__(self):
        self.waiver_policy = WaiverPolicy()

    def bind_year(self, year: int) -> None:
        """Hook for strategies with year-specific (leave-one-out) params."""

    # -- draft ---------------------------------------------------------
    def pick(self, state: DraftState, team: Team, rng: random.Random) -> PlayerSeason:
        elig = state.eligible_positions(team)
        rnd = len(team.roster) + 1
        cands = [p for p in state.available
                 if p.pos in elig and not self.banned(p, rnd, team, state)]
        if not cands:  # bans would leave nothing legal -> ignore them
            cands = [p for p in state.available if p.pos in elig]
        cands = cands[:self.window]  # board is in draft_rank order
        scored = [(self.score(p, rnd, team, state, rng), p) for p in cands]
        return min(scored, key=lambda t: t[0])[1]

    def banned(self, p: PlayerSeason, rnd: int, team: Team, state: DraftState) -> bool:
        # Universal restraint: no backup QB/TE until the late rounds.
        if p.pos == "QB" and team.count_pos("QB") >= 1 and rnd < 10:
            return True
        if p.pos == "TE" and team.count_pos("TE") >= 1 and rnd < 11:
            return True
        return False

    def score(self, p: PlayerSeason, rnd: int, team: Team,
              state: DraftState, rng: random.Random) -> float:
        """Lower is better. Base: ADP-board order, nudged toward
        unfilled starting slots (same competence for every strategy)."""
        need = set(state.unfilled_starters(team))
        fills = p.pos in need or ("FLEX" in need and p.pos in state.league.flex_positions)
        return p.draft_rank * (0.93 if fills else 1.08)


class BPA(DraftStrategy):
    """Control group: takes the board in ADP order, fills needs sanely,
    no positional convictions at all."""
    name = "bpa"
    label = "BPA (ADP order)"


class Family(DraftStrategy):
    """The family baseline, calibrated to the league's six real drafts
    (analysis/draft_tendencies.py):

    - Pick noise: the real reach spread is 2-7x the FFC market stdev
      (sd ~17 picks even in rounds 1-2), so perceived pick ~
      N(adp, max(noise_mult * adp_sd, noise_floor)).
    - Rookies got reached on by ~7 picks on average -> rookie_bias.
    - They do NOT reach for RBs (mean RB reach +5.1, i.e. slightly
      late vs market); QBs slip ~7 picks -> mild delay biases.
    - Kicker/DST endgame timing is handled by the draft engine.
    """
    name = "family"
    label = "Family baseline"

    def __init__(self, noise_mult: float = 3.0, noise_floor: float = 30.0,
                 rookie_bias: float = 0.95, pos_bias: dict | None = None):
        # Injected noise is ~2x the observed reach sd because min-
        # selection across 12 noisy bots compresses realized spread
        # (verified in analysis/calibrate.py).
        super().__init__()
        self.noise_mult = noise_mult
        self.noise_floor = noise_floor
        self.rookie_bias = rookie_bias
        self.pos_bias = ({"QB": 1.08, "RB": 1.05, "TE": 1.02}
                         if pos_bias is None else pos_bias)
        self.waiver_policy = PointsChaser()

    def score(self, p, rnd, team, state, rng):
        base = p.adp if p.adp is not None else float(p.draft_rank)
        sd = max(p.adp_sd * self.noise_mult, self.noise_floor)
        perceived = base + rng.gauss(0.0, sd)
        perceived *= self.pos_bias.get(p.pos, 1.0)
        if p.rookie:
            perceived *= self.rookie_bias
        need = set(state.unfilled_starters(team))
        fills = p.pos in need or ("FLEX" in need and p.pos in state.league.flex_positions)
        perceived *= 0.93 if fills else 1.08
        return perceived


class RobustRB(DraftStrategy):
    """Old-school: hammer RBs with the first three picks, then BPA."""
    name = "robust_rb"
    label = "Robust RB (RB-RB-RB)"

    def banned(self, p, rnd, team, state):
        if rnd <= 3 and p.pos != "RB":
            return True
        return super().banned(p, rnd, team, state)


class ZeroRB(DraftStrategy):
    """No RBs through round 5: load up on WR/TE/QB while the room
    burns picks on fragile RBs, then attack RB volume in the mid rounds."""
    name = "zero_rb"
    label = "Zero RB"

    def __init__(self, trigger: int = 6):
        super().__init__()
        self.trigger = trigger

    def banned(self, p, rnd, team, state):
        if p.pos == "RB" and rnd < self.trigger:
            return True
        return super().banned(p, rnd, team, state)

    def score(self, p, rnd, team, state, rng):
        s = super().score(p, rnd, team, state, rng)
        if p.pos == "RB" and rnd >= self.trigger and team.count_pos("RB") < 5:
            s *= 0.80
        return s


class HeroRB(DraftStrategy):
    """One elite RB in round 1, then avoid RBs until the mid rounds."""
    name = "hero_rb"
    label = "Hero RB"

    def banned(self, p, rnd, team, state):
        if rnd == 1 and p.pos != "RB":
            return True
        if p.pos == "RB" and 2 <= rnd <= 6:
            return True
        return super().banned(p, rnd, team, state)

    def score(self, p, rnd, team, state, rng):
        s = super().score(p, rnd, team, state, rng)
        if p.pos == "RB" and rnd > 6 and team.count_pos("RB") < 5:
            s *= 0.85
        return s


class EarlyQB(DraftStrategy):
    """Grab an elite QB by round ~3 (QBs are the top scorers in
    standard; the question is opportunity cost)."""
    name = "early_qb"
    label = "Early QB"

    def score(self, p, rnd, team, state, rng):
        s = super().score(p, rnd, team, state, rng)
        if p.pos == "QB" and team.count_pos("QB") == 0 and rnd >= 2:
            s *= 0.55
        return s


class LateQB(DraftStrategy):
    """No QB before round 10; stream a second one off waivers."""
    name = "late_qb"
    label = "Late-round QB"

    def __init__(self):
        super().__init__()
        self.waiver_policy = Streamer("QB")

    def banned(self, p, rnd, team, state):
        if p.pos == "QB" and rnd < 10:
            return True
        return super().banned(p, rnd, team, state)


class PuntTE(DraftStrategy):
    """No TE before round 12, then live off the waiver wire at TE all
    season. Tests whether the position is deep enough to punt."""
    name = "punt_te"
    label = "Punt TE + stream"

    def __init__(self):
        super().__init__()
        self.waiver_policy = Streamer("TE")

    def banned(self, p, rnd, team, state):
        if p.pos == "TE" and rnd < 12:
            return True
        return super().banned(p, rnd, team, state)


class WRHeavy(DraftStrategy):
    """Lean WR in the early rounds without a hard RB ban."""
    name = "wr_heavy"
    label = "WR heavy"

    def score(self, p, rnd, team, state, rng):
        s = super().score(p, rnd, team, state, rng)
        if p.pos == "WR" and rnd <= 6:
            s *= 0.85
        return s


class PickValue(DraftStrategy):
    """Drafts by cost-of-waiting: at every pick, a candidate is worth
        E[pts | his ADP] - E[pts | best at his position at my NEXT pick]
    using E[season pts] = a + b*ln(adp) fit on the OTHER five seasons
    (leave-one-year-out, so the strategy never sees the year it drafts).
    Take the biggest number. VORP falls out as the special case where a
    position's curve has flattened to waiver level (K: wait cost ~0)."""
    name = "pick_value"
    label = "Pick value (wait-cost)"
    EXHAUSTED_ADP = 250.0   # pseudo-ADP when a position empties out

    def __init__(self, year: int | None = None):
        super().__init__()
        self._fits_all = json.loads(
            (DATA_DIR / "pick_value_fits.json").read_text())
        self._cache: tuple[int, dict] | None = None
        self.bind_year(year)

    def bind_year(self, year):
        key = str(year) if str(year) in self._fits_all else "pooled"
        self.fits = self._fits_all[key]

    def _E(self, pos: str, pick: float) -> float:
        a, b = self.fits[pos]
        return a + b * math.log(max(pick, 1.0))

    @staticmethod
    def _adp_eff(p: PlayerSeason) -> float:
        return p.adp if p.adp is not None else float(p.draft_rank)

    def _next_pick_values(self, state: DraftState, team: Team, rnd: int) -> dict:
        """E[pts] of the best player left at each position at this
        team's next turn, assuming the room drafts in ADP order."""
        if self._cache and self._cache[0] == state.overall_pick:
            return self._cache[1]
        n = state.league.n_teams
        seat = team.idx
        nxt_round = rnd + 1
        in_round = seat + 1 if nxt_round % 2 == 1 else n - seat
        nxt_pick = (nxt_round - 1) * n + in_round
        vals = {}
        for pos in ("QB", "RB", "WR", "TE", "K"):
            future = [self._adp_eff(p) for p in state.available
                      if p.pos == pos and self._adp_eff(p) >= nxt_pick]
            vals[pos] = self._E(pos, min(future) if future else self.EXHAUSTED_ADP)
        self._cache = (state.overall_pick, vals)
        return vals

    BENCH_WEIGHT = 0.45   # a bench pick only pays off via flex/injury

    def score(self, p, rnd, team, state, rng):
        at_next = self._next_pick_values(state, team, rnd)
        wait_cost = self._E(p.pos, self._adp_eff(p)) - at_next[p.pos]
        # Marginal lineup value: points on the bench aren't points in
        # the lineup. Without this, pure wait-cost drafts 7 RBs and
        # starts scrub WRs.
        need = set(state.unfilled_starters(team))
        fills = p.pos in need or ("FLEX" in need
                                  and p.pos in state.league.flex_positions)
        return -(wait_cost if fills else wait_cost * self.BENCH_WEIGHT)


class PickValueHC(PickValue):
    """PickValue, but from the mid-late rounds it treats the handcuff
    of an early-round RB it already rosters as insurance: full lineup
    weight plus a bonus for the negative covariance (the cuff scores
    exactly when your starter's slot would otherwise crater — measured
    9.5 ppg with the starter out vs 4.6 in, analysis/rules_tests.py)."""
    name = "pick_value_hc"
    label = "Pick value + own handcuffs"
    HC_FROM_ROUND = 9
    HC_BONUS = 10.0   # season-points equivalent of the insurance value

    def score(self, p, rnd, team, state, rng):
        if p.pos == "RB" and rnd >= self.HC_FROM_ROUND:
            my_rb_teams = {q.team for q in team.roster
                           if q.pos == "RB" and (q.adp or 999) <= 72}
            if p.team in my_rb_teams:
                at_next = self._next_pick_values(state, team, rnd)
                wait_cost = self._E(p.pos, self._adp_eff(p)) - at_next[p.pos]
                return -(wait_cost + self.HC_BONUS)
        return super().score(p, rnd, team, state, rng)


STRATEGIES: dict[str, type] = {
    cls.name: cls for cls in
    (BPA, Family, RobustRB, ZeroRB, HeroRB, EarlyQB, LateQB, PuntTE,
     WRHeavy, PickValue, PickValueHC)
}


def make(name: str, **kwargs) -> DraftStrategy:
    return STRATEGIES[name](**kwargs)


class QBAtRound(DraftStrategy):
    """Sweep family: refuse QB before round N, then pull hard for the
    best one. Isolates *when* to draft the position, holding everything
    else at baseline behavior."""
    target = 6

    def banned(self, p, rnd, team, state):
        if p.pos == "QB" and rnd < self.target:
            return True
        return super().banned(p, rnd, team, state)

    def score(self, p, rnd, team, state, rng):
        s = super().score(p, rnd, team, state, rng)
        if p.pos == "QB" and team.count_pos("QB") == 0 and rnd >= self.target:
            s *= 0.40
        return s


for _r in (2, 3, 4, 5, 6, 8, 10, 12):
    STRATEGIES[f"qb_r{_r}"] = type(
        f"QBAtRound{_r}", (QBAtRound,),
        {"target": _r, "name": f"qb_r{_r}", "label": f"QB in round {_r}"})


class BenchTilt(DraftStrategy):
    """Once every starting slot is covered, tilt the remaining bench
    picks toward one position. Tests the 'bench RBs are lottery
    tickets, bench WRs are dead weight' theory."""
    prefer = "RB"
    avoid = "WR"

    def score(self, p, rnd, team, state, rng):
        s = super().score(p, rnd, team, state, rng)
        if not state.unfilled_starters(team):
            if p.pos == self.prefer:
                s *= 0.72
            elif p.pos == self.avoid:
                s *= 1.18
        return s


STRATEGIES["bench_rb"] = type("BenchRBs", (BenchTilt,), {
    "prefer": "RB", "avoid": "WR", "name": "bench_rb", "label": "Bench: hoard RBs"})
STRATEGIES["bench_wr"] = type("BenchWRs", (BenchTilt,), {
    "prefer": "WR", "avoid": "RB", "name": "bench_wr", "label": "Bench: hoard WRs"})
