"""Optional descriptive usage export; never changes the expected-points model.

Run with --season YEAR [--refresh]. Without --refresh, strictly cache-only.
FTN charting: FTN Data via nflverse, CC-BY-SA 4.0. PFR fields retain their
source identity. Missing or partially charted totals stay null, not zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

import polars as pl

from common import CACHE, DATA, SKILL, now_iso
import ep_model

KEY = ["season", "week", "game_id", "player_id", "team"]


def build(pbp, stats, ftn=None, pfr=None, ids=None, snaps=None):
    usage = ep_model.usage(pbp)
    # Denominator includes every identified receiver, even non-skill players.
    usage = usage.with_columns(
        pl.col("tgt").sum().over(["season", "game_id", "team"]).alias("team_targets")
    ).with_columns(
        (pl.col("rush_att") + pl.col("tgt")).alias("opportunities"),
        pl.when(pl.col("team_targets") > 0)
        .then(pl.col("tgt") / pl.col("team_targets")).alias("target_share"))
    meta = stats.filter(pl.col("season_type") == "REG").select(
        "season", "week", "player_id", pl.col("player_display_name").alias("name"),
        "position", "receptions", "rushing_yards", "receiving_yards")
    out = usage.join(meta, on=["season", "week", "player_id"], validate="m:1")
    out = out.filter(pl.col("position").is_in(SKILL))
    targets = pbp.filter(
        (pl.col("season_type") == "REG") & (pl.col("play_type") == "pass")
        & (pl.col("pass_attempt") == 1) & pl.col("receiver_player_id").is_not_null()
        & pl.col("posteam").is_not_null()).select(
            "season", "week", "game_id", pl.col("play_id").cast(pl.Int64),
            pl.col("receiver_player_id").alias("player_id"),
            pl.col("posteam").alias("team"), "yardline_100", "air_yards")
    # Keep the screenshot's strict <20 definition alongside our model's <=20.
    context = targets.group_by(KEY).agg(
        (pl.col("yardline_100") < 20).sum().alias("tgt_rz_lt20"),
        pl.col("air_yards").count().alias("air_yards_known_targets"))
    out = out.join(context, on=KEY, how="left", validate="1:1")
    out = out.with_columns(
        pl.col("tgt_rz_lt20").fill_null(0),
        pl.col("air_yards_known_targets").fill_null(0))
    out = out.with_columns(pl.when(pl.col("air_yards_known_targets") == pl.col("tgt"))
                           .then(pl.col("air_yds")).alias("air_yds"))
    if ftn is not None and ftn.height:
        chart = ftn.select(pl.col("nflverse_game_id").alias("game_id"),
                           pl.col("nflverse_play_id").cast(pl.Int64).alias("play_id"),
                           "is_catchable_ball", "is_drop")
        joined = targets.join(chart, on=["game_id", "play_id"], how="left", validate="1:1")
        agg = joined.group_by(KEY).agg(
            pl.col("is_catchable_ball").count().alias("ftn_catchable_known_targets"),
            pl.col("is_drop").count().alias("ftn_drop_known_targets"),
            pl.col("is_catchable_ball").sum().alias("ftn_catchable_targets"),
            pl.col("is_drop").sum().alias("ftn_drops"))
        out = out.join(agg, on=KEY, how="left", validate="1:1")
    else:
        out = out.with_columns([pl.lit(None, dtype=pl.Int64).alias(c) for c in
            ("ftn_catchable_known_targets", "ftn_drop_known_targets",
             "ftn_catchable_targets", "ftn_drops")])
    out = out.with_columns(pl.col("ftn_catchable_known_targets").fill_null(0),
                           pl.col("ftn_drop_known_targets").fill_null(0))
    for label, count in [("ftn_catchable_targets", "ftn_catchable_known_targets"),
                         ("ftn_drops", "ftn_drop_known_targets")]:
        out = out.with_columns(pl.when((pl.col("tgt") > 0) & (pl.col(count) == pl.col("tgt")))
                               .then(pl.col(label)).alias(label))
    out = out.with_columns(pl.when(pl.col("tgt") > 0)
        .then(pl.col("ftn_catchable_known_targets") / pl.col("tgt")).alias("ftn_target_coverage"))
    crosswalk = (ids.select(pl.col("gsis_id").alias("player_id"), "pfr_id")
                 .drop_nulls().unique() if ids is not None else None)
    if pfr is not None and pfr.height and crosswalk is not None:
        rush = pfr.filter(pl.col("game_type") == "REG").join(
            crosswalk, left_on="pfr_player_id", right_on="pfr_id", validate="m:1").select(
                *KEY, pl.col("carries").alias("pfr_carries"),
                pl.col("rushing_yards_before_contact").alias("pfr_yards_before_contact"))
        out = out.join(rush, on=KEY, how="left", validate="1:1")
    else:
        out = out.with_columns(pl.lit(None, dtype=pl.Float64).alias("pfr_carries"),
                               pl.lit(None, dtype=pl.Float64).alias("pfr_yards_before_contact"))
    out = out.with_columns(
        pl.when(pl.col("pfr_carries").is_null()).then(pl.lit("unavailable"))
        .when(pl.col("pfr_carries") != pl.col("rush_att")).then(pl.lit("carry_mismatch"))
        .when(pl.col("pfr_yards_before_contact").is_null()).then(pl.lit("unavailable"))
        .otherwise(pl.lit("available")).alias("pfr_status"))
    out = out.with_columns(pl.when(pl.col("pfr_status") == "available")
                           .then(pl.col("pfr_yards_before_contact")).alias("pfr_yards_before_contact"))
    # PFR snap counts. offense_pct is PFR's own share of team offensive
    # snaps; we carry it rather than divide by a denominator of our own,
    # which would disagree with them on penalties and kneels. This is the
    # closest free stand-in for the route share the paid charting sells:
    # it says a player was on the field, not that he ran a route.
    if snaps is not None and snaps.height and crosswalk is not None:
        sn = snaps.filter(pl.col("game_type") == "REG").join(
            crosswalk, left_on="pfr_player_id", right_on="pfr_id", validate="m:1").select(
                *KEY, pl.col("offense_snaps").alias("snaps_off"),
                pl.col("offense_pct").alias("snap_share"))
        out = out.join(sn, on=KEY, how="left", validate="1:1")
    else:
        out = out.with_columns(pl.lit(None, dtype=pl.Float64).alias("snaps_off"),
                               pl.lit(None, dtype=pl.Float64).alias("snap_share"))
    out = out.with_columns(
        pl.when(pl.col("snaps_off").is_null()).then(pl.lit("unavailable"))
        .otherwise(pl.lit("available")).alias("snap_status"))
    return out.select(*KEY, "name", "position", "opportunities", "rush_att", "tgt",
        "team_targets", "target_share", "receptions", "rushing_yards", "receiving_yards",
        "air_yds", "air_yards_known_targets", "tgt_rz", "tgt_rz_lt20", "tgt_ez",
        "ftn_catchable_targets", "ftn_drops", "ftn_catchable_known_targets",
        "ftn_drop_known_targets", "ftn_target_coverage", "pfr_carries",
        "pfr_yards_before_contact", "pfr_status", "snaps_off", "snap_share",
        "snap_status").sort(["week", "position", "player_id"])


def write(season, refresh=False, refresh_base=True):
    import nflreadpy as nfl
    sources = {}

    def read(name, loader, optional=False):
        path = CACHE / f"{name}.parquet"
        error = None
        if refresh and (optional or refresh_base):
            try:
                frame = loader()
                frame.write_parquet(path)
            except Exception as exc:
                if not optional:
                    raise
                error = f"{type(exc).__name__}: {exc}"
        if not path.exists():
            if not optional:
                raise FileNotFoundError(f"Missing {path}; run with --refresh")
            sources[name] = {"status": "unavailable", "error": error}
            return None
        frame = pl.read_parquet(path)
        sources[name] = {"status": "cached_after_refresh_error" if error else "available",
            "error": error, "rows": frame.height,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "cache_written_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
        return frame

    pbp = read(f"pbp_{season}", lambda: nfl.load_pbp([season]))
    stats = read(f"player_stats_{season}", lambda: nfl.load_player_stats([season], summary_level="week"))
    ftn = read(f"ftn_{season}", lambda: nfl.load_ftn_charting([season]), True)
    pfr = read(f"pfr_rush_week_{season}", lambda: nfl.load_pfr_advstats(
        seasons=[season], stat_type="rush", summary_level="week"), True)
    ids = read("pfr_ids", lambda: nfl.load_players().select("gsis_id", "pfr_id"), True)
    snaps = read(f"snaps_{season}", lambda: nfl.load_snap_counts([season]), True)
    out = build(pbp, stats, ftn, pfr, ids, snaps)
    path = DATA / f"advanced_usage_{season}_weekly.csv"
    out.write_csv(path, float_precision=8)
    manifest = {"season": season, "generated_at": now_iso(), "sources": sources,
        "output_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "attribution": "FTN Data via nflverse (CC-BY-SA 4.0); PFR advanced rushing and snap counts via nflverse; nflverse play-by-play/player stats",
        "source_documentation": {
            "ftn": "https://nflreadr.nflverse.com/reference/load_ftn_charting.html",
            "pfr": "https://nflreadr.nflverse.com/reference/load_pfr_advstats.html",
            "snaps": "https://nflreadr.nflverse.com/reference/load_snap_counts.html",
            "schedule": "https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html"},
        "definitions": {"target_share": "player targets / all identified team targets in that game",
            "tgt_rz": "line of scrimmage <=20 yards to goal", "tgt_rz_lt20": "line of scrimmage <20 yards to goal",
            "ftn_catchable_targets": "FTN is_catchable_ball, not receptions plus drops",
            "snaps_off": "PFR offensive snaps played in that game",
            "snap_share": "PFR offense_pct, the player's share of team offensive snaps",
            "snap_share_is_not_route_share": "snaps say a player was on the field. "
                "Routes run, route share and targets per route run are PFF/FTN "
                "charting we do not have; target_share is the free stand-in.",
            "nulls": "unavailable or partial; zero only when observed", "purpose": "descriptive context; not model inputs"},
        "coverage_by_week": out.group_by("week").agg(
            pl.col("game_id").n_unique().alias("games"), pl.len().alias("player_rows"),
            (pl.col("tgt") > 0).sum().alias("targeted_players"),
            pl.col("ftn_catchable_targets").count().alias("players_with_complete_catchability"),
            (pl.col("pfr_status") == "available").sum().alias("players_with_ybcon"),
            (pl.col("snap_status") == "available").sum().alias("players_with_snaps")).sort("week").to_dicts()}
    path.with_suffix(".sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return out, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    table, manifest = write(args.season, args.refresh)
    print(json.dumps(manifest["coverage_by_week"], indent=2))
