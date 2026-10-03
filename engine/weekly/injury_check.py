"""One-call injury answer: next game, official reports, missed games, news, timing.

Pure helpers here; mcp_server.injury_check wires in the live readers. Every
field says where it came from and when. There is no chance-to-play model:
the output is evidence plus the next moment it can change, never odds.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
WEEKDAY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def norm(name: str) -> str:
    n = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c))
    n = re.sub(r"[.'’]", "", n.lower())
    return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())


def resolve(name: str, players: list[dict]) -> list[dict]:
    """Exact normalized name first, else substring. Caller must reject multiple hits."""
    n = norm(name)
    exact = [p for p in players if norm(p["name"]) == n]
    return exact or [p for p in players if n and n in norm(p["name"])]


def player_index(usage: list[dict], depth: list[dict], injuries: list[dict], live: list[dict]) -> list[dict]:
    """All positions, including zero-usage players; retain ambiguous identities.

    Live league roster > latest depth snapshot > saved injury > usage identity.
    These identify a player/team, not an injury status. IDs reconcile transfers;
    equally recent conflicting teams remain ambiguous instead of choosing one.
    """
    crosswalk = {str(r["espn_id"]): r["gsis_id"] for r in depth if r.get("espn_id") and r.get("gsis_id")}
    candidates = []
    for r in usage:
        candidates.append((1, int(r["week"]), {"name": r["name"], "pos": r["position"], "team": r["team"],
                           "player_id": r["player_id"], "identity_source": f"saved usage week {r['week']}"}))
    for r in injuries:
        candidates.append((2, int(r["week"]), {"name": r["full_name"], "pos": r["position"], "team": r["team"],
                           "player_id": r.get("gsis_id"), "identity_source": f"saved injury identity week {r['week']}"}))
    for r in depth:
        candidates.append((3, r.get("dt", ""), {"name": r["player_name"], "pos": r["pos_abb"], "team": r["team"],
                           "player_id": r.get("gsis_id"), "espn_id": r.get("espn_id"),
                           "identity_source": f"saved depth chart {r.get('dt') or 'date unknown'}"}))
    for r in live:
        if r["pos"] == "DST":
            continue
        candidates.append((4, "live", {"name": r["name"], "pos": r["pos"], "team": r.get("team"),
                           "player_id": crosswalk.get(str(r["id"])), "espn_id": r["id"],
                           "espn_tag": r.get("injury"), "identity_source": "live ESPN league roster/pool"}))
    # Recover a GSIS ID from a unique same-name saved identity when the roster
    # crosswalk has no entry. Never collapse different known IDs with one name.
    ids = {}
    for _, _, p in candidates:
        if p.get("player_id"):
            ids.setdefault(norm(p["name"]), set()).add(p["player_id"])
    grouped = {}
    for priority, stamp, p in candidates:
        known = ids.get(norm(p["name"]), set())
        if not p.get("player_id") and len(known) == 1:
            p["player_id"] = next(iter(known))
        key = p.get("player_id") or (("espn", str(p["espn_id"])) if p.get("espn_id")
                                    else (norm(p["name"]), p["pos"]))
        group = grouped.setdefault(key, [])
        if not group or (priority, stamp) > group[0][:2]:
            grouped[key] = [(priority, stamp, p)]
        elif (priority, stamp) == group[0][:2] and not any(x[2]["team"] == p["team"] for x in group):
            group.append((priority, stamp, p))
    return [p for group in grouped.values() for _, _, p in group]


def kickoff(raw: str | None) -> datetime | None:
    """UTC kickoff. nflverse writes naive Eastern, the ESPN overlay writes Z."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=EASTERN)).astimezone(timezone.utc)


def team_games(team: str, lines: list[dict], schedule: list[dict]) -> list[dict]:
    """Schedule determines opponents/dates even when betting lines are missing."""
    rows = {int(r["week"]): {**r, "source": "saved betting lines"} for r in lines if r["team"] == team}
    own = [g for g in schedule if team in (g["home_team"], g["away_team"])]
    if len({int(g["week"]) for g in own}) == 17:
        rows = {}  # A complete team schedule also establishes byes.
    for g in own:
        home = g["home_team"] == team
        rows[int(g["week"])] = {"week": int(g["week"]), "team": team,
            "opp": g["away_team"] if home else g["home_team"], "home": home,
            "kickoff": f"{g['gameday']}T{g['gametime']}" if g.get("gameday") and g.get("gametime") else None,
            "played": g.get("home_score") is not None and g.get("away_score") is not None,
            "source": "saved NFL schedule"}
    return list(rows.values())


def next_game(team: str, lines: list[dict], now: datetime, from_week: int,
              schedule: list[dict] | None = None, exact_week: bool = False) -> dict | None:
    """Next kickoff, or the explicitly requested game. Missing odds never prove a bye."""
    schedule = schedule or []
    rows = team_games(team, lines, schedule)
    complete = len({int(g["week"]) for g in schedule if team in (g["home_team"], g["away_team"])}) == 17
    weeks = [from_week] if exact_week else range(from_week, 19)
    byes = []
    unknown = []
    for w in weeks:
        row = next((r for r in rows if int(r["week"]) == w), None)
        if row is None:
            (byes if complete else unknown).append(w)
            continue
        ko = kickoff(row.get("kickoff"))
        if not exact_week and (str(row.get("played", "")).lower() == "true" or (ko and ko <= now)):
            continue
        return {"week": w, "opp": row["opp"], "home": str(row.get("home")).lower() == "true",
                "kickoff_utc": ko.isoformat() if ko else None, "byes_before": byes,
                "unknown_weeks_before": unknown, "source": row["source"]}
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
    hits = [r for r in rows if norm(r["player"]) == n and
            (report.get("week") is None or r.get("week") == report["week"]) and
            (report.get("team") is None or r.get("team") == report["team"])]
    if len(hits) != 1:
        return None
    hit = hits[0]
    days = [d for d in (hit.get("practice_days") or "").split(",") if d]
    return {"week": hit["week"], "position": hit.get("position"), "injury": hit.get("injury") or "",
            "practice": {d: hit.get(d) or "" for d in days},
            "designation": hit.get("game_status") or "", "source": hit.get("source"),
            "published_at": hit.get("published_at")}


def report_state(report: dict | None) -> str:
    """available / pending / unavailable / not fetched, from the report coverage."""
    if not report:
        return "not fetched"
    retrieval = report.get("retrieval") or {}
    if retrieval.get("status") in {"unavailable", "missing", "stale"}:
        return retrieval["status"]
    if not report.get("report"):
        return report.get("state") or "not fetched"
    return (report["report"].get("coverage") or {}).get("status") or "unknown"


def current_status(row: dict | None, state: str) -> str:
    """An explicit classification; never promote an ESPN tag or missing row to active."""
    if state in {"pending", "not published yet"}:
        return "pending"
    if state != "available":
        return "unavailable"
    if row is None:
        return "not_listed"
    designation = row["designation"].strip().lower()
    return designation if designation in {"out", "doubtful", "questionable"} else "listed_without_designation"


def next_step(status: str) -> str:
    """A stop/recovery instruction beside the status, not buried in a runbook."""
    return {
        "out": "Answer that the official report lists him Out for the stated week. Recheck only for a newer official update.",
        "doubtful": "Report Doubtful, not confirmed Out. Check the final club update/inactive list before kickoff.",
        "questionable": "Report Questionable, not a predicted chance of playing. Check the final report/inactive list before kickoff.",
        "pending": "Answer that this week's designation is not yet established. Wait for the next scheduled report; do not immediately retry other tools for the same missing report.",
        "not_listed": "Report that he is not listed. If returning from injury/IR, verify club activation and inactives before calling him active.",
        "listed_without_designation": "Report the recorded practice participation. Wait for the final designation; a blank status is not clearance.",
        "unavailable": "Report the source gap. Use a dated official club announcement if available; do not relabel failure as pending or healthy, or retry repeatedly.",
        "unresolved": "Supply the full player name and an NFL team abbreviation via team=; do not guess a player.",
        "ambiguous": "Choose the intended full name and NFL team from the matches, then repeat this call once.",
        "identity_unverified": "Verify the player's NFL team/full name. The supplied team has no exact official match; a pending report cannot verify identity.",
        "unknown_team": "Verify the current NFL team, then repeat injury_check with team=.",
        "schedule_unavailable": "Use schedule(team=..., weeks=...) to verify the requested game or bye. Missing data does not establish a bye.",
    }.get(status, "Report the uncertainty; do not infer availability.")


def missed(pid: str | None, team: str, usage: list[dict], injuries: list[dict], pos: str = "WR") -> dict:
    """Weeks the team played but this player had no usage, and weeks reported Out."""
    team_weeks = sorted({int(r["week"]) for r in usage if r["team"] == team})
    own = {int(r["week"]) for r in usage if pid and r["player_id"] == pid and r["team"] == team}
    out = sorted({int(r["week"]) for r in injuries
                  if pid and r.get("gsis_id") == pid and r.get("team", team) == team
                  and (r.get("report_status") or "").lower() == "out"})
    return {"team_weeks_on_file": team_weeks,
            "no_usage_weeks": [w for w in team_weeks if w not in own] if pid and pos in {"QB", "RB", "WR", "TE", "FB"} else [],
            "reported_out_weeks": out}


def summary(name: str, pos: str, team: str, game: dict | None, cur: dict | None,
            cur_state: str, prev: dict | None, gone: dict, espn: str | None,
            times: dict | None, news: list[dict] | None = None, requested_week: bool = False) -> str:
    """Plain facts in a fixed order. No odds, no verdict beyond the designation."""
    parts = [f"{name} ({pos} {team})."]
    history = []
    if gone["no_usage_weeks"]:
        history.append(f"No usage in week(s) {', '.join(map(str, gone['no_usage_weeks']))}"
                     + (f" (reported Out: {', '.join(map(str, gone['reported_out_weeks']))})"
                        if gone["reported_out_weeks"] else "") + ".")
    if prev:
        prac = " ".join(f"{d.title()} {v or '-'}" for d, v in prev["practice"].items())
        history.append(f"Week {prev['week']} report: {prev['injury'] or 'injury n/a'}; {prac}; "
                     f"designation {prev['designation'] or 'none'}.")
    if game:
        where = ("vs " if game["home"] else "@") + game["opp"]
        parts.append(f"{'Requested game' if requested_week else 'Next game'}: week {game['week']} {where}, {times['kickoff_et'] if times else 'kickoff unknown'}.")
        if cur:
            prac = " ".join(f"{d.title()} {v or '-'}" for d, v in cur["practice"].items())
            parts.append(f"Week {game['week']} report so far: {cur['injury'] or 'injury n/a'}; {prac}; "
                         f"designation {cur['designation'] or 'not yet'}.")
        elif cur_state == "available":
            parts.append(f"Week {game['week']} report is out and does not list him "
                         "(not listed is not clearance for a player coming off an absence).")
        elif times and cur_state in {"pending", "not published yet", "not published"}:
            parts.append(f"Week {game['week']} report not out yet ({cur_state}); "
                         f"first report {times['first_practice_report']}.")
        else:
            parts.append(f"Week {game['week']} official report could not be verified ({cur_state}); status unknown.")
        if times:
            parts.append(f"Designation comes on the final report {times['final_report_with_designation']}; "
                         f"inactives about {times['inactives_about']}.")
    else:
        parts.append("No matching game found in saved schedule/lines; verify schedule or bye. Missing data does not establish a bye or health.")
    parts.extend(history)
    if espn:
        parts.append(f"ESPN tag: {espn} (lags club reports).")
    if news:
        top = news[0]
        text = " ".join(top["text"].split())[:160]
        parts.append(f"Newest news ({top['at'][:16].replace('T', ' ')} UTC, {top['by']}, "
                     f"unverified wire): {text}")
    else:
        parts.append("No matching news in the sampled feeds (not evidence of health; check coverage).")
    return " ".join(parts)
