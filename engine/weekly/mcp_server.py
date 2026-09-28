"""ff-weekly: MCP tools for the in-season week.

Numerical tools read saved weekly inputs plus live ESPN league data.
Practice/news tools use dated local caches of public sources. The agent
reads these next to Reddit context and decides; the only tools that
write to ESPN are execute_transaction and apply_lineup, and both
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

from common import (CACHE, DATA, ESPN_SLOTS, SKILL, TEAMS, load_env, nfl_state,
                    norm_team, now_iso, week_key)
import advisor

mcp = MCPServer("ff-weekly", version="1.0.0", instructions=(
    "For 'will X play / when is X back' call injury_check(names) first and quote its summary. "
    "For team questions read weekly_checklist and research_sources. Establish the decision "
    "season/week with week_status and pass it explicitly; observed usage weeks are different. "
    "Use practice_report for current official status and player_news for dated context. "
    "Check source dates, coverage and cache freshness; old injury tags are not current designations. "
    "Tools return compact text sized for one question; ask for one team or player rather than "
    "the whole league. For anything the tools do not summarise, query_data runs read-only SQL "
    "over the saved weekly files (data_tables lists them) instead of a scratch script. "
    "Research does not authorize ESPN writes; exact proposal/token confirmation is still required."
))
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


def _week(week: int, season: int = 0) -> tuple[int, int]:
    if not season or not week:
        current_season, cur = _state()
        season, week = season or current_season, week or cur
    if not 1 <= week <= 18 or not 2000 <= season <= 2100:
        raise ValueError("Use an NFL regular-season week 1–18 and an explicit season")
    return season, week


def _bundle(season: int, week: int) -> dict:
    """Never return another decision week's latest.json as the requested week."""
    for path in (DATA / f"week_{week_key(season, week)}.json", DATA / "latest.json"):
        if path.exists():
            data = json.loads(path.read_text())
            if (data.get("season"), data.get("week")) == (season, week):
                return data
    raise ValueError(f"No saved bundle for {season} week {week}. "
                     "Do not substitute another week; build the requested bundle first.")


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


def _ecr_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ecr_index(season: int, week: int) -> dict:
    """(name, pos) -> this week's expert consensus. D/ST is also keyed by
    (team, pos): every source spells a defense differently, and the
    fftiers feed carries the team so that join does not have to guess."""
    idx = {}
    for r in _read_csv(DATA / f"ecr_{week_key(season, week)}.csv"):
        v = {"rank": _ecr_float(r.get("rank_ecr")), "tier": _ecr_float(r.get("tier")),
             "sd": _ecr_float(r.get("rank_std"))}
        idx[(_norm_name(r["name"]), r["pos"])] = v
        if r["pos"] == "DST" and r.get("team"):
            idx[(r["team"], "DST")] = v
    return idx


def _ecr_str(e: dict) -> str:
    """'ECR 12 (T3, sd 2.1)'. The tier is the part that decides a start/sit:
    a gap inside a tier is disagreement, a gap between tiers is an order."""
    out = f"{e['rank']:.0f}" if e.get("rank") is not None else "?"
    if e.get("tier") is not None:
        out += f" (T{e['tier']:.0f}"
        out += f", sd {e['sd']:.1f})" if e.get("sd") is not None else ")"
    return out


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


def projector(season: int, week: int):
    """(league, settings, attach): attach(espn_row) -> row with proj/value,
    the same recipe for every roster in the league (advisor.project)."""
    lg = _league(season)
    s = lg.settings()
    fmt = s["scoring_format"]
    opp = _opportunity(season)
    xw = _crosswalk()
    by_name = {(_norm_name(r["name"]), r["pos"]): r for r in opp.values()}
    lines = _lines_week(season, week)
    byes = _byes(season, week)
    ecr = _ecr_index(season, week)

    def attach(p):
        gsis = xw.get(str(p["id"]))
        row = opp.get(gsis) if gsis else None
        if row is None:
            row = by_name.get((_norm_name(p["name"]), p["pos"]))
        return advisor.project(p, row, lines.get(p["team"]), fmt,
                               on_bye=p["team"] in byes,
                               ecr=(ecr.get((_norm_name(p["name"]), p["pos"]))
                                    or ecr.get((p.get("team"), p["pos"]))))

    return lg, s, attach


def _projected_roster(season: int, week: int):
    """(league, settings, my roster with projections, free agents with projections)."""
    lg, s, attach = projector(season, week)
    roster = [attach(p) for p in lg.my_roster(week)]
    fas = [attach(p) for p in lg.free_agents(week) if p.get("team")]   # unsigned players are not pickups
    return lg, s, roster, fas


def _stale_note(season: int) -> str | None:
    """A line when a finished game is missing from the saved usage file."""
    import schedule_view
    try:
        return schedule_view.usage_gap(season)
    except Exception:  # noqa: BLE001 - a freshness hint must never break a read
        return None


def _with_stale(season: int, text: str) -> str:
    note = _stale_note(season)
    return f"{text}\n{note}" if note else text


def _fmt_player(p: dict, with_sources: bool = True) -> str:
    m = p.get("matchup") or {}
    opp = f"{'' if m.get('home') else '@'}{m.get('opp')} (imp {m.get('imp_own')})" if m else "no game"
    src = p.get("sources", {})
    bits = [f"{p['name']:24} {p['pos']:3} {p.get('team') or '?':4} {p.get('slot_name') or '':6}",
            f"id={p['id']}" if p.get("id") is not None else "",
            f"proj {p['proj']:5.1f}", f"value {p.get('value') if p.get('value') is not None else '-':>5}",
            opp]
    if with_sources:
        def r1(v):
            return f"{v:.1f}" if isinstance(v, float) else v
        bits.append(f"espn {r1(src.get('espn_proj'))} | ewmaEP {r1(src.get('ewma_ep'))} | lastEP/pts "
                    f"{r1(src.get('last_ep'))}/{r1(src.get('last_pts'))}")
        if src.get("ecr"):
            bits.append("ECR " + _ecr_str(src["ecr"]))
    if p.get("flags"):
        bits.append("[" + ", ".join(p["flags"]) + "]")
    return "  ".join(str(b) for b in bits if b != "")


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
    return Path(__file__).with_name("RESEARCH.md").read_text(encoding="utf-8")


@mcp.tool()
def week_status(week: int = 0, season: int = 0) -> str:
    """Current NFL week versus requested decision season/week, matching saved bundle,
    recorded usage weeks, timestamps and configured optional feeds. Usage can be partial."""
    import schedule_view
    current_season, current_week = _state()
    season, week = _week(week, season)
    env = load_env()
    out = [f"NFL season {current_season}, week {current_week} (Sleeper state; it rolls over "
           "Tuesday night, so on Monday it still names the week being finished)",
           schedule_view.decision_week_hint(current_season, current_week),
           f"Decision: season {season}, week {week}. As of {now_iso()}."]
    stale = _stale_note(season)
    if stale:
        out.append(stale)
    p = DATA / "latest.json"
    if p.exists():
        d = json.loads(p.read_text())
        out.append(f"data/weekly/latest.json: {d['label']} built {d['generated']} "
                   f"({d.get('games_played_this_week', 0)} games already played, "
                   f"{len(d['skill'])} skill rows)")
        if (d.get("season"), d["week"]) != (season, week):
            out.append(f"  -> stale season/week for this decision: do not use latest as week {week}")
    else:
        out.append("data/weekly/latest.json missing -> run refresh_week()")
    try:
        requested = _bundle(season, week)
        out.append(f"requested-week bundle: {requested['label']}, built {requested['generated']}")
    except ValueError as exc:
        out.append(str(exc))
    usage = _read_csv(DATA / f"opportunity_{season}_weekly.csv")
    observed = sorted({int(r['week']) for r in usage if r.get('week')})
    out.append(f"recorded usage weeks: {observed or 'none'}; decision week is not a usage week. "
               "A listed week can be partial; check game coverage before calling it complete.")
    ecr_path = DATA / f"ecr_{week_key(season, week)}.csv"
    ecr_rows = _read_csv(ecr_path)
    if ecr_rows:
        mf = ecr_path.with_suffix(".sources.json")
        when = json.loads(mf.read_text()).get("generated_at", "?") if mf.exists() else "?"
        per: dict[str, int] = {}
        for r in ecr_rows:
            per[r["pos"]] = per.get(r["pos"], 0) + 1
        out.append(f"expert consensus: {len(ecr_rows)} ranked via "
                   f"{ecr_rows[0].get('source') or 'fantasypros API'} at {when} ("
                   + ", ".join(f"{k} {v}" for k, v in per.items()) + ")")
        if mf.exists():
            sources = json.loads(mf.read_text()).get("sources", {})
            missing = [pos for pos, source in sources.items() if source.get("status") != "available"]
            if missing:
                out.append("  missing consensus coverage: " + ", ".join(missing))
    else:
        out.append(f"expert consensus: none for week {week} -> run refresh_week()")
    out.append(f"ESPN league: {'configured' if env.get('ESPN_LEAGUE_ID') else 'ESPN_LEAGUE_ID missing'}; "
               f"cookies: {'present' if env.get('ESPN_S2') and env.get('ESPN_SWID') else 'MISSING (private league reads and all writes need ESPN_S2 + ESPN_SWID in engine/weekly/.env)'}")
    out.append("FantasyPros key: " + ("present (paid API: start/sit grades, no tiers)"
               if env.get("FANTASYPROS_API_KEY")
               else "absent -> keyless fftiers bucket (same consensus, plus tiers)"))
    return "\n".join(out)


@mcp.tool()
def research_sources() -> str:
    """Where to look for team questions: tools, week semantics and local cache/refresh policy."""
    return (Path(__file__).parents[2] / "docs" / "TEAM-QUESTIONS.md").read_text()


@mcp.tool()
def practice_report(team: str, week: int = 0, season: int = 0, player: str = "",
                    refresh: bool = False, cache_only: bool = False) -> dict:
    """Current official club practice grid and game designation. Use before ESPN injury tags.

    One team; optional player-name filter. Explicit season/week prevent carryover.
    Local cache lasts 5 minutes; refresh=True rechecks, cache_only=True does no
    network and labels expired evidence stale. Not listed/blank is not clearance.

    Weeks: the current week reads live pages. An earlier week is read from the
    saved cache only (stated in `mode`). Next week (e.g. asking on Monday) is
    fetched live once the team's first report day has arrived; before that the
    result says when the first report is due instead of erroring.
    """
    import evidence
    import injury_check as ic
    from datetime import datetime, timezone
    season, week = _week(week, season)
    if cache_only:
        return evidence.practice(team, season, week, player, refresh, True)
    state = _state()
    if (season, week) == state:
        return evidence.practice(team, season, week, player, refresh, False)
    if (season, week) < state:
        result = evidence.practice(team, season, week, player, False, True)
        result["mode"] = "past week: saved cache only; live pages show the current week"
        return result
    t = norm_team(team)
    game = next((r for r in _read_csv(DATA / f"lines_{season}.csv")
                 if int(r["week"]) == week and r["team"] == t), None)
    ko = ic.kickoff(game.get("kickoff")) if game else None
    if ko is None:
        return {"season": season, "week": week, "team": t, "state": "no game on file",
                "note": f"{t} has no week {week} game in the lines file (bye or not posted)."}
    times = ic.timeline(ko)
    first = times["first_practice_report"].split()[-1]
    if datetime.now(timezone.utc).astimezone(ic.EASTERN).date().isoformat() < first:
        return {"season": season, "week": week, "team": t, "state": "not published yet",
                "timeline": times,
                "note": f"The week {week} report is not out: the first one is due "
                        f"{times['first_practice_report']}. Use injury_check or the week "
                        f"{state[1]} report meanwhile; not published is not clearance."}
    result = evidence.practice(team, season, week, player, refresh, False)
    result["mode"] = "next week: live pages, first report day reached"
    return result


@mcp.tool()
def player_news(names: str, week: int = 0, season: int = 0, hours: int = 24,
                refresh: bool = False, cache_only: bool = False) -> dict:
    """Dated Bluesky news for 1–6 comma-separated full player names, with source links/gaps.

    hours: look-back window, 1–168 (7 days); larger values are capped at 168
    and the result says so. Each account's feed is its newest 100 posts, so
    a long window on a busy wire can still miss older posts. This is a feed
    read, not a search: there is no keyword search of all of Bluesky.

    Cached locally per account and decision season/week for 10 minutes. Reuses
    feeds across players. refresh=True rechecks; cache_only=True is offline and
    labels old evidence stale. A past week is read from the saved cache only
    (live feeds cannot reconstruct it) and says so in `mode`. Decision week does
    not establish a post's event week. Wire reporting is context, not an
    official game designation.
    """
    import evidence
    season, week = _week(week, season)
    notes = []
    if hours > 168:
        notes.append(f"hours={hours} capped at 168 (7 days), the longest window the feeds support")
        hours = 168
    hours = max(1, hours)
    if not cache_only and (season != _state()[0] or week < _state()[1]):
        cache_only = True
        notes.append("past week: saved feed snapshots only; live feeds show the current week")
    result = evidence.news(names, season, week, hours, refresh, cache_only)
    if notes:
        result["mode"] = "; ".join(notes)
    return result


@mcp.tool()
def injury_check(names: str = "", refresh: bool = False, roster: str = "") -> dict:
    """START HERE for "will X play / when is X back / is X hurt" (1-6 comma-separated names).

    roster="mine", "opponent" (this week's fantasy opponent) or a league
    team_id checks every QB/RB/WR/TE/K on that fantasy roster instead of
    `names` (D/ST skipped), returning only each player's summary to keep
    the answer short; call again with names for a player's full detail.

    One call works out each player's next unplayed game (Monday questions
    land on next week automatically), then returns: the official club
    report for that game if published, otherwise when it will be; the
    previous week's official report; weeks he had no usage or was
    reported Out; ESPN's tag; the last 72h of dated news; kickoff, final
    designation day and inactive time. `summary` states those facts in
    plain words; quote it, then add news context.

    No chance-to-play model exists: do not turn this into odds. Club
    reports beat news beat ESPN tags. Not listed is not clearance.
    Players are resolved from the season's usage file (anyone with a
    carry or target); others return "not found".
    """
    import evidence
    import injury_check as ic
    from datetime import datetime, timezone
    season, state_week = _state()
    now = datetime.now(timezone.utc)
    asked = [n.strip() for n in names.split(",") if n.strip()]
    roster_label = None
    league_rosters = None
    if roster:
        lg = _league(season)
        settings = lg.settings()
        league_rosters = lg.rosters(state_week)
        key = roster.strip().lower()
        if key == "mine":
            tid = settings["my_team_id"]
        elif key == "opponent":
            m = lg.matchup(state_week)
            tid = m["opponent_id"] if m else None
        elif key.isdigit():
            tid = int(key)
        else:
            raise ValueError('roster must be "mine", "opponent" or a team_id from league_settings')
        if tid not in league_rosters:
            raise ValueError(f"no roster for team {roster!r}; read league_settings for team ids")
        roster_label = next((t["name"] for t in settings["teams"] if t["id"] == tid), str(tid))
        asked = [p["name"] for p in league_rosters[tid] if p["pos"] != "DST"]
    elif not 1 <= len(asked) <= 6:
        raise ValueError("Supply 1–6 comma-separated player names, or roster=")
    lines = _read_csv(DATA / f"lines_{season}.csv")
    usage = _read_csv(DATA / f"advanced_usage_{season}_weekly.csv")
    injuries = _read_csv(DATA / f"injuries_{season}.csv")
    players = list(_opportunity(season).values())
    espn_tags, espn_note = {}, None
    try:
        for team_roster_ in (league_rosters or _league(season).rosters(state_week)).values():
            for p in team_roster_:
                espn_tags[_norm_name(p["name"])] = p["injury"]
    except Exception as e:  # noqa: BLE001 - optional source
        espn_note = f"ESPN tags unavailable: {type(e).__name__}"
    news = {"posts": []}
    # The wire read takes 6 names at a time; feeds are cached, so batches are cheap.
    for i in range(0, len(asked), 6):
        try:
            got = evidence.news(",".join(n for n in asked[i:i + 6] if len(n) >= 3),
                                season, state_week, 72, refresh and i == 0)
            news["posts"] += got.get("posts", [])
            news.setdefault("coverage_note", got.get("coverage_note"))
        except Exception as e:  # noqa: BLE001 - optional source
            news["error"] = f"{type(e).__name__}: {e}"
    out = {"as_of": now.isoformat(), "season": season, "nfl_state_week": state_week,
           "rule": "Evidence and timing only; no chance-to-play model. Club report > news > ESPN tag.",
           "players": []}
    for name in asked:
        hits = ic.resolve(name, players)
        if not hits:
            out["players"].append({"name": name, "found": False,
                                   "summary": f"{name}: not in the {season} usage file; use practice_report(team) "
                                              "and player_news directly."})
            continue
        if len(hits) > 1 and ic.norm(hits[0]["name"]) != ic.norm(name):
            out["players"].append({"name": name, "found": False,
                                   "summary": f"{name!r} is ambiguous: "
                                              + ", ".join(f"{h['name']} ({h['team']})" for h in hits[:5])})
            continue
        p = hits[0]
        team = p["team"]
        game = ic.next_game(team, lines, now, state_week)
        times = ic.timeline(datetime.fromisoformat(game["kickoff_utc"])) if game and game["kickoff_utc"] else None
        cur = cur_report = None
        cur_state = "not fetched"
        if game and times:
            first = times["first_practice_report"].split()[-1]
            if now.astimezone(ic.EASTERN).date().isoformat() >= first:
                try:
                    cur_report = evidence.practice(team, season, game["week"], "", refresh)
                    cur = ic.report_row(cur_report, p["name"])
                    cur_state = ic.report_state(cur_report)
                except Exception as e:  # noqa: BLE001
                    cur_state = f"fetch failed: {type(e).__name__}"
            else:
                cur_state = "not published yet"
        prev_weeks = [int(r["week"]) for r in lines
                      if r["team"] == team and int(r["week"]) < (game["week"] if game else 99)]
        prev = None
        if prev_weeks:
            pw = max(prev_weeks)
            try:
                prev = ic.report_row(evidence.practice(team, season, pw, "", cache_only=True), p["name"])
            except Exception:  # noqa: BLE001 - fall back to the saved nflverse report
                prev = None
            if prev is None:
                row = next((r for r in injuries if r.get("gsis_id") == p["player_id"]
                            and int(r["week"]) == pw), None)
                if row:
                    prev = {"week": pw, "injury": row.get("report_primary_injury") or "",
                            "practice": {"last": row.get("practice_status") or ""},
                            "designation": row.get("report_status") or "",
                            "source": f"saved nflverse injuries_{season}.csv"}
        gone = ic.missed(p["player_id"], team, usage, injuries)
        espn = espn_tags.get(_norm_name(p["name"]))
        posts = [{"at": x["created_at"], "by": x["handle"], "text": x["text"][:240], "url": x["url"]}
                 for x in news.get("posts", []) if ic.norm(p["name"]) in ic.norm(x["text"])
                 or p["name"].casefold() in x["text"].casefold()][:6]
        out["players"].append({
            "name": p["name"], "found": True, "team": team, "pos": p["pos"],
            "summary": ic.summary(p["name"], p["pos"], team, game, cur, cur_state, prev, gone,
                                  espn, times, posts),
            "next_game": game, "timeline": times,
            "official_report_next_game": cur, "official_report_next_game_state": cur_state,
            "official_report_previous_week": prev, "absences": gone,
            "espn_tag": espn or ("not on a league roster" if espn_tags else espn_note),
            "news_72h": posts,
        })
    out["news_note"] = news.get("error") or news.get("coverage_note")
    if roster_label:
        return {"as_of": out["as_of"], "roster": roster_label, "rule": out["rule"],
                "players": [{"name": p["name"], "summary": p["summary"]} for p in out["players"]],
                "detail": "injury_check(names=...) returns full reports for any of these players",
                "news_note": out["news_note"]}
    return out


@mcp.tool()
def refresh_week(week: int = 0) -> str:
    """Re-fetch lines, stats, injuries, depth charts and expert consensus
    ranks, and rebuild data/weekly/latest.json for the given week
    (0 = current). Consensus needs no key: without FANTASYPROS_API_KEY it
    comes from the public fftiers bucket, with tiers."""
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
    return _with_stale(d.get("season") or _state()[0], "\n".join(out))


@mcp.tool()
def player_lookup(name: str, week: int = 0, season: int = 0, weekly: bool = False,
                  seasons: str = "", scoring: str = "std") -> str:
    """Everything on file for 1-4 comma-separated players: season usage and
    expected points, the decision week's game line, the saved injury report,
    depth-chart slot and snap share.

    week/season: the decision week for the line and report (Monday pickup
    questions usually mean next week; pass it). weekly=True adds a game log:
    per week opponent, snap %, carries, targets, target share, red-zone and
    end-zone looks, receptions, yards, TDs, expected and actual points
    (QBs get passing lines, kickers field goals by distance). seasons="2025",
    "2023-2025", "last3" or "all" adds regular-season totals per year from
    box scores back to 2021 with the position rank. scoring: std|half|ppr for
    the expected/actual points columns.

    Anyone in the box scores is found, including kickers, backups and players
    with no carry or target this year. League-scored points (exact ESPN rules,
    D/ST too) come from league_points. Reads saved files only.
    """
    import player_history as ph
    season, week = _week(week, season)
    fmt = scoring if scoring in ("std", "half", "ppr") else "std"
    asked = [n.strip() for n in name.split(",") if n.strip()]
    if not 1 <= len(asked) <= 4:
        raise ValueError("Supply 1-4 comma-separated player names")
    years = ph.parse_seasons(seasons, season)
    opp_rows = list(_opportunity(season).values())
    lines = _lines_week(season, week)
    byes = _byes(season, week)
    inj = {}
    for r in _read_csv(DATA / f"injuries_{season}.csv"):
        if int(r["week"]) <= week:
            inj[r["gsis_id"]] = r      # latest saved report up to the decision week
    depth = {r["gsis_id"]: r for r in _read_csv(DATA / f"depth_{season}.csv")}
    usage = sorted(_read_csv(DATA / f"advanced_usage_{season}_weekly.csv"),
                   key=lambda u: int(u["week"]))
    out = []
    for query in asked:
        n = _norm_name(query)
        exact = [r for r in opp_rows if _norm_name(r["name"]) == n]
        opp = exact or [r for r in opp_rows if n in _norm_name(r["name"])]
        if not opp:
            hits = ph.find(query, season)
            if not hits:
                out.append(f"{query}: no player by that name in {season} usage or 2021-{season} box scores")
                continue
            h = hits[0]
            out.append(f"{h['name']} {h['pos']} {h['team']} (last seen {h['season']}; "
                       "no carry or target this season)")
            if h["season"] == season:
                out += ph.weekly(season, h["player_id"], fmt)
            if years:
                out += ph.seasons(h["player_id"], years)
            if len(hits) > 1:
                out.append("  also matched: " + ", ".join(f"{x['name']} ({x['pos']} {x['team']})"
                                                          for x in hits[1:4]))
            continue
        if len(opp) > 1:
            out.append(f"{query}: several matches, showing the first; also "
                       + ", ".join(f"{r['name']} ({r['team']})" for r in opp[1:4]))
        r = opp[0]
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
        elif r["team"] in byes:
            out.append(f"  week {week}: BYE")
        else:
            out.append(f"  week {week}: no line on file (schedule(team) shows the game)")
        ij = inj.get(r["player_id"])
        if ij:
            out.append(f"  saved injury report wk{ij['week']}: {ij['report_status'] or '-'} "
                       f"{ij['report_primary_injury'] or ''}; practice {ij['practice_status'] or '-'} "
                       f"{ij['practice_primary_injury'] or ''} (not current status: injury_check)")
        dc = depth.get(r["player_id"])
        if dc:
            out.append(f"  depth chart ({dc['dt'][:10]}): {dc['team']} {dc['pos_abb']}{dc['pos_rank']}")
        sn = [u for u in usage if u["player_id"] == r["player_id"]
              and u.get("snaps_off") not in ("", None)
              and u.get("snap_share") not in ("", None)]
        if sn and not weekly:
            weeks = " ".join(f"wk{int(u['week'])} {float(u['snaps_off']):.0f}"
                             f"({float(u['snap_share']):.0%})" for u in sn[-6:])
            out.append(f"  snaps: {weeks}")
            out.append("    snaps are field time, not routes run; route share and TPRR "
                       "are paid charting we do not have")
        if weekly:
            out += ph.weekly(season, r["player_id"], fmt)
        if years:
            out += ph.seasons(r["player_id"], years)
    return _with_stale(season, "\n".join(out))


@mcp.tool()
def injury_report(team: str = "", position: str = "", week: int = 0, season: int = 0) -> str:
    """Saved weekly injury snapshot, NOT live practice status. For current news use practice_report.
    Select the explicit season/week; never substitute another week's bundle."""
    season, week = _week(week, season)
    d = _bundle(season, week)
    rows = d["injuries"]
    if team:
        rows = [r for r in rows if r["team"] == team.upper()]
    if position:
        rows = [r for r in rows if r["pos"] == position.upper()]
    if not rows:
        return (f"{d['label']} saved injury snapshot built {d.get('generated', 'unknown')}: "
                "no rows match; this is not clearance. This table is the weekly nflverse "
                "snapshot and often lags the club: for a player use injury_check(names), "
                "for a whole club practice_report(team).")
    out = [f"{d['label']} injury snapshot ({len(rows)} rows), built {d.get('generated', 'unknown')}. "
           "Cached weekly data; use practice_report for current status."]
    for r in sorted(rows, key=lambda r: (r["team"], r["pos"], r["name"])):
        out.append(f"  {r['team']:4} {r['pos']:3} {r['name']:24} {r['status'] or '-':12} "
                   f"{r['injury'] or '':16} {r['practice'] or ''}")
    return "\n".join(out)


@mcp.tool()
def dst_rankings(week: int = 0, season: int = 0, horizon: int = 1, team: str = "") -> str:
    """Defences ranked by opponent implied total (lowest first), finding 27.

    horizon=1 (default) is the saved weekly bundle, the published method.
    horizon=N (2-6) adds a planning table for weeks week..week+N-1: each
    defence's opponent implied total per week and the average, from posted
    lines where they exist and otherwise the August preseason team-strength
    prior (labelled). Use it for "hold this defence or stream?" — the
    far weeks are priors, not lines, and move once lines post. team=
    limits the planning table to one defence.
    """
    import schedule_view
    season, week = _week(week, season)
    out = []
    if horizon <= 1 or not team:
        try:
            d = _bundle(season, week)
            out = [f"{d['label']} D/ST — opponent implied total, ascending (top 3 = stream); "
                   f"bundle built {d.get('generated', 'unknown')} (not a live odds retrieval)"]
            for i, r in enumerate(d["dst"], 1):
                out.append(f"  {i:>2} {r['abbr']:4} {'vs' if r['home'] else '@ '} {r['opp']:12} {r['imp']:5.1f}"
                           f"{'  (played)' if r.get('played') else ''}")
        except ValueError as e:
            if horizon <= 1:
                raise
            out = [str(e)]
    if horizon > 1:
        horizon = min(horizon, 6)
        last = min(18, week + horizon - 1)
        teams = [norm_team(team)] if team else sorted(TEAMS)
        rows = []
        for t in teams:
            wk = schedule_view.team_weeks(season, t, week, last)
            cells, vals, pre = [], [], False
            for r in wk:
                if r["bye"]:
                    cells.append(f"wk{r['week']} BYE")
                    continue
                v = r["imp_opp"]
                pre |= r["imp_source"] == "preseason prior"
                cells.append(f"wk{r['week']} {'vs' if r['home'] else '@'}{r['opp']} "
                             + ("?" if v is None else f"{v:.1f}{'*' if r['imp_source'] == 'preseason prior' else ''}"))
                if v is not None:
                    vals.append(v)
            rows.append((sum(vals) / len(vals) if vals else 99, t, cells))
        rows.sort()
        out.append(f"D/ST planning, weeks {week}-{last}: opponent implied points per week "
                   f"(* = preseason prior, not a line), sorted by the average")
        out += [f"  {t:4} avg {avg:5.1f}  " + " | ".join(cells) for avg, t, cells in rows]
    return "\n".join(out)


@mcp.tool()
def kicker_rankings(week: int = 0, season: int = 0) -> str:
    """Kicker slots ranked by own-offence implied total (+0.7 dome)."""
    d = _bundle(*_week(week, season))
    out = [f"{d['label']} K — own implied total, descending, dome +0.7"]
    for i, r in enumerate(d["k"], 1):
        out.append(f"  {i:>2} {r['abbr']:4} {'vs' if r['home'] else '@ '} {r['opp']:12} {r['imp']:5.1f}"
                   f"{' dome' if r['dome'] else ''}{'  (played)' if r.get('played') else ''}")
    return "\n".join(out)


# Pooling weight for each metric: the count of plays that carried a value
# for it, which team_context.py writes beside it as <metric>_n.
TC_WEIGHT = ["proe", "epa_pass", "epa_rush", "sr_pass", "sr_rush", "sr_first",
             "cpoe", "expl_pass", "expl_rush", "sack_rate", "aypa", "deep_rate"]


def _pool(rows: list[dict]) -> dict:
    """Weighted pooled rates for one team's rows (see _team_context)."""
    acc = {"team": rows[0]["team"], "weeks": 0}
    for r in rows:
        acc["weeks"] += 1
        for col in ("plays", "dropbacks", "rushes", "attempts"):
            acc[col] = acc.get(col, 0) + float(r[col] or 0)
        for m in TC_WEIGHT:
            v, w = r.get(m), float(r.get(f"{m}_n") or 0)
            if v in ("", None) or not w:
                continue
            acc[f"_{m}"] = acc.get(f"_{m}", 0.0) + float(v) * w
            acc[f"_{m}_w"] = acc.get(f"_{m}_w", 0.0) + w
    for m in TC_WEIGHT:
        w = acc.pop(f"_{m}_w", 0.0)
        acc[m] = acc.pop(f"_{m}", 0.0) / w if w else None
    return acc


def _team_context(season: int, week: int, last: int = 1):
    """(rows by team, weeks pooled). Each row carries `_weeks`, its own weeks.

    week 0 = each team's own latest game(s) on file: a team's row exists
    only once its game is in the play-by-play, so NYJ's finished Sunday
    game counts even while Monday night is still to play. An explicit
    week pools the same calendar weeks for every team (a team on bye has
    no row that week).

    `last` pools that many most recent games as a weighted mean over each
    rate's own denominator — an average of weekly averages would let a
    12-play week count as much as a 70-play one. Pooled rows carry no
    percentile or rank: those are defined per team-game.
    """
    all_rows = _read_csv(DATA / f"team_context_{season}.csv")
    if not all_rows or week < 0:
        return {}, []
    n = max(1, last)
    if week:
        done = sorted({int(r["week"]) for r in all_rows if int(r["week"]) <= week})
        keep = set(done[-n:])
        if not keep:
            return {}, []
        picked: dict[str, list[dict]] = {}
        for r in all_rows:
            if int(r["week"]) in keep:
                picked.setdefault(r["team"], []).append(r)
    else:
        by_team: dict[str, list[dict]] = {}
        for r in all_rows:
            by_team.setdefault(r["team"], []).append(r)
        picked = {t: sorted(rs, key=lambda r: int(r["week"]))[-n:] for t, rs in by_team.items()}
    out = {}
    for t, rs in picked.items():
        rs = sorted(rs, key=lambda r: int(r["week"]))
        row = dict(rs[-1]) if len(rs) == 1 else _pool(rs)
        row["_weeks"] = [int(r["week"]) for r in rs]
        out[t] = row
    weeks = sorted({w for r in out.values() for w in r["_weeks"]})
    return out, weeks


# (column, label, format, note). The percentile is always the percentile
# of the raw value, so it reads as "good" only where a bigger number is
# better. sack_rate is the one metric that runs the other way, and PROE,
# air yards, deep rate and play volume are style rather than quality —
# they get no direction at all. Mirrors team_context.METRICS.
TC_FIELDS = [("proe", "PROE", "{:+.1f}", "style, not quality"),
             ("plays", "plays", "{:.0f}", ""),
             ("epa_pass", "pass EPA", "{:+.2f}", ""),
             ("epa_rush", "rush EPA", "{:+.2f}", ""),
             ("sr_pass", "pass SR", "{:.0%}", ""),
             ("sr_rush", "rush SR", "{:.0%}", ""),
             ("sr_first", "1st-dn SR", "{:.0%}", ""),
             ("cpoe", "CPOE", "{:+.1f}", ""),
             ("expl_pass", "expl pass", "{:.0%}", ""),
             ("expl_rush", "expl rush", "{:.0%}", ""),
             ("deep_rate", "20+ air", "{:.0%}", "style, not quality"),
             ("aypa", "air yds/att", "{:.1f}", "style, not quality"),
             ("sack_rate", "sack rate", "{:.0%}", "LOW is better")]


@mcp.tool()
def team_context(team: str = "", week: int = 0, last: int = 1) -> str:
    """How each offence actually played that week: PROE, CPOE, EPA and
    success rate per dropback and per designed rush, explosive and deep
    rates, sacks and play volume.

    Computed locally from nflverse play-by-play — not scraped from any
    rankings site. Each metric carries a percentile against every
    2021-2025 team-game and a rank within its own week, so "95th
    percentile passing" and "1st in PROE" both mean something exact.

    week 0 (the default) is each team's own latest completed game: a team
    that played Sunday counts while Monday night is still to come, and the
    league table shows which week each row is. An explicit week is that
    calendar week for everyone (a team on bye has no row). The week you are
    deciding about has not been played. last=N pools the N most recent
    games, weighted by each rate's own denominator; use it from about week
    4, because one game is a small sample and these rates are noisy over
    it. Pooled output drops the percentiles and ranks (per team-game).

    With no team, the league table sorted by pass EPA. With a team
    (abbreviation), that offence in full.

    This is matchup context, not a projection. Usage beats team
    environment (finding 26), so read it beside a player's own
    opportunity row, not instead of it.
    """
    season = _week(week)[0] if week else _state()[0]
    rows, weeks = _team_context(season, week, last)
    if not rows:
        return (f"no team context on file for {season}; run refresh_week() "
                f"(needs play-by-play for completed games)")

    def span_of(ws):
        if len(ws) == 1:
            return f"week {ws[0]}"
        run = ws == list(range(ws[0], ws[-1] + 1))
        return f"weeks {ws[0]}-{ws[-1]} pooled" if run else f"weeks {'/'.join(map(str, ws))} pooled"
    single = all(len(r["_weeks"]) == 1 for r in rows.values())
    if team:
        t = norm_team(team)
        r = rows.get(t)
        if not r:
            return f"{t} has no completed game in {season} {span_of(weeks)}"
        span = span_of(r["_weeks"])
        out = [f"{t} offence, {season} {span} "
               f"({int(float(r['plays']))} pass+rush plays)"]
        for key, label, fmt, note in TC_FIELDS:
            v, pct, rk = r.get(key), r.get(f"{key}_pctl"), r.get(f"{key}_rk")
            if v in ("", None):
                continue
            out.append((f"  {label:11} {fmt.format(float(v)):>7}"
                        + (f"   p{int(pct):<3}" if pct not in ("", None) else "       ")
                        + (f" rk {int(float(rk)):>2}/32" if rk not in ("", None) else "")
                        + (f"   {note}" if note else "")).rstrip())
        out.append("  p = percentile of the raw value among 2021-2025 team-games "
                   "(so higher = better except where marked); rk = within that week"
                   if len(r["_weeks"]) == 1 else
                   "  pooled rates carry no percentile or rank: both are per team-game")
        return _with_stale(season, "\n".join(out))
    ranked = sorted(rows.values(),
                    key=lambda r: float(r["epa_pass"] if r["epa_pass"] not in ("", None) else -99),
                    reverse=True)
    ends = {r["_weeks"][-1] for r in rows.values()}
    if week:
        head = span_of(weeks)
    elif len(ends) == 1:
        head = span_of(next(iter(rows.values()))["_weeks"]) if single else f"last {last} games per team"
    else:
        head = (f"each team's latest {'game' if single else f'{last} games'} "
                f"(through week {max(ends)}; wk = the team's latest week on file)")
    out = [(f"{season} {head} offences, by EPA per dropback "
            + ("(p = percentile vs 2021-2025 team-games)" if single else "")).rstrip(),
           f"  {'tm':4} {'passEPA':>8} {'rush EPA':>9} {'PROE':>7} {'CPOE':>6} {'plays':>6}"
           + ("  wk" if len(ends) > 1 else "")]
    for r in ranked:
        def value(key, fmt):
            v = r.get(key)
            return fmt.format(float(v)) if v not in ("", None) else "n/a"
        pp = f" p{int(r['epa_pass_pctl']):<3}" if r.get("epa_pass_pctl") else ""
        rp = f" p{int(r['epa_rush_pctl']):<3}" if r.get("epa_rush_pctl") else ""
        out.append(f"  {r['team']:4} {value('epa_pass', '{:+7.2f}')}{pp}"
                   f" {value('epa_rush', '{:+6.2f}')}{rp}"
                   f" {value('proe', '{:+6.1f}')} {value('cpoe', '{:+6.1f}')}"
                   f" {int(float(r['plays'])):>5}"
                   + (f"  {r['_weeks'][-1]}" if len(ends) > 1 else ""))
    return _with_stale(season, "\n".join(out))


@mcp.tool()
def target_share(team: str = "", player: str = "", position: str = "", last: int = 0,
                 flagged_only: bool = False, min_share: float = -1, season: int = 0,
                 format: str = "text") -> str:
    """Target share by week, absences and vacated share. Ask narrowly: the
    whole-league detail is too big to read at once.

    - no team/player: one line per team — its top 3 target earners (share
      when active) and any flagged player with the share he vacates.
      flagged_only=True keeps only teams with a flag ("whose injuries left
      targets?"). position= (WR/TE/RB) filters both lists.
    - team="LA": that team's table — per player targets, share and snap %
      by week, share over all weeks and when active, latest report, flags.
    - player="Name,Name": those players' rows, whatever their team.

    A flag means a real role (>=10% when active) and no usage in the team's
    latest week, or Out/Doubtful on the latest report; vacated share sums
    those players' share when active. last=N keeps the N most recent usage
    weeks (0 = all). min_share hides minor players (default 0 for a team,
    0.10 otherwise); totals and flags still count them. format="json" returns
    the one-team structure as JSON. For any other cut (a week range, a share
    threshold, a join with snaps) use query_data on tables `targets` and
    `vacated` instead of asking for everything.

    Saved nflverse play-by-play and weekly injury reports, not a live feed:
    a missing week can be a bye or an unplayed game; no usage is not a
    confirmed inactive. Current status comes from injury_check. Vacated
    share is opportunity freed up, not a forecast of who absorbs it.
    """
    import target_share as ts
    season = season or _state()[0]
    code = norm_team(team) if team else ""
    pos = position.upper()
    if min_share < 0:
        min_share = 0.0 if (code or player) else 0.10
    result = ts.load(DATA, season, code, last, min_share)
    if not result["teams"]:
        return (f"no target data on file for {season}"
                + (f" {code}" if code else "")
                + "; run refresh_week() after games are played")
    if code:
        if format == "json":
            return json.dumps(result, indent=1)
        text = ts.team_text(code, result["teams"][code], pos, result["injury_report_week"])
    elif player:
        text = ts.players_text(result, [n for n in player.split(",") if n.strip()], _norm_name)
    else:
        text = ts.league_text(result, pos, flagged_only)
    return _with_stale(season, text)


def _week_range(spec: str, default_first: int, default_last: int) -> tuple[int, int]:
    """'5' -> (5, 5); '4-9' -> (4, 9); '' -> defaults."""
    spec = (spec or "").strip()
    if not spec:
        return default_first, default_last
    a, _, b = spec.partition("-")
    first, last = int(a), int(b or a)
    if not (1 <= first <= last <= 18):
        raise ValueError("weeks must look like '5' or '4-9' within 1-18")
    return first, last


@mcp.tool()
def schedule(team: str = "", weeks: str = "", week: int = 0, season: int = 0) -> str:
    """NFL schedule and results from the saved nflverse schedule. No network.

    team="MIA": that team's weeks (default all 18; weeks="4-9" narrows) with
    opponent, home/away, kickoff (ET), roof, final score if played, byes,
    and implied points for and against — from the posted line when there is
    one, else labelled as the August preseason team-strength prior. Answers
    "who does X play", "what was the score", "bye week", "good matchups
    ahead". No team: one week's slate with scores and byes (week= or the
    current week).
    """
    import schedule_view
    if team:
        season = season or _state()[0]
        first, last = _week_range(weeks, 1, 18)
        return schedule_view.team_text(season, norm_team(team), first, last)
    season, week = _week(week, season)
    return schedule_view.week_text(season, week)


@mcp.tool()
def depth_chart(team: str, position: str = "", league_status: bool = True) -> str:
    """One NFL team's depth chart (latest saved ESPN snapshot) with each
    player's season usage and, by default, who owns him in this fantasy
    league — "who backs up X", "do they have another TE", "are his backups
    available".

    position: QB/RB/WR/TE to narrow. Usage columns: games, carries and
    targets per game, target share when active and last week's snap %.
    league_status=False skips the one ESPN read. "available" means on no
    league roster (free agent or on waivers). Depth charts lag real usage;
    snaps and targets show who actually plays.
    """
    season, week = _state()
    t = norm_team(team)
    pos = position.upper()
    rows = [r for r in _read_csv(DATA / f"depth_{season}.csv")
            if r["team"] == t and (not pos or r["pos_abb"] == pos)]
    if not rows:
        return f"no saved depth chart rows for {t}{' ' + pos if pos else ''}; refresh_week() rebuilds it"
    latest = max(r["dt"] for r in rows)
    rows = sorted((r for r in rows if r["dt"] == latest),
                  key=lambda r: ("QB RB WR TE".find(r["pos_abb"]), int(r["pos_rank"])))
    opp = _opportunity(season)
    usage: dict[str, list[dict]] = {}
    for u in _read_csv(DATA / f"advanced_usage_{season}_weekly.csv"):
        usage.setdefault(u["player_id"], []).append(u)
    owners, note = {}, None
    if league_status:
        try:
            lg = _league(season)
            names = {tm["id"]: tm["name"] for tm in lg.settings()["teams"]}
            for tid, roster in lg.rosters(week).items():
                for p in roster:
                    owners[_norm_name(p["name"])] = names.get(tid, str(tid))
        except Exception as e:  # noqa: BLE001 - league status is optional here
            note = f"league status unavailable ({type(e).__name__})"
    out = [f"{t} depth chart (ESPN snapshot {latest[:16]}Z)"
           + ("" if not league_status or note else "; owner = fantasy team holding him")]
    for r in rows:
        o = opp.get(r["gsis_id"]) or {}
        us = sorted(usage.get(r["gsis_id"], []), key=lambda u: int(u["week"]))
        snap = next((float(u["snap_share"]) for u in reversed(us)
                     if u.get("snap_share") not in ("", None)), None)
        tgt = sum(float(u["tgt"] or 0) for u in us)
        team_t = sum(float(u["team_targets"] or 0) for u in us)
        use = (f"g {int(o.get('games') or 0)}  car/g {o.get('rush_att_pg') or 0:.1f}  "
               f"tgt/g {o.get('tgt_pg') or 0:.1f}  share {tgt / team_t:.2f}" if o and team_t else
               f"g {int(o.get('games') or 0)}  car/g {o.get('rush_att_pg') or 0:.1f}" if o else "no usage this season")
        if snap is not None:
            use += f"  last snap {snap:.0%} (wk{us[-1]['week']})"
        owner = ""
        if league_status and not note:
            owner = "  owner: " + owners.get(_norm_name(r["player_name"]), "available")
        out.append(f"  {r['pos_abb']}{r['pos_rank']:<2} {r['player_name'][:24]:24} {use}{owner}")
    if note:
        out.append(f"  {note}")
    return _with_stale(season, "\n".join(out))


@mcp.tool()
def data_tables(table: str = "", match: str = "") -> str:
    """List the saved data tables query_data can read, or one table's columns.

    No table: every table with a one-line description (usage, targets,
    vacated, opportunity_weekly, opportunity, stats 2021+, schedule, lines,
    depth, injuries, snaps, team_context, players, pbp and pbp_<year>).
    table="pbp", match="air": only columns containing "air" (pbp has ~370).
    Each description ends with an example query.
    """
    import datastore
    return datastore.describe(_state()[0], table, match)


@mcp.tool()
def query_data(sql: str, limit: int = 50, season: int = 0) -> str:
    """Read-only SQL over the saved weekly data: the way to answer a
    question no other tool summarises without writing a scratch script or
    loading whole files.

    One SELECT (or WITH ... SELECT) in polars SQL; tables and columns from
    data_tables(). Returns at most `limit` rows (max 200) as CSV text, cut
    at 12,000 characters — select the columns you need and aggregate
    (GROUP BY, SUM, AVG) rather than pulling raw rows. Examples:
      target share of one team's TEs by week:
        SELECT week, name, targets, share FROM targets WHERE team='PIT' AND pos='TE'
      a player's past seasons:
        SELECT season, SUM(targets), SUM(receiving_yards) FROM stats
        WHERE player_display_name='Darnell Washington' AND season_type='REG' GROUP BY season
      receiver usage by quarterback:
        SELECT passer_player_name, receiver_player_name, COUNT(*) FROM pbp
        WHERE posteam='NYG' AND pass_attempt=1 GROUP BY 1, 2 ORDER BY 3 DESC
    Files only, no network; nothing can be written. season selects the
    season-scoped tables (default current); stats and pbp_<year> cover
    earlier seasons.
    """
    import datastore
    return datastore.query(season or _state()[0], sql, limit)


@mcp.tool()
def findings(topic: str) -> str:
    """Search this repo's own research for a topic ("opportunity
    regression", "kicker", "td luck", "defense implied total"): numbered
    league-sim findings with their confidence, and research/ studies, with
    paths to read. Read the file before quoting a number; its latest
    correction or audit section overrides the index line.
    """
    import findings_index
    return findings_index.search(topic)


@mcp.tool()
def fantasypros_rankings(position: str = "RB", week: int = 0, top: int = 30) -> str:
    """FantasyPros expert consensus (ECR) and tiers for the week.

    position: QB, RB, WR, TE, K, DST, or FLX for the cross-position flex
    ranking. Tiers come from the keyless fftiers feed; with a
    FANTASYPROS_API_KEY the paid API fills the same file instead and
    supplies a start/sit grade but no tiers.

    Tiers group nearby expert ranks; they are not calibrated win
    probabilities or proof of a performance gap. A high sd or a tier
    disagreement is a cue to inspect the relevant usage and news.
    """
    season, week = _week(week)
    pos = position.upper()
    rows = [r for r in _read_csv(DATA / f"ecr_{week_key(season, week)}.csv") if r["pos"] == pos]
    if not rows:
        return (f"no ECR on file for {pos} in {season} week {week}; run refresh_week() "
                "(no API key needed, the fftiers fallback is keyless)")
    rows.sort(key=lambda r: float(r["rank_ecr"] or 999))
    src = rows[0].get("source") or "fantasypros API"
    out = [f"FantasyPros ECR {season} week {week} {pos} (via {src}); "
           f"{len(rows)} ranked, showing {min(top, len(rows))}"]
    tier = None
    for r in rows[:top]:
        if r.get("tier") and r["tier"] != tier:
            tier = r["tier"]
            out.append(f"  -- tier {tier} --")
        # fftiers supplies only the opponent for skill players. An unlabeled
        # abbreviation after a blank team was being read as the player's club.
        out.append(f"  {r['rank_ecr']:>3} {r['name']:24} "
                   f"team={r['team'] or 'unknown'} opp={r['opp'] or 'unknown'} "
                   f"range {r['rank_min']}-{r['rank_max']} sd {r['rank_std']} {r.get('start_sit_grade') or ''}".rstrip())
    return "\n".join(out)


@mcp.tool()
def subvertadown_rankings(position: str = "FLEX", top: int = 40, names: str = "",
                          refresh: bool = False) -> str:
    """Subvertadown's weekly RB/WR/TE rankings and projected points: one
    model's projection, a second opinion beside the FantasyPros consensus.

    SCORING: Subvertadown's page is 0.5 PPR and this league is STANDARD.
    Compare ranks, not points; his points run higher than a standard
    projection, most for pass-catching backs, slot WRs and TEs.

    position: FLEX (default), RB, WR or TE. names: comma-separated players
    to look up (e.g. "Stefon Diggs,Jameson Williams"); a name he does not
    list is outside his top ~150, which is itself an answer. Cached for six
    hours; refresh=True refetches. Members-only content for personal use:
    never commit, publish or quote it anywhere public.
    """
    import subvertadown
    season, week = _state()
    try:
        data = subvertadown.load(season, week, refresh=refresh)
    except Exception as e:  # noqa: BLE001 - report, do not crash the server
        return f"Subvertadown unavailable: {e}"
    pos = position.upper()
    key = "rank_flex" if pos == "FLEX" else "rank_pos"
    rows = [r for r in data["rows"] if pos == "FLEX" or r["pos"] == pos]
    out = [f"Subvertadown {pos} {season} week {data['week']}, fetched {data['fetched_at']}",
           f"  NOTE: {subvertadown.SCORING_NOTE}"]
    if data.get("stale"):
        out.append(f"  STALE: {data['stale']}")

    def line(r):
        return (f"  {pos} {r[key]:>3}  {r['name']:24} {r['pos']:2} {r['team']}-{r['depth']} "
                f"{'vs' if r['home'] else '@ '} {r['opp'] or '?':3}  {r['points_half']:5.1f} (half-PPR)"
                + (f"  [FLEX {r['rank_flex']}]" if pos != "FLEX" else ""))

    if names:
        by = {_norm_name(r["name"]): r for r in rows}
        for n in (x.strip() for x in names.split(",") if x.strip()):
            r = by.get(_norm_name(n))
            out.append(line(r) if r else f"  {n}: not in his {pos} list (outside his top ~150)")
    else:
        out += [line(r) for r in sorted(rows, key=lambda r: r[key] or 999)[:top]]
    return "\n".join(out)


@mcp.tool()
def firstdown_rankings(position: str = "RB", top: int = 30, names: str = "") -> str:
    """First Down Studio's weekly projections built from sportsbook player
    props (yards, attempts, receptions, anytime-TD odds), in STANDARD
    scoring like this league: the betting market's view, a third opinion
    beside the FantasyPros consensus and our usage model.

    position: RB (default), WR, TE, QB, K or FLEX. names: comma-separated
    players to look up. A player missing from the list has no props posted
    (often an injury or a small role), which is not a low ranking.
    "not from props" marks stats First Down filled with its own estimate.

    Reads ONLY pages the user saved from their browser: First Down's terms
    forbid scrapers, so this never downloads anything. If it reports no
    save or a stale snapshot, ask the user to open
    https://www.firstdown.studio/rankings/rb and save it (Ctrl+S) into
    engine/weekly/cache/firstdown/ or ~/Downloads (Thursday evening and
    Sunday morning are enough). Personal use: never commit, publish or
    quote the table anywhere public.
    """
    import firstdown
    season, week = _state()
    try:
        data = firstdown.load(season, week)
    except Exception as e:  # noqa: BLE001 - report, do not crash the server
        return f"First Down unavailable: {e}"
    pos = position.upper()
    rows = firstdown.select(data["rows"], pos)
    out = [f"First Down Vegas-props {pos} {season} week {data['week']} (standard scoring), "
           f"snapshot generated {data['generated_at']}, from {data.get('source_file')}"]
    note = firstdown.freshness(data)
    if note:
        out.append(f"  STALE: {note}")
    if names:
        ranked = {_norm_name(r["name"]): (i, r) for i, r in enumerate(rows, 1)}
        for n in (x.strip() for x in names.split(",") if x.strip()):
            hit = ranked.get(_norm_name(n))
            out.append(firstdown.line(hit[1], hit[0]) if hit
                       else f"  {n}: not listed at {pos} (no props posted)")
    else:
        out += [firstdown.line(r, i) for i, r in enumerate(rows[:top], 1)]
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
    ir = s.get("ir_slots") or 0
    out.append(f"IR slots: {ir}" + ("" if ir else " — no IR: an injured player keeps a bench "
                                   "spot until dropped, so a season-ending injury is a drop question"))
    keepers = s.get("keeper_count")
    out.append("keepers: " + ("none (redraft)" if keepers == 0 else str(keepers) if keepers else "unknown"))
    if s.get("playoff_teams"):
        out.append(f"regular season: {s.get('regular_season_weeks')} weeks; playoffs: top "
                   f"{s['playoff_teams']} of {len(s['teams'])}, seeding/tiebreak "
                   f"{s.get('playoff_seeding')} (standings() shows the race)")
    if s.get("trade_deadline"):
        from datetime import datetime, timezone
        out.append("trade deadline: " + datetime.fromtimestamp(
            s["trade_deadline"] / 1000, timezone.utc).strftime("%Y-%m-%d"))
    return "\n".join(out)


@mcp.tool()
def standings() -> str:
    """League standings: W-L-T, points for/against, games back of the last
    playoff seed, the playoff format and tiebreak, and your remaining
    schedule with each opponent's record and scoring (live score for a
    matchup in progress). Records and schedule only: it does not compute a
    playoff probability, and none should be made up from it."""
    import standings as st
    season, _ = _state()
    lg = _league(season)
    s = lg.settings()
    return st.report(s, lg.schedule(), s["my_team_id"])


@mcp.tool()
def league_points(position: str = "", weeks: str = "", names: str = "",
                  available_only: bool = False, top: int = 20) -> str:
    """Actual fantasy points in THIS league's scoring, per week, from ESPN —
    the only tool with scored results for kickers and D/ST. Each row shows
    the owner (fantasy team, WAIVERS or free agent) and ownership %.

    position: QB, RB, WR, TE, K or DST (blank needs names). weeks: "1-3" or
    "3" (default: every week so far). names: comma-separated players.
    available_only=True keeps players on no roster ("top-scoring kickers on
    waivers"). One ESPN read per week, cached (finished weeks 12 hours).
    Past points describe what happened; finding 04 and 28 say early kicker
    scoring does not predict kicker scoring.
    """
    import league_points as lp
    import schedule_view
    season, state_week = _state()
    if not position and not names:
        raise ValueError("give a position (QB/RB/WR/TE/K/DST) or names")
    first, last = _week_range(weeks, 1, state_week)
    done = set(schedule_view.completed_weeks(season))
    lg = _league(season)
    return lp.report(lg, lg.settings(), season, list(range(first, last + 1)), position, names,
                     available_only, top, open_weeks={w for w in range(first, last + 1) if w not in done})


@mcp.tool()
def power_rankings(week: int = 0) -> str:
    """Every team in the league ranked by roster strength: the best
    lineup by season value (no matchup or injury term), bench depth,
    this week's optimal projection, record and points scored so far."""
    import power_rankings as pr
    season, week = _week(week)
    return (pr.report(pr.league_rankings(season, week))
            + "\nRoster strength and projections, not a chance of winning: a point "
              "lead is not a win probability. standings() has the playoff race.")


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
    out.append(f"current starters total proj: {sum(p['proj'] for p in starters):.1f} "
               "(a projection gap is not a win probability)")
    return "\n".join(out)


@mcp.tool()
def team_roster(team_id: int, week: int = 0) -> str:
    """Read any league team's roster and legal optimal lineup using the same model as yours.

    Get team_id from league_settings. Current live roster, not a historical
    roster reconstruction. Pass the decision week explicitly. Retains locks;
    exposes bench alternatives, projections and injury tags. No win probability,
    proposal token or ESPN write. Verify injuries with practice_report.
    """
    season, week = _week(week)
    lg, settings, attach = projector(season, week)
    teams = {t['id']: t['name'] for t in settings['teams']}
    if team_id not in teams:
        raise ValueError("Unknown team_id; read league_settings first")
    rosters = lg.rosters(week)
    if team_id not in rosters:
        raise ValueError("Requested team's roster is unavailable")
    roster = [attach(p) for p in rosters[team_id]]
    current = sum(p['proj'] for p in roster if p.get('slot') not in (20, 21))
    res = advisor.optimal_lineup(roster, settings['slots'])
    out = [f"{teams[team_id]} — {season} decision week {week}, {settings['scoring_format']}; "
           f"live roster read {now_iso()}",
           "ESPN injury tags may lag; confirm current official status with practice_report.",
           f"Current starters: {current:.1f} projected points; legal optimal: {res['total']:.1f}",
           "Current roster:"]
    out += [_fmt_player(p) for p in roster]
    out.append("Legal optimal starters (locks retained):")
    out += [f"  {ESPN_SLOTS.get(slot, slot)}: {p['name']} ({p['proj']:.1f})" if p
            else f"  {ESPN_SLOTS.get(slot, slot)}: empty" for slot, p in res['starters']]
    out += advisor.timing_note(res['starters'])
    out.append("Point totals are not a calibrated chance of winning. No changes made.")
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
    timing = advisor.timing_note(res["starters"])
    if timing:
        out.append("open slots hold the latest kickoffs (same points, more room to "
                   "replace a late scratch):")
        out += timing
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
        out += [f"  {m['name']}: {m['from']} -> {m['to']}"
                + ("  (slot timing only, no points change)" if m.get("timing") else "")
                for m in res["moves"]]
        out.append(f"apply with apply_lineup(token='{token}', confirmed=True) after the user approves")
    else:
        out.append("no moves: the current lineup is already optimal")
    return "\n".join(out)


def _availability(lg, settings: dict, fas: list[dict], week: int, names: list[str]) -> list[str]:
    """One line per asked name: free agent / waivers / rostered by whom."""
    teams = {t["id"]: t["name"] for t in settings["teams"]}
    rostered = {}
    for tid, roster in lg.rosters(week).items():
        for p in roster:
            rostered.setdefault(_norm_name(p["name"]), (tid, p))
    by_name = {_norm_name(p["name"]): p for p in fas}
    out = []
    for raw in names:
        n = _norm_name(raw)
        hit = by_name.get(n) or next((p for k, p in by_name.items() if n in k), None)
        own = rostered.get(n) or next((v for k, v in rostered.items() if n in k), None)
        if own:
            tid, p = own
            mine = "  (your team)" if tid == settings["my_team_id"] else ""
            out.append(f"  {p['name']:24} {p['pos']:3} {p['team'] or '?':4} id={p['id']}  ROSTERED by "
                       f"{teams.get(tid, tid)}{mine}")
        elif hit:
            out.append("  " + _fmt_player(hit) + f"  own {hit['pct_owned']}%  "
                       + ("ON WAIVERS (claim)" if hit.get("waiver") else "FREE AGENT (add now)"))
        else:
            out.append(f"  {raw}: on no league roster, but not in ESPN's top-300 available pool "
                       "(a deep free agent, or the name is spelled differently)")
    return out


@mcp.tool()
def free_agents(position: str = "", top: int = 25, week: int = 0, names: str = "") -> str:
    """Available players (free agents + waivers) with value and this
    week's projection; hottest adds by ownership change listed first.

    names="A,B,C": check those players instead — free agent, on waivers,
    or rostered and by which fantasy team — with ESPN ids for
    propose_transaction. Each row carries id=... for the same purpose."""
    season, week = _week(week)
    if names:
        lg, s, _, fas = _projected_roster(season, week)
        asked = [n.strip() for n in names.split(",") if n.strip()]
        return "\n".join([f"week {week} availability ({s['scoring_format']})"]
                         + _availability(lg, s, fas, week, asked))
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
    if not s.get("ir_slots"):
        out.append("league has no IR slot: a player out for the season holds a bench spot "
                   "until dropped, which is why he can appear as a drop candidate")
    return "\n".join(out)


def _pick(pool: list[dict], name: str) -> tuple[dict | None, str | None]:
    n = _norm_name(name)
    exact = [p for p in pool if _norm_name(p["name"]) == n]
    hits = exact or [p for p in pool if n in _norm_name(p["name"])]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, "no match"
    return None, "ambiguous: " + ", ".join(f"{p['name']} ({p['pos']} {p['team']}, id={p['id']})"
                                           for p in hits[:5])


@mcp.tool()
def propose_transaction(add_id: int = 0, drop_id: int = 0, bid: int = -1, week: int = 0,
                        add_name: str = "", drop_name: str = "") -> str:
    """Preview an add (and optional drop) exactly as it would be sent to
    ESPN, and get the question to put to the user plus a token. Does
    not send anything.

    Name the players (add_name / drop_name, matched against the available
    pool and your roster) or pass ESPN ids (id=... in free_agents,
    my_roster and waiver_recommendations)."""
    season, week = _week(week)
    lg, s, roster, fas = _projected_roster(season, week)
    if add_name and not add_id:
        add, why = _pick(fas, add_name)
        if add is None:
            return (f"{add_name!r}: {why} in the available pool; free_agents(names=...) shows "
                    "whether he is rostered")
        add_id = add["id"]
    if drop_name and not drop_id:
        drop, why = _pick(roster, drop_name)
        if drop is None:
            return f"{drop_name!r}: {why} on your roster"
        drop_id = drop["id"]
    if not add_id:
        return "name the player to add (add_name=...) or pass add_id"
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
