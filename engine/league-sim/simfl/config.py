"""League and scoring configuration.

Defaults match the family league: 12-team ESPN standard (non-PPR),
whole-point scoring, FLEX is RB/WR only, no D/ST, rolling waiver
priority.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringConfig:
    """ESPN standard scoring. Yardage points are floored per category
    (97 rush yds = 9 pts), which is ESPN's non-fractional default."""

    pass_yds_per_pt: int = 25
    pass_td: int = 4
    interception: int = -2
    rush_yds_per_pt: int = 10
    rush_td: int = 6
    rec_yds_per_pt: int = 10
    rec_td: int = 6
    reception: float = 0.0      # 0 non-PPR, 0.5 half PPR, 1.0 full PPR
    fumble_lost: int = -2
    two_pt: int = 2
    return_td: int = 6
    # Kickers: distance-based FGs
    fg_0_39: int = 3
    fg_40_49: int = 4
    fg_50_plus: int = 5
    pat: int = 1
    fg_miss: int = 0            # ESPN default has no miss penalty


@dataclass(frozen=True)
class LeagueConfig:
    n_teams: int = 12
    # Sumfun League setting (ESPN waiverOrderReset=True): priority is
    # rebuilt worst-record-first before every run. "rolling" = ESPN
    # default (claim something, go to the back).
    waiver_mode: str = "reverse_standings"
    # Starting lineup slots. FLEX is RB/WR only in this league.
    starters: dict = field(default_factory=lambda: {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1,
    })
    flex_positions: tuple = ("RB", "WR")
    bench: int = 7
    regular_season_weeks: int = 14
    playoff_teams: int = 6      # ESPN default: 1-2 seeds get byes
    playoff_weeks: tuple = (15, 16, 17)

    @property
    def roster_size(self) -> int:
        return sum(self.starters.values()) + self.bench

    @property
    def rounds(self) -> int:
        return self.roster_size

    @property
    def starter_count(self) -> int:
        return sum(self.starters.values())


DEFAULT_SCORING = ScoringConfig()
DEFAULT_LEAGUE = LeagueConfig()

# The three scoring formats the site publishes advice for. Everything
# else about the league is held fixed across them, so a difference
# between two arms is caused by receptions and nothing else.
SCORING_FORMATS = {
    "std": ScoringConfig(),
    "half": ScoringConfig(reception=0.5),
    "ppr": ScoringConfig(reception=1.0),
}

# Full-PPR and half-PPR leagues usually make the flex TE-eligible. That
# is a lineup change, not a scoring one, so it is a separate arm rather
# than something folded into the formats above.
TE_FLEX_LEAGUE = LeagueConfig(flex_positions=("RB", "WR", "TE"))

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]

# Positions the simulation drafts and rosters. D/ST intentionally
# excluded (drafted last, behaves nothing like the other positions).
POSITIONS = ("QB", "RB", "WR", "TE", "K")
