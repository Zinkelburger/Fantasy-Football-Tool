"""Cache-only feasibility check of the two receiver-analysis posts.

Run from the repo with .venv-league-sim/bin/python research/receiver-role-audit/audit.py
Writes only results.json beside this script. No forecasts or production changes.
"""
from pathlib import Path
import hashlib
import json

import polars as pl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / "engine/weekly/cache"
SOURCES = {}


def read(name):
    path = CACHE / f"{name}.parquet"
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pl.read_parquet(path)


def ratio(a, b):
    return a / b if b else None


def receiving(d):
    totals = {k: d[k].sum() for k in [
        "targets", "receptions", "receiving_yards", "receiving_air_yards",
        "receiving_yards_after_catch", "receiving_tds", "receiving_16"]}
    t, r = totals["targets"], totals["receptions"]
    return dict(totals, games=d.height,
                yards_per_target=ratio(totals["receiving_yards"], t),
                adot=ratio(totals["receiving_air_yards"], t),
                yac_per_reception=ratio(totals["receiving_yards_after_catch"], r),
                ppr_ppg=d["fantasy_points_ppr"].mean())


def main():
    stats = read("player_stats_2025").filter(pl.col("season_type") == "REG")
    assert stats.select("player_id", "week").is_duplicated().sum() == 0
    flowers = stats.filter(pl.col("player_display_name") == "Zay Flowers")
    assert flowers.height == 17
    player_id = flowers["player_id"].unique().item()
    result = {"season": 2025, "purpose": "descriptive reproduction, not a predictive backtest"}
    result["flowers_full_regular_season"] = receiving(flowers)
    result["flowers_weeks_1_17"] = receiving(flowers.filter(pl.col("week") <= 17))

    # Ratios of totals in the player's recorded games, not averages of weekly shares.
    team = stats.join(flowers.select("team", "week"), on=["team", "week"], how="semi")
    ts = ratio(flowers["targets"].sum(), team["targets"].sum())
    ays = ratio(flowers["receiving_air_yards"].sum(), team["receiving_air_yards"].sum())
    result["flowers_opportunity"] = {
        "team_targets": team["targets"].sum(),
        "team_air_yards": team["receiving_air_yards"].sum(),
        "target_share": ts, "air_yards_share": ays, "wopr": 1.5 * ts + 0.7 * ays}
    lamar_weeks = stats.filter((pl.col("player_display_name") == "Lamar Jackson")
                               & (pl.col("attempts") > 0))["week"].to_list()
    result["flowers_lamar_game_splits"] = {
        "definition": "Lamar recorded at least one pass attempt; not a health or on-field split",
        "with": receiving(flowers.filter(pl.col("week").is_in(lamar_weeks))),
        "without": receiving(flowers.filter(~pl.col("week").is_in(lamar_weeks)))}

    pbp = read("pbp_2025").filter(
        (pl.col("season_type") == "REG") & pl.col("play_type").is_in(["pass", "run"])
        & (pl.col("qb_kneel") == 0) & (pl.col("qb_spike") == 0)
        & (pl.col("two_point_attempt") == 0)
        & ((pl.col("qb_dropback") == 1) | (pl.col("rush_attempt") == 1)))
    ftn = read("ftn_2025").select(
        pl.col("nflverse_game_id").alias("game_id"),
        pl.col("nflverse_play_id").cast(pl.Float64).alias("play_id"),
        "is_play_action", "is_motion", "is_screen_pass", "read_thrown")
    assert ftn.select("game_id", "play_id").is_duplicated().sum() == 0
    plays = pbp.join(ftn, on=["game_id", "play_id"], how="left", validate="1:1")
    result["team_context"] = {}
    for team_name in ["BAL", "CHI", "DEN"]:
        p = plays.filter(pl.col("posteam") == team_name)
        drop = p.filter(pl.col("qb_dropback") == 1)
        first = p.filter(pl.col("down") == 1)
        row = {"plays": p.height, "dropbacks": drop.height,
               "games": p["game_id"].n_unique(),
               "dropback_rate": p["qb_dropback"].mean(),
               "mean_pass_oe_percentage_points": p["pass_oe"].mean(),
               "pass_oe_known_plays": p["pass_oe"].count(),
               "first_down_dropback_rate": first["qb_dropback"].mean()}
        for field, population in [("is_play_action", drop), ("is_motion", p)]:
            known = population[field].count()
            row[field + "_known"] = known
            row[field + "_population"] = population.height
            row[field + "_rate"] = population[field].mean() if known == population.height else None
        result["team_context"][team_name] = row

    targets = plays.filter((pl.col("receiver_player_id") == player_id)
                           & (pl.col("pass_attempt") == 1))
    assert targets.height == flowers["targets"].sum()
    result["flowers_target_splits"] = {}
    for field in ["is_play_action", "is_motion", "is_screen_pass", "read_thrown"]:
        rows = []
        for label in targets[field].unique().sort().to_list():
            part = targets.filter(pl.col(field).is_null() if label is None else pl.col(field) == label)
            rows.append({"label": label, "targets": part.height,
                         "receptions": part["complete_pass"].sum(),
                         "receiving_yards": part["receiving_yards"].sum(),
                         "yards_per_target": ratio(part["receiving_yards"].sum(), part.height)})
        result["flowers_target_splits"][field] = rows
    assert targets["receiving_yards"].sum() == flowers["receiving_yards"].sum()
    result["definitions_and_limits"] = [
        "All games are 2025 REG; separate weeks 1-17 sensitivity excludes Week 18.",
        "PPR is nflverse fantasy_points_ppr, including rushing and fumbles.",
        "Team target denominator includes all identified receivers, not just WRs.",
        "WOPR = 1.5 * target share + 0.7 * air-yards share.",
        "FTN motion identifies motion on the play, not which player moved or motion specifically at snap.",
        "FTN read_thrown labels the targeted read, not every receiver's assigned progression.",
        "Team PA denominator is all retained dropbacks; motion denominator is all retained offensive plays.",
        "Missing charting is unknown; aggregate rates require full coverage, and splits retain a null bucket.",
        "Target splits are yards per TARGET. Routes, route types, route depth and YPRR are unavailable.",
        "Provider play/target definitions can differ. Rank among 250-route qualifiers cannot be reproduced.",
        "Historical finalized caches do not establish when data was available for a live decision."]
    result["attribution"] = "nflverse player stats/PBP; FTN Data via nflverse (CC-BY-SA 4.0)"
    result["source_sha256"] = SOURCES
    (HERE / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
