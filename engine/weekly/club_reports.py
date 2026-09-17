"""Official club-site reports: the daily practice grid, transactions,
and the team-published depth chart, straight from each team's own site.

Every NFL club runs the same league CMS, so one URL shape works for all 32:

    https://<club host>/team/injury-report/week/REG-<week>
    https://<club host>/team/transactions/
    https://<club host>/team/depth-chart

These pages are server-rendered HTML with no key, no login and no rate limit
worth worrying about, and they carry two things nflverse's weekly injury
table does not: each practice day in its own column (so a Wed DNP that
becomes a Thu LP is visible the moment it posts) and the club's own depth
chart. nflverse remains the source of record for the season-long report;
this module is what to call mid-week when a Thursday or Friday update
decides a lineup.

Timing: clubs post the day's report in the late afternoon ET, so Thursday's
column is empty until roughly 4pm ET. Friday brings the game-status
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

import polars as pl

from common import DATA, nfl_state, norm_team, now_iso

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
    rows: list[dict] = []
    for owner, table in _labelled_tables(page):
        headers, body = table
        keys = [h.lower() for h in headers]
        if "player" not in keys or not any(k in keys for k in DAYS):
            continue
        for cells in body:
            row = dict(zip(keys, cells))
            if not row.get("player"):
                continue
            status = (row.get("game status") or "").strip()
            # The opponent's table on a club page runs the position into the
            # name cell ("Chig Okonkwo, TE") and leaves Position empty.
            name, pos = row["player"], row.get("position", "").strip()
            if not pos and "," in name:
                name, _, pos = name.rpartition(",")
                name, pos = name.strip(), pos.strip()
            rows.append({
                "team": owner or team,
                "week": week,
                "player": name,
                "position": pos,
                "injury": row.get("injury", ""),
                **{day: row.get(day, "") for day in DAYS},
                "practice_days": ",".join(k for k in keys if k in DAYS),
                # A club writes UNSPECIFIED (own table) or "(-)" (opponent
                # table) until it designates on Friday.
                "game_status": "" if status.upper() in ("UNSPECIFIED", "(-)", "-")
                               else status,
                "page_team": team,
                "source": url,
            })
    return rows


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


def build(season: int, week: int, teams: list[str] | None = None,
          skill_only: bool = False) -> pl.DataFrame:
    """Fetch all 32 club injury reports and write the week's CSV. Teams that
    fail are recorded in the sources file rather than failing the build."""
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
    df = pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={"team": pl.Utf8, "week": pl.Int64, "player": pl.Utf8,
                "position": pl.Utf8, "injury": pl.Utf8,
                **{day: pl.Utf8 for day in DAYS}, "practice_days": pl.Utf8,
                "game_status": pl.Utf8,
                "page_team": pl.Utf8, "source": pl.Utf8})
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
    if skill_only and df.height:
        df = df.filter(pl.col("position").str.to_uppercase().is_in(SKILL))
    if df.height:
        df = df.sort(["team", "position", "player"])
    out = report_path(season, week, teams, skill_only)
    df.write_csv(out)
    out.with_suffix(".sources.json").write_text(
        json.dumps({"season": season, "week": week, "generated_at": now_iso(),
                    "requested_hosts": teams, "skill_only": skill_only,
                    "missing_teams": sorted(set(teams) - set(df["team"].to_list())),
                    "teams": sources}, indent=2) + "\n")
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
        with pl.Config(tbl_rows=-1, fmt_str_lengths=28):
            print(df.drop("source") if df.height else df)
        return

    fetch = transactions if a.what == "transactions" else depth_chart
    for team in (teams or list(CLUB_HOSTS)):
        for row in fetch(team):
            print(" ".join(str(v) for k, v in row.items() if k != "source"))


if __name__ == "__main__":
    main()
