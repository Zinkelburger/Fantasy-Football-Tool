"""Shared bits for the weekly engine: paths, season/week detection, team
abbreviations, scoring formats, and the .env loader.

Everything in engine/weekly/ is deterministic given its inputs. Network
fetches are isolated in nfl_data.py, espn_league.py and fantasypros.py;
the rest is pure computation over what those wrote to disk.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                      # repo root
DATA = ROOT / "data" / "weekly"                # committed outputs (site inputs)
CACHE = HERE / "cache"                         # gitignored nflverse cache
MODEL = HERE / "model"                         # fitted coefficients (committed)
DATA.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

# The three scoring formats the public site publishes. The family league
# (ESPN "Sumfun League") is standard, whole-point; ESPN projections come
# back in league scoring already, so the league-specific tools use those
# directly and only the opportunity model needs to know the format.
FORMATS = {"std": 0.0, "half": 0.5, "ppr": 1.0}

SKILL = ("QB", "RB", "WR", "TE")

# nflverse abbreviations -> full name, for the site. Rams are "LA" and
# Washington is "WAS" in nflverse; ESPN says LAR / WSH.
TEAMS = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}
# Anything another source might call a team -> nflverse abbreviation.
TEAM_ALIASES = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX", "OAK": "LV",
                "SD": "LAC", "STL": "LA", "GNB": "GB", "KAN": "KC",
                "NWE": "NE", "NOR": "NO", "SFO": "SF", "TAM": "TB"}

# ESPN proTeamId -> nflverse abbreviation.
ESPN_PRO_TEAMS = {
    1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN",
    8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LA",
    15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ",
    21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA",
    27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}
ESPN_POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
# ESPN lineup slot ids. Eligibility comes from each player's own
# eligibleSlots list, so this is for labels only.
ESPN_SLOTS = {0: "QB", 1: "TQB", 2: "RB", 3: "RB/WR", 4: "WR", 5: "WR/TE",
              6: "TE", 7: "OP", 16: "DST", 17: "K", 20: "BE", 21: "IR",
              23: "FLEX"}
NON_STARTING_SLOTS = {20, 21}


def norm_team(t: str | None) -> str | None:
    if not t:
        return None
    t = t.upper()
    return TEAM_ALIASES.get(t, t)


def load_env() -> dict:
    """KEY=value lines from engine/weekly/.env, falling back to the
    league-sim .env (same ESPN_* names). Real environment wins."""
    env: dict[str, str] = {}
    for p in (ROOT / "engine" / "league-sim" / ".env", HERE / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    for k in list(env) + ["ESPN_LEAGUE_ID", "ESPN_TEAM_ID", "ESPN_S2",
                          "ESPN_SWID", "FANTASYPROS_API_KEY", "ODDS_API_KEY"]:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def http_json(url: str, headers: dict | None = None, timeout: int = 30):
    # No browser User-Agent on purpose: ESPN's site API answers 403 to
    # a Mozilla string from a non-browser client but 200 to the plain
    # python-urllib default. Other hosts don't care.
    req = urllib.request.Request(url, headers=dict(headers or {}))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def nfl_state() -> dict:
    """Current NFL season and week. Sleeper's state endpoint is public,
    tiny, and rolls the week over on Tuesday night like every fantasy
    site does. Cached to disk so an offline build still knows the week.
    """
    path = CACHE / "nfl_state.json"
    try:
        s = http_json("https://api.sleeper.app/v1/state/nfl", timeout=10)
        out = {"season": int(s["season"]), "week": int(s["week"]),
               "season_type": s.get("season_type", "regular"),
               "fetched": now_iso()}
        path.write_text(json.dumps(out))
        return out
    except Exception as e:  # noqa: BLE001 - offline fallback
        if path.exists():
            return json.loads(path.read_text())
        raise RuntimeError(f"cannot determine NFL week: {e}") from e


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def week_key(season: int, week: int) -> str:
    return f"{season}_wk{week:02d}"
