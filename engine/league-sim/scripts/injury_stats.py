"""RB vs WR: availability and the injury tax, 2020-2025.

Answers: do RBs really miss more games, and is their per-game premium
big enough to survive it? Drafted players only, split by draft capital.

Run:  venv/bin/python scripts/injury_stats.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simfl.config import DEFAULT_SCORING
from simfl.pool import build_pool

MAX_GAMES = {2020: 16}          # 17 from 2021 on
BANDS = [("rounds 1-3 (ADP<=36)", 0, 36), ("rounds 4-6 (37-72)", 37, 72),
         ("rounds 7-10 (73-120)", 73, 120)]


def season_rows():
    rows = []
    for year in range(2020, 2026):
        gmax = MAX_GAMES.get(year, 17)
        for p in build_pool(year, DEFAULT_SCORING):
            if p.adp is None or p.pos not in ("RB", "WR", "QB", "TE"):
                continue
            games = len(p.week_pts)
            last = max(p.week_pts) if p.week_pts else 0
            rows.append({
                "year": year, "pos": p.pos, "adp": p.adp,
                "games": games, "gmax": gmax,
                "missed": gmax - games,
                "tot": sum(p.week_pts.values()),
                "ppg": sum(p.week_pts.values()) / games if games else 0.0,
                "ended_early": last <= 13 and games > 0,   # proxy: season over by wk13
                "zero": games == 0,
            })
    return rows


if __name__ == "__main__":
    rows = season_rows()
    print("Availability by position and draft capital, 2020-2025")
    print("(drafted players; 'out early' = last game by week 13)\n")
    for label, lo, hi in BANDS:
        print(f"== {label} ==")
        for pos in ("RB", "WR", "QB", "TE"):
            c = [r for r in rows if r["pos"] == pos and lo <= r["adp"] <= hi]
            n = len(c)
            if n < 8:
                continue
            avail = sum(r["games"] / r["gmax"] for r in c) / n
            m4 = sum(r["missed"] >= 4 for r in c) / n
            early = sum(r["ended_early"] or r["zero"] for r in c) / n
            ppg = sum(r["ppg"] for r in c) / n
            tot = sum(r["tot"] for r in c) / n
            print(f"  {pos:2s} n={n:3d}  avail {avail:4.0%}  miss4+ {m4:4.0%}  "
                  f"out-early {early:4.0%}  ppg {ppg:5.1f}  season tot {tot:5.0f}")
        print()
    # The head-to-head that matters: early RB vs early WR, total delivered
    print("The verdict cell — rounds 1-3, points actually delivered:")
    for pos in ("RB", "WR"):
        c = [r for r in rows if r["pos"] == pos and r["adp"] <= 36]
        n = len(c)
        tot = sum(r["tot"] for r in c) / n
        ppg = sum(r["ppg"] for r in c) / n
        avail = sum(r["games"] / r["gmax"] for r in c) / n
        print(f"  {pos}: {tot:.0f} season pts on average "
              f"({ppg:.1f} ppg x {avail:.0%} availability, n={n})")
