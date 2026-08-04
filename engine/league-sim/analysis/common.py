"""Shared helpers for the analysis scripts."""

import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simfl.config import DEFAULT_SCORING, SEASONS  # noqa: E402
from simfl.data import load_weekly, norm_name  # noqa: E402

FANTASY_WEEKS = 17  # weeks 1-17 span every league week 2020-2025
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def weekly(year: int) -> pl.DataFrame:
    """Fantasy-relevant weekly rows with fpts."""
    df = load_weekly(year, DEFAULT_SCORING)
    return (df.filter(pl.col("position").is_in(POSITIONS),
                      pl.col("week") <= FANTASY_WEEKS)
            .with_columns(pl.col("player_display_name")
                          .map_elements(norm_name, return_dtype=pl.String)
                          .alias("nname")))


def season_totals(year: int, weeks: tuple[int, int] = (1, FANTASY_WEEKS)) -> pl.DataFrame:
    """One row per player: total, games, ppg, positional rank over a
    week range (rank 1 = most total points at the position)."""
    lo, hi = weeks
    wk = weekly(year).filter(pl.col("week").is_between(lo, hi))
    out = (wk.group_by("player_id", "player_display_name", "nname", "position")
           .agg(pl.col("fpts").sum().alias("total"),
                pl.len().alias("games"))
           .with_columns((pl.col("total") / pl.col("games")).alias("ppg"))
           .with_columns(pl.col("total").rank("ordinal", descending=True)
                         .over("position").alias("pos_rank")))
    return out.with_columns(pl.lit(year).alias("year"))


def league_drafted(year: int) -> set[str]:
    """Normalized names actually drafted in the Sumfun League."""
    picks = pl.read_parquet(ROOT / "data" / "espn" / "picks.parquet")
    return {norm_name(p) for p in
            picks.filter(pl.col("year") == year).get_column("player").to_list()}
