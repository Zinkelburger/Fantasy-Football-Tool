"""One-call injury answer: next game, official reports, missed games, news, timing.

Pure helpers here; mcp_server.injury_check wires in the live readers. Every
field says where it came from and when. There is no chance-to-play model:
the output is evidence plus the next moment it can change, never odds.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
WEEKDAY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def norm(name: str) -> str:
    n = re.sub(r"[.'’]", "", (name or "").lower())
    return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())


def resolve(name: str, players: list[dict]) -> list[dict]:
    """Opportunity rows matching a name: exact normalised match first, else substring."""
    n = norm(name)
    exact = [p for p in players if norm(p["name"]) == n]
    return exact or [p for p in players if n and n in norm(p["name"])]


def kickoff(raw: str | None) -> datetime | None:
    """UTC kickoff. nflverse writes naive Eastern, the ESPN overlay writes Z."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=EASTERN)).astimezone(timezone.utc)


def next_game(team: str, lines: list[dict], now: datetime, from_week: int) -> dict | None:
    """The team's first game from `from_week` on that has not kicked off.
    Weeks with no line for the team are listed as byes on the way."""
    weeks = sorted({int(r["week"]) for r in lines if int(r["week"]) >= from_week})
    byes = []
    for w in weeks:
        row = next((r for r in lines if int(r["week"]) == w and r["team"] == team), None)
        if row is None:
            byes.append(w)
            continue
        ko = kickoff(row.get("kickoff"))
        if str(row.get("played", "")).lower() == "true" or (ko and ko <= now):
            continue
        return {"week": w, "opp": row["opp"], "home": str(row.get("home")).lower() == "true",
                "kickoff_utc": ko.isoformat() if ko else None, "byes_before": byes}
    return None


def timeline(kickoff_utc: datetime) -> dict:
    """When official information for this game appears (Eastern dates).

    Sunday games report Wed/Thu/Fri, Thursday games Mon/Tue/Wed, Monday
    games Thu/Fri/Sat, Saturday games Wed/Thu/Fri; the last report carries the game designation and
    inactives are announced about 90 minutes before kickoff.
    """
    local = kickoff_utc.astimezone(EASTERN)
    game_day = local.date()
    lead = 3 if game_day.weekday() in (3, 5) else 4
    first = game_day - timedelta(days=lead)
    final = first + timedelta(days=2)
    inactives = local - timedelta(minutes=90)
    return {"kickoff_et": local.strftime("%a %b %d %H:%M ET"),
            "first_practice_report": f"{WEEKDAY[first.weekday()].title()} {first.isoformat()}",
            "final_report_with_designation": f"{WEEKDAY[final.weekday()].title()} {final.isoformat()}",
            "inactives_about": inactives.strftime("%a %b %d %H:%M ET")}


def report_row(report: dict | None, name: str) -> dict | None:
    """This player's row in a practice_report payload, if listed."""
    rows = ((report or {}).get("report") or {}).get("rows") or []
    n = norm(name)
    hit = next((r for r in rows if norm(r["player"]) == n), None) or \
        next((r for r in rows if n in norm(r["player"])), None)
    if not hit:
        return None
    days = [d for d in (hit.get("practice_days") or "").split(",") if d]
    return {"week": hit["week"], "injury": hit.get("injury") or "",
            "practice": {d: hit.get(d) or "" for d in days},
            "designation": hit.get("game_status") or "", "source": hit.get("source")}


def report_state(report: dict | None) -> str:
    """available / pending / unavailable / not fetched, from the report coverage."""
    if not report or not report.get("report"):
        return "not fetched"
    return (report["report"].get("coverage") or {}).get("status") or "unknown"


def missed(pid: str, team: str, usage: list[dict], injuries: list[dict]) -> dict:
    """Weeks the team played but this player had no usage, and weeks reported Out."""
    team_weeks = sorted({int(r["week"]) for r in usage if r["team"] == team})
    own = {int(r["week"]) for r in usage if r["player_id"] == pid}
    out = sorted({int(r["week"]) for r in injuries
                  if r.get("gsis_id") == pid and (r.get("report_status") or "").lower() == "out"})
    return {"team_weeks_on_file": team_weeks,
            "no_usage_weeks": [w for w in team_weeks if w not in own],
            "reported_out_weeks": out}


def summary(name: str, pos: str, team: str, game: dict | None, cur: dict | None,
            cur_state: str, prev: dict | None, gone: dict, espn: str | None,
            times: dict | None, news: list[dict] | None = None) -> str:
    """Plain facts in a fixed order. No odds, no verdict beyond the designation."""
    parts = [f"{name} ({pos} {team})."]
    if gone["no_usage_weeks"]:
        parts.append(f"No usage in week(s) {', '.join(map(str, gone['no_usage_weeks']))}"
                     + (f" (reported Out: {', '.join(map(str, gone['reported_out_weeks']))})"
                        if gone["reported_out_weeks"] else "") + ".")
    if prev:
        prac = " ".join(f"{d.title()} {v or '-'}" for d, v in prev["practice"].items())
        parts.append(f"Week {prev['week']} report: {prev['injury'] or 'injury n/a'}; {prac}; "
                     f"designation {prev['designation'] or 'none'}.")
    if game:
        where = ("vs " if game["home"] else "@") + game["opp"]
        parts.append(f"Next game: week {game['week']} {where}, {times['kickoff_et'] if times else 'kickoff unknown'}.")
        if cur:
            prac = " ".join(f"{d.title()} {v or '-'}" for d, v in cur["practice"].items())
            parts.append(f"Week {game['week']} report so far: {cur['injury'] or 'injury n/a'}; {prac}; "
                         f"designation {cur['designation'] or 'not yet'}.")
        elif cur_state == "available":
            parts.append(f"Week {game['week']} report is out and does not list him "
                         "(not listed is not clearance for a player coming off an absence).")
        elif times:
            parts.append(f"Week {game['week']} report not out yet ({cur_state}); "
                         f"first report {times['first_practice_report']}.")
        if times:
            parts.append(f"Designation comes on the final report {times['final_report_with_designation']}; "
                         f"inactives about {times['inactives_about']}.")
    else:
        parts.append("No remaining game found in the saved schedule.")
    if espn:
        parts.append(f"ESPN tag: {espn} (lags club reports).")
    if news:
        top = news[0]
        text = " ".join(top["text"].split())[:160]
        parts.append(f"Newest news ({top['at'][:16].replace('T', ' ')} UTC, {top['by']}, "
                     f"unverified wire): {text}")
    else:
        parts.append("No news posts in the last 72h (not evidence of health).")
    return " ".join(parts)
