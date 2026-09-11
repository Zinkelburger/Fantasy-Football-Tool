"""ff-weekly: MCP tools for the in-season week.

Every tool is deterministic over files the fetchers wrote (data/weekly/)
plus, for the league tools, a live read of the ESPN league. The agent
reads these next to Reddit/news context and decides; the only tools
that change anything are execute_transaction and apply_lineup, and both
refuse to run without a proposal token the agent previewed AND
confirmed=True, which the agent may only pass after the user said yes.

Registered in .mcp.json as "ff-weekly". Run by hand:
    .venv-league-sim/bin/python engine/weekly/mcp_server.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from common import CACHE, DATA, ESPN_SLOTS, SKILL, TEAMS, load_env, nfl_state, now_iso, week_key
import advisor

mcp = MCPServer("ff-weekly", version="1.0.0")
PROPOSALS = CACHE / "proposals.json"
PROPOSAL_TTL = 24 * 3600


# ------------------------------------------------------------ helpers
def _latest() -> dict:
    p = DATA / "latest.json"
    if not p.exists():
        raise RuntimeError("data/weekly/latest.json missing: run refresh_week first")
    return json.loads(p.read_text())


def _state() -> tuple[int, int]:
    st = nfl_state()
    return st["season"], st["week"]


def _week(week: int) -> tuple[int, int]:
    season, cur = _state()
    return season, (week or cur)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _num(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return v


def _opportunity(season: int) -> dict[str, dict]:
    rows = {}
    for r in _read_csv(DATA / f"opportunity_{season}.csv"):
        rows[r["player_id"]] = {k: (_num(v) if k not in ("player_id", "name", "pos", "team") else v)
                                for k, v in r.items()}
    return rows


def _crosswalk() -> dict[str, str]:
    """espn_id -> gsis_id (nflverse players table, cached parquet)."""
    p = CACHE / "players.parquet"
    if not p.exists():
        import nfl_data
        nfl_data.players()
    import polars as pl
    df = pl.read_parquet(p).filter(pl.col("espn_id").is_not_null())
    return dict(zip(df["espn_id"].cast(pl.Utf8).to_list(), df["gsis_id"].to_list()))


def _norm_name(n: str) -> str:
    n = re.sub(r"[.'’]", "", (n or "").lower())
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())
    return n


def _lines_week(season: int, week: int) -> dict[str, dict]:
    out = {}
    for r in _read_csv(DATA / f"lines_{season}.csv"):
        if int(r["week"]) == week:
            out[r["team"]] = {k: (_num(v) if k in ("imp_own", "imp_opp", "spread", "total") else
                                  (v == "true") if k in ("home", "dome", "played") else v)
                              for k, v in r.items()}
    return out


def _byes(season: int, week: int) -> set[str]:
    import polars as pl
    p = CACHE / f"schedules_{season}.parquet"
    if not p.exists():
        return set()
    s = pl.read_parquet(p).filter(pl.col("week") == week)
    playing = set(s["home_team"].to_list()) | set(s["away_team"].to_list())
    return set(TEAMS) - playing


def _bye_map(season: int, week: int, horizon: int = 2) -> dict[str, int]:
    out = {}
    for w in range(week + 1, week + 1 + horizon):
        for t in _byes(season, w):
            out.setdefault(t, w)
    return out


def _league(season: int):
    import espn_league
    return espn_league.League(season)


def _projected_roster(season: int, week: int):
    """(settings, roster rows with projections, free agents with projections)."""
    lg = _league(season)
    s = lg.settings()
    fmt = s["scoring_format"]
    opp = _opportunity(season)
    xw = _crosswalk()
    by_name = {(_norm_name(r["name"]), r["pos"]): r for r in opp.values()}
    lines = _lines_week(season, week)
    byes = _byes(season, week)
    ecr = {(_norm_name(r["name"]), r["pos"]): r.get("rank_ecr") for r in _read_csv(DATA / f"ecr_{week_key(season, week)}.csv")}

    def attach(p):
        gsis = xw.get(str(p["id"]))
        row = opp.get(gsis) if gsis else None
        if row is None:
            row = by_name.get((_norm_name(p["name"]), p["pos"]))
        return advisor.project(p, row, lines.get(p["team"]), fmt,
                               on_bye=p["team"] in byes,
                               ecr=ecr.get((_norm_name(p["name"]), p["pos"])))

    roster = [attach(p) for p in lg.my_roster(week)]
    fas = [attach(p) for p in lg.free_agents(week) if p.get("team")]   # unsigned players are not pickups
    return lg, s, roster, fas


def _fmt_player(p: dict, with_sources: bool = True) -> str:
    m = p.get("matchup") or {}
    opp = f"{'' if m.get('home') else '@'}{m.get('opp')} (imp {m.get('imp_own')})" if m else "no game"
    src = p.get("sources", {})
    bits = [f"{p['name']:24} {p['pos']:3} {p.get('team') or '?':4} {p.get('slot_name') or '':6}",
            f"proj {p['proj']:5.1f}", f"value {p.get('value') if p.get('value') is not None else '-':>5}",
            opp]
    if with_sources:
        bits.append(f"espn {src.get('espn_proj')} | ewmaEP {src.get('ewma_ep')} | lastEP/pts "
                    f"{src.get('last_ep')}/{src.get('last_pts')}")
        if src.get("ecr"):
            bits.append(f"ECR {src['ecr']}")
    if p.get("flags"):
        bits.append("[" + ", ".join(p["flags"]) + "]")
    return "  ".join(str(b) for b in bits)


def _save_proposal(kind: str, payload: dict, week: int) -> str:
    props = json.loads(PROPOSALS.read_text()) if PROPOSALS.exists() else {}
    now = time.time()
    props = {k: v for k, v in props.items() if now - v["ts"] < PROPOSAL_TTL}
    token = hashlib.sha1(json.dumps({"k": kind, "p": payload, "w": week}, sort_keys=True).encode()).hexdigest()[:10]
    props[token] = {"kind": kind, "payload": payload, "week": week, "ts": now}
    PROPOSALS.write_text(json.dumps(props, indent=1))
    return token


def _load_proposal(token: str) -> dict:
    props = json.loads(PROPOSALS.read_text()) if PROPOSALS.exists() else {}
    p = props.get(token)
    if not p:
        raise RuntimeError("unknown or expired proposal token; preview it again")
    if time.time() - p["ts"] > PROPOSAL_TTL:
        raise RuntimeError("proposal expired; preview it again")
    return p


# ------------------------------------------------------------ tools: status
@mcp.tool()
def weekly_checklist() -> str:
    """The order of operations for a weekly pass. Read this first."""
    return """WEEKLY PASS (every tool here is deterministic; you supply the judgment)

Tuesday / Wednesday (waivers):
  1. week_status()               is the data fresh? which week? creds present?
  2. refresh_week()              if latest.json is older than the last games
  3. my_roster()                 injuries, byes, who under-performed usage
  4. waiver_recommendations()    positional needs + add/drop proposals
  5. For each proposal you like: search_reddit(player) / player_news(player)
     from the ff-reddit server, injury_report(team=...), player_lookup(name).
  6. propose_transaction(add_id, drop_id)  ->  returns a token and the exact
     question to ask. ASK THE USER. Only if they say yes:
  7. execute_transaction(token, confirmed=True)

Thursday / Saturday / Sunday morning (lineup):
  1. refresh_week()              lines move; injuries get designations Friday
  2. lineup_recommendation()     optimal lineup, the moves, and why
  3. For close calls (proj within ~2 pts) read Reddit start/sit threads and
     the injury report; the model does not know about a late scratch.
  4. apply_lineup(token, confirmed=True) after the user approves the moves.

Rules of thumb the numbers already encode (don't double count):
  - usage (ewma_ep) beats last week's points for predicting next week
  - a bad Vegas total is a mild penalty, never a benching by itself
  - QUESTIONABLE is x0.8, DOUBTFUL x0.15, OUT 0; check for late news
  - D/ST: play the defence facing the lowest implied total (dst_rankings)
  - K: highest own implied total, +0.7 in a dome (kicker_rankings)"""


@mcp.tool()
def week_status() -> str:
    """Current NFL season/week, when the data was last built, and which
    optional feeds/credentials are configured."""
    season, week = _state()
    env = load_env()
    out = [f"NFL season {season}, week {week} (Sleeper state)"]
    p = DATA / "latest.json"
    if p.exists():
        d = json.loads(p.read_text())
        out.append(f"data/weekly/latest.json: {d['label']} built {d['generated']} "
                   f"({d.get('games_played_this_week', 0)} games already played, "
                   f"{len(d['skill'])} skill rows, ECR {'yes' if d.get('ecr_available') else 'no'})")
        if d["week"] != week:
            out.append("  -> stale week: run refresh_week()")
    else:
        out.append("data/weekly/latest.json missing -> run refresh_week()")
    out.append(f"ESPN league: {'configured' if env.get('ESPN_LEAGUE_ID') else 'ESPN_LEAGUE_ID missing'}; "
               f"cookies: {'present' if env.get('ESPN_S2') and env.get('ESPN_SWID') else 'MISSING (private league reads and all writes need ESPN_S2 + ESPN_SWID in engine/weekly/.env)'}")
    out.append(f"FantasyPros key: {'present' if env.get('FANTASYPROS_API_KEY') else 'absent (ECR skipped)'}")
    return "\n".join(out)


@mcp.tool()
def refresh_week(week: int = 0) -> str:
    """Re-fetch lines, stats, injuries, depth charts (and ECR if keyed) and
    rebuild data/weekly/latest.json for the given week (0 = current)."""
    import build_week
    season, week = _week(week)
    d = build_week.build(season, week, refresh=True)
    return (f"rebuilt {d['label']} at {d['generated']}: {len(d['skill'])} skill rows, "
            f"{len(d['lines'])} team lines, {len(d['injuries'])} injury rows")


# ------------------------------------------------------------ tools: public data
@mcp.tool()
def vegas_lines(week: int = 0) -> str:
    """Every game's spread, total and implied team totals for the week."""
    season, week = _week(week)
    rows = _lines_week(season, week)
    if not rows:
        return f"no lines on file for {season} week {week}; refresh_week()"
    seen, out = set(), [f"{season} week {week} lines (home margin = spread; implied = expected points)"]
    for t, r in sorted(rows.items(), key=lambda kv: kv[1]["kickoff"] or ""):
        key = tuple(sorted((t, r["opp"])))
        if key in seen:
            continue
        seen.add(key)
        home, away = (t, r["opp"]) if r["home"] else (r["opp"], t)
        h, a = rows[home], rows[away]
        out.append(f"  {away}@{home:4} total {h['total']:5} | {home} {h['imp_own']:5} vs {away} {a['imp_own']:5} "
                   f"| {'dome' if h['dome'] else 'outdoors':8} {h['kickoff']} {h['provider']}"
                   f"{'  (played)' if h['played'] else ''}")
    byes = _byes(season, week)
    if byes:
        out.append("  bye: " + ", ".join(sorted(byes)))
    return "\n".join(out)


@mcp.tool()
def opportunity_scores(position: str = "RB", top: int = 30, scoring: str = "") -> str:
    """Opportunity scores (expected points from usage) for a position,
    ranked by the leak-free EWMA. scoring: std|half|ppr (default: the
    league's format if configured, else std)."""
    d = _latest()
    pos = position.upper()
    fmt = scoring or "std"
    rows = [r for r in d["skill"] if r["pos"] == pos]
    rows.sort(key=lambda r: -r["ewma"][fmt])
    out = [f"{d['label']} opportunity scores, {pos}, {fmt} scoring, sorted by EWMA expected points",
           f"{'#':>3} {'player':24} {'tm':4} {'opp':5} {'imp':>5} {'g':>2} {'ewma':>5} {'EP/g':>5} {'pts/g':>5} "
           f"{'lastEP':>6} {'lastPts':>7} {'car':>4} {'tgt':>4} {'rz':>3} {'ez':>3} injury"]
    for i, r in enumerate(rows[:top], 1):
        u = r["usage"]
        inj = r.get("injury") or {}
        opp = f"{'' if r.get('home') else '@'}{r['opp']}" if r.get("opp") else "bye?"
        out.append(f"{i:>3} {r['name'][:24]:24} {r['team'] or '?':4} {opp:5} {r['imp_own'] or '-':>5} {r['games']:>2} "
                   f"{r['ewma'][fmt]:5.1f} {r['ep'][fmt] if r['ep'][fmt] is not None else '-':>5} "
                   f"{r['pts'][fmt] if r['pts'][fmt] is not None else '-':>5} "
                   f"{r['last']['ep'][fmt] if r['last']['ep'][fmt] is not None else '-':>6} "
                   f"{r['last']['pts'][fmt] if r['last']['pts'][fmt] is not None else '-':>7} "
                   f"{u['rush_att'] if u['rush_att'] is not None else '-':>4} {u['tgt'] if u['tgt'] is not None else '-':>4} "
                   f"{(u['rush_rz'] or 0) + (u['tgt_rz'] or 0) if r['games'] else '-':>3} "
                   f"{u['tgt_ez'] if u['tgt_ez'] is not None else '-':>3} "
                   f"{(inj.get('status') or inj.get('practice') or '')[:28]}")
    out.append("ewma = expected points from usage going forward; EP/g vs pts/g gap = ran hot (+) or cold (-)")
    return "\n".join(out)


@mcp.tool()
def player_lookup(name: str) -> str:
    """Everything on file for one player: opportunity row, usage, this
    week's line, injury report, depth-chart slot."""
    season, week = _state()
    n = _norm_name(name)
    opp = [r for r in _opportunity(season).values() if n in _norm_name(r["name"])]
    if not opp:
        return f"no opportunity row matches {name!r} (top-of-depth-chart skill players only)"
    out = []
    lines = _lines_week(season, week)
    inj = {r["gsis_id"]: r for r in _read_csv(DATA / f"injuries_{season}.csv") if int(r["week"]) == week}
    depth = {r["gsis_id"]: r for r in _read_csv(DATA / f"depth_{season}.csv")}
    for r in opp[:3]:
        out.append(f"{r['name']} {r['pos']} {r['team']} — games {int(r['games'] or 0)}, "
                   f"EWMA EP std/half/ppr {r['ewma_ep_std']:.1f}/{r['ewma_ep_half']:.1f}/{r['ewma_ep_ppr']:.1f}")
        if r.get("games"):
            out.append(f"  season: EP/g {r['ep_std']:.1f} pts/g {r['pts_std']:.1f} gap {r['gap_std']:+.1f} (std); "
                       f"last wk{int(r['last_week'])}: EP {r['last_ep_std']:.1f} pts {r['last_pts_std']:.1f}")
            out.append(f"  usage/g: carries {r['rush_att_pg']:.1f} (rz {r['rush_rz_pg']:.1f}), targets {r['tgt_pg']:.1f} "
                       f"(rz {r['tgt_rz_pg']:.1f}, ez {r['tgt_ez_pg']:.1f}), air yds {r['air_yds_pg']:.0f}")
        ln = lines.get(r["team"])
        if ln:
            out.append(f"  week {week}: {'' if ln['home'] else '@'}{ln['opp']}, implied {ln['imp_own']} vs {ln['imp_opp']}, "
                       f"total {ln['total']}, {'dome' if ln['dome'] else 'outdoors'}, {ln['kickoff']}")
        else:
            out.append(f"  week {week}: no line (bye or not posted)")
        ij = inj.get(r["player_id"])
        if ij:
            out.append(f"  injury: {ij['report_status'] or '-'} {ij['report_primary_injury'] or ''}; "
                       f"practice {ij['practice_status'] or '-'} {ij['practice_primary_injury'] or ''}")
        dc = depth.get(r["player_id"])
        if dc:
            out.append(f"  depth chart ({dc['dt'][:10]}): {dc['team']} {dc['pos_abb']}{dc['pos_rank']}")
    return "\n".join(out)


@mcp.tool()
def injury_report(team: str = "", position: str = "") -> str:
    """This week's official injury report (NFL practice + game status)
    for skill positions, filtered by team and/or position."""
    d = _latest()
    rows = d["injuries"]
    if team:
        rows = [r for r in rows if r["team"] == team.upper()]
    if position:
        rows = [r for r in rows if r["pos"] == position.upper()]
    if not rows:
        return "no injury rows match (reports post Wed-Fri; refresh_week() Friday evening)"
    out = [f"{d['label']} injury report ({len(rows)} rows)"]
    for r in sorted(rows, key=lambda r: (r["team"], r["pos"], r["name"])):
        out.append(f"  {r['team']:4} {r['pos']:3} {r['name']:24} {r['status'] or '-':12} "
                   f"{r['injury'] or '':16} {r['practice'] or ''}")
    return "\n".join(out)


@mcp.tool()
def dst_rankings() -> str:
    """Defences ranked by opponent implied total (lowest first)."""
    d = _latest()
    out = [f"{d['label']} D/ST — opponent implied total, ascending (top 3 = stream)"]
    for i, r in enumerate(d["dst"], 1):
        out.append(f"  {i:>2} {r['abbr']:4} {'vs' if r['home'] else '@ '} {r['opp']:12} {r['imp']:5.1f}"
                   f"{'  (played)' if r.get('played') else ''}")
    return "\n".join(out)


@mcp.tool()
def kicker_rankings() -> str:
    """Kicker slots ranked by own-offence implied total (+0.7 dome)."""
    d = _latest()
    out = [f"{d['label']} K — own implied total, descending, dome +0.7"]
    for i, r in enumerate(d["k"], 1):
        out.append(f"  {i:>2} {r['abbr']:4} {'vs' if r['home'] else '@ '} {r['opp']:12} {r['imp']:5.1f}"
                   f"{' dome' if r['dome'] else ''}{'  (played)' if r.get('played') else ''}")
    return "\n".join(out)


@mcp.tool()
def fantasypros_rankings(position: str = "RB", week: int = 0, top: int = 30) -> str:
    """FantasyPros expert consensus (ECR) for the week, if an API key is
    configured and the week was fetched."""
    season, week = _week(week)
    rows = [r for r in _read_csv(DATA / f"ecr_{week_key(season, week)}.csv") if r["pos"] == position.upper()]
    if not rows:
        return "no ECR on file (set FANTASYPROS_API_KEY in engine/weekly/.env and refresh_week())"
    rows.sort(key=lambda r: float(r["rank_ecr"] or 999))
    out = [f"FantasyPros ECR {season} week {week} {position.upper()}"]
    for r in rows[:top]:
        out.append(f"  {r['rank_ecr']:>3} {r['name']:24} {r['team'] or '':4} {r['opp'] or '':5} "
                   f"range {r['rank_min']}-{r['rank_max']} sd {r['rank_std']} {r.get('start_sit_grade') or ''}")
    return "\n".join(out)


# ------------------------------------------------------------ tools: my league
@mcp.tool()
def league_settings() -> str:
    """League name, roster slots, scoring format, teams, and which team
    is yours (from ESPN_TEAM_ID or your SWID)."""
    season, _ = _state()
    s = _league(season).settings()
    slots = ", ".join(f"{ESPN_SLOTS.get(k, k)}x{v}" for k, v in sorted(s["slots"].items()))
    out = [f"{s['league']} ({season}) — ESPN week {s['current_week']}, matchup period {s['matchup_period']}",
           f"slots: {slots}", f"scoring: {s['scoring_format']}; waivers {s['waiver_type']} "
           f"(order reset {s['waiver_order_reset']})", "teams:"]
    for t in s["teams"]:
        rec = t.get("record", {})
        out.append(f"  {t['id']:>2} {t['name']:30} {rec.get('wins', 0)}-{rec.get('losses', 0)}"
                   f"{'   <- you' if t['id'] == s['my_team_id'] else ''}")
    if s["my_team_id"] is None:
        out.append("your team was not identified: set ESPN_TEAM_ID in engine/weekly/.env")
    return "\n".join(out)


@mcp.tool()
def my_roster(week: int = 0) -> str:
    """Your roster with this week's projection per player, its sources
    (ESPN projection, usage-based expected points, matchup), injury
    flags, bye, and lock status; plus your matchup."""
    season, week = _week(week)
    lg, s, roster, _ = _projected_roster(season, week)
    m = lg.matchup(week)
    order = sorted(roster, key=lambda p: (p.get("slot") in (20, 21), p.get("slot") or 0, -p["proj"]))
    out = [f"{s['league']} week {week} — your roster (team {s['my_team_id']}), {s['scoring_format']} scoring"]
    if m:
        out.append(f"matchup: vs {m['opponent']} (ESPN live proj {m['my_projected']} vs {m['opp_projected']}; "
                   f"scored {m['my_points']} vs {m['opp_points']})")
    out += [_fmt_player(p) for p in order]
    starters = [p for p in roster if p.get("slot") not in (20, 21)]
    out.append(f"current starters total proj: {sum(p['proj'] for p in starters):.1f}")
    return "\n".join(out)


@mcp.tool()
def lineup_recommendation(week: int = 0) -> str:
    """The optimal starting lineup by projection, the slot moves to get
    there, and the close calls worth a second look. Returns a token for
    apply_lineup. Nothing is changed."""
    season, week = _week(week)
    lg, s, roster, _ = _projected_roster(season, week)
    res = advisor.optimal_lineup(roster, s["slots"])
    cur = sum(p["proj"] for p in roster if p.get("slot") not in (20, 21))
    out = [f"week {week} optimal lineup: {res['total']:.1f} proj (current lineup {cur:.1f})"]
    for slot, p in res["starters"]:
        out.append(f"  {ESPN_SLOTS.get(slot, slot):6} " + (_fmt_player(p) if p else "(empty — no eligible healthy player)"))
    out.append("bench:")
    for p in sorted(res["bench"], key=lambda p: -p["proj"]):
        out.append("         " + _fmt_player(p, with_sources=False))
    # Close calls: bench player within 2 pts of a starter he could replace.
    close = []
    for p in res["bench"]:
        for slot, st in res["starters"]:
            if st and slot in p["eligible_slots"] and abs(st["proj"] - p["proj"]) <= 2.0 and p["proj"] > 0:
                close.append(f"  {p['name']} ({p['proj']}) vs {st['name']} ({st['proj']}) at {ESPN_SLOTS.get(slot)}")
    if close:
        out.append("close calls (read the news before trusting a coin flip):")
        out += close
    if res["moves"]:
        token = _save_proposal("lineup", {"moves": res["moves"]}, week)
        out.append("moves:")
        out += [f"  {m['name']}: {m['from']} -> {m['to']}" for m in res["moves"]]
        out.append(f"apply with apply_lineup(token='{token}', confirmed=True) after the user approves")
    else:
        out.append("no moves: the current lineup is already optimal")
    return "\n".join(out)


@mcp.tool()
def free_agents(position: str = "", top: int = 25, week: int = 0) -> str:
    """Available players (free agents + waivers) with value and this
    week's projection; hottest adds by ownership change listed first."""
    season, week = _week(week)
    _, s, _, fas = _projected_roster(season, week)
    if position:
        fas = [p for p in fas if p["pos"] == position.upper()]
    fas.sort(key=lambda p: -(p.get("value") or 0))
    out = [f"week {week} free agents{' ' + position.upper() if position else ''} by value ({s['scoring_format']})"]
    for p in fas[:top]:
        w = " WAIVERS" if p.get("waiver") else ""
        out.append(_fmt_player(p) + f"  own {p['pct_owned']}% ({p['pct_change']:+.1f}){w}")
    hot = sorted(fas, key=lambda p: -p.get("pct_change", 0))[:8]
    out.append("hottest adds (ownership change this week):")
    out += [f"  {p['name']:24} {p['pos']:3} {p['team'] or '?':4} {p['pct_change']:+.1f}% -> {p['pct_owned']}%  value {p.get('value')}"
            for p in hot if p.get("pct_change", 0) > 0]
    return "\n".join(out)


@mcp.tool()
def waiver_recommendations(week: int = 0) -> str:
    """Positional needs on your roster, drop candidates, and ranked
    add/drop proposals with the value gained. Use propose_transaction
    on the one you want to ask the user about."""
    season, week = _week(week)
    _, s, roster, fas = _projected_roster(season, week)
    lineup = advisor.optimal_lineup(roster, s["slots"])
    needs = advisor.positional_needs(roster, fas, s["slots"], _bye_map(season, week))
    drops = advisor.drop_candidates(roster, lineup, fas)
    props = advisor.proposals(roster, lineup, fas, s["slots"])
    out = [f"week {week} waiver review ({s['scoring_format']}; waivers {s['waiver_type']})", "needs:"]
    out += [f"  [{n['urgency']}] {n['pos']:3} {n['kind']:8} {n['detail']}" for n in needs] or ["  none flagged"]
    out.append("drop candidates (most droppable first; surplus = value over replacement level at position):")
    out += [f"  {p['name']:24} {p['pos']:3} value {p.get('value')} surplus {p['surplus']:+.1f} own {p['pct_owned']}%"
            for p in drops[:6]] or ["  none (every bench player beats the wire)"]
    out.append("proposals:")
    for p in props:
        out.append(f"  +{p['add']} ({p['add_pos']} {p['add_team']}, value {p['add_value']}, proj {p['add_proj']}"
                   f"{', WAIVERS' if p['waiver'] else ''})  -{p['drop']} ({p['drop_pos']}, value {p['drop_value']})"
                   f"  delta {p['delta']:+.1f}  ids add={p['add_id']} drop={p['drop_id']}"
                   + (f"  notes: {'; '.join(p['notes'])}" if p["notes"] else ""))
    if not props:
        out.append("  nothing on the wire beats a drop candidate by more than 0.5")
    return "\n".join(out)


@mcp.tool()
def propose_transaction(add_id: int, drop_id: int = 0, bid: int = -1, week: int = 0) -> str:
    """Preview an add (and optional drop) exactly as it would be sent to
    ESPN, and get the question to put to the user plus a token. Does
    not send anything."""
    season, week = _week(week)
    lg, s, roster, fas = _projected_roster(season, week)
    add = next((p for p in fas if p["id"] == add_id), None)
    drop = next((p for p in roster if p["id"] == drop_id), None) if drop_id else None
    if add is None:
        return f"player {add_id} is not in the free-agent pool (free_agents())"
    if drop_id and drop is None:
        return f"player {drop_id} is not on your roster"
    if drop and drop.get("locked"):
        return f"{drop['name']} is locked (game underway); pick another drop"
    payload = {"add_id": add_id, "drop_id": drop_id or None, "waiver": bool(add.get("waiver")),
               "bid": bid if bid >= 0 else None}
    preview = lg.add_drop(add_id, drop_id or None, week, waiver=payload["waiver"],
                          bid=payload["bid"], dry_run=True)
    token = _save_proposal("add_drop", payload, week)
    q = (f"Do you want to {'claim' if payload['waiver'] else 'pick up'} {add['name']} ({add['pos']} {add['team']}, "
         f"proj {add['proj']}, value {add.get('value')})"
         + (f" and drop {drop['name']} ({drop['pos']}, value {drop.get('value')})" if drop else "") + "?")
    return "\n".join([f"ASK THE USER: {q}",
                      f"then execute_transaction(token='{token}', confirmed=True) only on a clear yes",
                      "payload ESPN would receive:", json.dumps(preview["would_post"], indent=1)])


@mcp.tool()
def execute_transaction(token: str, confirmed: bool = False) -> str:
    """Send a previewed add/drop to ESPN. Requires the token from
    propose_transaction and confirmed=True, which you may only pass after
    the user explicitly approved that exact proposal."""
    if not confirmed:
        return "not sent: confirmed=False (ask the user first)"
    p = _load_proposal(token)
    if p["kind"] != "add_drop":
        return "that token is a lineup proposal; use apply_lineup"
    season, _ = _state()
    lg = _league(season)
    pay = p["payload"]
    res = lg.add_drop(pay["add_id"], pay["drop_id"], p["week"], waiver=pay["waiver"],
                      bid=pay["bid"], dry_run=False)
    return "sent to ESPN:\n" + json.dumps(res.get("response"), indent=1)[:2000]


@mcp.tool()
def apply_lineup(token: str, confirmed: bool = False) -> str:
    """Send the lineup moves from lineup_recommendation to ESPN. Requires
    that token and confirmed=True after the user approved the moves."""
    if not confirmed:
        return "not sent: confirmed=False (ask the user first)"
    p = _load_proposal(token)
    if p["kind"] != "lineup":
        return "that token is an add/drop proposal; use execute_transaction"
    season, _ = _state()
    lg = _league(season)
    res = lg.set_lineup(p["payload"]["moves"], p["week"], dry_run=False)
    return "sent to ESPN:\n" + json.dumps(res.get("response"), indent=1)[:2000]


if __name__ == "__main__":
    mcp.run()
