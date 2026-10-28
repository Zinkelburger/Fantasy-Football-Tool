#!/usr/bin/env python3
"""Add every player on the current ESPN depth charts to the resolver's pool.

The pool is a FantasyPros draft export: 337 players who were draftable in
August. By week 8 the players a weekly question is about are often not in it
— Jonah Coleman and Omar Cooper were, Kendrick Bourne and Bam Knight were not
— and a player outside the pool gets no surname or nickname search terms in
research_brief and no team for the resolver's context scoring.

data/weekly/depth_2026.csv is the ESPN depth-chart snapshot the weekly build
already saves (QB/RB/WR/TE with team and depth rank). Every player on it who
is not already in the pool is appended with:

    Average_ADP  999      never drafted; ADP tie-breaks keep favouring the
                          draftable player who shares the surname
    POS          <pos>99  position with a sentinel positional rank
    Depth        <pos><rank>, Depth_Rank <rank>   from the snapshot
    Bye          the team's bye as the pool already records it
    espn_id      kept for later identity work; blank on the original rows

Players already in the pool are matched by the same suffix/punctuation-blind
key refresh_pool.py uses ("Marvin Harrison Jr." is "Marvin Harrison"). Rows
are only ever added here; teams are corrected by refresh_pool.py afterwards.

    python expand_pool.py --dry-run
    python expand_pool.py
"""
import argparse
import csv
import pathlib
import re
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
POOL = HERE / "combined_with_depth.csv"
DEPTH = HERE.parent.parent / "data" / "weekly" / "depth_2026.csv"
SUFFIX = re.compile(r"\s+(?:Jr\.?|Sr\.?|II|III|IV|V)$", re.I)
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def key(name):
    return SUFFIX.sub("", str(name)).lower().replace("'", "").replace(".", "").strip()


def expand(pool_rows, depth_rows):
    """Return (new_rows, skipped) without touching disk."""
    have = {key(r["Player"]) for r in pool_rows}
    byes = {r["Team"]: r["Bye"] for r in pool_rows
            if str(r.get("Team", "")).strip() not in ("", "nan")
            and str(r.get("Bye", "")).strip() not in ("", "nan")}
    fields = list(pool_rows[0].keys())
    new, skipped = [], Counter()
    for d in depth_rows:
        name = " ".join(str(d.get("player_name", "")).split())
        pos = str(d.get("pos_abb", "")).upper()
        if not name:
            skipped["blank name"] += 1
            continue
        if pos not in POSITIONS:
            skipped[f"position {pos or '?'}"] += 1
            continue
        k = key(name)
        if k in have:
            skipped["already in pool"] += 1
            continue
        have.add(k)
        rank = str(d.get("pos_rank", "")).strip() or "9"
        row = {f: "" for f in fields}
        row.update({"Player": name, "Team": d.get("team", ""), "Bye": byes.get(d.get("team", ""), ""),
                    "POS": f"{pos}99", "Average_ADP": "999", "Depth": f"{pos}{rank}",
                    "Depth_Rank": rank, "Nickname": ""})
        if "espn_id" in row:
            row["espn_id"] = d.get("espn_id", "")
        new.append(row)
    return new, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not DEPTH.exists():
        raise SystemExit(f"no depth snapshot at {DEPTH}; run the weekly build first")
    pool_rows = list(csv.DictReader(POOL.open(encoding="utf-8", newline="")))
    depth_rows = list(csv.DictReader(DEPTH.open(encoding="utf-8", newline="")))
    fields = list(pool_rows[0].keys())
    if "espn_id" not in fields:
        fields.append("espn_id")
        for r in pool_rows:
            r["espn_id"] = ""
    new, skipped = expand(pool_rows, depth_rows)
    print(f"{len(pool_rows)} pool rows, {len(depth_rows)} depth rows -> {len(new)} to add; "
          + ", ".join(f"{v} {k}" for k, v in sorted(skipped.items())))
    if new:
        print("  " + ", ".join(f"{r['Player']} ({r['Team']} {r['Depth']})" for r in new[:8])
              + (" ..." if len(new) > 8 else ""))
    if args.dry_run or not new:
        print("--dry-run: nothing written." if args.dry_run else "nothing to write.")
        return 0
    with POOL.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(pool_rows + new)
    print(f"wrote {POOL.name}: {len(pool_rows) + len(new)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
