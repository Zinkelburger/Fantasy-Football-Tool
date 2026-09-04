#!/usr/bin/env python3
"""Correct the pool's Team and Bye columns against Sleeper's live roster.

The pool comes from a FantasyPros overall-ADP export, which is a manual
download and therefore a snapshot. Ours was taken 2026-08-10, before final
roster cuts, and by early September it was wrong in ways that matter:

  - Keenan Allen was still listed LAC after signing with Indianapolis. The
    corpus had already noticed — 76 of his 77 mentions in team subreddits
    landed in r/Colts — but the resolver scores candidates partly on team, so
    a stale team makes it worse at exactly the players in the news.
  - Six players carried no team at all, because they were free agents when the
    export was taken: Diggs, Ekeler, Tyreek Hill, Mattison, Kareem Hunt, Mixon.

Sleeper's player endpoint is public, needs no key, and carries team, position
and roster status for every NFL player. It cannot replace the ADP export —
it has no ADP and no notion of who is draftable — so this does not rebuild the
pool. It corrects the two columns the export gets stale on, and reports the
players Sleeper no longer has on an active roster, which is a decision for a
person rather than a script.

    python refresh_pool.py --dry-run     # report only
    python refresh_pool.py               # write combined_with_depth.csv
"""

import argparse
import csv
import json
import pathlib
import re
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
POOL = HERE / "combined_with_depth.csv"
SLEEPER = "https://api.sleeper.app/v1/players/nfl"
SUFFIX = re.compile(r"\s+(?:Jr\.?|Sr\.?|II|III|IV|V)$", re.I)

# Sleeper and FantasyPros abbreviate the same franchises differently. Without
# this the script "corrects" all eight Jaguars to JAX, which is the same team
# and would break every consumer that keys on the pool's spelling — TEAM_WORDS
# in the resolver, and the board CSVs.
SAME_TEAM = [{"JAC", "JAX"}, {"LA", "LAR"}, {"WAS", "WSH"}, {"SF", "SFO"},
             {"TB", "TAM"}, {"NO", "NOR"}, {"KC", "KAN"}, {"GB", "GNB"},
             {"NE", "NWE"}, {"ARI", "ARZ"}, {"BAL", "BLT"}, {"CLE", "CLV"},
             {"HOU", "HST"}]


def same_team(a, b):
    return a == b or any({a, b} <= g for g in SAME_TEAM)


def key(name):
    return SUFFIX.sub("", str(name)).lower().replace("'", "").replace(".", "").strip()


def fetch():
    with urllib.request.urlopen(SLEEPER, timeout=120) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(POOL.open(encoding="utf-8")))
    live = {}
    for v in fetch().values():
        n = v.get("full_name")
        if not n or not v.get("position"):
            continue
        # Prefer a rostered entry when two players share a name.
        k = (key(n), v["position"])
        if k not in live or (v.get("team") and not live[k].get("team")):
            live[k] = v

    # Bye weeks are a property of the team, and the export already knows them
    # for every team that has a rostered player in the pool.
    byes = {r["Team"]: r["Bye"] for r in rows
            if str(r.get("Team", "")).strip() not in ("", "nan")
            and str(r.get("Bye", "")).strip() not in ("", "nan")}

    changed, filled, gone, unmatched = [], [], [], []
    for r in rows:
        name, pos = r["Player"], str(r.get("POS", ""))[:2].upper()
        if "DST" in name or pos.startswith("K") or pos == "DS":
            continue                       # Sleeper models kickers and
                                           # defenses differently
        v = live.get((key(name), pos))
        if v is None:
            unmatched.append(name)
            continue
        old = str(r.get("Team", "")).strip()
        new = (v.get("team") or "").strip()
        if not new:
            gone.append((name, old, v.get("status") or "no team"))
            continue
        if old in ("", "nan"):
            filled.append((name, new))
        elif same_team(old, new):
            continue                       # same franchise, different spelling
        else:
            changed.append((name, old, new))
        r["Team"] = new
        if byes.get(new):
            r["Bye"] = byes[new]

    print(f"{len(rows)} pool rows checked against {len(live)} Sleeper entries\n")
    if changed:
        print(f"team CHANGED ({len(changed)}):")
        for n, o, w in changed:
            print(f"   {n:26} {o:>4} -> {w}")
    if filled:
        print(f"\nteam FILLED IN ({len(filled)}):")
        for n, w in filled:
            print(f"   {n:26}      -> {w}")
    if gone:
        print(f"\nNOT ON A ROSTER per Sleeper ({len(gone)}) — decide by hand, "
              f"left untouched:")
        for n, o, s in gone:
            print(f"   {n:26} {o:>4}    {s}")
    if unmatched:
        print(f"\nno Sleeper match ({len(unmatched)}): {', '.join(unmatched[:12])}"
              + (" ..." if len(unmatched) > 12 else ""))

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return
    if not (changed or filled):
        print("\nnothing to write.")
        return
    with POOL.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {POOL.name}: {len(changed)} corrected, {len(filled)} filled.")
    print("Delete corpus/index_cache.json so the ranking re-resolves with the "
          "new teams.")


if __name__ == "__main__":
    main()
