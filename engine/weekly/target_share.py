"""Team target share by week, with absences and vacated share. No network.

Reads saved weekly files only:
  data/weekly/advanced_usage_<season>_weekly.csv  targets per player-game from
      nflverse play-by-play; team_targets counts every identified receiver.
  data/weekly/injuries_<season>.csv                nflverse weekly injury reports.

A player has a usage row only in a game where he had a carry, target or pass,
so a missing row means "no usage", not a confirmed inactive. The injury report
supplies the designation. Neither is current status: use practice_report.

The legacy vacated_share field sums shares from different active-week samples.
It is diagnostic only: neither confirmed missing opportunity nor an additive
team share. Text views show individual flags instead. For decision-week
opportunity, use receiving_opportunity with common team-game denominators.
"""
from __future__ import annotations

import csv
from pathlib import Path

FLAG_STATUSES = {"out", "doubtful"}
# A missing usage row flags only a player who had a real role; a WR5 with one
# target in week 1 is not a vacancy when he goes unused in week 3.
FLAG_MIN_SHARE = 0.10


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def build(usage: list[dict], injuries: list[dict], team: str = "", last: int = 0,
          min_share: float = 0.0) -> dict:
    """{team: {...}} over the selected usage weeks (last=0: all weeks on file).

    min_share hides players below that share in every view (all weeks, when
    active); team totals and flags still count them.
    """
    all_weeks = sorted({int(r["week"]) for r in usage})
    weeks = all_weeks[-last:] if last > 0 else all_weeks
    rows = [r for r in usage if int(r["week"]) in weeks and (not team or r["team"] == team)]
    report_weeks = sorted({int(r["week"]) for r in injuries})
    report_week = report_weeks[-1] if report_weeks else None
    inj = {}
    for r in injuries:
        inj.setdefault(r["gsis_id"], {})[int(r["week"])] = r

    teams: dict[str, dict] = {}
    for r in rows:
        t = teams.setdefault(r["team"], {"team_targets": {}, "players": {}})
        w = int(r["week"])
        t["team_targets"][w] = _f(r["team_targets"])
        p = t["players"].setdefault(r["player_id"], {
            "name": r["name"], "pos": r["position"], "targets": {}, "snap_pct": {}})
        p["targets"][w] = _f(r["tgt"])
        if r.get("snap_share") not in ("", None):
            p["snap_pct"][w] = round(_f(r["snap_share"]), 2)

    out = {}
    for code, t in sorted(teams.items()):
        tw = sorted(t["team_targets"])
        team_total = sum(t["team_targets"].values())
        latest = tw[-1]
        players, vacated = [], []
        for pid, p in t["players"].items():
            tgt = sum(p["targets"].values())
            if not tgt:
                continue
            used = sorted(p["targets"])
            active_total = sum(t["team_targets"][w] for w in used)
            share_active = tgt / active_total if active_total else 0.0
            reports = inj.get(pid, {})
            out_weeks = [w for w in tw if (reports.get(w, {}).get("report_status") or "").lower() == "out"]
            latest_report = reports.get(report_week) if report_week else None
            status = (latest_report or {}).get("report_status") or ""
            row = {
                "name": p["name"], "pos": p["pos"],
                "targets": {str(w): p["targets"].get(w) for w in tw},
                "share": {str(w): (round(p["targets"][w] / t["team_targets"][w], 3)
                                   if w in p["targets"] and t["team_targets"][w] else None)
                          for w in tw},
                "snap_pct": {str(w): p["snap_pct"].get(w) for w in tw},
                "total_targets": tgt,
                "share_all_weeks": round(tgt / team_total, 3) if team_total else 0.0,
                "share_when_active": round(share_active, 3),
                "no_usage_weeks": [w for w in tw if w not in p["targets"]],
                "reported_out_weeks": out_weeks,
                "latest_report": ({"week": report_week, "status": status,
                                   "injury": latest_report.get("report_primary_injury") or "",
                                   "practice": latest_report.get("practice_status") or ""}
                                  if latest_report else None),
            }
            if not row["latest_report"]:
                del row["latest_report"]
            for key in ("no_usage_weeks", "reported_out_weeks"):
                if not row[key]:
                    del row[key]
            if max(row["share_all_weeks"], row["share_when_active"]) >= min_share:
                players.append(row)
            reasons = []
            if latest not in p["targets"] and share_active >= FLAG_MIN_SHARE:
                reasons.append(f"no usage in week {latest}"
                               + (" (reported Out)" if latest in out_weeks else ""))
            if status.lower() in FLAG_STATUSES:
                reasons.append(f"{status} on week {report_week} report")
            if reasons:
                vacated.append({"name": p["name"], "pos": p["pos"],
                                "share_when_active": row["share_when_active"],
                                "reasons": reasons})
        players.sort(key=lambda r: -r["total_targets"])
        vacated.sort(key=lambda r: -r["share_when_active"])
        out[code] = {
            "weeks": tw,
            "team_targets": {str(w): t["team_targets"][w] for w in tw},
            "players": players,
            "flagged": vacated,
            "vacated_share": round(sum(v["share_when_active"] for v in vacated), 3),
        }
    return {"weeks_requested": weeks, "injury_report_week": report_week, "teams": out,
            "interpretation": "Historical flags, not confirmed current absences. Legacy vacated_share sums different active-week samples; do not treat it as an additive team share or forecast. Use receiving_opportunity for decision-week evidence."}


def load(data: Path, season: int, team: str = "", last: int = 0,
         min_share: float = 0.0) -> dict:
    usage = _read(data / f"advanced_usage_{season}_weekly.csv")
    injuries = _read(data / f"injuries_{season}.csv")
    result = build(usage, injuries, team, last, min_share)
    result["season"] = season
    return result


# ------------------------------------------------------------ text views
# Text is for the agent's context: a whole-league JSON dump ran past 50k
# characters, so the league view is one line per team and detail is
# requested per team or per player. SQL over the same numbers lives in
# datastore.py (tables `targets` and `vacated`).

def _pct(v) -> str:
    return "-" if v is None else f"{v:.2f}".lstrip("0") if v < 1 else "1.0"


def _series(d: dict, weeks: list[int], fmt) -> str:
    return "/".join(fmt(d.get(str(w))) for w in weeks)


def _count(v) -> str:
    return "-" if v is None else f"{v:.0f}"


def _flag_text(f: dict) -> str:
    return f"{f['name']} {f['pos']} {_pct(f['share_when_active'])} ({'; '.join(f['reasons'])})"


def player_line(p: dict, weeks: list[int], flags: dict | None = None) -> str:
    rep = p.get("latest_report") or {}
    bits = [f"  {p['name'][:24]:24} {p['pos']:2}",
            f"tgt {_series(p['targets'], weeks, _count)}",
            f"share {_series(p['share'], weeks, _pct)}",
            f"snap {_series(p['snap_pct'], weeks, _pct)}",
            f"all {_pct(p['share_all_weeks'])} active {_pct(p['share_when_active'])}"]
    if rep.get("status") or rep.get("practice"):
        bits.append(f"wk{rep['week']} report: {rep.get('status') or 'no designation'}"
                    + (f" {rep['injury']}" if rep.get("injury") else ""))
    reasons = (flags or {}).get(p["name"])
    if reasons:
        bits.append("FLAG: " + "; ".join(reasons))
    return "  ".join(bits)


def team_text(code: str, t: dict, position: str = "", report_week=None) -> str:
    weeks = t["weeks"]
    flags = {f["name"]: f["reasons"] for f in t["flagged"]}
    players = [p for p in t["players"] if not position or p["pos"] == position]
    out = [f"{code} target share, weeks {'/'.join(map(str, weeks))} "
           f"(team targets {_series(t['team_targets'], weeks, _count)}); "
           f"latest injury report week {report_week or 'none'}"]
    out += [player_line(p, weeks, flags) for p in players]
    if t["flagged"]:
        out.append("  historical absence flags (not confirmed vacancies): "
                   + ", ".join(_flag_text(f) for f in t["flagged"]))
    out.append("For injury-related pickups: receiving_opportunity(team, week, season, concern). Saved reports and missing usage do not establish current absence.")
    return "\n".join(out)


def league_text(result: dict, position: str = "", flagged_only: bool = False, top: int = 3) -> str:
    out = [f"{result['season']} target share by team, weeks {result['weeks_requested']}; "
           f"injury report week {result['injury_report_week']}. "
           f"Top {top} by targets (share when active), then flags."]
    for code, t in result["teams"].items():
        flagged = [f for f in t["flagged"] if not position or f["pos"] == position]
        if flagged_only and not flagged:
            continue
        players = [p for p in t["players"] if not position or p["pos"] == position][:top]
        line = (f"  {code:3} " + ", ".join(f"{p['name']} {p['pos']} {_pct(p['share_when_active'])}"
                                           for p in players))
        if flagged:
            line += (" | historical flags: "
                     + ", ".join(_flag_text(f) for f in flagged))
        out.append(line)
    if len(out) == 1:
        out.append("  no team matches" + (" (no flagged players)" if flagged_only else ""))
    out.append("Detail: target_share(team=...) or target_share(player=...); "
               "ad-hoc questions: query_data on tables targets / vacated.")
    out.append("Flags are historical, not confirmed vacancies. Midgame injuries can be missed; use injury_check then receiving_opportunity for pickups.")
    return "\n".join(out)


def players_text(result: dict, names: list[str], norm) -> str:
    wanted = {norm(n): n for n in names}
    out, found = [], set()
    for code, t in result["teams"].items():
        flags = {f["name"]: f["reasons"] for f in t["flagged"]}
        for p in t["players"]:
            key = norm(p["name"])
            hit = next((k for k in wanted if k == key or k in key), None)
            if hit:
                found.add(hit)
                out.append(f"{code} (team targets {_series(t['team_targets'], t['weeks'], _count)}, "
                           f"weeks {'/'.join(map(str, t['weeks']))})")
                out.append(player_line(p, t["weeks"], flags))
    out += [f"{wanted[k]}: no target on file this season" for k in wanted if k not in found]
    return "\n".join(out)
