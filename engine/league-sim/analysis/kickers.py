"""Truth #1: do kickers matter, and is the hot week-1/2 kicker on waivers?

- Spread between kicker season finishes (K1 vs K12): how many points
  per week does the best kicker actually buy you over the worst starter?
- Variance decomposition: how much of a given kicker-week is "which
  kicker you own" vs pure noise?
- The hot-start test: the top scorer through weeks 1-2 each year — was
  he drafted in the Sumfun League, and how did he do rest-of-season?
"""

import polars as pl

from common import SEASONS, league_drafted, season_totals, weekly


def spread():
    print("== Kicker season totals: K1 / K6 / K12 / K18 (weeks 1-17) ==")
    rows = []
    for y in SEASONS:
        ks = season_totals(y).filter(pl.col("position") == "K").sort("pos_rank")
        get = lambda r: ks.filter(pl.col("pos_rank") == r).get_column("total").item()
        rows.append({"year": y, "K1": get(1), "K6": get(6), "K12": get(12),
                     "K18": get(18),
                     "K1-K12 per week": round((get(1) - get(12)) / 17, 2)})
    print(pl.DataFrame(rows))


def variance():
    """Within- vs between-kicker weekly variance, top-24 kickers by season."""
    parts = []
    for y in SEASONS:
        top = (season_totals(y).filter(pl.col("position") == "K", pl.col("pos_rank") <= 24)
               .get_column("player_id"))
        parts.append(weekly(y).filter(pl.col("player_id").is_in(top))
                     .select("player_id", "fpts").with_columns(pl.lit(y).alias("year")))
    df = pl.concat(parts).with_columns(
        pl.concat_str("player_id", pl.col("year").cast(pl.String)).alias("kseason"))
    total_var = df.get_column("fpts").var()
    means = df.group_by("kseason").agg(pl.col("fpts").mean().alias("m"), pl.len().alias("n"))
    grand = df.get_column("fpts").mean()
    between = ((means.get_column("m") - grand) ** 2 * means.get_column("n")).sum() / len(df)
    print(f"\n== Weekly kicker score variance (top-24 kickers, all years) ==")
    print(f"total var {total_var:.1f}; explained by WHICH kicker: "
          f"{between / total_var:.1%} — the rest is week-to-week noise")


def hot_start():
    print("\n== Top kicker through weeks 1-2: drafted in Sumfun? rest-of-season? ==")
    rows = []
    for y in SEASONS:
        early = season_totals(y, weeks=(1, 2)).filter(pl.col("position") == "K")
        hot = early.sort("total", descending=True).row(0, named=True)
        rest = season_totals(y, weeks=(3, 17)).filter(pl.col("position") == "K")
        r = rest.filter(pl.col("player_id") == hot["player_id"])
        rows.append({
            "year": y, "hot K (wk1-2)": hot["player_display_name"],
            "drafted?": hot["nname"] in league_drafted(y),
            "rest-of-season rank": r.get_column("pos_rank").item() if len(r) else None,
            "ros ppg": round(r.get_column("ppg").item(), 1) if len(r) else None,
        })
    print(pl.DataFrame(rows))

    print("\n== Eventual season K1: was he drafted in Sumfun? ==")
    rows = []
    for y in SEASONS:
        k1 = (season_totals(y).filter(pl.col("position") == "K", pl.col("pos_rank") == 1)
              .row(0, named=True))
        rows.append({"year": y, "season K1": k1["player_display_name"],
                     "total": k1["total"],
                     "drafted?": k1["nname"] in league_drafted(y)})
    print(pl.DataFrame(rows))


if __name__ == "__main__":
    spread()
    variance()
    hot_start()
