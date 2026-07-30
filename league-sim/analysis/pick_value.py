"""The draft decision metric: cost of waiting, in real fantasy points.

1. Fit E[season points | ADP] per position from 2020-2025 outcomes.
   Expectation is honest: busts, injuries and never-played seasons all
   count (a first-round pick's expectation already includes his 40%
   bust rate).
2. At each draft slot, the best player still available at a position
   sits at roughly the first ADP after that slot.  So
       E_pos(pick) = curve(first ADP at pos > pick)
   and the metric shown to the drafter is
       wait_cost(pos, pick, next_pick) = E_pos(pick) - E_pos(next_pick)
   Take the position with the biggest wait_cost your roster allows.
"""

import numpy as np
import polars as pl

from common import SEASONS, season_totals
from simfl.data import load_adp, norm_name

POS = ["QB", "RB", "WR", "TE", "K"]


def outcomes() -> pl.DataFrame:
    """Every ADP-listed player-season with his actual total (0 if he
    never produced)."""
    parts = []
    for y in SEASONS:
        adp = pl.DataFrame(load_adp(y)).with_columns(
            pl.col("name").map_elements(norm_name, return_dtype=pl.String).alias("nname"))
        tot = season_totals(y).select("nname", "total")
        parts.append(adp.join(tot, on="nname", how="left")
                     .with_columns(pl.col("total").fill_null(0.0),
                                   pl.lit(y).alias("year"))
                     .select("year", "nname", "pos", "adp", "total"))
    return pl.concat(parts)


def fit_curves(df: pl.DataFrame) -> dict[str, tuple[float, float]]:
    """Log-linear fit per position: E[total] = a + b * ln(adp).
    Two numbers per position — trivial to port to Go."""
    fits = {}
    print("== Fitted E[season points | ADP] = a + b*ln(ADP) ==")
    for pos in POS:
        d = df.filter(pl.col("pos") == pos)
        x, y = np.log(d["adp"].to_numpy()), d["total"].to_numpy()
        b, a = np.polyfit(x, y, 1)
        pred = a + b * x
        r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        fits[pos] = (a, b)
        print(f"{pos:>3}: a={a:6.1f}  b={b:6.1f}   R^2={r2:.2f}  (n={len(d)})")
    return fits


def check_fit(df: pl.DataFrame, fits) -> None:
    print("\n== Fit vs reality, by round (RB & WR): mean actual / mean fitted ==")
    d = df.filter(pl.col("pos").is_in(["RB", "WR"])).with_columns(
        ((pl.col("adp") - 1) // 12 + 1).alias("round"))
    for pos in ["RB", "WR"]:
        a, b = fits[pos]
        rows = []
        for r in range(1, 11):
            dd = d.filter(pl.col("pos") == pos, pl.col("round") == r)
            if len(dd) < 5:
                continue
            fitted = a + b * np.log(dd["adp"].to_numpy())
            rows.append(f"R{r}: {dd['total'].mean():5.0f}/{fitted.mean():5.0f}")
        print(f"{pos}: " + "  ".join(rows))


def best_available(df: pl.DataFrame, pos: str, pick: int) -> float:
    """Average over years of the first ADP at `pos` after `pick`."""
    vals = []
    for y in SEASONS:
        nxt = (df.filter(pl.col("year") == y, pl.col("pos") == pos,
                         pl.col("adp") > pick)
               .get_column("adp").min())
        if nxt is not None:
            vals.append(nxt)
    return float(np.mean(vals)) if vals else np.inf


def wait_cost_table(df: pl.DataFrame, fits) -> None:
    """The money table: points lost by waiting ONE round, per position,
    at the turn of each round (12-team league)."""
    E = lambda pos, pick: (fits[pos][0]
                           + fits[pos][1] * np.log(best_available(df, pos, pick)))
    print("\n== SEASON points lost by waiting one round (12-team) ==")
    header = "pick now->next   " + "".join(f"{p:>7}" for p in POS)
    print(header)
    for r in range(1, 13):
        now, nxt = (r - 1) * 12 + 6, r * 12 + 6  # mid-round vantage
        cells = ""
        for pos in POS:
            delta = E(pos, now) - E(pos, nxt)
            cells += f"{delta:7.1f}"
        print(f"R{r:<2} ({now:>3}->{nxt:<3})  {cells}")

    print("\n== E[season points] of best available at position, by pick ==")
    print("pick        " + "".join(f"{p:>7}" for p in POS))
    for pick in [1, 6, 12, 18, 24, 36, 48, 60, 72, 96, 120, 144]:
        cells = "".join(f"{E(pos, pick):7.0f}" for pos in POS)
        print(f"{pick:<12}{cells}")


if __name__ == "__main__":
    df = outcomes()
    fits = fit_curves(df)
    check_fit(df, fits)
    wait_cost_table(df, fits)
