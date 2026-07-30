"""Waiver-wire policies and the rolling-priority claim processor.

After each week's games every team may submit ranked claims (add, drop).
Claims resolve in priority order; a successful claim sends that team to
the back of the line (ESPN rolling priority). The free-agent pool is
whatever no simulated team rosters — so 'can I stream a TE?' is answered
by the sim itself, not by assumption.
"""

import random

from .config import LeagueConfig
from .draft import POS_CAPS
from .lineup import ProjectionTable, lineup_holes
from .models import PlayerSeason, Team

MAX_CLAIMS = 2          # ranked claims a team may submit per week
EARLY_ROUND_LOYALTY = 7  # picks from rounds 1..N are protected early on
LOYALTY_WEEKS = 5        # ...through this week (even if hurt/suspended:
                         # nobody cuts a name-brand pick in September)


class WaiverPolicy:
    """Sensible default: fix lineup holes first, then claim clear
    projection upgrades over the worst bench player."""

    upgrade_threshold = 3.0   # projected ppg edge required to bother

    def droppable(self, team: Team, week: int, table: ProjectionTable) -> list[PlayerSeason]:
        """Roster sorted worst-first by keep value, respecting early-pick
        loyalty (nobody cuts their 3rd-rounder in week 2)."""
        cands = []
        for p in team.roster:
            draft_round = team.drafted_round.get(p.pid, 99)
            if week <= LOYALTY_WEEKS and draft_round <= EARLY_ROUND_LOYALTY:
                continue
            if p.pos == "K":
                continue  # kickers swap only via hole-fixing
            cands.append(p)
        cands.sort(key=lambda p: table.keep_value(p, week + 1))
        return cands

    def _fix_holes(self, team, week, table, fa_by_pos, league, claims):
        for pos in lineup_holes(team, week + 1, league):
            pool = [p for p in fa_by_pos.get(pos, []) if p.played(week + 1)]
            if not pool:
                continue
            add = max(pool, key=lambda p: table.fa_proj(p, week + 1))
            drop = self._hole_drop(team, week, table, pos)
            if drop is not None:
                claims.append((add, drop))

    def _hole_drop(self, team, week, table, pos):
        if pos == "K":
            ks = [p for p in team.roster if p.pos == "K"]
            if ks:
                return min(ks, key=lambda p: table.keep_value(p, week + 1))
        drops = self.droppable(team, week, table)
        return drops[0] if drops else None

    def upgrades(self, team, week, table, fa_by_pos, league) -> list[tuple]:
        drops = self.droppable(team, week, table)
        if not drops:
            return []
        floor_val = table.keep_value(drops[0], week + 1)
        cands = []
        for pos in ("RB", "WR", "TE", "QB"):
            if team.count_pos(pos) >= POS_CAPS[pos]:
                continue
            for p in fa_by_pos.get(pos, [])[:12]:
                gain = table.fa_proj(p, week + 1) - floor_val
                if gain > self.upgrade_threshold:
                    cands.append((gain, p))
        cands.sort(key=lambda t: -t[0])
        return [(p, drops[0]) for _, p in cands[:MAX_CLAIMS]]

    def desired_claims(self, team: Team, week: int, table: ProjectionTable,
                       fa_by_pos: dict[str, list[PlayerSeason]],
                       league: LeagueConfig, rng: random.Random) -> list[tuple]:
        claims: list[tuple] = []
        self._fix_holes(team, week, table, fa_by_pos, league, claims)
        claims += self.upgrades(team, week, table, fa_by_pos, league)
        return claims[:MAX_CLAIMS]


# Average waiver adds per season by franchise, from the real league's
# ESPN transaction counters 2020-2025 (team ids 1-12 -> seats 0-11).
# The league is heterogeneous and the traits are persistent: seat 5
# (46 adds in 3 of 6 years) churns 3x more than seats 3 and 7.
SEAT_SEASON_ADDS = [30.8, 30.0, 18.0, 12.3, 23.2, 39.7,
                    24.0, 12.0, 21.3, 15.7, 14.7, 25.8]
_FULL_ACTIVITY_ADDS = 34.0  # adds/season a trait-1.0 chaser produces


class PointsChaser(WaiverPolicy):
    """The family: grabs whoever just had a big game (recency bias),
    still fixes bye/injury holes like a competent manager. How *often*
    a given bot bothers is a persistent per-seat trait calibrated to
    the real league's transaction counts."""

    splash_threshold = 8.0    # last-week points that catch the eye
    scan = 6                  # different eyes land on different names

    def __init__(self, activity: float | None = None):
        self.activity = activity  # None -> per-seat trait at claim time

    def _trait(self, team) -> float:
        if self.activity is not None:
            return self.activity
        return SEAT_SEASON_ADDS[team.idx % 12] / _FULL_ACTIVITY_ADDS

    def desired_claims(self, team, week, table, fa_by_pos, league, rng):
        claims: list[tuple] = []
        self._fix_holes(team, week, table, fa_by_pos, league, claims)
        if rng.random() >= min(self._trait(team), 1.0):
            return claims[:MAX_CLAIMS]
        drops = self.droppable(team, week, table)
        if not drops:
            return claims[:MAX_CLAIMS]
        floor_val = table.keep_value(drops[0], week + 1)
        cands = []
        for pos in ("RB", "WR", "TE", "QB"):
            if team.count_pos(pos) >= POS_CAPS[pos]:
                continue
            for p in fa_by_pos.get(pos, []):
                splash = p.points(week)
                if splash >= self.splash_threshold and splash > floor_val + 2:
                    cands.append((splash, p))
        cands.sort(key=lambda t: -t[0])
        # Each manager fixates on their own guy from the top of the
        # scoreboard, not everyone on the consensus #1 add.
        pool = cands[:self.scan]
        n = min(2, len(pool), len(drops))
        picks = rng.sample(pool, k=n) if n else []
        picks.sort(key=lambda t: -t[0])
        claims += [(p, drops[i]) for i, (_, p) in enumerate(picks)]
        return claims[:MAX_CLAIMS]


class Streamer(WaiverPolicy):
    """Default policy plus aggressive weekly streaming at one position
    (the punt-TE / late-QB endgame: live off the wire)."""

    def __init__(self, pos: str, edge: float = 0.5):
        self.pos = pos
        self.edge = edge

    def desired_claims(self, team, week, table, fa_by_pos, league, rng):
        claims = []
        self._fix_holes(team, week, table, fa_by_pos, league, claims)
        mine = [p for p in team.roster if p.pos == self.pos]
        best_mine = max((table.proj(p, week + 1) for p in mine
                         if p.played(week + 1)), default=-1.0)
        pool = [p for p in fa_by_pos.get(self.pos, []) if p.played(week + 1)]
        if pool:
            add = max(pool, key=lambda p: table.fa_proj(p, week + 1))
            if table.fa_proj(add, week + 1) > best_mine + self.edge:
                if mine and team.count_pos(self.pos) >= POS_CAPS[self.pos]:
                    drop = min(mine, key=lambda p: table.keep_value(p, week + 1))
                else:
                    drops = self.droppable(team, week, table)
                    drop = drops[0] if drops else None
                if drop is not None:
                    claims.append((add, drop))
        claims += self.upgrades(team, week, table, fa_by_pos, league)
        return claims[:MAX_CLAIMS]


def run_waivers(priority: list[Team], teams: list[Team], week: int,
                table: ProjectionTable, free_agents: dict[str, PlayerSeason],
                league: LeagueConfig, rng: random.Random) -> list[tuple]:
    """Process one waiver run after `week`'s games. Mutates rosters,
    priority order, and the FA pool. Returns a transaction log."""
    fa_by_pos: dict[str, list[PlayerSeason]] = {}
    for p in free_agents.values():
        fa_by_pos.setdefault(p.pos, []).append(p)
    for pos in fa_by_pos:
        fa_by_pos[pos].sort(key=lambda p: -table.fa_proj(p, week + 1))

    wants: dict[int, list[tuple]] = {}
    for t in teams:
        wants[t.idx] = t.strategy.waiver_policy.desired_claims(
            t, week, table, fa_by_pos, league, rng)

    log = []
    for _pass in range(MAX_CLAIMS):
        moved: list[Team] = []
        for t in list(priority):
            for add, drop in wants[t.idx]:
                if add.pid not in free_agents or drop not in t.roster:
                    continue
                t.roster.remove(drop)
                t.roster.append(add)
                del free_agents[add.pid]
                free_agents[drop.pid] = drop
                t.moves += 1
                log.append((week, t, add, drop))
                wants[t.idx] = [c for c in wants[t.idx] if c[0].pid != add.pid]
                moved.append(t)
                break
        for t in moved:
            priority.remove(t)
            priority.append(t)
        if not moved:
            break
    return log
