"""How the Sumfun League actually drafts QBs, 2020-2025:
QB1/QB2 timing per team from the real ESPN draft exports.

Run:  venv/bin/python scripts/family_qb_history.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nflreadpy as nfl
import polars as pl

ESPN_DIR = Path(__file__).resolve().parent.parent / "data" / "espn"

_ids = nfl.load_ff_playerids().filter(pl.col("espn_id").is_not_null())
POS = {int(r["espn_id"]): r["position"]
       for r in _ids.select(["espn_id", "position"]).iter_rows(named=True)}

if __name__ == "__main__":
    qb1_rounds, qb2_rounds, teams_with_2 = [], [], 0
    total_team_drafts = 0
    per_year = {}
    for f in sorted(ESPN_DIR.glob("league_*.json")):
        d = json.load(open(f))
        if isinstance(d, list):
            d = d[0]
        year = d["seasonId"]
        names = {t["id"]: t["name"] for t in d["teams"]}
        qbs = {}
        unresolved = 0
        for pk in d["draftDetail"]["picks"]:
            pid = pk["playerId"]
            if pid < 0:
                continue
            pos = POS.get(pid)
            if pos is None:
                unresolved += 1
                continue
            if pos == "QB":
                qbs.setdefault(pk["teamId"], []).append(pk["roundId"])
        n2 = sum(1 for v in qbs.values() if len(v) >= 2)
        total_team_drafts += len(names)
        teams_with_2 += n2
        for tid, rounds in qbs.items():
            rounds.sort()
            qb1_rounds.append(rounds[0])
            if len(rounds) >= 2:
                qb2_rounds.append(rounds[1])
        per_year[year] = (n2, len(names), unresolved,
                          sorted(r for v in qbs.values() for r in v[:1]))
        jack = qbs.get(1, [])
        print(f"{year}: {n2}/{len(names)} teams drafted 2+ QBs; QB1 rounds "
              f"{per_year[year][3]}; Jackels QB rounds {jack}"
              + (f"  [{unresolved} unresolved picks]" if unresolved else ""))
    import statistics as st
    print(f"\nOverall: {teams_with_2}/{total_team_drafts} team-drafts took a 2nd QB "
          f"({teams_with_2/total_team_drafts:.0%})")
    print(f"QB1 round: median {st.median(qb1_rounds):.0f}, range {min(qb1_rounds)}-{max(qb1_rounds)}")
    if qb2_rounds:
        print(f"QB2 round (when taken): median {st.median(qb2_rounds):.0f}, range {min(qb2_rounds)}-{max(qb2_rounds)}")
