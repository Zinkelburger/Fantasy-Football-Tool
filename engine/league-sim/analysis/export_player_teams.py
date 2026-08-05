"""Export player -> 2026 team for the site build.

site/build_site.py needs a team for every board player (the per-player
offense readout), but it must stay stdlib-only — it runs as the
Cloudflare Pages build command — so it can't read roster_2026.parquet.
This writes the fantasy-relevant slice as a small tracked CSV instead.
Re-run after refreshing the roster parquet.

Run:  venv/bin/python analysis/export_player_teams.py
"""
from pathlib import Path

import pandas as pd

MKT = Path(__file__).resolve().parent.parent / "data" / "market"

r = pd.read_parquet(MKT / "roster_2026.parquet")[
    ["full_name", "position", "team"]].dropna()
r = r[r.position.isin(("QB", "RB", "WR", "TE"))] \
    .rename(columns={"full_name": "name", "position": "pos"}) \
    .drop_duplicates(subset=["name", "pos"]) \
    .sort_values(["pos", "name"])
r.to_csv(MKT / "player_teams_2026.csv", index=False)
print(f"{len(r)} players -> {MKT / 'player_teams_2026.csv'}")
