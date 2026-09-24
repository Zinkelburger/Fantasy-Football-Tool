#!/usr/bin/env python3
"""ff-weather: hourly weather for any place and for every NFL game.

    weather       a place (city, "City, ST", team, stadium, or "lat,lon"),
                  hour by hour from now, a date, or a local time
    game_weather  every game in a week (or one team's), kickoff to final
                  whistle at the venue, with wind/rain/cold/heat flags
    stadium       the committed venue map: coordinates, time zone, roof

NWS for US points within ~6.5 days, Open-Meteo otherwise; no API keys.
Venues come from stadiums.json, so a game is never geocoded. Weather is
context only; no ranking or projection in this repo uses it.

Registered in .mcp.json as "ff-weather" (engine/mcp_launch.sh weather).
Run by hand:  .venv-league-sim/bin/python engine/weather/mcp_server.py
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer

import weather as W

mcp = MCPServer("ff-weather", version="1.0.0")
UTC = timezone.utc


def _window(start: str, hours: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """"" -> now; "2026-09-27" -> that local day; "2026-09-27 13:00" or
    "2026-09-27T13:00" -> that local hour. hours=0 means 12 from now, or the
    whole day for a date."""
    s = start.strip()
    if not s:
        begin = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        return begin, begin + timedelta(hours=hours or 12)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        begin = datetime.fromisoformat(s).replace(tzinfo=tz)
        return begin, begin + timedelta(hours=hours or 24)
    begin = datetime.fromisoformat(s.replace(" ", "T"))
    begin = begin if begin.tzinfo else begin.replace(tzinfo=tz)
    return begin, begin + timedelta(hours=hours or 12)


@mcp.tool()
def weather(place: str, start: str = "", hours: int = 0, source: str = "auto") -> str:
    """Hourly weather for a place.

    place: "Green Bay, WI", "London", "Buffalo NY", a team ("GB",
    "Packers"), a stadium ("Lambeau Field"), or "44.50,-88.06".
    start: "" for now, "YYYY-MM-DD" for that local day, or
    "YYYY-MM-DD HH:MM" in the place's local time. Past dates work (recent
    ones from the forecast model, older ones from the reanalysis archive).
    hours: how many hours (default 12 from now, 24 for a date; max 168).
    source: auto (NWS for US points within ~6.5 days, else Open-Meteo),
    nws, or open-meteo.
    """
    p = W.resolve_place(place)
    tz = ZoneInfo(p["tz"]) if p.get("tz") else UTC
    begin, end = _window(start, min(max(hours, 0), 168), tz)
    src, issued, rows = W.hours(p["lat"], p["lon"], begin, end, p.get("us"), source)
    if not rows:
        return f"{p['name']}: no hourly data for {begin:%Y-%m-%d %H:%M} to {end:%H:%M}"
    head = [f"{p['name']}  ({p['lat']:.4f}, {p['lon']:.4f}, {tz.key})",
            f"source: {src}" + (f", issued {issued}" if issued else "")]
    if p.get("roof") == "fixed":
        head.append("note: fixed roof; the field is indoors, weather does not reach play")
    elif p.get("roof") == "retractable":
        head.append("note: retractable roof; usually closed in bad weather")
    s = W.summarise(rows)
    head.append("summary: " + W.fmt_summary(s)
                + (f"  FLAGS: {', '.join(s['flags'])}" if s["flags"] else ""))
    return "\n".join(head + W.fmt_rows(rows, tz, 1 if len(rows) <= 48 else 3))


@mcp.tool()
def game_weather(week: int = 0, team: str = "", season: int = 0) -> str:
    """Weather at every NFL game in a week, kickoff to about 3.5 hours after,
    at the venue's own coordinates and local time.

    week/season 0 = the current NFL week. team: an abbreviation (GB) to show
    just that team's game. Fixed-roof venues are marked indoors and not
    fetched. Flags (wind >= 15 mph, gusts >= 25, rain likely, <= 32F,
    >= 90F) are for reading only; no ranking in this repo adjusts for them.
    """
    cur_season, cur_week = W.current_week()
    season, week = season or cur_season, week or cur_week
    games = W.week_games(season, week)
    if team:
        t = team.strip().upper()
        games = [g for g in games if t in (g["away"], g["home"])]
        if not games:
            return f"no {t} game in {season} week {week} (bye?)"
    out = [f"{season} Week {week} game weather, fetched "
           f"{datetime.now(UTC):%Y-%m-%d %H:%M}Z. Kickoffs ET; window local."]
    for g in games:
        v = g["venue"]
        k = g["kickoff"]
        line = f"{g['away']:>3} @ {g['home']:<3} {k:%a %m-%d %H:%M} ET  "
        if not v:
            out.append(line + f"unmapped venue {g['raw_stadium']!r}: add it to stadiums.json")
            continue
        vtz = ZoneInfo(v["tz"])
        line += f"{v['name']}, {v['city']}"
        if v["roof"] == "fixed":
            out.append(line + "  | indoors (fixed roof)")
            continue
        end = k + timedelta(hours=W.GAME_HOURS)
        try:
            src, _, rows = W.hours(v["lat"], v["lon"], k, end, W.is_us(v["tz"]))
        except LookupError as e:
            out.append(line + f"  | no forecast yet ({e})")
            continue
        except Exception as e:  # noqa: BLE001 - one venue failing is not fatal
            out.append(line + f"  | fetch failed: {e}")
            continue
        if not rows:
            out.append(line + "  | no hourly data")
            continue
        s = W.summarise(rows)
        roof = " [retractable roof: likely closed if bad]" if v["roof"] == "retractable" else ""
        sky = sorted({r["sky"] for r in rows if r["sky"]}, key=[r["sky"] for r in rows].index)
        out.append(line + f" ({k.astimezone(vtz):%H:%M} local){roof}\n"
                   f"      {W.fmt_summary(s)}; {' / '.join(sky[:3])}"
                   f"  [{src.split(' (')[0]}]"
                   + (f"\n      FLAGS: {', '.join(s['flags'])}" if s["flags"] else ""))
    return "\n".join(out)


@mcp.tool()
def stadium(query: str = "") -> str:
    """The committed venue map. No query: every venue (id, name, city, roof,
    home teams). query: a team, stadium name or nflverse stadium_id."""
    if query:
        hit = W.find_stadium(query)
        if not hit:
            return f"no venue matches {query!r}"
        sid, s = hit
        return (f"{sid}  {s['name']}, {s['city']}\n  lat {s['lat']}, lon {s['lon']}, "
                f"tz {s['tz']}, roof {s['roof']}, home {', '.join(s['home']) or '(neutral site)'}"
                + (f"\n  also known as: {', '.join(s['aliases'])}" if s["aliases"] else ""))
    rows = [f"{sid:<6} {s['roof']:<11} {','.join(s['home']) or '-':<7} {s['name']}, {s['city']}"
            for sid, s in sorted(W.stadiums().items(), key=lambda kv: (not kv[1]['home'], kv[0]))]
    return "\n".join(["id     roof        home    venue"] + rows)


if __name__ == "__main__":
    mcp.run()
