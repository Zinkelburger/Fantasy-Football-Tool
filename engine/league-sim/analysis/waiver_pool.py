"""Truths #3 and #8 (data half): if you punt TE / QB / K, is there a
good one sitting on waivers after a few weeks?

Uses the players ACTUALLY undrafted in the Sumfun League each year.
"Hot pickup at week 3" = the undrafted player with the most points
through weeks 1-3; we then measure his rest-of-season (wk 4-17) ppg
and where that ranks among ALL players at the position.

Whether he's still available by the time you want him is a contention
question -> simulator territory.  This is the ceiling of the strategy.
"""

import polars as pl

from common import SEASONS, league_drafted, season_totals


def hot_pickup(pos: str):
    print(f"\n== {pos}: best undrafted-in-Sumfun through wk 1-3, then rest-of-season ==")
    rows = []
    for y in SEASONS:
        undrafted = ~pl.col("nname").is_in(list(league_drafted(y)))
        early = (season_totals(y, weeks=(1, 3))
                 .filter(pl.col("position") == pos, undrafted)
                 .sort("total", descending=True))
        hot = early.row(0, named=True)
        ros = season_totals(y, weeks=(4, 17)).filter(pl.col("position") == pos)
        r = ros.filter(pl.col("player_id") == hot["player_id"])
        rows.append({
            "year": y, "pickup": hot["player_display_name"],
            "wk1-3 pts": hot["total"],
            "ros ppg": round(r["ppg"].item(), 1) if len(r) else 0.0,
            "ros rank": r["pos_rank"].item() if len(r) else None,
        })
    print(pl.DataFrame(rows))


def waiver_depth(pos: str, top_n: int = 12):
    """How many of the position's ROS top-N were undrafted? (pool depth)"""
    counts = []
    for y in SEASONS:
        undrafted = ~pl.col("nname").is_in(list(league_drafted(y)))
        ros = season_totals(y, weeks=(4, 17)).filter(pl.col("position") == pos)
        counts.append(len(ros.filter(pl.col("pos_rank") <= top_n, undrafted)))
    print(f"{pos}: of the ROS top-{top_n}, undrafted count by year "
          f"{counts} (avg {sum(counts) / len(counts):.1f})")


def te_punt_vs_early():
    """Compare: TEs your league spent early picks on (rounds 1-8) vs the
    best week-3 waiver TE, on rest-of-season ppg."""
    print("\n== TE punt check: early-drafted TEs vs the wk-3 waiver pickup ==")
    picks = pl.read_parquet("data/espn/picks.parquet")
    from simfl.data import norm_name
    rows = []
    for y in SEASONS:
        early_tes = (picks.filter(pl.col("year") == y, pl.col("pos") == "TE",
                                  pl.col("round") <= 8)
                     .with_columns(pl.col("player").map_elements(
                         norm_name, return_dtype=pl.String).alias("nname")))
        ros = season_totals(y, weeks=(4, 17)).filter(pl.col("position") == "TE")
        drafted_ros = ros.join(early_tes.select("nname"), on="nname", how="inner")
        undrafted = ~pl.col("nname").is_in(list(league_drafted(y)))
        hot3 = (season_totals(y, weeks=(1, 3)).filter(pl.col("position") == "TE", undrafted)
                .sort("total", descending=True).head(1))
        hot_ros = ros.join(hot3.select("player_id"), on="player_id", how="inner")
        rows.append({
            "year": y,
            "early TEs drafted (R1-8)": len(early_tes),
            "their avg ros ppg": round(drafted_ros["ppg"].mean(), 1),
            "best of them": round(drafted_ros["ppg"].max(), 1),
            "wk3 waiver TE ros ppg": round(hot_ros["ppg"].item(), 1) if len(hot_ros) else 0.0,
        })
    print(pl.DataFrame(rows))


if __name__ == "__main__":
    for pos in ["TE", "QB", "K"]:
        hot_pickup(pos)
    print("\n== Waiver pool depth: how much of each position's ROS top-12 went undrafted ==")
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        waiver_depth(pos)
    te_punt_vs_early()
