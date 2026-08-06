"""Fit the in-game "remaining fantasy points" model and export it for the site.

Downloads nflverse play-by-play, attributes fantasy points per play with
a game clock attached, then fits the three things the live tracker needs:

  1. the decay rate a, in  remaining = a * projection * fraction_of_game_left
  2. sigma(position, clock), the spread of that estimate
  3. the correlation between a QB and his own pass-catchers

Writes engine/league-sim/data/market/ingame_params.json, which
site/build_site.py bundles for the browser.

Findings write-up: findings/35-in-game-model.md

Usage:
    python analysis/ingame_model.py --fetch     # download pbp first
    python analysis/ingame_model.py             # fit + export
"""

import argparse
import json
import urllib.request
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parent.parent
PBP = ROOT / "data" / "pbp"
OUT = ROOT / "data" / "market" / "ingame_params.json"

SEASONS = [2021, 2022, 2023, 2024, 2025]
FIT_YEARS = [2021, 2022, 2023, 2024]
POS = ["QB", "RB", "WR", "TE"]
CHECKS = list(range(0, 3601, 300))
PPR = 0.5   # half-PPR is the worldwide median; the shape barely moves with format

PBP_URL = ("https://github.com/nflverse/nflverse-data/releases/download/pbp/"
           "play_by_play_{year}.parquet")


# --------------------------------------------------------------- fetch
def fetch() -> None:
    PBP.mkdir(parents=True, exist_ok=True)
    for y in SEASONS:
        dest = PBP / f"play_by_play_{y}.parquet"
        if dest.exists():
            print(f"{y}: cached")
            continue
        print(f"{y}: downloading ...", flush=True)
        urllib.request.urlretrieve(PBP_URL.format(year=y), dest)
        print(f"{y}: {dest.stat().st_size / 1e6:.0f} MB")


# ------------------------------------------------------- attribution
def attribute(df: pl.DataFrame) -> pl.DataFrame:
    """One row per (player, play) carrying the points that play gave them."""
    zero = ["passing_yards", "receiving_yards", "rushing_yards", "pass_touchdown",
            "rush_touchdown", "complete_pass", "interception", "fumble_lost"]
    df = df.with_columns([pl.col(c).fill_null(0) for c in zero])
    base = ["game_id", "season", "week", "posteam", "game_seconds_remaining",
            "score_differential", "spread_line", "total_line", "home_team"]

    parts = [
        df.filter(pl.col("passer_player_id").is_not_null()).select(
            *base, pl.col("passer_player_id").alias("player_id"),
            (pl.col("passing_yards") * 0.04 + pl.col("pass_touchdown") * 4
             + pl.col("interception") * -2).alias("pts")),
        df.filter(pl.col("rusher_player_id").is_not_null()).select(
            *base, pl.col("rusher_player_id").alias("player_id"),
            (pl.col("rushing_yards") * 0.1 + pl.col("rush_touchdown") * 6).alias("pts")),
        df.filter(pl.col("receiver_player_id").is_not_null()).select(
            *base, pl.col("receiver_player_id").alias("player_id"),
            (pl.col("receiving_yards") * 0.1 + pl.col("pass_touchdown") * 6
             + pl.col("complete_pass") * PPR).alias("pts")),
        df.filter((pl.col("fumble_lost") == 1)
                  & pl.col("fumbled_1_player_id").is_not_null()).select(
            *base, pl.col("fumbled_1_player_id").alias("player_id"),
            pl.lit(-2.0).alias("pts")),
    ]
    return (pl.concat(parts, how="vertical_relaxed")
            .filter(pl.col("game_seconds_remaining").is_not_null()))


def build_panel() -> pl.DataFrame:
    frames = []
    for y in SEASONS:
        raw = pl.read_parquet(PBP / f"play_by_play_{y}.parquet")
        frames.append(attribute(raw.filter(pl.col("season_type") == "REG")))
    plays = pl.concat(frames)

    pos = pl.concat([pl.read_parquet(ROOT / f"data/weekly_{y}.parquet")
                     .select("player_id", "position").unique() for y in SEASONS]
                    ).unique(subset=["player_id"])

    pg = (plays.group_by("season", "week", "game_id", "player_id")
          .agg(pl.col("pts").sum().alias("total"),
               pl.col("posteam").drop_nulls().first().alias("team"))
          .join(pos, on="player_id", how="left")
          .filter(pl.col("position").is_in(POS))
          .sort("season", "week"))

    # leak-free stand-in for "the projection a manager had": EWMA of prior games
    pg = pg.with_columns(
        pl.col("total").shift(1).ewm_mean(alpha=0.35, ignore_nulls=True)
        .over(["player_id", "season"]).alias("proj"),
        pl.col("total").shift(1).cum_count().over(["player_id", "season"]).alias("n_prior"))

    snaps = []
    for sec in CHECKS:
        cum = (plays.filter(pl.col("game_seconds_remaining") >= sec)
               .group_by("game_id", "player_id").agg(pl.col("pts").sum().alias("so_far")))
        s = (pg.join(cum, on=["game_id", "player_id"], how="left")
             .with_columns(pl.col("so_far").fill_null(0.0), pl.lit(sec).alias("sec_left")))
        snaps.append(s.with_columns((pl.col("total") - pl.col("so_far")).alias("remaining")))

    panel = pl.concat(snaps).with_columns((pl.col("sec_left") / 3600).alias("frac_left"))
    return panel.filter(pl.col("proj").is_not_null() & (pl.col("n_prior") >= 3))


# ------------------------------------------------------------- fitting
def fit(panel: pl.DataFrame) -> dict:
    train = panel.filter(pl.col("season").is_in(FIT_YEARS))
    params = {"decay": {}, "sigma": {}, "sigma_var_fn": {}, "clock_curve": {},
              "correlation": {}, "shrink": 0.87,
              "_meta": {"seasons": SEASONS, "fit_years": FIT_YEARS,
                        "scoring": "half-PPR decimal", "checkpoints": CHECKS}}

    resid_frames = []
    for pos in POS:
        d = train.filter(pl.col("position") == pos)
        x = (d.get_column("proj") * d.get_column("frac_left")).to_numpy()
        y = d.get_column("remaining").to_numpy()
        a = float(x @ y / (x @ x))
        params["decay"][pos] = round(a, 4)

        full = panel.filter(pl.col("position") == pos)
        xf = (full.get_column("proj") * full.get_column("frac_left")).to_numpy()
        resid_frames.append(full.with_columns(
            pl.Series("pred", a * xf),
            pl.Series("resid", full.get_column("remaining").to_numpy() - a * xf)))

    res = pl.concat(resid_frames)
    tr = res.filter(pl.col("season").is_in(FIT_YEARS))

    for pos in POS:
        by_clock = {}
        for sec in CHECKS[1:]:
            f = tr.filter((pl.col("position") == pos) & (pl.col("sec_left") == sec))
            if len(f) < 100:
                continue
            by_clock[str(sec)] = round(float(f.get_column("resid").std(ddof=1)), 3)
        params["sigma"][pos] = by_clock

        # Var(remaining) = c0 + c1*pred + c2*pred^2, fit at kickoff
        f = tr.filter((pl.col("position") == pos) & (pl.col("sec_left") == 3600))
        pr = f.get_column("pred").to_numpy()
        r2 = f.get_column("resid").to_numpy() ** 2
        X = np.column_stack([np.ones_like(pr), pr, pr ** 2])
        beta, *_ = np.linalg.lstsq(X, r2, rcond=None)
        params["sigma_var_fn"][pos] = [round(float(b), 5) for b in beta]

    # clock curve: share of a game's fantasy points scored by each checkpoint
    pooled = tr.group_by("sec_left").agg(pl.col("so_far").mean().alias("sf"),
                                         pl.col("total").mean().alias("t")).sort("sec_left")
    params["clock_curve"] = {str(r["sec_left"]): round(r["sf"] / r["t"], 4)
                             for r in pooled.iter_rows(named=True)}

    # QB <-> own pass-catcher, and opposing-QB shootout
    k = res.filter(pl.col("sec_left") == 3600).select(
        "game_id", "player_id", "team", "position", "resid")
    pr = k.join(k, on="game_id", suffix="_b").filter(
        pl.col("player_id") != pl.col("player_id_b"))

    def rho(df):
        if len(df) < 200:
            return None
        return round(float(np.corrcoef(df.get_column("resid").to_numpy(),
                                       df.get_column("resid_b").to_numpy())[0, 1]), 4)

    same = pr.filter(pl.col("team") == pl.col("team_b"))
    opp = pr.filter(pl.col("team") != pl.col("team_b"))
    params["correlation"] = {
        "qb_wr_same_team": rho(same.filter((pl.col("position") == "QB")
                                           & (pl.col("position_b") == "WR"))),
        "qb_te_same_team": rho(same.filter((pl.col("position") == "QB")
                                           & (pl.col("position_b") == "TE"))),
        "qb_rb_same_team": rho(same.filter((pl.col("position") == "QB")
                                           & (pl.col("position_b") == "RB"))),
        "wr_wr_same_team": rho(same.filter((pl.col("position") == "WR")
                                           & (pl.col("position_b") == "WR"))),
        "qb_qb_opposing": rho(opp.filter((pl.col("position") == "QB")
                                         & (pl.col("position_b") == "QB"))),
        "wr_wr_opposing": rho(opp.filter((pl.col("position") == "WR")
                                         & (pl.col("position_b") == "WR"))),
    }
    return params


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="download play-by-play first")
    args = ap.parse_args()

    if args.fetch:
        fetch()
    if not (PBP / f"play_by_play_{SEASONS[0]}.parquet").exists():
        raise SystemExit("no play-by-play cached — rerun with --fetch")

    panel = build_panel()
    print(f"panel: {len(panel):,} player-game-checkpoints")
    params = fit(panel)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(params, indent=2))
    print(f"wrote {OUT}")
    print(json.dumps({k: params[k] for k in ("decay", "correlation", "shrink")}, indent=2))


if __name__ == "__main__":
    main()
