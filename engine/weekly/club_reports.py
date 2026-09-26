"""Official club-site reports: the daily practice grid, transactions,
and the team-published depth chart, straight from each team's own site.

Every NFL club runs the same league CMS, but some publish their own report
only in a news article. Start with the shared page shapes:

    https://<club host>/team/injury-report/week/REG-<week>
    https://<club host>/team/transactions/
    https://<club host>/team/depth-chart

Missing teams fall back to official injury-report articles discovered in the
club's RSS feed, checked against the requested matchup and publication date.
These pages are server-rendered HTML with no key or login and carry two
things nflverse's weekly injury
table does not: each practice day in its own column (so a Wed DNP that
becomes a Thu LP is visible the moment it posts) and the club's own depth
chart. nflverse remains the source of record for the season-long report;
this module is what to call mid-week when a Thursday or Friday update
decides a lineup.

Timing: clubs post the day's report in the late afternoon ET. Sunday games
usually report Wed/Thu/Fri; Thursday games Mon/Tue/Wed and Monday games
Thu/Fri/Sat. Empty later columns mean "not posted yet". The final report brings the game-status
designation (Out / Doubtful / Questionable); "UNSPECIFIED" means the club
has not designated yet, not that the player is fine.

Output: data/weekly/club_injuries_<season>_wk<NN>.csv plus a .sources.json
recording what each fetch returned, in the shape build_week.py uses.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import polars as pl

from common import DATA, TEAMS, nfl_state, norm_team, now_iso

# nflverse abbreviation -> club site host.
CLUB_HOSTS = {
    "ARI": "www.azcardinals.com", "ATL": "www.atlantafalcons.com",
    "BAL": "www.baltimoreravens.com", "BUF": "www.buffalobills.com",
    "CAR": "www.panthers.com", "CHI": "www.chicagobears.com",
    "CIN": "www.bengals.com", "CLE": "www.clevelandbrowns.com",
    "DAL": "www.dallascowboys.com", "DEN": "www.denverbroncos.com",
    "DET": "www.detroitlions.com", "GB": "www.packers.com",
    "HOU": "www.houstontexans.com", "IND": "www.colts.com",
    "JAX": "www.jaguars.com", "KC": "www.chiefs.com",
    "LA": "www.therams.com", "LAC": "www.chargers.com",
    "LV": "www.raiders.com", "MIA": "www.miamidolphins.com",
    "MIN": "www.vikings.com", "NE": "www.patriots.com",
    "NO": "www.neworleanssaints.com", "NYG": "www.giants.com",
    "NYJ": "www.newyorkjets.com", "PHI": "www.philadelphiaeagles.com",
    "PIT": "www.steelers.com", "SEA": "www.seahawks.com",
    "SF": "www.49ers.com", "TB": "www.buccaneers.com",
    "TEN": "www.tennesseetitans.com", "WAS": "www.commanders.com",
}

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0 Safari/537.36")
SKILL = ("QB", "RB", "WR", "TE", "K", "FB")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# The league CDN's logo codes differ from nflverse for one team.
LOGO_ALIASES = {"AZ": "ARI"}


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _parse_table(tbl: str) -> tuple[list[str], list[list[str]]]:
    """One <table> as (header cells, body rows). The club CMS renders plain
    <thead>/<tbody> tables, so this is all the parsing needed."""
    head = re.search(r"<thead.*?</thead>", tbl, re.S)
    headers = ([_text(c) for c in
                re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", head.group(0), re.S)]
               if head else [])
    rows = []
    body = re.search(r"<tbody.*?</tbody>", tbl, re.S)
    for tr in re.findall(r"<tr.*?</tr>", (body.group(0) if body else tbl), re.S):
        cells = [_text(c) for c in
                 re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if cells and any(cells):
            rows.append(cells)
    return headers, rows


def _tables(page: str) -> list[tuple[list[str], list[list[str]]]]:
    return [_parse_table(t) for t in re.findall(r"<table.*?</table>", page, re.S)]


def _labelled_tables(page: str) -> list[tuple[str | None, tuple[list[str], list[list[str]]]]]:
    """Each table paired with the club it belongs to. The CMS puts the club
    logo and name immediately before its table:

        .../clubs/logos/BAL" ... <span class="...__club-name">Baltimore Ravens</span>
    """
    labels = [(m.start(), LOGO_ALIASES.get(m.group(1), norm_team(m.group(1))))
              for m in re.finditer(r"clubs/logos/([A-Z]{2,3})\b", page)]
    out = []
    for m in re.finditer(r"<table.*?</table>", page, re.S):
        before = [abbr for pos, abbr in labels if pos < m.start()]
        out.append((before[-1] if before else None, _parse_table(m.group(0))))
    return out


def injury_report(team: str, week: int, season_type: str = "REG") -> list[dict]:
    """The practice grid on one club's page. Columns are Player, Position,
    Injury, Wed, Thu, Fri, Game Status; practice cells are FP / LP / DNP,
    and blank means that day has not posted yet.

    A club's page carries the official report for *both* teams in its game,
    one table per club, so every row is attributed from the table's own
    club label rather than from whose site it is. That also means the 32
    hosts cover each team twice: if one club's site is down, its opponent's
    page still has the table.
    """
    host = CLUB_HOSTS[team]
    url = f"https://{host}/team/injury-report/week/{season_type}-{week}"
    page = _get(url)
    return [row for owner, (headers, body) in _labelled_tables(page)
            for row in _injury_rows(headers, body, owner or team, team, week, url)]


def _injury_rows(headers, body, owner, page_team, week, url):
    """Shared schema for the CMS grid and the club's news-article tables."""
    aliases = {"name": "player", "pos": "position", "game statis": "game status"}
    aliases.update({full: short for full, short in zip(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"), DAYS)})
    keys = [aliases.get(h.lower().strip(), h.lower().strip()) for h in headers]
    if "player" not in keys or not any(k in DAYS for k in keys):
        return []
    rows = []
    for cells in body:
        row = dict(zip(keys, cells))
        if not row.get("player"):
            continue
        name, pos = row["player"], row.get("position", "").strip()
        if not pos and "," in name:
            name, _, pos = name.rpartition(",")
            name, pos = name.strip(), pos.strip()
        status = (row.get("game status") or "").strip()
        rows.append({
            "team": owner, "week": week, "player": name, "position": pos,
            "injury": row.get("injury", ""),
            **{day: row.get(day, "") for day in DAYS},
            "practice_days": ",".join(k for k in keys if k in DAYS),
            "game_status": "" if status.upper() in ("UNSPECIFIED", "(-)", "-") else status,
            "page_team": page_team, "source": url,
            "source_kind": "club_grid", "published_at": "",
        })
    return rows


def parse_article(page: str, team: str, week: int, url: str) -> list[dict]:
    """Article tables need their own team heading, never a navigation logo.

    Saints use Name and full weekday names; Jets also have an opponent's
    table. Only return the requested club, with explicit heading attribution.
    """
    owner = None
    rows = []
    for match in re.finditer(r"<h[1-4]\b[^>]*>.*?</h[1-4]>|<table\b.*?</table>", page, re.S | re.I):
        fragment = match.group()
        if fragment.lower().startswith("<table"):
            if owner == team:
                headers, body = _parse_table(fragment)
                rows.extend(_injury_rows(headers, body, owner, team, week, url))
        else:
            label = _text(fragment).casefold()
            owner = next((abbr for abbr, nickname in TEAMS.items()
                          if label == nickname.casefold()
                          or label.endswith(" " + nickname.casefold())), None)
    for row in rows:
        row["source_kind"] = "club_article"
    return rows


def _game_schedule(season: int, week: int) -> dict:
    import nfl_data
    games = nfl_data.schedules(season).filter(
        (pl.col("game_type") == "REG") & (pl.col("week") == week))
    out = {}
    for game in games.iter_rows(named=True):
        for team, opp in ((game["home_team"], game["away_team"]),
                          (game["away_team"], game["home_team"])):
            out[team] = {"opponent": opp, "game_date": str(game["gameday"])}
    return out


def article_report(team: str, week: int, game: dict) -> tuple[list[dict], dict]:
    """Bounded fallback: current matchup's official RSS-linked injury reports.

    Check week, opponent, publication date and host before opening at most
    three articles. Never infer practice participation from narrative prose.
    """
    host = CLUB_HOSTS[team]
    rss_url = f"https://{host}/rss/news"
    meta = {"status": "not_found", "feed": rss_url, "articles": []}
    root = ET.fromstring(_get(rss_url))
    game_date = date.fromisoformat(game["game_date"])
    candidates = []
    for item in root.findall(".//item"):
        title, url = item.findtext("title") or "", item.findtext("link") or ""
        # Some clubs (including the Giants) put Week N only in the slug.
        identity = title + " " + urllib.parse.urlsplit(url).path.replace("-", " ").replace("_", " ")
        stated_weeks = {int(w) for w in re.findall(r"\bweek\s+(\d+)\b", identity, re.I)}
        if ("injury report" not in title.lower() or "preseason" in identity.lower()
                or stated_weeks != {week}
                or TEAMS[game["opponent"]].casefold() not in title.casefold()):
            continue
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != host or not parsed.path.startswith("/news/"):
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                continue
            report_date = published.astimezone(ZoneInfo("America/New_York")).date()
        except (ValueError, TypeError):
            continue
        if game_date - timedelta(days=6) <= report_date <= game_date:
            candidates.append((published, url))
    for published, url in sorted(set(candidates), reverse=True)[:3]:
        try:
            rows = parse_article(_get(url), team, week, url)
        except (urllib.error.URLError, TimeoutError) as exc:
            meta["articles"].append({"url": url, "status": "failed", "error": str(exc)})
            continue
        meta["articles"].append({"url": url, "status": "available" if rows else "unparsed",
                                 "published_at": published.isoformat(), "rows": len(rows)})
        if rows:
            for row in rows:
                row["published_at"] = published.isoformat()
            meta["status"] = "available"
            return rows, meta
    if candidates:
        meta["status"] = "unavailable"
    return [], meta


def coverage(teams, rows, sources, games, now=None):
    """Separate a late-game reporting window from missing/failed retrieval."""
    eastern = ZoneInfo("America/New_York")
    today = (now or datetime.now(eastern)).astimezone(eastern).date()
    out = {}
    for team in teams:
        own = [r for r in rows if r["team"] == team]
        info = {"status": "available" if own else "unavailable", "rows": len(own),
                "sources": sorted({r["source"] for r in own})}
        game = games.get(team)
        if game:
            game_day = date.fromisoformat(game["game_date"])
            # Thursday: Mon/Tue/Wed; Sun: Wed/Thu/Fri; Mon: Thu/Fri/Sat.
            lead = 3 if game_day.weekday() == 3 else 4
            first = game_day - timedelta(days=lead)
            info.update(game, expected_first_report_date=first.isoformat())
            retrieval = sources.get(team, {})
            fallback = retrieval.get("article_fallback", {})
            if (not own and today <= first and retrieval.get("status") != "failed"
                    and fallback.get("status") not in ("failed", "unavailable")):
                info["status"] = "pending"
                info["reason"] = "No report found yet; first practice report expected " + first.isoformat()
        elif games and not own:
            info["status"] = "not_scheduled"
        out[team] = info
    return out


def transactions(team: str) -> list[dict]:
    """The club's own transaction log, newest month first. Catches practice
    squad elevations and IR moves before they reach any aggregator."""
    host = CLUB_HOSTS[team]
    url = f"https://{host}/team/transactions/"
    page = _get(url)
    out: list[dict] = []
    for headers, body in _tables(page):
        month = headers[0] if headers else ""
        for cells in body:
            if len(cells) >= 2:
                out.append({"team": team, "month": month, "date": cells[0],
                            "text": cells[1], "source": url})
    return out


def depth_chart(team: str) -> list[dict]:
    """The club-published depth chart: position, then 1st/2nd/3rd/4th."""
    host = CLUB_HOSTS[team]
    url = f"https://{host}/team/depth-chart"
    page = _get(url)
    out: list[dict] = []
    for headers, body in _tables(page):
        keys = [h.lower() for h in headers]
        if "position" not in keys:
            continue
        for cells in body:
            row = dict(zip(keys, cells))
            pos = row.get("position", "")
            for rank, key in enumerate(("1st", "2nd", "3rd", "4th"), 1):
                name = (row.get(key) or "").strip()
                if name:
                    out.append({"team": team, "position": pos, "rank": rank,
                                "player": name, "source": url})
    return out


def report_path(season: int, week: int, teams: list[str] | None = None,
                skill_only: bool = False):
    """Filtered reads must not overwrite the complete league snapshot."""
    suffix = "_" + "-".join(sorted(set(teams))) if teams and set(teams) != set(CLUB_HOSTS) else ""
    if skill_only:
        suffix += "_skill"
    return DATA / f"club_injuries_{season}_wk{week:02d}{suffix}.csv"


def collect(season: int, week: int, teams: list[str] | None = None,
            skill_only: bool = False) -> tuple[pl.DataFrame, dict]:
    """Fetch reports and coverage without changing published/committed files."""
    if season != nfl_state()["season"]:
        raise ValueError("Club report URLs serve only the current season")
    teams = teams or list(CLUB_HOSTS)
    rows: list[dict] = []
    sources: dict[str, dict] = {}
    for team in teams:
        try:
            got = injury_report(team, week)
            rows.extend(got)
            sources[team] = {"status": "available" if got else "no_report",
                             "rows": len(got), "error": None,
                             "reported_teams": sorted({r["team"] for r in got})}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            sources[team] = {"status": "failed", "rows": 0, "error": str(e)}
    missing = set(teams) - {r["team"] for r in rows}
    games, schedule_error = {}, None
    if missing:
        try:
            games = _game_schedule(season, week)
        except Exception as exc:  # optional fallback cannot erase good grid rows
            schedule_error = str(exc)
        for team in sorted(missing):
            if team not in games:
                sources[team]["article_fallback"] = {
                    "status": "skipped", "reason": "No verified matchup for this week"}
                continue
            try:
                got, meta = article_report(team, week, games[team])
                rows.extend(got)
                sources[team]["article_fallback"] = meta
            except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
                sources[team]["article_fallback"] = {"status": "failed", "error": str(exc)}
    df = pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={"team": pl.Utf8, "week": pl.Int64, "player": pl.Utf8,
                "position": pl.Utf8, "injury": pl.Utf8,
                **{day: pl.Utf8 for day in DAYS}, "practice_days": pl.Utf8,
                "game_status": pl.Utf8,
                "page_team": pl.Utf8, "source": pl.Utf8,
                "source_kind": pl.Utf8, "published_at": pl.Utf8})
    if df.height:
        # Each table appears on both clubs' pages. Keep the copy with the
        # most practice days filled in, so a lagging host cannot hide a
        # Thursday update that the opponent's page already shows.
        df = (df.with_columns(
                  (pl.sum_horizontal([pl.col(day).str.len_chars().sign() for day in DAYS])
                   + pl.col("game_status").str.len_chars().sign()).alias("_filled"),
                  (pl.col("team") == pl.col("page_team")).alias("_own"))
              .sort(["team", "player", "_filled", "_own"],
                    descending=[False, False, True, True])
              .unique(subset=["team", "player"], keep="first", maintain_order=True)
              .drop("_filled", "_own"))
    # Coverage describes the report, even if a skill-only view removes all
    # of that team's rows (an all-defensive report is still a valid report).
    team_coverage = coverage(teams, df.to_dicts(), sources, games)
    if skill_only and df.height:
        df = df.filter(pl.col("position").str.to_uppercase().is_in(SKILL))
    if df.height:
        df = df.sort(["team", "position", "player"])
    manifest = {"season": season, "week": week, "generated_at": now_iso(),
                    "requested_hosts": teams, "skill_only": skill_only,
                    "missing_teams": sorted(t for t, c in team_coverage.items()
                                            if c["status"] in ("pending", "unavailable")),
                    "pending_teams": sorted(t for t, c in team_coverage.items() if c["status"] == "pending"),
                    "unavailable_teams": sorted(t for t, c in team_coverage.items() if c["status"] == "unavailable"),
                    "coverage": team_coverage, "schedule_error": schedule_error,
                    "teams": sources}
    return df, manifest


def build(season: int, week: int, teams: list[str] | None = None,
          skill_only: bool = False) -> pl.DataFrame:
    """Refresh the week's CSV and coverage manifest for the weekly build."""
    df, manifest = collect(season, week, teams, skill_only)
    out = report_path(season, week, teams, skill_only)
    df.write_csv(out)
    out.with_suffix(".sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return df


def latest_practice_day(row: dict) -> tuple[str, str]:
    """The most recent practice cell a club has filled in, as (day, value).
    Empty later columns mean "not posted yet", so read right to left."""
    days = (row.get("practice_days") or ",".join(DAYS)).split(",")
    for day in reversed(days):
        if (row.get(day) or "").strip():
            return day, row[day].strip()
    return "", ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("what", choices=["injuries", "transactions", "depth"])
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--team", default="", help="one team, else all 32")
    ap.add_argument("--skill-only", action="store_true")
    a = ap.parse_args()
    teams = [norm_team(a.team)] if a.team else None
    if teams and teams[0] not in CLUB_HOSTS:
        ap.error(f"unknown team: {a.team}")

    if a.what == "injuries":
        state = nfl_state()
        a.season, a.week = a.season or state["season"], a.week or state["week"]
        df = build(a.season, a.week, teams, a.skill_only)
        print(f"{df.height} rows -> {report_path(a.season, a.week, teams, a.skill_only)}")
        manifest = json.loads(report_path(a.season, a.week, teams, a.skill_only)
                              .with_suffix(".sources.json").read_text())
        for team, info in manifest["coverage"].items():
            if info["status"] != "available":
                print(f"{team}: {info['status']} — "
                      + info.get("reason", "See source manifest for retrieval details"))
        with pl.Config(tbl_rows=-1, fmt_str_lengths=28):
            print(df.drop("source") if df.height else df)
        return

    fetch = transactions if a.what == "transactions" else depth_chart
    for team in (teams or list(CLUB_HOSTS)):
        for row in fetch(team):
            print(" ".join(str(v) for k, v in row.items() if k != "source"))


if __name__ == "__main__":
    main()
