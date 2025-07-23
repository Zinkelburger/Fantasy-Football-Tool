from dataclasses import dataclass
from typing import List
import pandas as pd
import re


@dataclass
class FootballPlayer:
    player_name: str
    team_name: str
    player_position: str
    player_adp: float
    player_depth: str

    @property
    def slug(self) -> str:
        """
        Safe filename slug, lowercased with non-alphanumerics turned to underscores.
        """
        s = self.player_name.lower()
        # replace non-word chars with underscore
        return re.sub(r"[^a-z0-9]", "_", s).strip("_")

    @classmethod
    def from_csv(cls, csv_path: str) -> List["FootballPlayer"]:
        """
        Initialize FootballPlayer instances from CSV file.

        Args:
            csv_path: Path to the CSV file containing player data

        Returns:
            List of FootballPlayer instances
        """
        df = pd.read_csv(csv_path)
        players: List[FootballPlayer] = []
        for row in df.itertuples(index=False):
            players.append(
                cls(
                    player_name=row.Name,
                    team_name=row.Team,
                    player_position=row.Pos,
                    player_adp=row.ADP,
                    player_depth=row.Depth,
                )
            )
        return players
