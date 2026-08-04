"""Compute fantasy points from nflverse weekly stat rows."""

import polars as pl

from .config import ScoringConfig

# Every stat column the scoring formula touches; filled with 0 when null.
STAT_COLS = [
    "passing_yards", "passing_tds", "passing_interceptions",
    "rushing_yards", "rushing_tds",
    "receiving_yards", "receiving_tds", "receptions",
    "fumbles_lost_total",
    "passing_2pt_conversions", "rushing_2pt_conversions",
    "receiving_2pt_conversions",
    "special_teams_tds",
    "fg_made_0_19", "fg_made_20_29", "fg_made_30_39",
    "fg_made_40_49", "fg_made_50_59", "fg_made_60_",
    "pat_made", "fg_missed",
]


def _floor_div(col: str, per: int) -> pl.Expr:
    # ESPN whole-point scoring: floor(yards / increment), per category.
    return (pl.col(col).cast(pl.Float64) / per).floor()


def add_fantasy_points(df: pl.DataFrame, sc: ScoringConfig) -> pl.DataFrame:
    df = df.with_columns([pl.col(c).fill_null(0) for c in STAT_COLS if c in df.columns])
    for c in STAT_COLS:
        if c not in df.columns:
            df = df.with_columns(pl.lit(0).alias(c))

    fpts = (
        _floor_div("passing_yards", sc.pass_yds_per_pt)
        + pl.col("passing_tds") * sc.pass_td
        + pl.col("passing_interceptions") * sc.interception
        + _floor_div("rushing_yards", sc.rush_yds_per_pt)
        + pl.col("rushing_tds") * sc.rush_td
        + _floor_div("receiving_yards", sc.rec_yds_per_pt)
        + pl.col("receiving_tds") * sc.rec_td
        + pl.col("receptions") * sc.reception
        + pl.col("fumbles_lost_total") * sc.fumble_lost
        + (pl.col("passing_2pt_conversions") + pl.col("rushing_2pt_conversions")
           + pl.col("receiving_2pt_conversions")) * sc.two_pt
        + pl.col("special_teams_tds") * sc.return_td
        + (pl.col("fg_made_0_19") + pl.col("fg_made_20_29") + pl.col("fg_made_30_39")) * sc.fg_0_39
        + pl.col("fg_made_40_49") * sc.fg_40_49
        + (pl.col("fg_made_50_59") + pl.col("fg_made_60_")) * sc.fg_50_plus
        + pl.col("pat_made") * sc.pat
        + pl.col("fg_missed") * sc.fg_miss
    )
    return df.with_columns(fpts.alias("fpts"))
