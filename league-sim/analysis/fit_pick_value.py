"""Fit E[season points | ADP] = a + b*ln(adp) per position, leave-one-
year-out: the fit used to draft year Y excludes year Y's outcomes, so
the PickValue strategy never sees the season it is drafting.

Writes data/pick_value_fits.json:
    {"2022": {"QB": [a, b], ...}, ..., "pooled": {...}}
"""

import json

import numpy as np
import polars as pl

from common import ROOT, SEASONS, season_totals
from simfl.data import load_adp, norm_name

POS = ["QB", "RB", "WR", "TE", "K"]


def outcomes() -> pl.DataFrame:
    parts = []
    for y in SEASONS:
        adp = pl.DataFrame(load_adp(y)).with_columns(
            pl.col("name").map_elements(norm_name, return_dtype=pl.String).alias("nname"))
        tot = season_totals(y).select("nname", "total")
        parts.append(adp.join(tot, on="nname", how="left")
                     .with_columns(pl.col("total").fill_null(0.0), pl.lit(y).alias("year"))
                     .select("year", "pos", "adp", "total"))
    return pl.concat(parts)


def fit(df: pl.DataFrame) -> dict[str, list[float]]:
    out = {}
    for pos in POS:
        d = df.filter(pl.col("pos") == pos)
        b, a = np.polyfit(np.log(d["adp"].to_numpy()), d["total"].to_numpy(), 1)
        out[pos] = [round(a, 2), round(b, 2)]
    return out


if __name__ == "__main__":
    df = outcomes()
    fits = {str(y): fit(df.filter(pl.col("year") != y)) for y in SEASONS}
    fits["pooled"] = fit(df)
    path = ROOT / "data" / "pick_value_fits.json"
    path.write_text(json.dumps(fits, indent=1))
    print(json.dumps(fits, indent=1))
