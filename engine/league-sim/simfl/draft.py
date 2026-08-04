"""Snake draft engine.

The engine is strategy-agnostic: each pick it hands the drafting team's
strategy a view of the board and takes back a player. Shared roster-
construction rules (positional caps, must-fill, kicker timing) live
here so every strategy drafts a *legal, sane* roster and differences
between strategies are purely about priorities, not competence.
"""

import random

from .config import LeagueConfig
from .models import PlayerSeason, Team

# Nobody sane drafts a 3rd QB or a 2nd kicker in a 12-team league.
POS_CAPS = {"QB": 2, "RB": 8, "WR": 8, "TE": 2, "K": 1}


class DraftState:
    def __init__(self, pool: list[PlayerSeason], league: LeagueConfig,
                 teams: list[Team]):
        self.league = league
        self.teams = teams
        self.available: list[PlayerSeason] = sorted(pool, key=lambda p: p.draft_rank)
        self._taken: set[str] = set()
        self.overall_pick = 0

    def take(self, player: PlayerSeason) -> None:
        self._taken.add(player.pid)
        self.available = [p for p in self.available if p.pid != player.pid]

    def picks_remaining(self, team: Team) -> int:
        return self.league.rounds - len(team.roster)

    def unfilled_starters(self, team: Team) -> list[str]:
        """Starting slots this roster cannot yet cover ('FLEX' generic)."""
        lg = self.league
        need = []
        counts = {pos: team.count_pos(pos) for pos in POS_CAPS}
        for pos, n in lg.starters.items():
            if pos == "FLEX":
                continue
            need += [pos] * max(0, n - counts[pos])
        flex_pool = sum(counts[p] for p in lg.flex_positions)
        flex_used = sum(lg.starters[p] for p in lg.flex_positions)
        need += ["FLEX"] * max(0, lg.starters["FLEX"] - max(0, flex_pool - flex_used))
        return need

    def eligible_positions(self, team: Team) -> set[str]:
        """Positions this team may draft right now."""
        remaining = self.picks_remaining(team)
        need = self.unfilled_starters(team)
        # Endgame: exactly enough picks left to fill starters -> forced.
        if remaining <= len(need):
            out = set()
            for slot in need:
                out.update(self.league.flex_positions if slot == "FLEX" else {slot})
            return out
        out = set()
        for pos, cap in POS_CAPS.items():
            if team.count_pos(pos) >= cap:
                continue
            # Kickers wait for the endgame (the family does this right).
            if pos == "K" and remaining > 2:
                continue
            out.add(pos)
        return out


def snake_order(n_teams: int, rounds: int) -> list[int]:
    order = []
    for rnd in range(rounds):
        seats = range(n_teams) if rnd % 2 == 0 else range(n_teams - 1, -1, -1)
        order += list(seats)
    return order


def run_draft(pool: list[PlayerSeason], teams: list[Team],
              league: LeagueConfig, rng: random.Random) -> list[tuple[int, Team, PlayerSeason]]:
    """Run a full snake draft. Returns the pick log."""
    state = DraftState(pool, league, teams)
    log = []
    for seat in snake_order(league.n_teams, league.rounds):
        team = teams[seat]
        state.overall_pick += 1
        player = team.strategy.pick(state, team, rng)
        state.take(player)
        team.roster.append(player)
        team.drafted_round[player.pid] = len(team.roster)
        log.append((state.overall_pick, team, player))
    return log
