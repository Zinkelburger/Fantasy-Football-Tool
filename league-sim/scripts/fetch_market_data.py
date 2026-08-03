"""Fetch the market/roster data used by analysis/player_model.py.

Sources (all public nflverse releases, github.com/nflverse/nflverse-data):
- contracts: OverTheCap contract data incl. per-season cap hits
- draft_picks: draft capital (round/overall) per player
- combine: measurables
- roster_{year}: seasonal rosters (age, experience, team)

Files land in data/market/ and are skipped if already present.
"""
import urllib.request
from pathlib import Path

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
OUT = Path(__file__).resolve().parent.parent / "data" / "market"

FILES = [
    ("contracts/historical_contracts.parquet", "historical_contracts.parquet"),
    ("draft_picks/draft_picks.parquet", "draft_picks.parquet"),
    ("combine/combine.parquet", "combine.parquet"),
] + [(f"rosters/roster_{y}.parquet", f"roster_{y}.parquet")
     for y in range(2017, 2027)]

# full-URL extras: game results + Vegas lines (Lee Sharpe/nflverse) and
# nfelo's QB Elo (greerreNFL/nfeloqb)
EXTRAS = [
    ("https://github.com/nflverse/nfldata/raw/master/data/games.csv",
     "games.csv"),
    ("https://raw.githubusercontent.com/greerreNFL/nfeloqb/main/qb_elos.csv",
     "qb_elos.csv"),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    urls = [(f"{BASE}/{rel}", name) for rel, name in FILES] + EXTRAS
    for url, name in urls:
        dst = OUT / name
        if dst.exists():
            print(f"have    {name}")
            continue
        try:
            urllib.request.urlretrieve(url, dst)
            print(f"fetched {name} ({dst.stat().st_size // 1024} KB)")
        except Exception as e:              # noqa: BLE001 - 2026 roster may not exist yet
            print(f"skip    {name}: {e}")


if __name__ == "__main__":
    main()
