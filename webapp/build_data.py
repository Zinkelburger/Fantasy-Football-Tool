#!/usr/bin/env python3
"""Bundle player CSVs and analysis notes from ../data into webapp/data/players-data.js.

The output is a plain JS file (not JSON) so the web app works from file:// with no
server and no fetch/CORS concerns. Re-run this whenever the CSVs or notes change.
"""
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
OUT_PATH = os.path.join(HERE, "data", "players-data.js")

# Scoring format -> CSV file (matches archive/go-tool/loader.go getPlayerDataFilename)
FORMATS = {
    "STD": "std_with_depth.csv",
    "0.5PPR": "0.5_ppr_with_depth.csv",
    "PPR": "ppr_with_depth.csv",
}

# 2025 usage-based expected points (engine/league-sim/analysis/
# export_opportunity.py). Format -> column suffix in that CSV.
OPP_CSV = os.path.join(HERE, "..", "engine", "league-sim", "data",
                       "market", "opportunity_2025.csv")
OPP_FMT = {"STD": "std", "0.5PPR": "half", "PPR": "ppr"}

# Per-player draft marks from the findings (engine/league-sim/analysis/
# findings_marks.py): tested buy/fade/watch rules with the player's own
# numbers. Bundled keyed by clean name, like notes.
FM_CSV = os.path.join(HERE, "..", "engine", "league-sim", "data",
                      "market", "findings_marks_2026.csv")
FM_DIR_ORDER = {"buy": 0, "fade": 1, "watch": 2}

# Matches archive/go-tool/loader.go nameCleaner: strips Jr./Sr./II/III/IV/V suffixes
SUFFIX_RE = re.compile(r"\s+(?:Jr\.|Sr\.|II|III|IV|V)$")


def clean_name(name: str) -> str:
    return SUFFIX_RE.sub("", name.strip()).strip()


def norm_name(name: str) -> str:
    """Join key across data sources: lowercase, no punctuation/suffixes
    (FantasyPros 'D.K. Metcalf' == nflverse 'DK Metcalf')."""
    n = clean_name(name).lower()
    return re.sub(r"\s+", " ", n.replace(".", "").replace("'", "").replace("’", ""))


def load_opportunity():
    """(normalized name, pos) -> opportunity row, or {} if the CSV is
    missing (the app must render fine without it)."""
    if not os.path.exists(OPP_CSV):
        print("WARNING: no opportunity_2025.csv — players get no "
              "expected-points fields (run engine/league-sim/"
              "analysis/export_opportunity.py)")
        return {}
    with open(OPP_CSV, newline="", encoding="utf-8") as f:
        return {(norm_name(r["name"]), r["pos"]): r
                for r in csv.DictReader(f)}


def load_findings_marks():
    """(normalized name, pos) -> [{f, dir, note}], buys first."""
    if not os.path.exists(FM_CSV):
        print("WARNING: no findings_marks_2026.csv — note panes get no "
              "findings block (run engine/league-sim/analysis/"
              "findings_marks.py)")
        return {}
    out = {}
    with open(FM_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault((norm_name(r["name"]), r["pos"]), []).append(
                {"f": int(r["finding"]), "slug": r["slug"],
                 "dir": r["dir"], "note": r["note"]})
    for v in out.values():
        v.sort(key=lambda m: (FM_DIR_ORDER.get(m["dir"], 3), m["f"]))
    return out


def load_format(path: str, opp, opp_fmt: str):
    players = []
    matched = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"Rank", "Player", "Team", "Bye", "POS", "ESPN_Rank", "Sleeper_Rank"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"ERROR: {path} missing columns: {sorted(missing)}")
        for row in reader:
            name = (row["Player"] or "").strip()
            if not name:
                continue
            try:
                rank_num = float(row["Rank"])
            except (TypeError, ValueError):
                rank_num = 9999.0
            p = {
                "name": name,
                "team": (row["Team"] or "").strip(),
                "pos": (row["POS"] or "").strip(),
                "bye": (row["Bye"] or "").strip(),
                "rank": (row["Rank"] or "").strip(),
                "rankNum": rank_num,
                "espn": (row["ESPN_Rank"] or "").strip(),
                "sleeper": (row["Sleeper_Rank"] or "").strip(),
            }
            o = opp.get((norm_name(name), p["pos"]))
            if o:
                matched += 1
                # 2025 opportunity read: expected PPG from usage, actual
                # PPG, position-centered gap (threshold on this, never on
                # ppg-xfp — see export_opportunity.py), TD luck, games.
                p.update({
                    "xfp": float(o[f"ep_{opp_fmt}"]),
                    "ppg25": float(o[f"ppg_{opp_fmt}"]),
                    "gapc": float(o[f"gapc_{opp_fmt}"]),
                    "tdl": float(o["td_luck_pg"]),
                    "g25": int(o["games"]),
                })
            players.append(p)
    if opp:
        print(f"  opportunity data: {matched}/{len(players)} players matched")
    players.sort(key=lambda p: p["rankNum"])
    return players


def load_notes():
    notes = {}
    analysis_dir = os.path.join(DATA_DIR, "notes")
    for fn in sorted(os.listdir(analysis_dir)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(analysis_dir, fn), encoding="utf-8") as f:
            content = f.read()
        # Draft status lives in localStorage in the web app; drop stale markers
        lines = [l for l in content.split("\n") if not l.strip().startswith("# To Draft:")]
        notes[fn[:-3]] = "\n".join(lines).strip()
    return notes


def main():
    formats = {}
    opp = load_opportunity()
    for fmt, fname in FORMATS.items():
        path = os.path.join(DATA_DIR, "ranks", fname)
        if not os.path.exists(path):
            sys.exit(f"ERROR: missing CSV {path}")
        formats[fmt] = load_format(path, opp, OPP_FMT[fmt])
        print(f"{fmt}: {len(formats[fmt])} players from {fname}")

    notes = load_notes()
    print(f"notes: {len(notes)} analysis files")

    fm = load_findings_marks()
    fmarks, fm_hit = {}, set()
    for players in formats.values():
        for p in players:
            key = clean_name(p["name"])
            if key in fmarks:
                continue
            mlist = fm.get((norm_name(p["name"]), p["pos"]))
            if mlist:
                fmarks[key] = mlist
                fm_hit.add((norm_name(p["name"]), p["pos"]))
    if fm:
        print(f"findings marks: {len(fmarks)} board players marked "
              f"({len(fm) - len(fm_hit)} marked names not on the board)")

    # Same check as the legacy Go tool: every player should have a note file
    missing = []
    for fmt, players in formats.items():
        for p in players:
            if clean_name(p["name"]) not in notes:
                missing.append(f"{p['name']} ({fmt})")
    if missing:
        print(f"WARNING: {len(missing)} players without note files (app shows 'No note'):")
        for m in sorted(set(missing)):
            print(f"  - {m}")

    data = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "formats": formats,
        "notes": notes,
        "fmarks": fmarks,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("// Generated by build_data.py — do not edit by hand.\n")
        f.write("window.FF_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    size_mb = os.path.getsize(OUT_PATH) / (1024 * 1024)
    print(f"wrote {OUT_PATH} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
