"""Subvertadown's weekly FLEX rankings: RB/WR/TE ranks and projected points.

A second rankings source beside fftiers.py (FantasyPros consensus). One
model's projection, not an expert poll, so it disagrees with ECR in ways
worth reading: it ranks by projected points and gives each player his
team depth slot (BAL-1, DET-2).

    https://subvertadown.com/weekly/flex

**Scoring: the page is 0.5 PPR. Our league is standard.** Ranks carry
over well; the points run higher than a standard projection, most for
high-catch backs, slot receivers and tight ends. Compare the rank, and
read the points only against other Subvertadown points.

The page is server-rendered HTML (Laravel/Livewire): each row is a
<tr x-show="matchesPosition('WR', 'BAL')"> with the name in a title
attribute, a JSON map of ranks per view (FLEX, WR, RB/WR, ...), the depth
slot, home/away + opponent, and the projection. The page names its week
in the heading; `fetch()` checks that and the matchups against the
schedule, and refuses another week's rankings.

**Personal use only.** The page is marked members-only content for the
personal use of Subvertadown members, with no copying, sharing or
publishing. The parsed rows therefore go to engine/weekly/cache/ (gitignored)
and never to data/weekly/, which is committed to a public repo and feeds
andrewbernal.com. Do not move them, publish them, or quote the table
anywhere public.

    python subvertadown.py            # fetch this week, print the top 40
    python subvertadown.py --pos WR   # one position
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request

from common import CACHE, nfl_state, norm_team, now_iso, week_key

URL = "https://subvertadown.com/weekly/flex"
SCORING = "half"
SCORING_NOTE = ("Subvertadown's page is 0.5 PPR; this league is standard. "
                "Compare ranks, not points: his points run higher, most for "
                "pass-catching backs, slot WRs and TEs.")
TERMS_NOTE = ("Members-only content, personal use only: kept in the gitignored "
              "cache, never committed or published.")
MAX_AGE = 6 * 3600  # he refreshes during the week; six hours is plenty fresh
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")

ROW = re.compile(r"<tr\s+x-show=\"matchesPosition\(\s*'(\w+)',\s*'(\w+)'\s*\)\"\s*>(.*?)</tr>", re.S)
RANKS = re.compile(r"JSON\.parse\('(\{.*?\})'\)")
NAME = re.compile(r'title="([^"]+)"')
DEPTH = re.compile(r">\s*([A-Z]{2,3})-(\d+)\s*<")
OPP = re.compile(r"sub-text-muted\">\s*(@|vs\.)\s*</span>\s*([A-Z]{2,3})\s*<")
POINTS = re.compile(r"dark:text-gray-100\">\s*(-?\d+(?:\.\d+)?)\s*<")
WEEK = re.compile(r"Rankings for Fantasy Football Flex Players.*?Week\s+(\d+)", re.S)


def path(season: int, week: int):
    return CACHE / f"subvertadown_flex_{week_key(season, week)}.json"


def _ranks(raw: str) -> dict[str, int]:
    """The x-text JSON is JS-escaped (\\u0022 for quotes); undoing that
    leaves JSON's own \\/ for the slash in "RB/WR", which json reads."""
    s = re.sub(r"\\(u[0-9a-fA-F]{4}|.)",
               lambda m: chr(int(m.group(1)[1:], 16)) if len(m.group(1)) == 5 else m.group(1), raw)
    return {k: int(v) for k, v in json.loads(s).items()}


def parse(page: str) -> tuple[int | None, list[dict]]:
    """Page HTML -> (week, rows). Pure; no network."""
    m = WEEK.search(page)
    week = int(m.group(1)) if m else None
    rows = []
    for pos, team, body in ROW.findall(page):
        name, ranks = NAME.search(body), RANKS.search(body)
        pts, depth, opp = POINTS.search(body), DEPTH.search(body), OPP.search(body)
        if not (name and ranks and pts):
            continue
        r = _ranks(ranks.group(1))
        rows.append({"name": html.unescape(name.group(1)), "pos": pos,
                     "team": norm_team(team),
                     "depth": int(depth.group(2)) if depth else None,
                     "opp": norm_team(opp.group(2)) if opp else None,
                     "home": (opp.group(1) == "vs.") if opp else None,
                     "rank_flex": r.get("FLEX"), "rank_pos": r.get(pos),
                     "points_half": float(pts.group(1))})
    rows.sort(key=lambda x: x["rank_flex"] or 999)
    return week, rows


def _schedule(season: int, week: int) -> dict[str, str]:
    import nfl_data
    import polars as pl
    games = nfl_data.schedules(season).filter(
        (pl.col("week") == week) & (pl.col("game_type") == "REG"))
    out = {}
    for g in games.iter_rows(named=True):
        out[g["home_team"]] = g["away_team"]
        out[g["away_team"]] = g["home_team"]
    return out


def fetch(season: int, week: int, schedule: dict[str, str] | None = None) -> list[dict]:
    """Download, verify the week, cache. Raises on another week's page."""
    state = nfl_state()
    if (season, week) != (state["season"], state["week"]):
        raise ValueError("Subvertadown serves only the current week's rankings")
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8")
    page_week, rows = parse(page)
    if not rows:
        raise RuntimeError("Subvertadown page parsed to no rows; the layout may have changed")
    if page_week != week:
        raise RuntimeError(f"Subvertadown page is for week {page_week}, not week {week}")
    schedule = _schedule(season, week) if schedule is None else schedule
    bad = [f"{r['name']} ({r['team']}) vs {r['opp']}" for r in rows
           if r["team"] and r["opp"] and schedule and schedule.get(r["team"]) != r["opp"]]
    if bad:
        raise RuntimeError(f"Subvertadown matchups disagree with the {season} week {week} "
                           f"schedule ({len(bad)}, e.g. {bad[0]})")
    path(season, week).write_text(json.dumps(
        {"season": season, "week": week, "scoring": SCORING, "url": URL,
         "fetched_at": now_iso(), "fetched_ts": time.time(),
         "note": SCORING_NOTE, "terms": TERMS_NOTE, "rows": rows}, indent=1))
    return rows


def load(season: int, week: int, refresh: bool = False) -> dict:
    """Cached payload, refetched when older than MAX_AGE or on request.
    A failed refetch falls back to the cached copy, marked stale."""
    p = path(season, week)
    cached = json.loads(p.read_text()) if p.exists() else None
    if cached and not refresh and time.time() - cached.get("fetched_ts", 0) < MAX_AGE:
        return cached
    try:
        fetch(season, week)
        return json.loads(p.read_text())
    except Exception as e:  # noqa: BLE001 - an old copy beats nothing
        if cached:
            cached["stale"] = f"refetch failed ({e}); showing copy from {cached['fetched_at']}"
            return cached
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pos", default="FLEX")
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args(argv)
    st = nfl_state()
    data = load(st["season"], st["week"], refresh=True)
    pos = a.pos.upper()
    rows = [r for r in data["rows"] if pos == "FLEX" or r["pos"] == pos]
    key = "rank_flex" if pos == "FLEX" else "rank_pos"
    print(f"Subvertadown {pos} week {data['week']} (0.5 PPR; league is standard)")
    for r in sorted(rows, key=lambda r: r[key] or 999)[:a.top]:
        print(f"{r[key]:>4} {r['name']:26} {r['pos']:2} {r['team']}-{r['depth']} "
              f"{'vs' if r['home'] else '@ '} {r['opp']:3} {r['points_half']:5.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
