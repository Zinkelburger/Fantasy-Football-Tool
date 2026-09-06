#!/usr/bin/env python3
"""Refresh every draft board and market comparison from public feeds.

The main Rank is FFC's per-format, 12-team mock-draft ADP order; ADP stores
its actual average pick. ESPN/Sleeper comparison columns remain independent.
Players outside FFC's sample stay searchable with no main rank. Never retain
old ranks after a successful refresh. Reject incomplete/stale primary feeds
before writing any board. SOURCES.json records fetch time and sample windows.

    python3 engine/update_ranks.py
    python3 webapp/build_data.py    # local dashboard
    python3 build_deploy.py         # assemble deployable site, no publication
"""
import csv
import math
from datetime import date, datetime, timezone
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RANKS = ROOT / "data" / "ranks"
SNAPSHOT = HERE / "league-sim" / "data" / "market" / "adp_2026.csv"

SEASON = 2026
TEAMS = 12
UA = {"User-Agent": "Mozilla/5.0 (foss.football rank refresh; github.com/Zinkelburger/Fantasy-Football-Tool)"}

# CSV file -> sleeper adp field. ESPN has one ADP (no per-format split);
# the same ESPN rank goes into all three files.
FORMATS = {
    "std_with_depth.csv":     "adp_std",
    "0.5_ppr_with_depth.csv": "adp_half_ppr",
    "ppr_with_depth.csv":     "adp_ppr",
}

FFC_FORMATS = {"std_with_depth.csv": "standard",
               "0.5_ppr_with_depth.csv": "half-ppr",
               "ppr_with_depth.csv": "ppr"}
POSITIONS = {"QB", "RB", "WR", "TE"}

SUFFIX_RE = re.compile(r"\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$")


def norm(name: str) -> str:
    n = name.lower().strip()
    n = n.replace(".", "").replace("'", "").replace("’", "")
    n = SUFFIX_RE.sub("", n)
    return re.sub(r"\s+", " ", n)


def get_json(url: str, headers: dict = None) -> object:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_espn():
    """name -> overall order by ESPN ADP (not standard-only or room order)."""
    flt = json.dumps({"players": {"limit": 500,
                                  "sortAdp": {"sortPriority": 1, "sortAsc": True}}})
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
           f"{SEASON}/segments/0/leaguedefaults/3?view=kona_player_info")
    data = get_json(url, {"X-Fantasy-Filter": flt, "Accept": "application/json"})
    pairs = []
    for entry in data.get("players", []):
        p = entry.get("player") or {}
        name = p.get("fullName")
        adp = (p.get("ownership") or {}).get("averageDraftPosition")
        if name and adp and adp > 0:
            pairs.append((adp, norm(name)))
    pairs.sort()
    out = {}
    for i, (_, n) in enumerate(pairs, 1):
        out.setdefault(n, i)
    print(f"ESPN: {len(out)} players ranked by ADP")
    return out


def fetch_sleeper():
    """Returns (ranks, meta):
    ranks: name -> {'adp_std': overall rank, 'adp_half_ppr': ..., 'adp_ppr': ...}
    meta:  name -> {'display', 'team', 'pos'}  (for snapshot rows not on our board)
    """
    pos = "".join(f"&position%5B%5D={p}" for p in ("QB", "RB", "WR", "TE"))
    url = (f"https://api.sleeper.com/projections/nfl/{SEASON}"
           f"?season_type=regular{pos}&order_by=adp_std")
    data = get_json(url)
    # Collect raw ADP per format, then convert to overall rank 1..N.
    raw = {}  # field -> [(adp, name)]
    meta = {}
    for e in data:
        p = e.get("player") or {}
        st = e.get("stats") or {}
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        if not name:
            continue
        n = norm(name)
        if any(st.get(f) for f in ("adp_std", "adp_half_ppr", "adp_ppr")):
            meta.setdefault(n, {"display": name, "team": p.get("team") or "",
                                "pos": p.get("position") or ""})
        for field in ("adp_std", "adp_half_ppr", "adp_ppr"):
            adp = st.get(field)
            if adp and 0 < adp < 999:
                raw.setdefault(field, []).append((adp, n))
    out = {}
    for field, pairs in raw.items():
        pairs.sort()
        for i, (_, n) in enumerate(pairs, 1):
            out.setdefault(n, {}).setdefault(field, i)
    print(f"Sleeper: {len(out)} players with ADP")
    return out, meta


def validate_ffc(data, fmt, today=None):
    """Reject partial, wrong-format/year, or stale responses before any writes."""
    today = today or date.today()
    meta = data.get("meta", {})
    expected = {"standard": "Non-PPR", "half-ppr": "Half-PPR", "ppr": "PPR"}[fmt]
    end = date.fromisoformat(meta.get("end_date", ""))
    start = date.fromisoformat(meta.get("start_date", ""))
    if (data.get("status") != "Success" or meta.get("type") != expected
            or meta.get("teams") != TEAMS or end.year != SEASON
            or not 0 <= (today - end).days <= 7 or start > end
            or meta.get("total_drafts", 0) <= 0):
        raise ValueError(f"FFC {fmt}: wrong format, empty sample, or stale date: {meta}")
    players = data.get("players", [])
    seen = set()
    skill_count = 0
    for p in players:
        n = norm(p.get("name", ""))
        adp = float(p.get("adp", 0))
        if not n or n in seen or not math.isfinite(adp) or not 0 < adp < 999:
            raise ValueError(f"FFC {fmt}: invalid/duplicate player or ADP: {p}")
        seen.add(n)
        skill_count += p.get("position") in POSITIONS
    if skill_count < 100:
        raise ValueError(f"FFC {fmt}: only {skill_count} skill players; refusing partial board")
    return sorted(players, key=lambda p: (float(p["adp"]), norm(p["name"])))


def fetch_ffc():
    out, samples, feeds = {}, {}, {}
    for fmt in FFC_FORMATS.values():
        url = f"https://fantasyfootballcalculator.com/api/v1/adp/{fmt}?teams={TEAMS}&year={SEASON}"
        data = get_json(url)
        feeds[fmt] = validate_ffc(data, fmt)
        samples[fmt] = {"url": url, **data["meta"]}
        for p in feeds[fmt]:
            out.setdefault(norm(p["name"]), {})[fmt] = p["adp"]
        print(f"FFC {fmt}: {len(feeds[fmt])} players; sample through {data['meta']['end_date']}")
    return out, samples, feeds


def build_board(previous, players, espn, sleeper, slp_field):
    old = {norm(r["Player"]): r for r in previous}
    rows, seen = [], set()
    # Keep overall positions, including picks spent on K/DST, but only show
    # skill players. ADP remains the raw average pick, not an ordinal rank.
    for rank, p in enumerate(players, 1):
        if p["position"] not in POSITIONS:
            continue
        n = norm(p["name"])
        seen.add(n)
        prior = old.get(n, {})
        rows.append({"Rank": str(rank), "Player": prior.get("Player", p["name"]),
                     "Team": p.get("team") or "", "Bye": str(p.get("bye") or ""),
                     "POS": p["position"], "ADP": str(p["adp"])})
    for n, row in old.items():
        if n not in seen:
            rows.append({**row, "Rank": "", "ADP": ""})
    for row in rows:
        n = norm(row["Player"])
        # Absence is missing data, never permission to keep yesterday's value.
        row["ESPN_Rank"] = str(espn.get(n, ""))
        row["Sleeper_Rank"] = str(sleeper.get(n, {}).get(slp_field, ""))
    return rows


def update_csvs(espn, sleeper, feeds, samples):
    boards = {}
    for fname, slp_field in FORMATS.items():
        with open(RANKS / fname, newline="", encoding="utf-8") as f:
            previous = list(csv.DictReader(f))
        boards[fname] = build_board(previous, feeds[FFC_FORMATS[fname]], espn, sleeper, slp_field)
    # All primary feeds and all board transformations have succeeded.
    for fname, rows in boards.items():
        path = RANKS / fname
        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Rank", "Player", "Team", "Bye", "POS",
                                             "ESPN_Rank", "Sleeper_Rank", "ADP"],
                               lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        temporary.replace(path)
        print(f"{fname}: {sum(bool(r['Rank']) for r in rows)} ranked; "
              f"{sum(not r['Rank'] for r in rows)} without current FFC ADP")
    metadata = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON, "board_source": "Fantasy Football Calculator",
        "board_kind": "12-team mock-draft ADP", "formats": samples,
        "espn": "Overall ADP order; not standard-only and not draft-room order",
        "sleeper": "Per-format ADP order; values of 999 are excluded",
        "missing": "Blank ranks/ADP mean outside the current source sample",
    }
    (RANKS / "SOURCES.json").write_text(json.dumps(metadata, indent=2) + "\n")


def write_snapshot(espn, sleeper, sleeper_meta, ffc):
    """One tracked CSV joining all sources: our STD board players first, then
    any other player inside Sleeper's top-300 STD ADP (so the site's
    model-vs-market join covers deep QB/TE the 225-player board omits)."""
    with open(RANKS / "std_with_depth.csv", newline="", encoding="utf-8") as f:
        board = list(csv.DictReader(f))
    rows = [(row["Player"], row["Team"], row["POS"], norm(row["Player"]))
            for row in board]
    on_board = {r[3] for r in rows}
    extras = [(m["display"], m["team"], m["pos"], n)
              for n, m in sleeper_meta.items()
              if n not in on_board and sleeper.get(n, {}).get("adp_std", 9999) <= 300]
    extras.sort(key=lambda r: sleeper[r[3]]["adp_std"])
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["player", "team", "pos", "espn",
                    "sleeper_std", "sleeper_half", "sleeper_ppr",
                    "ffc_std", "ffc_half", "ffc_ppr"])
        for display, team, pos, n in rows + extras:
            s, c = sleeper.get(n, {}), ffc.get(n, {})
            w.writerow([
                display, team, pos, espn.get(n, ""),
                s.get("adp_std", ""), s.get("adp_half_ppr", ""), s.get("adp_ppr", ""),
                c.get("standard", ""), c.get("half-ppr", ""), c.get("ppr", ""),
            ])
    print(f"wrote {SNAPSHOT.relative_to(ROOT)} "
          f"({len(rows)} board + {len(extras)} extra players)")


def main():
    ffc, samples, feeds = fetch_ffc()
    espn = fetch_espn()
    sleeper, sleeper_meta = fetch_sleeper()
    if not espn and not sleeper:
        sys.exit("ERROR: both ESPN and Sleeper fetches failed; nothing updated")
    update_csvs(espn, sleeper, feeds, samples)
    write_snapshot(espn, sleeper, sleeper_meta, ffc)
    print("\nNext: python3 build_deploy.py  (then commit + push to redeploy)")


if __name__ == "__main__":
    main()
