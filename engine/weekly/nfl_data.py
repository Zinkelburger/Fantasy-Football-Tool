"""nflverse loaders with a local parquet cache, plus the free odds feed.

Every function returns a polars DataFrame and writes what it fetched to
engine/weekly/cache/ so the compute steps can run offline. The current
season is refreshed on every call with refresh=True (the default in
build_week.py); past seasons are fetched once.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from common import CACHE, TEAMS, http_json, norm_team, now_iso


def _cached(name: str, loader, refresh: bool) -> pl.DataFrame:
    path = CACHE / f"{name}.parquet"
    if path.exists() and not refresh:
        return pl.read_parquet(path)
    df = loader()
    df.write_parquet(path)
    return df


def pbp(season: int, refresh: bool = False) -> pl.DataFrame:
    import nflreadpy as nfl
    return _cached(f"pbp_{season}", lambda: nfl.load_pbp([season]), refresh)


def player_stats(season: int, refresh: bool = False) -> pl.DataFrame:
    import nflreadpy as nfl
    return _cached(f"player_stats_{season}",
                   lambda: nfl.load_player_stats([season], summary_level="week"),
                   refresh)


def schedules(season: int, refresh: bool = False) -> pl.DataFrame:
    import nflreadpy as nfl
    return _cached(f"schedules_{season}", lambda: nfl.load_schedules([season]),
                   refresh)


def injuries(season: int, refresh: bool = False) -> pl.DataFrame:
    import nflreadpy as nfl
    return _cached(f"injuries_{season}", lambda: nfl.load_injuries([season]),
                   refresh)


def depth_charts(season: int, refresh: bool = False) -> pl.DataFrame:
    import nflreadpy as nfl
    return _cached(f"depth_{season}", lambda: nfl.load_depth_charts([season]),
                   refresh)


def players(refresh: bool = False) -> pl.DataFrame:
    """The id crosswalk: gsis_id <-> espn_id, with position and team."""
    import nflreadpy as nfl
    return _cached("players", lambda: nfl.load_players().select(
        ["gsis_id", "espn_id", "display_name", "position", "latest_team",
         "status"]), refresh)


def espn_scoreboard_odds(season: int, week: int) -> list[dict]:
    """Current lines from ESPN's public scoreboard (DraftKings). These
    move all week; nflverse's schedule file carries a lookahead line
    that is refreshed less often. One row per game:
      {game: 'SF@LA', away, home, kickoff, state, spread_home, total,
       provider}
    spread_home is the home margin (positive = home favoured), matching
    nflverse spread_line, so the same implied-total arithmetic applies.
    """
    url = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
           f"scoreboard?week={week}&seasontype=2&dates={season}")
    d = http_json(url)
    out = []
    for ev in d.get("events", []):
        c = ev["competitions"][0]
        teams = {t["homeAway"]: t for t in c["competitors"]}
        home = norm_team(teams["home"]["team"]["abbreviation"])
        away = norm_team(teams["away"]["team"]["abbreviation"])
        row = {"game": f"{away}@{home}", "away": away, "home": home,
               "kickoff": ev.get("date"),
               "state": c.get("status", {}).get("type", {}).get("name"),
               "spread_home": None, "total": None, "provider": None,
               "home_score": None, "away_score": None}
        if row["state"] in ("STATUS_FINAL", "STATUS_IN_PROGRESS"):
            row["home_score"] = int(teams["home"].get("score") or 0)
            row["away_score"] = int(teams["away"].get("score") or 0)
        for o in c.get("odds", []):
            if o.get("overUnder") is None:
                continue
            # ESPN's `spread` is from the home team's view (LAR -3.5 ->
            # spread=-3.5). nflverse spread_line is the home margin, so
            # flip the sign.
            sp = o.get("spread")
            row["spread_home"] = -float(sp) if sp is not None else None
            row["total"] = float(o["overUnder"])
            row["provider"] = o.get("provider", {}).get("name")
            break
        out.append(row)
    return out


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True))
