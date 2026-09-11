"""Opportunity score = expected fantasy points from usage.

A player's opportunity score for a game is what his touches were worth
on average, before anything he did with them: each carry, target and
pass attempt is priced by where on the field it happened and (for
targets) how deep it was thrown. It is a per-position linear model fit
on 2021-2025 play-by-play, refit with `python ep_model.py fit`.

    ep = b0 + sum(b_f * count_f)          one model per position x format

Features (per player-game, from nflverse play-by-play, regular season):
  rush_att        carries (designed runs + QB scrambles)
  rush_rz         carries from the 20 or closer
  rush_i10        carries from the 10 or closer
  rush_i5         carries from the 5 or closer
  tgt             targets
  tgt_rz          targets from the 20 or closer
  tgt_i10         targets from the 10 or closer
  tgt_ez          end-zone targets (air yards reach the goal line)
  tgt_deep        targets thrown 20+ yards downfield
  air_yds         total air yards on targets
  pass_att        pass attempts (QB)
  pass_rz         pass attempts from the 20 or closer (QB)
  pass_i10        pass attempts from the 10 or closer (QB)
  pass_air_yds    total air yards thrown (QB)

The response is the player's actual fantasy points in that game
(nflverse fantasy_points for standard, fantasy_points_ppr for PPR, the
mean for half). The fit is ordinary least squares via numpy; no
scikit-learn, no random seeds, nothing to drift between runs.

Why linear and not a boosted model: the point of the number is that a
reader can see why it moved. A goal-line carry is worth what the
coefficient says it is worth, every week, for everyone.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from common import FORMATS, MODEL, SKILL, now_iso
import nfl_data

FIT_SEASONS = [2021, 2022, 2023, 2024, 2025]
HOLDOUT = 2025

FEATURES = {
    "QB": ["pass_att", "pass_rz", "pass_i10", "pass_air_yds",
           "rush_att", "rush_rz", "rush_i10", "rush_i5"],
    "RB": ["rush_att", "rush_rz", "rush_i10", "rush_i5",
           "tgt", "tgt_rz", "tgt_i10", "tgt_ez", "tgt_deep", "air_yds"],
    "WR": ["rush_att", "rush_rz", "rush_i10",
           "tgt", "tgt_rz", "tgt_i10", "tgt_ez", "tgt_deep", "air_yds"],
    "TE": ["rush_att",
           "tgt", "tgt_rz", "tgt_i10", "tgt_ez", "tgt_deep", "air_yds"],
}
ALL_FEATURES = sorted({f for fs in FEATURES.values() for f in fs})
COEF_PATH = MODEL / "ep_coefficients.json"


def usage(pbp: pl.DataFrame) -> pl.DataFrame:
    """Per player-game usage counts from play-by-play.
    Columns: season, week, game_id, player_id, team, <ALL_FEATURES>.
    Regular season only; a player appears if he had any opportunity."""
    p = pbp.filter(
        (pl.col("season_type") == "REG")
        & pl.col("play_type").is_in(["run", "pass"])
        & pl.col("posteam").is_not_null())
    yl = pl.col("yardline_100")
    ay = pl.col("air_yards").fill_null(0.0)
    base = ["season", "week", "game_id", "posteam"]

    rush = (p.filter(pl.col("rusher_player_id").is_not_null())
            .select(base + [pl.col("rusher_player_id").alias("player_id"),
                            pl.lit(1).alias("rush_att"),
                            (yl <= 20).cast(pl.Int32).alias("rush_rz"),
                            (yl <= 10).cast(pl.Int32).alias("rush_i10"),
                            (yl <= 5).cast(pl.Int32).alias("rush_i5")]))
    tgt = (p.filter(pl.col("receiver_player_id").is_not_null()
                    & (pl.col("pass_attempt") == 1))
           .select(base + [pl.col("receiver_player_id").alias("player_id"),
                           pl.lit(1).alias("tgt"),
                           (yl <= 20).cast(pl.Int32).alias("tgt_rz"),
                           (yl <= 10).cast(pl.Int32).alias("tgt_i10"),
                           (ay >= yl).cast(pl.Int32).alias("tgt_ez"),
                           (ay >= 20).cast(pl.Int32).alias("tgt_deep"),
                           ay.alias("air_yds")]))
    pas = (p.filter(pl.col("passer_player_id").is_not_null()
                    & (pl.col("pass_attempt") == 1)
                    & (pl.col("sack").fill_null(0) == 0))
           .select(base + [pl.col("passer_player_id").alias("player_id"),
                           pl.lit(1).alias("pass_att"),
                           (yl <= 20).cast(pl.Int32).alias("pass_rz"),
                           (yl <= 10).cast(pl.Int32).alias("pass_i10"),
                           ay.alias("pass_air_yds")]))
    frames = []
    for f in (rush, tgt, pas):
        if f.height:
            frames.append(f.group_by(base + ["player_id"]).sum())
    out = frames[0]
    for f in frames[1:]:
        out = out.join(f, on=base + ["player_id"], how="full", coalesce=True)
    for c in ALL_FEATURES:
        if c not in out.columns:
            out = out.with_columns(pl.lit(0.0).alias(c))
    out = out.with_columns([pl.col(c).fill_null(0).cast(pl.Float64)
                            for c in ALL_FEATURES])
    return out.rename({"posteam": "team"}).select(
        ["season", "week", "game_id", "player_id", "team"] + ALL_FEATURES)


def actuals(stats: pl.DataFrame) -> pl.DataFrame:
    """Per player-game actual points in the three formats + position."""
    s = stats.filter(pl.col("season_type") == "REG")
    return s.select([
        "season", "week", "player_id",
        pl.col("player_display_name").alias("name"),
        "position",
        pl.col("fantasy_points").fill_null(0.0).alias("pts_std"),
        pl.col("fantasy_points_ppr").fill_null(0.0).alias("pts_ppr"),
    ]).with_columns(((pl.col("pts_std") + pl.col("pts_ppr")) / 2).alias("pts_half"))


def panel(season: int, refresh: bool = False) -> pl.DataFrame:
    """usage x actuals for one season, skill positions only."""
    u = usage(nfl_data.pbp(season, refresh))
    a = actuals(nfl_data.player_stats(season, refresh))
    df = u.join(a, on=["season", "week", "player_id"], how="inner")
    return df.filter(pl.col("position").is_in(SKILL))


def _design(df: pl.DataFrame, feats: list[str]) -> np.ndarray:
    X = df.select(feats).to_numpy().astype(float)
    return np.hstack([np.ones((X.shape[0], 1)), X])


def _fit(df: pl.DataFrame, feats: list[str], target: str) -> dict:
    X = _design(df, feats)
    y = df[target].to_numpy().astype(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"_intercept": float(beta[0]),
            **{f: float(b) for f, b in zip(feats, beta[1:])}}


def predict(df: pl.DataFrame, coef: dict, pos: str, fmt: str) -> np.ndarray:
    c = coef["coef"][pos][fmt]
    feats = coef["features"][pos]
    X = _design(df, feats)
    beta = np.array([c["_intercept"]] + [c[f] for f in feats])
    return X @ beta


def _r2(y, yhat) -> float:
    ss = float(((y - y.mean()) ** 2).sum())
    return 1 - float(((y - yhat) ** 2).sum()) / ss if ss else float("nan")


def fit(seasons=FIT_SEASONS, holdout=HOLDOUT) -> dict:
    frames = [panel(s) for s in seasons]
    full = pl.concat(frames)
    train = full.filter(pl.col("season") != holdout)
    test = full.filter(pl.col("season") == holdout)
    out = {"fit_seasons": seasons, "holdout": holdout, "features": FEATURES,
           "coef": {}, "eval": {}, "fitted": now_iso(), "n_rows": full.height}
    for pos in SKILL:
        feats = FEATURES[pos]
        out["coef"][pos] = {}
        out["eval"][pos] = {}
        tr, te = train.filter(pl.col("position") == pos), test.filter(pl.col("position") == pos)
        for fmt in FORMATS:
            tgt = f"pts_{fmt}"
            # Held-out score first (fit on the other seasons only)...
            c_ho = _fit(tr, feats, tgt)
            tmp = {"coef": {pos: {fmt: c_ho}}, "features": FEATURES}
            yhat = predict(te, tmp, pos, fmt)
            y = te[tgt].to_numpy()
            out["eval"][pos][fmt] = {
                "holdout_r2": round(_r2(y, yhat), 3),
                "holdout_rmse": round(float(np.sqrt(((y - yhat) ** 2).mean())), 2),
                "n_train": tr.height, "n_test": te.height}
            # ...then the shipped coefficients use every season.
            out["coef"][pos][fmt] = _fit(full.filter(pl.col("position") == pos), feats, tgt)
    return out


def load_coef() -> dict:
    return json.loads(COEF_PATH.read_text())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fit":
        res = fit()
        COEF_PATH.write_text(json.dumps(res, indent=1))
        print(f"wrote {COEF_PATH}")
        for pos in SKILL:
            e = res["eval"][pos]["half"]
            print(f"  {pos}: held-out {HOLDOUT} R2={e['holdout_r2']} "
                  f"RMSE={e['holdout_rmse']} (n={e['n_test']})")
    else:
        print(__doc__)
