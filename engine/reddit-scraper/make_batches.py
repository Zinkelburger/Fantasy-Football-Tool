#!/usr/bin/env python3
"""Split the board players into balanced batches for note writing, and write
stub notes for players with no corpus discussion.

Batches are round-robin over an ADP-sorted list so each writer gets a mix of
stars and deep-bench players (dossier size correlates with ADP).
"""

import argparse
import csv
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
DOSSIERS = HERE / "corpus" / "dossiers"
OUT_DIR = HERE / "markdown_data"
BOARD = HERE.parent.parent / "data" / "ranks" / "std_with_depth.csv"

SUFFIX_RE = re.compile(r"\s+(?:Jr\.|Sr\.|II|III|IV|V)$", re.IGNORECASE)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")


def clean_name(name: str) -> str:
    return SUFFIX_RE.sub("", name.strip()).strip()


def mentions(slug_name: str) -> int:
    path = DOSSIERS / f"{slug_name}.txt"
    if not path.exists():
        return 0
    first = path.read_text(encoding="utf-8").split("\n", 1)[0]
    m = re.search(r"(\d+) mentions", first)
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batches", type=int, default=14)
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    with open(BOARD, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    have, stubs = [], []
    for r in rows:
        s = slug(r["Player"])
        entry = {"name": r["Player"], "clean": clean_name(r["Player"]), "slug": s,
                 "team": r["Team"], "bye": r["Bye"], "pos": r["POS"],
                 "rank": r["Rank"], "mentions": mentions(s)}
        (have if entry["mentions"] > 0 else stubs).append(entry)

    # stub notes need no writer
    for e in stubs:
        (OUT_DIR / f"{e['clean']}.md").write_text(
            f"**{e['name']}** ({e['team']}, {e['pos']}, bye {e['bye']}) — board rank {e['rank']}\n\n"
            "**Room sentiment:** no discussion found in the r/fantasyfootball corpus "
            "(60-day draft-season window).\n\n"
            "- Nobody is talking about this player. That is itself the signal: no hype, "
            "no reported role change, no injury chatter.\n"
            "- Draft take: late-round dart or waiver-wire name; nothing in the community "
            "data argues for reaching.\n",
            encoding="utf-8")

    batches = [[] for _ in range(args.batches)]
    for i, e in enumerate(have):          # round-robin keeps sizes balanced
        batches[i % args.batches].append(e)

    manifest = HERE / "corpus" / "batches.json"
    manifest.write_text(json.dumps(batches, indent=1), encoding="utf-8")

    print(f"board players: {len(rows)}")
    print(f"  stub notes written (0 mentions): {len(stubs)}")
    print(f"  needing written notes: {len(have)}")
    for i, b in enumerate(batches):
        tot = sum(e["mentions"] for e in b)
        print(f"  batch {i+1}: {len(b)} players, {tot} mentions")
    print(f"manifest: {manifest}")


if __name__ == "__main__":
    main()
