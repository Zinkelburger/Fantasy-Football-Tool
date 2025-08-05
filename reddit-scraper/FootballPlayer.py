from dataclasses import dataclass
import pandas as pd
import re


@dataclass
class FootballPlayer:
    player_name: str
    team_name: str
    player_position: str
    player_adp: float
    player_depth: str
    player_nickname: str

    @property
    def slug(self) -> str:
        """
        Safe filename slug, lowercased with non-alphanumerics turned to underscores.
        """
        s = self.player_name.lower()
        # replace non-word chars with underscore
        return re.sub(r"[^a-z0-9]", "_", s).strip("_")
    
    @property
    def clean_name(self) -> str:
        """
        Clean name for .md files - removes suffixes and keeps spaces.
        """
        # Remove suffixes like Jr., Sr., II, III, IV, V
        name = re.sub(r"\s+(?:Jr\.|Sr\.|II|III|IV|V)$", "", self.player_name)
        return name.strip()

    @classmethod
    def from_csv(cls, csv_path: str) -> list["FootballPlayer"]:
        """
        Initialize FootballPlayer instances from CSV file.

        Args:
            csv_path: Path to the CSV file containing player data

        Returns:
            list of FootballPlayer instances
        """
        df = pd.read_csv(csv_path)
        players: list[FootballPlayer] = []
        for row in df.itertuples(index=False):
            players.append(
                cls(
                    player_name=row.Name,
                    team_name=row.Team,
                    player_position=row.Pos,
                    player_adp=row.ADP,
                    player_depth=row.Depth,
                    player_nickname=getattr(row, 'Nickname', ''),  # Handle missing nickname column gracefully
                )
            )
        return players
