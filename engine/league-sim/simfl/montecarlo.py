"""Monte Carlo experiments: one hero strategy against a field of
family bots, rotated through every draft seat, across many random
seeds and historical seasons."""

import random
from dataclasses import dataclass, field

from .config import DEFAULT_LEAGUE, DEFAULT_SCORING, LeagueConfig, ScoringConfig
from .lineup import ProjectionTable
from .pool import build_pool
from .season import run_season
from .strategies import make

_POOL_CACHE: dict[int, tuple] = {}


def get_pool(year: int, sc: ScoringConfig = DEFAULT_SCORING):
    if year not in _POOL_CACHE:
        pool = build_pool(year, sc)
        _POOL_CACHE[year] = (pool, ProjectionTable(pool))
    return _POOL_CACHE[year]


@dataclass
class HeroStats:
    year: int
    strategy: str
    n: int = 0
    wins: float = 0.0
    pf: float = 0.0
    all_play: float = 0.0
    playoffs: int = 0
    titles: int = 0
    finishes: list = field(default_factory=list)
    all_plays: list = field(default_factory=list)
    pfs: list = field(default_factory=list)
    # per-sim title flags: arms share a seed sequence, so these pair up
    # sim-for-sim (analysis/paired_arm_test.py)
    title_flags: list = field(default_factory=list)
    moves: float = 0.0

    def add(self, team, result):
        self.n += 1
        self.wins += team.wins + 0.5 * team.ties
        self.pf += team.points_for
        self.all_play += team.all_play_pct
        self.playoffs += team in result.playoff_seeds
        self.titles += team is result.champion
        self.finishes.append(result.standings.index(team) + 1)
        self.all_plays.append(team.all_play_pct)
        self.pfs.append(team.points_for)
        self.title_flags.append(1.0 if team is result.champion else 0.0)
        self.moves += team.moves

    @property
    def summary(self) -> dict:
        n = max(self.n, 1)
        return {
            "n": self.n,
            "avg_wins": self.wins / n,
            "avg_pf": self.pf / n,
            "all_play": self.all_play / n,
            "playoff_pct": self.playoffs / n,
            "title_pct": self.titles / n,
            "avg_finish": sum(self.finishes) / n if self.finishes else 0,
            "avg_moves": self.moves / n,
        }

    def to_dict(self) -> dict:
        return {"year": self.year, "strategy": self.strategy,
                "summary": self.summary, "finishes": self.finishes,
                "all_plays": self.all_plays, "pfs": self.pfs,
                "title_flags": self.title_flags,
                "playoffs": self.playoffs, "titles": self.titles}


def hero_experiment(year: int, hero: str, n_sims: int = 100, seed: int = 0,
                    league: LeagueConfig = DEFAULT_LEAGUE,
                    sc: ScoringConfig = DEFAULT_SCORING,
                    hero_kwargs: dict | None = None,
                    villain: str = "family") -> HeroStats:
    """Hero vs 11 villain bots (default: the calibrated family room);
    hero rotates seats so draft-slot luck averages out. Same seed
    sequence for every hero -> common random numbers across strategy
    comparisons within a room. villain="bpa" gives a theoretical sharp
    room: no draft noise, hero-grade waivers."""
    pool, table = get_pool(year, sc)
    stats = HeroStats(year=year, strategy=hero)
    for i in range(n_sims):
        rng = random.Random((seed, year, i).__hash__() & 0x7FFFFFFF)
        seat = i % league.n_teams
        strategies = [make(villain) for _ in range(league.n_teams)]
        strategies[seat] = make(hero, **(hero_kwargs or {}))
        for s in strategies:
            s.bind_year(year)
        result = run_season(pool, strategies, league, table, rng)
        stats.add(result.teams[seat], result)
    return stats


def compare(years: list[int], heroes: list[str], n_sims: int = 100,
            seed: int = 0, league: LeagueConfig = DEFAULT_LEAGUE,
            sc: ScoringConfig = DEFAULT_SCORING) -> dict:
    """{hero: {year: HeroStats}} for a grid of strategies and seasons."""
    out: dict[str, dict[int, HeroStats]] = {}
    for hero in heroes:
        out[hero] = {}
        for year in years:
            out[hero][year] = hero_experiment(year, hero, n_sims, seed,
                                              league, sc)
    return out


def pooled(per_year: dict[int, "HeroStats"]) -> dict:
    """Average the summary dicts across seasons (equal season weight)."""
    sums: dict[str, float] = {}
    ys = list(per_year.values())
    for s in ys:
        for k, v in s.summary.items():
            sums[k] = sums.get(k, 0.0) + v
    return {k: v / len(ys) for k, v in sums.items()}
