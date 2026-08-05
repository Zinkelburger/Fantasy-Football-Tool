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


# --- MockoScience imports (reddit, 2025 PPR study): strategy shapes
# from their permutation sim, tested here in OUR format (12T STD,
# RB/WR flex). Their own caveat predicts these lose RB-heavy formats.
class DualWRRB(DraftStrategy):
    """Their best PPR strategy: 2 RBs + 2 WRs within the first five
    picks (rounds 1-5 restricted to RB/WR, max 3 of either)."""
    name = "dual_wrrb"
    label = "Dual WR-RB (2+2 by r5)"

    def banned(self, p, rnd, team, state):
        if rnd <= 5 and (p.pos not in ("RB", "WR")
                         or team.count_pos(p.pos) >= 3):
            return True
        return super().banned(p, rnd, team, state)


class ThreePillars(DraftStrategy):
    """QB + RB + WR, one each, in the first three rounds (any order)."""
    name = "three_pillars"
    label = "Three Pillars (QB/RB/WR by r3)"

    def banned(self, p, rnd, team, state):
        if rnd <= 3 and (p.pos not in ("QB", "RB", "WR")
                         or team.count_pos(p.pos) >= 1):
            return True
        return super().banned(p, rnd, team, state)


class Rainbow(DraftStrategy):
    """QB/WR/RB/TE, one each, in the first four rounds (any order)."""
    name = "rainbow"
    label = "Rainbow (QB/WR/RB/TE by r4)"

    def banned(self, p, rnd, team, state):
        if rnd <= 4 and (p.pos == "K" or team.count_pos(p.pos) >= 1):
            return True
        return super().banned(p, rnd, team, state)


class HeroWR(DraftStrategy):
    """Mirror of HeroRB per their definition: one early WR, then a
    WR desert until the mid rounds."""
    name = "hero_wr"
    label = "Hero WR"

    def banned(self, p, rnd, team, state):
        if rnd == 1 and p.pos != "WR":
            return True
        if p.pos == "WR" and 2 <= rnd <= 6:
            return True
        return super().banned(p, rnd, team, state)

    def score(self, p, rnd, team, state, rng):
        s = super().score(p, rnd, team, state, rng)
        if p.pos == "WR" and rnd > 6 and team.count_pos("WR") < 5:
            s *= 0.85
        return s


class RobustThenValue(PickValue):
    """RB-RB-RB skeleton welded onto the wait-cost engine: does forcing
    robust_rb's opening onto pick_value's mid-round math beat either
    parent, or is the opening already what the math picks?"""
    name = "rb3_pv"
    label = "RB x3, then pick value"

    def banned(self, p, rnd, team, state):
        if rnd <= 3 and p.pos != "RB":
            return True
        return super().banned(p, rnd, team, state)


class ModelBoard(DraftStrategy):
    """Drafts veterans by OUR season projection model, everything else
    (rookies, kickers, unmodeled names) by ADP.

    Within each position, the ADP board's veteran slots are re-ordered
    by the model's predicted PPG — leave-that-year-out fits from
    analysis/export_model_history.py, so season Y is drafted from a
    list the model could have printed before Y. Cross-position timing,
    the rookie market and the shared competence layer all stay at
    baseline: paired against BPA, the only difference is WHICH veteran
    each slot buys, which is exactly the claim finding 25 makes."""
    name = "model"
    label = "Model board (LOYO)"

    _CSV = DATA_DIR / "market" / "model_board_hist.csv"

    def bind_year(self, year):
        import csv
        from .montecarlo import get_pool          # cached; no rebuild
        from .config import DEFAULT_SCORING
        pred = {}
        with open(self._CSV, newline="") as f:
            for r in csv.DictReader(f):
                if int(r["year"]) == year:
                    pred[r["pid"]] = float(r["pred"])
        pool, _ = get_pool(year, DEFAULT_SCORING)
        self._eff = {}
        for pos in ("QB", "RB", "WR", "TE"):
            vets = [p for p in pool if p.pos == pos and p.pid in pred]
            slots = sorted(p.draft_rank for p in vets)
            vets.sort(key=lambda p: -pred[p.pid])
            for slot, p in zip(slots, vets):
                self._eff[p.pid] = slot

    def pick(self, state, team, rng):
        # Window on the MODEL's board order, not ADP's — a vet the
        # model promotes from ADP 70 to slot 8 must be visible at 8.
        elig = state.eligible_positions(team)
        rnd = len(team.roster) + 1
        cands = [p for p in state.available
                 if p.pos in elig and not self.banned(p, rnd, team, state)]
        if not cands:
            cands = [p for p in state.available if p.pos in elig]
        cands.sort(key=lambda p: self._eff.get(p.pid, p.draft_rank))
        cands = cands[:self.window]
        scored = [(self.score(p, rnd, team, state, rng), p) for p in cands]
        return min(scored, key=lambda t: t[0])[1]

    def score(self, p, rnd, team, state, rng):
        need = set(state.unfilled_starters(team))
        fills = p.pos in need or ("FLEX" in need
                                  and p.pos in state.league.flex_positions)
        base = self._eff.get(p.pid, p.draft_rank)
        return base * (0.93 if fills else 1.08)


class ModelBlend(ModelBoard):
    """ADP with a model tilt: each veteran's effective slot is a
    weighted average of his ADP board rank and his model slot (the
    ModelBoard transplant). w=0 is BPA, w=1 is the pure model board —
    finding 25's corrected verdict says the board wins outright, so
    the open question this arm answers is whether a PARTIAL tilt of
    the board toward the model buys anything in league outcomes.

    `positions` gates WHERE the tilt applies. Finding 25's same-player
    table shows the board is not equally good everywhere (QB .55,
    RB .69, WR .64, TE .50), so a uniform tilt spends model error at
    RB — the board's best position — to buy whatever the model knows
    at TE, its worst. Subclasses tilt only the weak spots."""
    name = "blend50"
    label = "ADP + model 50/50"
    w = 0.5
    positions = ("QB", "RB", "WR", "TE")
    # Only tilt players this deep into their position's board.
    # analysis/disagreement_check.py: our disagreements with ADP carry
    # no information inside the top 12 at a position (corr -0.02) but
    # do beyond rank 30 (+0.16, 2.9se). A uniform tilt spends error at
    # the top to buy that, which is why blend50 lost.
    min_pos_rank = 0

    def bind_year(self, year):
        super().bind_year(year)
        from .config import DEFAULT_SCORING
        from .montecarlo import get_pool
        pool, _ = get_pool(year, DEFAULT_SCORING)
        rank = {p.pid: p.draft_rank for p in pool}
        pos = {p.pid: p.pos for p in pool}
        prank = {p.pid: p.pos_rank for p in pool}
        self._eff = {pid: (1 - self.w) * rank[pid] + self.w * slot
                     for pid, slot in self._eff.items()
                     if pos.get(pid) in self.positions
                     and prank.get(pid, 0) > self.min_pos_rank}


class ModelBlend25(ModelBlend):
    name = "blend25"
    label = "ADP + model 25% tilt"
    w = 0.25


class ModelBlendLate(ModelBlend):
    """Tilt only past position rank 30 — the one region where our
    disagreements with the market measurably point the right way.

    EXPLORATORY: the rank-30 cut was chosen by looking at these same
    seasons (analysis/disagreement_check.py), so this arm is selected
    in-sample. A win here is a hypothesis for 2026, not a finding."""
    name = "blend_late"
    label = "ADP + model tilt, late board only"
    w = 0.5
    min_pos_rank = 30


class ModelBlendNoTop(ModelBlend):
    """Same idea, looser cut: leave only the top 12 at each position
    alone (RB showed signal from the middle band onward)."""
    name = "blend_notop"
    label = "ADP + model tilt, outside top 12"
    w = 0.5
    min_pos_rank = 12


class ModelBlendTE(ModelBlend):
    """Tilt only TE — the position where the ADP board ranks worst."""
    name = "blend_te"
    label = "ADP + model tilt, TE only"
    w = 0.5
    positions = ("TE",)


class ModelBlendQBTE(ModelBlend):
    """Tilt only the board's two weakest positions."""
    name = "blend_qbte"
    label = "ADP + model tilt, QB+TE"
    w = 0.5
    positions = ("QB", "TE")


class RookieFlier(DraftStrategy):
    """BPA everywhere the market has an opinion; OUR rookie board for
    the last picks, where it has one and the market does not.

    ~70 drafted rookies reach the sim pool each season and the fantasy
    market prices only ~20. The rest sit past the end of the ADP board
    — and in a 12x15 league the draft is 180 picks against a 179-deep
    board, so simply re-sorting that tail changes nothing. The only
    way the coverage claim can pay in a DRAFT is if you spend real
    late picks on unpriced rookies instead of ADP-tail veterans, so
    that is what this arm does: the rookie model's top `n_promote`
    unpriced rookies are promoted to effective ranks starting at
    `promote_at`, i.e. the hero's last picks become model-chosen
    rookie fliers.

    Caveat that belongs with any result: drafted rookies who never
    recorded a stat are absent from the pool entirely (~8 of ~78 a
    year), so this arm is mildly flattered — its fliers cannot draw
    the very worst outcomes."""
    name = "rookie_flier"
    label = "ADP + rookie fliers (last 12)"
    n_promote = 12
    promote_at = 145

    _CSV = DATA_DIR / "market" / "rookie_board_hist.csv"

    def bind_year(self, year):
        import csv
        from .config import DEFAULT_SCORING
        from .montecarlo import get_pool
        pred = {}
        with open(self._CSV, newline="") as f:
            for r in csv.DictReader(f):
                if int(r["year"]) == year:
                    pred[r["pid"]] = float(r["pred"])
        pool, _ = get_pool(year, DEFAULT_SCORING)
        rooks = sorted((p for p in pool
                        if p.adp is None and p.rookie and p.pid in pred),
                       key=lambda p: -pred[p.pid])[:self.n_promote]
        self._eff = {p.pid: self.promote_at + i
                     for i, p in enumerate(rooks)}

    def pick(self, state, team, rng):
        elig = state.eligible_positions(team)
        rnd = len(team.roster) + 1
        cands = [p for p in state.available
                 if p.pos in elig and not self.banned(p, rnd, team, state)]
        if not cands:
            cands = [p for p in state.available if p.pos in elig]
        cands.sort(key=lambda p: self._eff.get(p.pid, p.draft_rank))
        cands = cands[:self.window]
        scored = [(self.score(p, rnd, team, state, rng), p) for p in cands]
        return min(scored, key=lambda t: t[0])[1]

    def score(self, p, rnd, team, state, rng):
        need = set(state.unfilled_starters(team))
        fills = p.pos in need or ("FLEX" in need
                                  and p.pos in state.league.flex_positions)
        base = self._eff.get(p.pid, p.draft_rank)
        return base * (0.93 if fills else 1.08)


class RookieFlierWide(RookieFlier):
    """Same idea, more aggressive: the last ~2.5 rounds go to fliers."""
    name = "rookie_flier25"
    label = "ADP + rookie fliers (last 25)"
    n_promote = 25
    promote_at = 130


class MarksTilt(DraftStrategy):
    """ADP, nudged by our TESTED buy/fade marks — the narrow shape our
    research edges actually came in.

    Findings 16/17: a WR or TE who scored well above what his targets
    and carries were worth gives it back next season (fade); one who
    scored well below holds his value (buy). Marks exported per season
    by analysis/export_marks_history.py. Everything else is BPA, so
    paired against BPA this prices the marks and nothing else.

    `strength` is the rank multiplier: 0.85 moves a marked player about
    15% of his board rank (roughly a round early in the mid rounds).
    """
    name = "marks"
    label = "ADP + buy/fade marks"
    strength = 0.85

    _CSV = DATA_DIR / "market" / "marks_hist.csv"

    def bind_year(self, year):
        import csv
        self._mark = {}
        with open(self._CSV, newline="") as f:
            for r in csv.DictReader(f):
                if int(r["year"]) == year:
                    self._mark[r["pid"]] = r["dir"]

    def score(self, p, rnd, team, state, rng):
        need = set(state.unfilled_starters(team))
        fills = p.pos in need or ("FLEX" in need
                                  and p.pos in state.league.flex_positions)
        base = float(p.draft_rank)
        d = self._mark.get(p.pid)
        if d == "buy":
            base *= self.strength
        elif d == "fade":
            base /= self.strength
        return base * (0.93 if fills else 1.08)


class MarksTiltHard(MarksTilt):
    """Same marks, acted on twice as hard (~2 rounds of movement)."""
    name = "marks_hard"
    label = "ADP + buy/fade marks (strong)"
    strength = 0.70


class RookieModelBoard(ModelBoard):
    """The other half of the rookie question: keep ADP for veterans,
    but re-rank the rookies the market DID price by our rookie model.

    Same transplant as ModelBoard — the rookie ADP slots stay, only
    who occupies them changes. This is finding 31's B-block ("do we
    beat rookie ADP where it exists?") asked in league outcomes
    instead of rank correlation."""
    name = "rookie_board"
    label = "ADP + model-ranked rookies"

    _CSV = DATA_DIR / "market" / "rookie_board_hist.csv"

    def bind_year(self, year):
        import csv
        from .config import DEFAULT_SCORING
        from .montecarlo import get_pool
        pred = {}
        with open(self._CSV, newline="") as f:
            for r in csv.DictReader(f):
                if int(r["year"]) == year:
                    pred[r["pid"]] = float(r["pred"])
        pool, _ = get_pool(year, DEFAULT_SCORING)
        self._eff = {}
        for pos in ("QB", "RB", "WR", "TE"):
            rk = [p for p in pool if p.pos == pos and p.rookie
                  and p.adp is not None and p.pid in pred]
            slots = sorted(p.draft_rank for p in rk)
            rk.sort(key=lambda p: -pred[p.pid])
            for slot, p in zip(slots, rk):
                self._eff[p.pid] = slot


STRATEGIES: dict[str, type] = {
    cls.name: cls for cls in
    (BPA, Family, RobustRB, ZeroRB, HeroRB, EarlyQB, LateQB, PuntTE,
     WRHeavy, PickValue, PickValueHC, RobustThenValue,
     DualWRRB, ThreePillars, Rainbow, HeroWR, ModelBoard, ModelBlend,
     ModelBlend25, ModelBlendLate, ModelBlendNoTop, ModelBlendTE, ModelBlendQBTE, RookieFlier,
     RookieFlierWide, RookieModelBoard, MarksTilt, MarksTiltHard)
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


class SecondArm:
    """Mixin: force (or forbid) a *second* QB/TE in the late rounds.

    `arms` is a tuple of (pos, round): at the first legal round >= that
    round the strategy spends the pick on the best remaining player at
    that position, no matter what the board says. round=None forbids the
    second one outright, so the bench spot goes to RB/WR instead.
    `no_before` optionally delays the *first* one (punt-then-darts).

    Deliberately base-agnostic — it overrides `pick`/`banned` and never
    touches `score` — so the identical intervention can be bolted onto
    the plain drafter and onto PickValue and compared like for like.
    """
    arms: tuple = ()
    no_before: dict = {}

    def banned(self, p, rnd, team, state):
        for pos, at in self.arms:
            if p.pos != pos:
                continue
            if team.count_pos(pos) >= 1:
                return at is None or rnd < at
        first = self.no_before.get(p.pos)
        if first is not None and team.count_pos(p.pos) == 0 and rnd < first:
            return True
        return super().banned(p, rnd, team, state)

    def pick(self, state, team, rng):
        rnd = len(team.roster) + 1
        elig = None
        for pos, at in self.arms:
            if at is None or rnd < at or team.count_pos(pos) != 1:
                continue
            if elig is None:
                elig = state.eligible_positions(team)
            if pos not in elig:
                continue      # engine says the roster can't afford it yet
            cands = [p for p in state.available if p.pos == pos]
            if cands:
                return cands[0]   # board is already in draft_rank order
        return super().pick(state, team, rng)


def _arm(name: str, label: str, base: type, arms: tuple,
         no_before: dict | None = None) -> None:
    STRATEGIES[name] = type(
        f"Arm_{name}", (SecondArm, base),
        {"arms": arms, "no_before": no_before or {},
         "name": name, "label": label})


# --- on the plain disciplined drafter (comparable to finding 14) ------
for _r in (10, 12, 14):
    _arm(f"te2_r{_r}", f"2nd TE in round {_r}", DraftStrategy, (("TE", _r),))
    _arm(f"qb2_r{_r}", f"2nd QB in round {_r}", DraftStrategy, (("QB", _r),))
_arm("te2_never", "Never a 2nd TE", DraftStrategy, (("TE", None),))
_arm("qb2_never", "Never a 2nd QB", DraftStrategy, (("QB", None),))
_arm("te_darts", "Punt TE, two late darts", DraftStrategy,
     (("TE", 12),), {"TE": 10})
# Same punt, single dart: isolates "delay TE1" from "add a TE2", since
# te_darts moves both levers at once.
_arm("te_punt_only", "Punt TE to r10, no 2nd", DraftStrategy,
     (("TE", None),), {"TE": 10})
_arm("both_late", "2nd TE r12 + 2nd QB r13", DraftStrategy,
     (("TE", 12), ("QB", 13)))

# --- the same arms on top of the wait-cost drafter --------------------
_arm("pv_te2_r12", "PickValue + 2nd TE r12", PickValue, (("TE", 12),))
_arm("pv_qb2_r12", "PickValue + 2nd QB r12", PickValue, (("QB", 12),))
_arm("pv_te2_never", "PickValue, never a 2nd TE", PickValue, (("TE", None),))
_arm("pv_qb2_never", "PickValue, never a 2nd QB", PickValue, (("QB", None),))
_arm("pv_both", "PickValue + 2nd TE r12 + 2nd QB r13", PickValue,
     (("TE", 12), ("QB", 13)))
# PickValue with the early-QB option removed: the wait-cost math still
# decides *when* after r6, it just can't spend a top-5-round pick there.
_arm("pv_late_qb", "PickValue, no QB before r6", PickValue, (), {"QB": 6})


class _NoWire:
    """Mixin: same drafter, but never uses the waiver wire. Paired
    against the stock version this prices the wire in lineup points."""

    def __init__(self, *a, **kw):
        from .waivers import NoClaims
        super().__init__(*a, **kw)
        self.waiver_policy = NoClaims()


for _base in (PickValue, RobustRB, BPA):
    _n = f"{_base.name}_nowire"
    STRATEGIES[_n] = type(f"NoWire_{_base.__name__}", (_NoWire, _base),
                          {"name": _n, "label": f"{_base.label} (no waivers)"})
