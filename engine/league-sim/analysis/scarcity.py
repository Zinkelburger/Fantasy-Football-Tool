"""Truths #3 and #4: QB flatness and RB scarcity.

- Points-per-week by positional finish rank, averaged across seasons:
  how steep is each position's dropoff?
- Value over replacement given THIS league's lineup (1 QB, 2 RB, 2 WR,
  1 TE, 1 RB/WR flex, 12 teams).
- In-season attrition: of the preseason (ADP) top-24 at each position,
  how much of the season did they actually play, and early vs late ppg?
"""

import polars as pl

from common import SEASONS, season_totals, weekly
from simfl.data import load_adp, norm_name

PPW_RANKS = [1, 3, 6, 9, 12, 18, 24, 30]
# Replacement rank: last streamable starter. 12 QB/TE starters; RB/WR
# fill 24 slots each plus 12 flex shared -> ~30th is replacement.
REPLACEMENT = {"QB": 13, "TE": 13, "RB": 30, "WR": 30, "K": 13}


def curve():
    frames = [season_totals(y) for y in SEASONS]
    df = pl.concat(frames)
    print("== Avg points per WEEK at positional finish rank (2020-2025) ==")
    rows = []
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        r = {"pos": pos}
        for rank in PPW_RANKS:
            v = df.filter(pl.col("position") == pos, pl.col("pos_rank") == rank)
            r[f"#{rank}"] = round(v.get_column("total").mean() / 17, 1)
        rows.append(r)
    t = pl.DataFrame(rows)
    print(t)

    print("\n== Value over replacement per week (rank X minus replacement rank) ==")
    rows = []
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        rep = (df.filter(pl.col("position") == pos,
                         pl.col("pos_rank") == REPLACEMENT[pos])
               .get_column("total").mean() / 17)
        r = {"pos": pos, "replacement": f"#{REPLACEMENT[pos]}"}
        for rank in [1, 3, 6, 12]:
            v = (df.filter(pl.col("position") == pos, pl.col("pos_rank") == rank)
                 .get_column("total").mean() / 17)
            r[f"#{rank}"] = round(v - rep, 1)
        rows.append(r)
    print(pl.DataFrame(rows))


def attrition():
    print("\n== Preseason (ADP) top-24 per position: how the season treats them ==")
    rows = []
    for pos in ["QB", "RB", "WR", "TE"]:
        early_all, late_all, games_all, missed6 = [], [], [], 0
        n = 0
        for y in SEASONS:
            adp = [norm_name(p["name"]) for p in load_adp(y) if p["pos"] == pos][:24]
            wk = weekly(y).filter(pl.col("nname").is_in(adp))
            per = (wk.group_by("nname")
                   .agg(pl.len().alias("games"),
                        pl.col("fpts").filter(pl.col("week") <= 8).mean().alias("early_ppg"),
                        pl.col("fpts").filter(pl.col("week") > 8).mean().alias("late_ppg")))
            n += len(adp)
            games_all += per.get_column("games").to_list()
            missed6 += len(per.filter(pl.col("games") <= 11)) + (len(adp) - len(per))
            early_all += per.get_column("early_ppg").drop_nulls().to_list()
            late_all += per.get_column("late_ppg").drop_nulls().to_list()
        rows.append({
            "pos": pos,
            "avg games (of 17)": round(sum(games_all) / n, 1),
            "missed 6+ wks %": round(100 * missed6 / n),
            "ppg wk1-8": round(sum(early_all) / len(early_all), 1),
            "ppg wk9-17": round(sum(late_all) / len(late_all), 1),
        })
    print(pl.DataFrame(rows))


def qb12_is_fine():
    print("\n== The 'QB12 is fine' check: weekly ppg gap vs same gap at RB ==")
    frames = pl.concat([season_totals(y) for y in SEASONS])
    for pos, hi, lo in [("QB", 5, 12), ("RB", 5, 12), ("RB", 12, 30), ("WR", 12, 30)]:
        a = frames.filter(pl.col("position") == pos, pl.col("pos_rank") == hi)["total"].mean() / 17
        b = frames.filter(pl.col("position") == pos, pl.col("pos_rank") == lo)["total"].mean() / 17
        print(f"{pos}#{hi} vs {pos}#{lo}: {a:.1f} vs {b:.1f} ppw  ->  gap {a - b:.1f}")


if __name__ == "__main__":
    curve()
    qb12_is_fine()
    attrition()
