"""Current-week injury report (nflverse, sourced from the NFL's official
practice/game-status reports) plus the latest depth chart.

Output: data/weekly/injuries_<season>.csv (whole season, refreshed) and
data/weekly/depth_<season>.csv (latest snapshot only, skill positions).
"""
from __future__ import annotations

import polars as pl

from common import DATA
import nfl_data


def build(season: int, refresh: bool = True) -> tuple[pl.DataFrame, pl.DataFrame]:
    inj = nfl_data.injuries(season, refresh).filter(pl.col("season_type") == "REG")
    inj = inj.select(["week", "team", "gsis_id", "full_name", "position",
                      "report_status", "report_primary_injury",
                      "practice_status", "practice_primary_injury"])
    inj.write_csv(DATA / f"injuries_{season}.csv")

    dc = nfl_data.depth_charts(season, refresh)
    latest = dc.filter(pl.col("dt") == dc["dt"].max())
    latest = (latest.filter(pl.col("pos_abb").is_in(["QB", "RB", "WR", "TE", "K"]))
              .select(["dt", "team", "player_name", "gsis_id", "espn_id",
                       "pos_abb", "pos_rank"])
              .sort(["team", "pos_abb", "pos_rank"]))
    latest.write_csv(DATA / f"depth_{season}.csv")
    return inj, latest


def load(season: int, week: int) -> pl.DataFrame:
    p = DATA / f"injuries_{season}.csv"
    if not p.exists():
        return pl.DataFrame()
    df = pl.read_csv(p, infer_schema_length=10000)
    return df.filter(pl.col("week") == week)


def load_depth(season: int) -> pl.DataFrame:
    p = DATA / f"depth_{season}.csv"
    return pl.read_csv(p, infer_schema_length=10000) if p.exists() else pl.DataFrame()
