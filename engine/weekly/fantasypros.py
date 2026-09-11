"""FantasyPros expert consensus rankings (ECR) for the week.

Needs FANTASYPROS_API_KEY in engine/weekly/.env (their public API:
https://api.fantasypros.com/public/v2/json/nfl/<season>/consensus-rankings).
Without a key this module writes nothing and every consumer treats ECR
as absent. Nothing here is scraped from the website.

Output: data/weekly/ecr_<season>_wk<NN>.csv
  pos, rank_ecr, name, team, opp, rank_min, rank_max, rank_ave, rank_std,
  start_sit_grade (when FantasyPros supplies one)
"""
from __future__ import annotations

import csv
import sys

from common import DATA, load_env, http_json, norm_team, week_key

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]
SCORING = {"std": "STD", "half": "HALF", "ppr": "PPR"}


def fetch(season: int, week: int, fmt: str = "std") -> list[dict] | None:
    key = load_env().get("FANTASYPROS_API_KEY")
    if not key:
        return None
    rows = []
    for pos in POSITIONS:
        url = (f"https://api.fantasypros.com/public/v2/json/nfl/{season}/"
               f"consensus-rankings?position={pos}&scoring={SCORING[fmt]}"
               f"&type=weekly&week={week}")
        d = http_json(url, headers={"x-api-key": key})
        for p in d.get("players", []):
            rows.append(dict(
                pos=pos, rank_ecr=p.get("rank_ecr"), name=p.get("player_name"),
                team=norm_team(p.get("player_team_id")),
                opp=norm_team((p.get("player_opponent") or "").lstrip("@")),
                rank_min=p.get("rank_min"), rank_max=p.get("rank_max"),
                rank_ave=p.get("rank_ave"), rank_std=p.get("rank_std"),
                start_sit_grade=p.get("start_sit_grade"),
                fp_id=p.get("player_id")))
    path = DATA / f"ecr_{week_key(season, week)}.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["pos"])
        w.writeheader()
        w.writerows(rows)
    return rows


def load(season: int, week: int) -> list[dict]:
    path = DATA / f"ecr_{week_key(season, week)}.csv"
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    from common import nfl_state
    st = nfl_state()
    r = fetch(st["season"], st["week"])
    print("no FANTASYPROS_API_KEY set; skipped" if r is None else f"{len(r)} ECR rows")
