"""Actual fantasy points in this league's own scoring, week by week, for
any position — including kickers and defences, which no usage file
covers. One ESPN read per week; finished weeks are cached on disk.

Answers "who are the top-scoring kickers on waivers", "what defences
have scored well", "how many points did X score each week".
"""
from __future__ import annotations

import json
import time

from common import CACHE

SLOT_FOR_POS = {"QB": 0, "RB": 2, "WR": 4, "TE": 6, "DST": 16, "K": 17}
TTL_FINAL = 12 * 3600      # stat corrections trickle in for a few days
TTL_OPEN = 10 * 60


def _cache_path(season: int, week: int, pos: str):
    d = CACHE / "espn_points"
    d.mkdir(exist_ok=True)
    return d / f"{season}_wk{week:02d}_{pos or 'ALL'}.json"


def week_points(lg, season: int, week: int, pos: str = "", final: bool = True) -> list[dict]:
    path = _cache_path(season, week, pos)
    ttl = TTL_FINAL if final else TTL_OPEN
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        return json.loads(path.read_text())
    slots = [SLOT_FOR_POS[pos]] if pos else None
    rows = [{k: p[k] for k in ("id", "name", "pos", "team", "espn_actual", "on_team_id",
                               "status", "pct_owned", "waiver")}
            for p in lg.player_points(week, slots)]
    path.write_text(json.dumps(rows))
    return rows


def _cell(v) -> str:
    return "-" if v is None else f"{v:.0f}"


def report(lg, settings: dict, season: int, weeks: list[int], pos: str = "", names: str = "",
           available_only: bool = False, top: int = 20, open_weeks: set[int] | None = None) -> str:
    pos = pos.upper()
    if pos and pos not in SLOT_FOR_POS:
        return f"position must be one of {', '.join(SLOT_FOR_POS)} (or blank with names)"
    open_weeks = open_weeks or set()
    teams = {t["id"]: t["name"] for t in settings["teams"]}
    players: dict[int, dict] = {}
    for w in weeks:
        for r in week_points(lg, season, w, pos, final=w not in open_weeks):
            p = players.setdefault(r["id"], {**r, "pts": {}})
            p.update({k: r[k] for k in ("on_team_id", "status", "pct_owned", "waiver")})
            p["pts"][w] = r["espn_actual"]
    rows = list(players.values())
    if names:
        from player_history import norm
        wanted = [norm(n) for n in names.split(",") if n.strip()]
        rows = [p for p in rows if any(w in norm(p["name"]) for w in wanted)]
    if available_only:
        rows = [p for p in rows if p["status"] != "ONTEAM"]
    for p in rows:
        vals = [v for v in p["pts"].values() if v is not None]
        p["total"], p["played"] = sum(vals), len(vals)
    rows.sort(key=lambda p: -p["total"])
    head = (f"{settings['league']} actual points in league scoring ({settings['scoring_format']}), "
            f"weeks {weeks[0]}-{weeks[-1]}" + (f", {pos}" if pos else "")
            + (", available only" if available_only else ""))
    out = [head, f"  {'player':26} {'tm':3} {'owner':22} " + " ".join(f"wk{w:<3}" for w in weeks) + " total  own%"]
    for p in rows[:top]:
        owner = (teams.get(p["on_team_id"], "?")[:22] if p["status"] == "ONTEAM"
                 else "WAIVERS" if p["waiver"] else "free agent")
        cells = " ".join(f"{_cell(p['pts'].get(w)):>5}" for w in weeks)
        out.append(f"  {p['name'][:26]:26} {p['team'] or '?':3} {owner:22} {cells} {p['total']:5.0f}  "
                   f"{p['pct_owned']:.0f}%")
    if not rows:
        out.append("  no players match")
    if open_weeks & set(weeks):
        out.append(f"  week(s) {sorted(open_weeks & set(weeks))} still in progress: '-' = not played yet")
    out.append("  '-' = no game that week (bye, inactive or not played yet). ESPN pool is the "
               "~400 most-owned players per read; deep free agents may be missing.")
    return "\n".join(out)
