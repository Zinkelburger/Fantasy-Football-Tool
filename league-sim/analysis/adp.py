"""Truth #2: how predictive is ADP, really?

- Spearman rank correlation, ADP order vs actual season finish, by
  year, position, and ADP tier.
- Hit/bust rates by draft round: P(top-12 positional finish | ADP round).
"""

import numpy as np
import polars as pl

from common import SEASONS, season_totals
from simfl.data import load_adp, norm_name


def joined(year: int) -> pl.DataFrame:
    adp = pl.DataFrame(load_adp(year)).with_columns(
        pl.col("name").map_elements(norm_name, return_dtype=pl.String).alias("nname"))
    tot = season_totals(year)
    return (adp.join(tot, on="nname", how="left")
            .with_columns(pl.col("total").fill_null(0.0),
                          ((pl.col("adp") - 1) // 12 + 1).cast(pl.Int32).alias("adp_round")))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def correlations():
    print("== Spearman(ADP, season finish) — 1.0 would be a perfect oracle ==")
    rows = []
    for y in SEASONS:
        j = joined(y).filter(pl.col("pos") != "K")
        r = {"year": y,
             "all": round(spearman(j["adp"].to_numpy(), -j["total"].to_numpy()), 2)}
        for pos in ["QB", "RB", "WR", "TE"]:
            jp = j.filter(pl.col("pos") == pos)
            r[pos] = round(spearman(jp["adp"].to_numpy(), -jp["total"].to_numpy()), 2)
        rows.append(r)
    df = pl.DataFrame(rows)
    print(df)
    print("mean:", {c: round(df[c].mean(), 2) for c in df.columns if c != "year"})

    print("\n== Same, but within ADP tiers (all positions, all years pooled) ==")
    parts = [joined(y).filter(pl.col("pos") != "K") for y in SEASONS]
    j = pl.concat([p.select("adp", "total") for p in parts])
    for lo, hi in [(1, 24), (25, 60), (61, 120), (121, 200)]:
        t = j.filter(pl.col("adp").is_between(lo, hi))
        rho = spearman(t["adp"].to_numpy(), -t["total"].to_numpy())
        print(f"ADP {lo:>3}-{hi:<3}: rho = {rho:5.2f}   (n={len(t)})")


def hit_rates():
    print("\n== P(finish top-12 at position | ADP round), skill positions pooled ==")
    parts = []
    for y in SEASONS:
        j = joined(y).filter(pl.col("pos").is_in(["QB", "RB", "WR", "TE"]))
        parts.append(j.with_columns(pl.col("pos_rank").fill_null(999)))
    j = pl.concat(parts)
    out = (j.filter(pl.col("adp_round") <= 10)
           .group_by("adp_round")
           .agg((pl.col("pos_rank") <= 12).mean().round(2).alias("top12_rate"),
                (pl.col("pos_rank") <= 24).mean().round(2).alias("top24_rate"),
                pl.len().alias("n"))
           .sort("adp_round"))
    print(out)

    print("\n== First-round picks (ADP 1-12) that finished OUTSIDE positional top-12 ==")
    busts = (j.filter(pl.col("adp") <= 12, pl.col("pos_rank") > 12)
             .select("name", "pos", "adp", "pos_rank")
             .sort("adp"))
    print(f"{len(busts)}/{len(j.filter(pl.col('adp') <= 12))} first-rounders busted:")
    print(busts)


if __name__ == "__main__":
    correlations()
    hit_rates()
