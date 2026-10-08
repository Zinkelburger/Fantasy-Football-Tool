"""Start/sit evidence for 2-4 players competing for one lineup spot.

Pure functions, no network. The MCP tool `start_sit` (mcp_server.py)
gathers the live inputs -- ESPN league identities and projections, the
official club reports through injury_check, this week's lines -- and
hands them here. Everything below is arithmetic and fixed wording, so
the same inputs always give the same report.

The players compared, their teammates and every number in the report
come from data files or live reads. Nothing is named from memory: the
teammates are the team's top usage players in the saved play-by-play
usage, and a teammate ESPN now lists on another team is dropped.

Projection used for the comparison (shown term by term in the output):

  usage_ep_adj = usage EP (EWMA) * clip(sqrt(team implied / 22.5), 0.8, 1.2)
  blend        = mean of {ESPN projection, usage_ep_adj} (whichever exist)
  adjusted     = blend * official designation multiplier
                 (Out 0, Doubtful 0.15, Questionable 0.8; none yet 1.0)

It is the advisor.project recipe with one change: the injury multiplier
comes from the official club designation, never from ESPN's lagging tag.

Default pick rule: the highest adjusted projection among players whose
official designation is not Out or Doubtful and whose game has not
started. A gap under TOSS_UP points is reported as a toss-up. The rule
does not read news, Reddit or teammate injuries; those are listed as
facts the projection does not include.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import advisor

EASTERN = ZoneInfo("America/New_York")
DESIGNATION_MULT = {"out": 0.0, "doubtful": 0.15, "questionable": 0.8}
TOSS_UP = 1.0           # projected-point gap below which the order is a toss-up
ROLE_SHARE = 0.15       # a teammate with this target or carry share has a real role
PARTIAL_SNAPS = 0.5     # a game under this snap share is flagged as partial
INACTIVES_LEAD = timedelta(minutes=90)


def _f(v) -> float:
    try:
        return float(v) if v not in ("", None) else 0.0
    except ValueError:
        return 0.0


def team_usage(usage: list[dict], team: str, before_week: int, last: int) -> dict:
    """The team's last `last` games on file before the decision week.

    {weeks, team_targets, team_carries, players: {pid: {name, pos, weeks: {w: {tgt, rush, snap}}}}}
    Team carries are the sum of every player's rush attempts that week.
    """
    rows = [r for r in usage if r["team"] == team and int(r["week"]) < before_week]
    weeks = sorted({int(r["week"]) for r in rows})[-last:]
    totals, carries, players = {}, {}, {}
    for r in rows:
        w = int(r["week"])
        if w not in weeks:
            continue
        totals[w] = _f(r["team_targets"])
        carries[w] = carries.get(w, 0.0) + _f(r.get("rush_att"))
        p = players.setdefault(r["player_id"], {"name": r["name"], "pos": r["position"], "weeks": {}})
        p["weeks"][w] = {"tgt": _f(r.get("tgt")), "rush": _f(r.get("rush_att")),
                         "snap": _f(r.get("snap_share")) if r.get("snap_share") not in ("", None) else None}
    return {"team": team, "weeks": weeks, "team_targets": [totals.get(w, 0.0) for w in weeks],
            "team_carries": [carries.get(w, 0.0) for w in weeks], "players": players}


def player_usage(tu: dict, pid: str | None) -> dict:
    """Per-week targets/carries/snap% aligned with tu['weeks'] (None = no usage row),
    pooled target and carry shares over the same team games, and partial games."""
    p = tu["players"].get(pid) if pid else None
    by = (p or {}).get("weeks", {})
    tgt = [by[w]["tgt"] if w in by else None for w in tu["weeks"]]
    rush = [by[w]["rush"] if w in by else None for w in tu["weeks"]]
    snap = [round(by[w]["snap"] * 100) if w in by and by[w]["snap"] is not None else None
            for w in tu["weeks"]]
    team_t, team_c = sum(tu["team_targets"]), sum(tu["team_carries"])
    return {"weeks": tu["weeks"], "targets": tgt, "carries": rush, "snap_pct": snap,
            "target_share": round(sum(x or 0 for x in tgt) / team_t, 3) if team_t else None,
            "carry_share": round(sum(x or 0 for x in rush) / team_c, 3) if team_c else None,
            "no_usage_weeks": [w for w, x in zip(tu["weeks"], tgt) if x is None],
            "partial_weeks": [w for w, s in zip(tu["weeks"], snap)
                              if s is not None and s < PARTIAL_SNAPS * 100]}


def top_teammates(tu: dict, exclude: set[str], n: int) -> list[str]:
    """The team's QB (most snaps in its latest game) plus the n RB/WR/TE with
    the largest pooled target + carry share. Player ids, best first."""
    team_t, team_c = sum(tu["team_targets"]) or 1.0, sum(tu["team_carries"]) or 1.0
    latest = tu["weeks"][-1] if tu["weeks"] else None

    def role(pid):
        ws = tu["players"][pid]["weeks"].values()
        return sum(x["tgt"] for x in ws) / team_t + sum(x["rush"] for x in ws) / team_c

    skill = sorted((pid for pid, p in tu["players"].items()
                    if p["pos"] in ("RB", "WR", "TE") and pid not in exclude),
                   key=lambda pid: (-role(pid), tu["players"][pid]["name"]))[:n]
    qbs = sorted((pid for pid, p in tu["players"].items()
                  if p["pos"] == "QB" and pid not in exclude and latest in p["weeks"]),
                 key=lambda pid: -(tu["players"][pid]["weeks"][latest]["snap"] or 0))
    return qbs[:1] + skill


def projection(espn: float | None, ewma: float | None, imp_own: float | None,
               designation: str | None) -> dict:
    """Every term of the comparison number, rounded for display."""
    factor = advisor.matchup_factor(imp_own)
    ep_adj = ewma * factor if ewma is not None else None
    have = [v for v in (espn, ep_adj) if v is not None]
    blend = sum(have) / len(have) if have else None
    d = (designation or "").strip().lower()
    mult = DESIGNATION_MULT.get(d, 1.0)
    adjusted = blend * mult if blend is not None else None

    def r(v):
        return round(v, 2) if v is not None else None
    return {"espn": r(espn), "usage_ep": r(ewma), "matchup_factor": round(factor, 3),
            "usage_ep_adj": r(ep_adj), "blend": r(blend),
            "designation": d or "none yet", "designation_mult": mult, "adjusted": r(adjusted)}


def projection_text(p: dict) -> str:
    def v(x):
        return f"{x:.1f}" if x is not None else "n/a"
    return (f"ESPN {v(p['espn'])} | usage EP {v(p['usage_ep'])} x matchup {p['matchup_factor']:.2f} "
            f"= {v(p['usage_ep_adj'])} | blend {v(p['blend'])} | designation {p['designation']} "
            f"x{p['designation_mult']:g} -> {v(p['adjusted'])}")


def results(games: list[dict], team: str, before_week: int, last: int) -> list[str]:
    """'wk 3 L 7-27 @CHI' for the team's last `last` finished games."""
    out = []
    for g in games:
        if g["week"] >= before_week or team not in (g["home_team"], g["away_team"]):
            continue
        if g.get("home_score") is None or g.get("away_score") is None:
            continue
        home = g["home_team"] == team
        us, them = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
        res = "W" if us > them else "L" if us < them else "T"
        opp = g["away_team"] if home else g["home_team"]
        out.append(f"wk {g['week']} {res} {int(us)}-{int(them)} {'vs ' if home else '@'}{opp}")
    return out[-last:]


def offense_by_week(tc_rows: list[dict], team: str, weeks: list[int]) -> list[str]:
    """'wk 3 pass EPA -0.31 (p12) rush EPA -0.20 (p20) plays 52' per week.
    p = percentile among 2021-2025 team-games, higher is better."""
    out = []
    for r in sorted((r for r in tc_rows if r["team"] == team and int(r["week"]) in weeks),
                    key=lambda r: int(r["week"])):
        def m(key):
            v, pc = r.get(key), r.get(f"{key}_pctl")
            if v in ("", None):
                return "n/a"
            return f"{float(v):+.2f}" + (f" (p{int(float(pc))})" if pc not in ("", None) else "")
        out.append(f"wk {r['week']} pass EPA {m('epa_pass')}, rush EPA {m('epa_rush')}, "
                   f"plays {int(_f(r.get('plays')))}")
    return out


def kickoff_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=EASTERN)).astimezone(timezone.utc)


def et(dt: datetime | None) -> str:
    return dt.astimezone(EASTERN).strftime("%a %m/%d %H:%M ET") if dt else "unknown"


def not_in_projection(player: dict, teammates: list[dict], line: dict | None) -> list[str]:
    """Facts the comparison number does not account for, in a fixed order."""
    out = []
    st = player.get("status")
    if st in ("pending", "listed_without_designation"):
        out.append(f"{player['name']}: official designation not out yet ({player.get('final_report') or 'final report date unknown'}).")
    if st in ("unavailable", "unresolved", "identity_unverified", "schedule_unavailable"):
        out.append(f"{player['name']}: official status could not be established ({st}).")
    u = player.get("usage") or {}
    if u.get("no_usage_weeks"):
        out.append(f"{player['name']}: no usage in week(s) {', '.join(map(str, u['no_usage_weeks']))} of the sample.")
    if u.get("partial_weeks"):
        out.append(f"{player['name']}: partial game(s) under {int(PARTIAL_SNAPS * 100)}% snaps in week(s) "
                   f"{', '.join(map(str, u['partial_weeks']))}; usage EP includes them.")
    for t in teammates:
        why = teammate_flag(t)
        if why:
            out.append(f"teammate {why}.")
    if line is None:
        out.append(f"{player['name']}: no line for this game.")
    elif line.get("stale"):
        out.append(f"{player['name']}: line is from a stale source ({line.get('source')}, retrieved {line.get('retrieved_at')}).")
    return out


def teammate_flag(t: dict) -> str | None:
    """Why a teammate with a real role (>= ROLE_SHARE of targets or carries)
    is worth a look, or None. On this week's report, or missing from the
    latest game while not on the report (IR and inactive players are not
    on practice reports, so 'not listed' does not mean he played)."""
    share = max(t.get("target_share") or 0, t.get("carry_share") or 0)
    if share < ROLE_SHARE:
        return None
    head = f"{t['name']} ({t['pos']}, {share:.0%} share)"
    if t.get("status") not in ("not_listed", None):
        return f"{head}: {t.get('report') or t.get('status')}"
    if (t.get("targets") or [0])[-1] is None:
        return (f"{head}: not on this week's report but no usage in week {t['weeks'][-1]}; "
                "IR or inactive players are not listed, verify his status")
    return None


def decide(players: list[dict], now: datetime) -> dict:
    """Apply the default pick rule. players carry name, status, kickoff_utc
    (datetime or None) and projection['adjusted']."""
    excluded, eligible = [], []
    for p in players:
        ko = p.get("kickoff_utc")
        if p.get("status") in ("out", "doubtful"):
            excluded.append(f"{p['name']} (officially {p['status']})")
        elif p.get("locked") or (ko and ko <= now):
            excluded.append(f"{p['name']} (game started; lineup locked)")
        elif (p.get("projection") or {}).get("adjusted") is None:
            excluded.append(f"{p['name']} (no projection)")
        else:
            eligible.append(p)
    eligible.sort(key=lambda p: (-p["projection"]["adjusted"], p["name"]))
    if not eligible:
        return {"pick": None, "gap": None, "toss_up": False, "excluded": excluded,
                "text": "No eligible player: " + "; ".join(excluded)}
    pick = eligible[0]
    gap = round(pick["projection"]["adjusted"] - eligible[1]["projection"]["adjusted"], 2) if len(eligible) > 1 else None
    toss = gap is not None and gap < TOSS_UP
    order = " > ".join(f"{p['name']} {p['projection']['adjusted']:.1f}" for p in eligible)
    text = (f"{pick['name']}" + (f" (toss-up: gap {gap:.1f} < {TOSS_UP:g})" if toss else
                                 f" (gap {gap:.1f})" if gap is not None else "")
            + f". Order: {order}.")
    if excluded:
        text += " Excluded: " + "; ".join(excluded) + "."
    return {"pick": pick["name"], "gap": gap, "toss_up": toss, "excluded": excluded, "text": text}


def swap_window(players: list[dict], pick: str | None) -> str | None:
    """Can the pick still be benched for each alternative after his inactives?
    Inactives come about 90 minutes before kickoff; a player whose game has
    started cannot be moved into the lineup."""
    p = next((x for x in players if x["name"] == pick), None)
    if not p or not p.get("kickoff_utc"):
        return None
    inactive = p["kickoff_utc"] - INACTIVES_LEAD
    bits = []
    for alt in players:
        if alt is p or not alt.get("kickoff_utc"):
            continue
        if alt["kickoff_utc"] > inactive:
            bits.append(f"{p['name']}'s inactives ({et(inactive)}) come before {alt['name']} kicks off "
                        f"({et(alt['kickoff_utc'])}): you can still swap to {alt['name']} if {p['name']} is inactive.")
        else:
            bits.append(f"{alt['name']} kicks off ({et(alt['kickoff_utc'])}) before {p['name']}'s inactives "
                        f"({et(inactive)}): if {p['name']} is a late scratch, {alt['name']} can no longer be swapped in.")
    return " ".join(bits) or None
