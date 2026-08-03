#!/usr/bin/env python3
"""Refresh site-rank columns and the market ADP snapshot from public APIs.

No keys, no auth, stdlib only. Sources (all verified working 2026-08-03):

- ESPN:    lm-api-reads.fantasy.espn.com kona_player_info — ranked by
           ESPN's live ADP (ownership.averageDraftPosition; one list,
           no per-format split).
- Sleeper: api.sleeper.com/projections — real Sleeper ADP for std,
           half-ppr and ppr formats.
- FFC:     fantasyfootballcalculator.com/api — 12-team mock-draft ADP
           (std / half / ppr), a third opinion for the site's board.

What it writes:

1. go/{std,0.5_ppr,ppr}_with_depth.csv — ESPN_Rank and Sleeper_Rank
   columns only. Rank / Player / Team / Bye / POS are never touched:
   Rank is OUR board, this script only refreshes the market columns.
2. league-sim/data/market/adp_2026.csv — tracked snapshot joining all
   three sources by player, consumed by site/build_site.py for the
   model-vs-market view.

Run it, eyeball the diff, then rebuild + redeploy:

    python3 update_ranks.py
    python3 build_deploy.py         # rebundles webapp + site data
    git add -A && git commit        # Cloudflare Pages redeploys on push

Cadence: weekly in July, every 2–3 days in August, daily draft week.
ADP moves fastest the final two weeks before Labor Day.
"""
import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GO = ROOT / "go"
SNAPSHOT = ROOT / "league-sim" / "data" / "market" / "adp_2026.csv"

SEASON = 2026
UA = {"User-Agent": "Mozilla/5.0 (foss.football rank refresh; github.com/Zinkelburger/Fantasy-Football-Tool)"}

# CSV file -> sleeper adp field. ESPN has one ADP (no per-format split);
# the same ESPN rank goes into all three files.
FORMATS = {
    "std_with_depth.csv":     "adp_std",
    "0.5_ppr_with_depth.csv": "adp_half_ppr",
    "ppr_with_depth.csv":     "adp_ppr",
}

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
    """name -> overall rank (1..N) by ESPN live ADP.

    NOT draftRanksByRankType: those ranks are an unpublished editorial list
    (identical for STD/PPR, wildly off ADP — e.g. Lamar rank 88 vs ADP 40,
    verified 2026-08-03). ownership.averageDraftPosition is what ESPN draft
    rooms actually follow."""
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
            if adp:
                raw.setdefault(field, []).append((adp, n))
    out = {}
    for field, pairs in raw.items():
        pairs.sort()
        for i, (_, n) in enumerate(pairs, 1):
            out.setdefault(n, {}).setdefault(field, i)
    print(f"Sleeper: {len(out)} players with ADP")
    return out, meta


def fetch_ffc():
    """name -> {'standard': adp, 'half-ppr': adp, 'ppr': adp} (raw pick numbers)"""
    out = {}
    for fmt in ("standard", "half-ppr", "ppr"):
        url = f"https://fantasyfootballcalculator.com/api/v1/adp/{fmt}?teams=12&year={SEASON}"
        try:
            data = get_json(url)
        except Exception as e:
            print(f"FFC {fmt}: FAILED ({e}) — continuing without it")
            continue
        n = 0
        for p in data.get("players", []):
            if p.get("name") and p.get("adp"):
                out.setdefault(norm(p["name"]), {})[fmt] = p["adp"]
                n += 1
        print(f"FFC {fmt}: {n} players")
    return out


def update_csvs(espn, sleeper):
    unmatched = set()
    for fname, slp_field in FORMATS.items():
        path = GO / fname
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        hit_e = hit_s = 0
        for row in rows:
            n = norm(row["Player"])
            e = espn.get(n)
            s = sleeper.get(n, {}).get(slp_field)
            if e:
                row["ESPN_Rank"] = str(e)
                hit_e += 1
            if s:
                row["Sleeper_Rank"] = str(s)
                hit_s += 1
            if not e and not s:
                unmatched.add(row["Player"])
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"{fname}: ESPN {hit_e}/{len(rows)}, Sleeper {hit_s}/{len(rows)}")
    if unmatched:
        print(f"\nWARNING: {len(unmatched)} board players matched NEITHER source "
              f"(stale rank kept — check name spelling or retirement):")
        for name in sorted(unmatched):
            print(f"  - {name}")


def write_snapshot(espn, sleeper, sleeper_meta, ffc):
    """One tracked CSV joining all sources: our STD board players first, then
    any other player inside Sleeper's top-300 STD ADP (so the site's
    model-vs-market join covers deep QB/TE the 225-player board omits)."""
    with open(GO / "std_with_depth.csv", newline="", encoding="utf-8") as f:
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
    espn = fetch_espn()
    sleeper, sleeper_meta = fetch_sleeper()
    ffc = fetch_ffc()
    if not espn and not sleeper:
        sys.exit("ERROR: both ESPN and Sleeper fetches failed; nothing updated")
    update_csvs(espn, sleeper)
    write_snapshot(espn, sleeper, sleeper_meta, ffc)
    print("\nNext: python3 build_deploy.py  (then commit + push to redeploy)")


if __name__ == "__main__":
    main()
