"""Round-by-round retrospective of Methuen Jackels' real 2025 draft.

At each of the user's 16 picks, reconstruct the actual board (everyone
already taken is gone), then show:
  - the pick they made (ADP, actual 2025 season points, weeks 1-17)
  - the best still-available player by ADP at each skill position
  - what the wait-cost metric would have recommended
  - the hindsight-best player still on the board

Process is judged by information available at the time (ADP / wait
cost); outcomes shown separately.
"""

import json
import math

import polars as pl

from common import ROOT, league_drafted, season_totals
from simfl.data import norm_name

YEAR = 2025
TEAM = 1  # Methuen Jackels

FITS = json.loads((ROOT / "data" / "pick_value_fits.json").read_text())[str(YEAR)]

ALIASES = {"jacory croskeymerritt": "bill croskeymerritt"}


def E(pos, pick):
    a, b = FITS[pos]
    return a + b * math.log(max(pick, 1.0))


def main():
    picks = (pl.read_parquet(ROOT / "data" / "espn" / "picks.parquet")
             .filter(pl.col("year") == YEAR).sort("overall"))
    tot = season_totals(YEAR)
    pts = {r["nname"]: r["total"] for r in tot.rows(named=True)}
    pos_rank = {r["nname"]: r["pos_rank"] for r in tot.rows(named=True)}

    def get_pts(name):
        n = ALIASES.get(norm_name(name), norm_name(name))
        return pts.get(n), pos_rank.get(n)

    # full ADP board for the year, in order
    from simfl.data import load_adp
    board = sorted(load_adp(YEAR), key=lambda p: p["adp"])
    for p in board:
        p["nname"] = norm_name(p["name"])

    my_picks = picks.filter(pl.col("team_id") == TEAM).rows(named=True)
    my_overalls = [r["overall"] for r in my_picks]
    taken_before = {}
    for r in picks.rows(named=True):
        taken_before[r["overall"]] = r

    roster_pos = []
    for i, mine in enumerate(my_picks):
        o = mine["overall"]
        gone = {ALIASES.get(norm_name(r["player"]), norm_name(r["player"]))
                for r in picks.rows(named=True) if r["overall"] < o}
        avail = [p for p in board if p["nname"] not in gone]
        nxt = my_overalls[i + 1] if i + 1 < len(my_picks) else 999

        # wait-cost per position given the real board
        wc = {}
        for pos in ("QB", "RB", "WR", "TE", "K"):
            now = [p["adp"] for p in avail if p["pos"] == pos]
            fut = [a for a in now if a >= nxt]
            if not now:
                continue
            wc[pos] = (E(pos, min(now)) - E(pos, min(fut) if fut else 250.0),
                       min(now))
        rec = max(wc, key=lambda k: wc[k][0])

        p_pts, p_rank = get_pts(mine["player"])
        adp = f"{mine['adp']:.0f}" if mine["adp"] else "--"
        print(f"\nR{mine['round']:<2} (pick {o:>3})  YOU: {mine['player']:<22}"
              f"{mine['pos']:<3} adp {adp:<4} -> {p_pts if p_pts is not None else '?'} pts"
              f"{f' ({mine[chr(34)+chr(34) if False else 'pos']}{p_rank})' if p_rank else ''}")

        line = "    best by ADP: "
        for pos in ("RB", "WR", "QB", "TE"):
            cand = next((p for p in avail if p["pos"] == pos), None)
            if cand:
                cp, cr = get_pts(cand["name"])
                line += (f"{pos} {cand['name']} (adp {cand['adp']:.0f}, "
                         f"{cp if cp is not None else '?'} pts)  ")
        print(line)
        costs = "  ".join(f"{k}:{v[0]:.0f}" for k, v in sorted(
            wc.items(), key=lambda kv: -kv[1][0]))
        print(f"    wait-cost says: take {rec}   [{costs}]")

        skill = [p for p in avail if p["pos"] != "K"]
        best_hind = max(skill, key=lambda p: (get_pts(p["name"])[0] or 0))
        bp, br = get_pts(best_hind["name"])
        print(f"    hindsight best available: {best_hind['name']} "
              f"({best_hind['pos']}, adp {best_hind['adp']:.0f}) -> {bp} pts ({best_hind['pos']}{br})")
        roster_pos.append(mine["pos"])


if __name__ == "__main__":
    main()
