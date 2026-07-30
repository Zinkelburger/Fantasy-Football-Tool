"""Core simulation objects."""

from dataclasses import dataclass, field


@dataclass
class PlayerSeason:
    """One player in one historical season: what the market thought
    pre-draft (adp) and what actually happened (week_pts)."""

    pid: str
    name: str
    pos: str
    team: str
    adp: float | None          # None = off the ADP board
    adp_sd: float              # pick-to-pick draft variance
    rookie: bool
    bye: int
    week_pts: dict[int, float]  # only weeks with a stat line
    draft_rank: int = 0         # ADP order, prev-season points as fallback
    pos_rank: int = 0           # draft_rank order within position
    prior_ppg: float = 0.0      # leak-free preseason expectation

    def points(self, week: int) -> float:
        return self.week_pts.get(week, 0.0)

    def played(self, week: int) -> bool:
        return week in self.week_pts

    def on_bye(self, week: int) -> bool:
        return week == self.bye

    def __repr__(self):
        adp = f"{self.adp:.1f}" if self.adp else "--"
        return f"<{self.name} {self.pos} adp={adp}>"


@dataclass
class Team:
    """A franchise in the simulated league."""

    idx: int
    name: str
    strategy: "object"          # DraftStrategy; also carries in-season policies
    roster: list[PlayerSeason] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    all_play_wins: int = 0
    all_play_games: int = 0
    weekly_scores: dict[int, float] = field(default_factory=dict)
    moves: int = 0              # waiver adds made
    drafted_round: dict[str, int] = field(default_factory=dict)  # pid -> round

    def count_pos(self, pos: str) -> int:
        return sum(1 for p in self.roster if p.pos == pos)

    @property
    def record(self) -> str:
        t = f"-{self.ties}" if self.ties else ""
        return f"{self.wins}-{self.losses}{t}"

    @property
    def all_play_pct(self) -> float:
        return self.all_play_wins / self.all_play_games if self.all_play_games else 0.0
