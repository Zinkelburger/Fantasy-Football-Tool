"""Leak-free weekly projections and lineup setting.

The projection for week W uses only weeks < W: an EWMA of observed
points blended with the preseason prior (which itself comes from the
previous season's positional curves). Managers know who is inactive or
on bye before kickoff — that mirrors real injury reports — but never
what anyone will score.

The whole table is precomputed once per season-year because it does not
depend on rosters, then shared across every Monte Carlo run.
"""

from .config import LeagueConfig
from .models import PlayerSeason, Team

EWMA_ALPHA = 0.35       # weight on the newest game
PRIOR_GAMES = 5         # observed games until the prior mostly fades


FA_PRIOR = 2.5          # skeptical prior for judging free agents

NEWS_PROMOTE = 0.75     # a promoted backup RB projects at this share of
                        # the sidelined starter's projection ("everyone
                        # reads the injury news"), for rosters and FAs
STARTER_ADP_CUTOFF = 120  # only real starters generate promotion news


class ProjectionTable:
    def __init__(self, pool: list[PlayerSeason], max_week: int = 18):
        self._proj: dict[str, list[float]] = {}
        self._fa: dict[str, list[float]] = {}
        self.by_pid: dict[str, PlayerSeason] = {p.pid: p for p in pool}
        for p in pool:
            row = [p.prior_ppg] * (max_week + 1)
            # FA view: pedigree doesn't count — only this season's tape.
            # Prevents the winner's-curse loop of claiming washed veterans
            # whose preseason prior never fades.
            fa_row = [FA_PRIOR] * (max_week + 1)
            ewma, seen = 0.0, 0
            for w in range(1, max_week + 1):
                if seen:
                    blend = min(1.0, seen / PRIOR_GAMES)
                    row[w] = blend * ewma + (1 - blend) * p.prior_ppg
                    fa_row[w] = min(blend * ewma + (1 - blend) * FA_PRIOR, row[w])
                if w in p.week_pts:
                    pts = p.week_pts[w]
                    ewma = pts if not seen else EWMA_ALPHA * pts + (1 - EWMA_ALPHA) * ewma
                    seen += 1
            self._proj[p.pid] = row
            self._fa[p.pid] = fa_row
        self._promote_backups(pool, max_week)

    def _promote_backups(self, pool, max_week: int) -> None:
        """News-aware RB promotion: in any week the top preseason RB of
        an NFL team sits, his best available backup projects at
        NEWS_PROMOTE x the starter's projection — managers don't wait
        for the EWMA to believe what the depth chart already says."""
        rbs_by_team: dict[str, list[PlayerSeason]] = {}
        for p in pool:
            if p.pos == "RB" and p.team:
                rbs_by_team.setdefault(p.team, []).append(p)
        for rbs in rbs_by_team.values():
            rbs.sort(key=lambda p: p.draft_rank)
            starter = rbs[0]
            if starter.adp is None or starter.adp > STARTER_ADP_CUTOFF:
                continue
            for w in range(1, max_week + 1):
                if starter.played(w):
                    continue
                cuff = next((p for p in rbs[1:] if p.played(w)), None)
                if cuff is None:
                    continue
                val = NEWS_PROMOTE * self._proj[starter.pid][w]
                if val > self._proj[cuff.pid][w]:
                    self._proj[cuff.pid][w] = val
                if val > self._fa[cuff.pid][w]:
                    self._fa[cuff.pid][w] = val

    def proj(self, p: PlayerSeason, week: int) -> float:
        return self._proj[p.pid][week]

    def fa_proj(self, p: PlayerSeason, week: int) -> float:
        """Skeptical value of an unrostered player: production-only."""
        return self._fa[p.pid][week]

    def keep_value(self, p: PlayerSeason, week: int) -> float:
        """Roster-spot value for add/drop decisions: projection discounted
        by observed availability (recent DNPs that weren't byes), floored
        by pedigree — managers remember why they drafted someone and
        don't cut a slow-starting early pick for a scrub."""
        v = self.proj(p, week)
        misses = sum(1 for w in range(max(1, week - 2), week)
                     if not p.played(w) and not p.on_bye(w))
        return max(v * (1.0, 0.75, 0.45)[min(misses, 2)], 0.6 * p.prior_ppg)


def set_lineup(team: Team, week: int, table: ProjectionTable,
               league: LeagueConfig) -> tuple[dict[str, list[PlayerSeason]], float]:
    """Greedy best-projection lineup among players active this week.
    Returns ({slot: players}, actual_points_scored)."""
    active = [p for p in team.roster if p.played(week)]
    active.sort(key=lambda p: -table.proj(p, week))
    used: set[str] = set()
    lineup: dict[str, list[PlayerSeason]] = {}
    for pos, n in league.starters.items():
        if pos == "FLEX":
            continue
        slot = [p for p in active if p.pos == pos and p.pid not in used][:n]
        used.update(p.pid for p in slot)
        lineup[pos] = slot
    flex = [p for p in active
            if p.pos in league.flex_positions and p.pid not in used]
    lineup["FLEX"] = flex[:league.starters["FLEX"]]
    used.update(p.pid for p in lineup["FLEX"])
    total = sum(p.points(week) for ps in lineup.values() for p in ps)
    return lineup, total


class _ZeroTable:
    def proj(self, p, week):  # ordering irrelevant for hole detection
        return 0.0


_ZERO = _ZeroTable()


def lineup_holes(team: Team, week: int, league: LeagueConfig) -> list[str]:
    """Starting positions with no active player available this week."""
    lineup, _ = set_lineup(team, week, _ZERO, league)
    holes = []
    for pos, n in league.starters.items():
        have = len(lineup.get(pos, []))
        if have < n:
            holes += [pos if pos != "FLEX" else league.flex_positions[0]] * (n - have)
    return holes
