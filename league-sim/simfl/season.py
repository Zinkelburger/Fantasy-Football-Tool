"""Week-by-week season simulation.

Draft -> 14-week head-to-head regular season with waivers after every
week -> 6-team playoff (weeks 15-17, top-2 byes). All-play record is
tracked alongside H2H because schedule luck is enormous in a 14-game
sample; the presentation leans on all-play.
"""

import random
from dataclasses import dataclass, field

from .config import LeagueConfig
from .draft import run_draft
from .lineup import ProjectionTable, set_lineup
from .models import PlayerSeason, Team
from .waivers import run_waivers


def round_robin(n: int, rng: random.Random) -> list[list[tuple[int, int]]]:
    """Circle-method schedule: n-1 rounds of perfect pairings, order
    shuffled per sim."""
    ids = list(range(n))
    rng.shuffle(ids)
    rounds = []
    for _ in range(n - 1):
        rounds.append([(ids[i], ids[n - 1 - i]) for i in range(n // 2)])
        ids.insert(1, ids.pop())
    rng.shuffle(rounds)
    return rounds


@dataclass
class SeasonResult:
    teams: list[Team]
    standings: list[Team]           # regular-season order
    playoff_seeds: list[Team]
    champion: Team
    transactions: list[tuple]
    slot_points: dict[int, dict[str, float]]  # team idx -> slot -> reg-season pts

    def team_by_strategy(self, name: str) -> list[Team]:
        return [t for t in self.teams if t.strategy.name == name]


def run_season(pool: list[PlayerSeason], strategies: list, league: LeagueConfig,
               table: ProjectionTable, rng: random.Random,
               names: list[str] | None = None) -> SeasonResult:
    assert len(strategies) == league.n_teams
    teams = [Team(idx=i, name=(names[i] if names else f"{s.label} (seat {i+1})"),
                  strategy=s) for i, s in enumerate(strategies)]
    run_draft(pool, teams, league, rng)

    rostered = {p.pid for t in teams for p in t.roster}
    free_agents = {p.pid: p for p in pool if p.pid not in rostered}
    # Initial priority is reverse draft order (ESPN). In rolling mode
    # this list persists and run_waivers cycles it; in reverse_standings
    # mode (the Sumfun setting) it is rebuilt worst-first every week,
    # with reverse draft order as the standing tiebreak.
    rolling = list(reversed(teams))
    tiebreak = {t.idx: i for i, t in enumerate(rolling)}

    def waiver_priority() -> list[Team]:
        if league.waiver_mode == "rolling":
            return rolling
        return sorted(teams, key=lambda t: (t.wins + 0.5 * t.ties,
                                            t.points_for, tiebreak[t.idx]))

    schedule = round_robin(league.n_teams, rng)
    slot_points: dict[int, dict[str, float]] = {t.idx: {} for t in teams}
    transactions: list[tuple] = []

    for week in range(1, league.regular_season_weeks + 1):
        scores = {}
        for t in teams:
            lineup, pts = set_lineup(t, week, table, league)
            scores[t.idx] = pts
            t.weekly_scores[week] = pts
            t.points_for += pts
            for slot, ps in lineup.items():
                got = sum(p.points(week) for p in ps)
                slot_points[t.idx][slot] = slot_points[t.idx].get(slot, 0.0) + got
        for i, j in schedule[(week - 1) % len(schedule)]:
            si, sj = scores[i], scores[j]
            teams[i].points_against += sj
            teams[j].points_against += si
            if si > sj:
                teams[i].wins += 1
                teams[j].losses += 1
            elif sj > si:
                teams[j].wins += 1
                teams[i].losses += 1
            else:
                teams[i].ties += 1
                teams[j].ties += 1
        vals = list(scores.values())
        for t in teams:
            others = [v for k, v in scores.items() if k != t.idx]
            t.all_play_wins += sum(1 for v in others if scores[t.idx] > v)
            t.all_play_wins += sum(0.5 for v in others if scores[t.idx] == v)
            t.all_play_games += len(others)
        transactions += run_waivers(waiver_priority(), teams, week, table,
                                    free_agents, league, rng)

    standings = sorted(teams, key=lambda t: (t.wins + 0.5 * t.ties, t.points_for),
                       reverse=True)
    seeds = standings[:league.playoff_teams]

    # Playoffs: week 15 QF (3v6, 4v5), week 16 SF (1 and 2 join), week 17 F.
    def duel(a: Team, b: Team, week: int) -> Team:
        pa = set_lineup(a, week, table, league)[1]
        pb = set_lineup(b, week, table, league)[1]
        if pa == pb:  # tie: better seed advances
            return a if seeds.index(a) < seeds.index(b) else b
        return a if pa > pb else b

    w15a = duel(seeds[2], seeds[5], 15)
    w15b = duel(seeds[3], seeds[4], 15)
    transactions += run_waivers(waiver_priority(), teams, 15, table, free_agents, league, rng)
    lo, hi = ((w15a, w15b) if seeds.index(w15a) > seeds.index(w15b) else (w15b, w15a))
    w16a = duel(seeds[0], lo, 16)
    w16b = duel(seeds[1], hi, 16)
    transactions += run_waivers(waiver_priority(), teams, 16, table, free_agents, league, rng)
    champion = duel(w16a, w16b, 17)

    return SeasonResult(teams=teams, standings=standings, playoff_seeds=seeds,
                        champion=champion, transactions=transactions,
                        slot_points=slot_points)
