from dataclasses import dataclass

@dataclass
class FootballPlayer:
    player_name: str
    team_name: str
    player_position: str
    player_adp: float
    player_depth: int

    @property
    def slug(self) -> str:
        """
        Safe filename slug, lowercased with non-alphanumerics turned to underscores.
        """
        import re
        s = self.player_name.lower()
        # replace non-word chars with underscore
        return re.sub(r"[^a-z0-9]", "_", s).strip("_")

