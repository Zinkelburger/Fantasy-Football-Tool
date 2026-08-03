#!/usr/bin/env python3
"""Download the JuiceBoxOne public Google Sheets and export every tab to CSV.

Both sheets are public, so this needs no auth or API key — Google's
`/export?format=xlsx` endpoint returns the whole workbook.

The sheets are updated through the preseason (they carry their own
"Date of Last Update" cell, which this records), so re-run before drafting.
See ../DATA-SOURCES.md for the links and staleness policy.

Usage:
    python scripts/fetch_juicebox.py                 # -> data/juicebox/<year>/
    python scripts/fetch_juicebox.py --year 2027
"""

import argparse
import datetime
import io
import json
import pathlib
import re
import sys

import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent

SHEETS = {
    "rankings": {
        "id": "1HTixsrRtIIpnUafVkOIhET83vCFjKXSUGiG24-5jTHY",
        "title": "JuiceBoxOne's Abusing Fantasy Draft Rankings",
        "note": "per-platform draft ranks (ESPN/Sleeper/Yahoo/CBS x scoring format) "
                "+ Landmine risk score. Source of ESPN_Rank/Sleeper_Rank in data/ranks/*.csv.",
    },
    "cheatsheet": {
        "id": "199izMhbkOOjTsNmrK-D56dYnnViJBYFfBEtxK268h4Y",
        "title": "JuiceSheets Draft Cheat Sheets",
        "note": "projected fantasy points (PROJ) per scoring format, plus ADP/VALUE. "
                "The 'Combined' tab is the useful one: one row per player with "
                "team, bye, platform ranks and Proj Std/Half/PPR.",
    },
}

# the cell may arrive as "7/31/2026" or, if pandas parsed it, "2026-07-31 00:00:00"
DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b")


def find_updated_at(tabs: dict) -> str:
    """The sheets carry a 'Date of Last Update' cell on their intro tab."""
    for df in tabs.values():
        flat = df.astype(str).to_numpy().ravel()
        for i, cell in enumerate(flat):
            if "date of last update" in cell.lower():
                for nxt in flat[i:i + 12]:
                    m = DATE_RE.search(nxt)
                    if m:
                        return m.group(1)
    return "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", default=str(datetime.date.today().year))
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    outdir = pathlib.Path(args.outdir) if args.outdir else ROOT / "data" / "juicebox" / args.year
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = {"fetched_at": datetime.date.today().isoformat(), "sheets": {}}

    for key, meta in SHEETS.items():
        url = f"https://docs.google.com/spreadsheets/d/{meta['id']}/export?format=xlsx"
        print(f"fetching {key}: {meta['title']}")
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"  ! HTTP {resp.status_code} — is the sheet still public?")
            sys.exit(1)

        tabs = pd.read_excel(io.BytesIO(resp.content), sheet_name=None, header=None)
        updated = find_updated_at(tabs)

        written = []
        for tab_name, df in tabs.items():
            safe = re.sub(r"[^A-Za-z0-9]+", "_", tab_name).strip("_")
            path = outdir / f"juicebox_{key}_{safe}.csv"
            df.to_csv(path, index=False, header=False)
            written.append(path.name)

        print(f"  sheet says last updated: {updated}; wrote {len(written)} tabs")
        manifest["sheets"][key] = {
            "id": meta["id"],
            "title": meta["title"],
            "note": meta["note"],
            "url": f"https://docs.google.com/spreadsheets/d/{meta['id']}/edit",
            "sheet_last_updated": updated,
            "tabs": written,
        }

    (outdir / "SOURCES.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {outdir}/SOURCES.json")
    print("These sheets change through the preseason — re-run before drafting.")


if __name__ == "__main__":
    main()
