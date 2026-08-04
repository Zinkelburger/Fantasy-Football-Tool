"""Fetch Sumfun League history from the ESPN fantasy API.

Pulls draft detail, teams, and settings for each season, plus the
season player-id -> name map, and caches everything under
data/espn/.  Reads credentials from league-sim/.env.
"""

import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "espn"
OUT.mkdir(parents=True, exist_ok=True)

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"

POSITION_IDS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
LEAGUE = ENV["ESPN_LEAGUE_ID"]
COOKIES = f"espn_s2={ENV['ESPN_S2']}; SWID={ENV['ESPN_SWID']}"


def get(url: str, extra_headers: dict | None = None):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 league-sim/0.1",
        "Cookie": COOKIES,
        **(extra_headers or {}),
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def fetch_league(year: int) -> dict:
    path = OUT / f"league_{year}.json"
    if path.exists():
        return json.loads(path.read_text())
    url = (f"{BASE}/leagueHistory/{LEAGUE}?seasonId={year}"
           "&view=mDraftDetail&view=mTeam&view=mSettings")
    data = get(url)
    if isinstance(data, list):
        data = data[0]
    path.write_text(json.dumps(data))
    return data


def fetch_players(year: int) -> dict:
    """player id -> {name, pos} for a season."""
    path = OUT / f"players_{year}.json"
    if path.exists():
        return json.loads(path.read_text())
    url = f"{BASE}/seasons/{year}/players?scoringPeriodId=0&view=players_wl"
    data = get(url, {"X-Fantasy-Filter": json.dumps({"filterActive": None})})
    out = {str(p["id"]): {"name": p.get("fullName", "?"),
                          "pos": POSITION_IDS.get(p.get("defaultPositionId"), "?")}
           for p in data}
    path.write_text(json.dumps(out))
    return out


def main():
    for year in SEASONS:
        lg = fetch_league(year)
        players = fetch_players(year)
        picks = lg.get("draftDetail", {}).get("picks", [])
        teams = {t["id"]: (t.get("name") or f"{t.get('location','')} {t.get('nickname','')}".strip())
                 for t in lg.get("teams", [])}
        n_rounds = max((p["roundId"] for p in picks), default=0)
        keepers = sum(1 for p in picks if p.get("keeper"))
        print(f"{year}: {len(picks)} picks, {n_rounds} rounds, "
              f"{len(teams)} teams, {keepers} keepers, "
              f"players mapped: {len(players)}")

    print(f"\ncached under {OUT}")


if __name__ == "__main__":
    main()
