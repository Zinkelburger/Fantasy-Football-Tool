"""Kicker and D/ST parameters for the live win-probability model.

`ingame_model.py` fits QB/RB/WR/TE off play-by-play, because those four
positions have their fantasy points attributable to a play with a clock
on it. It leaves out the other two starting slots, and the browser was
quietly falling back to a flat sigma of 6 for both — an invented number
sitting in the middle of a model that is otherwise measured.

This script fills the gap with the same method, and is honest about
where the method runs out:

- **K** gets the full treatment. Kicks are plays, `kick_distance` and
  `field_goal_result` are on them, so a kicker's remaining points at a
  given clock reading are as computable as a running back's.
- **D/ST** cannot get it. A defense's biggest scoring component is the
  points-allowed tier, which is only knowable when the game ends —
  "remaining D/ST points at halftime" is not well defined the way
  "remaining rushing points" is. So D/ST gets a real full-game sigma
  (fit on `dst_model.build_dst_weeks()`, the same weekly D/ST points
  finding 27 is built on) and **borrows the clock shape** from the
  pooled offensive positions. That borrowing is an assumption, not a
  measurement, and it is written into the output so nobody mistakes it
  for one.

Output merges into `data/market/ingame_params.json` next to the
positions ingame_model.py fits. Run that one first.

    python analysis/kdst_sigma.py
"""
import json
from pathlib import Path

import numpy as np
import polars as pl

import dst_model

ROOT = Path(__file__).resolve().parent.parent
PBP = ROOT / "data" / "pbp"
OUT = ROOT / "data" / "market" / "ingame_params.json"

SEASONS = [2021, 2022, 2023, 2024, 2025]
FIT_YEARS = [2021, 2022, 2023, 2024]
CHECKS = [0, 300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000, 3300, 3600]

# Standard kicker scoring, which is what every format this site targets
# uses: 3 for a field goal, +1 per 10 yards past 40, 1 for the PAT,
# -1 for a missed field goal.
def fg_points(dist: float) -> float:
    if dist is None:
        return 3.0
    if dist >= 50:
        return 5.0
    if dist >= 40:
        return 4.0
    return 3.0


# --------------------------------------------------------------- kicker
def kicker_plays() -> pl.DataFrame:
    """One row per kick, carrying the points it was worth and the clock."""
    frames = []
    for y in SEASONS:
        df = pl.read_parquet(
            PBP / f"play_by_play_{y}.parquet",
            columns=["game_id", "season", "week", "season_type", "posteam",
                     "game_seconds_remaining", "kicker_player_id",
                     "field_goal_result", "kick_distance",
                     "extra_point_result", "field_goal_attempt",
                     "extra_point_attempt"])
        df = df.filter((pl.col("season_type") == "REG")
                       & pl.col("kicker_player_id").is_not_null()
                       & pl.col("game_seconds_remaining").is_not_null()
                       & ((pl.col("field_goal_attempt") == 1)
                          | (pl.col("extra_point_attempt") == 1)))
        dist = df.get_column("kick_distance").to_numpy()
        fgr = df.get_column("field_goal_result").to_list()
        xpr = df.get_column("extra_point_result").to_list()
        fga = df.get_column("field_goal_attempt").to_numpy()

        pts = np.zeros(len(df))
        for i in range(len(df)):
            if fga[i] == 1:
                pts[i] = fg_points(dist[i]) if fgr[i] == "made" else -1.0
            else:
                pts[i] = 1.0 if xpr[i] == "good" else 0.0
        frames.append(df.with_columns(pl.Series("pts", pts))
                      .rename({"kicker_player_id": "player_id"})
                      .select("game_id", "season", "week", "posteam",
                              "game_seconds_remaining", "player_id", "pts"))
    return pl.concat(frames)


def kicker_panel(plays: pl.DataFrame) -> pl.DataFrame:
    """Same shape as ingame_model.build_panel: one row per
    (player, game, checkpoint) with the leak-free EWMA projection."""
    pg = (plays.group_by("season", "week", "game_id", "player_id")
          .agg(pl.col("pts").sum().alias("total"),
               pl.col("posteam").drop_nulls().first().alias("team"))
          .sort("season", "week"))
    pg = pg.with_columns(
        pl.col("total").shift(1).ewm_mean(alpha=0.35, ignore_nulls=True)
        .over(["player_id", "season"]).alias("proj"),
        pl.col("total").shift(1).cum_count()
        .over(["player_id", "season"]).alias("n_prior"))

    snaps = []
    for sec in CHECKS:
        cum = (plays.filter(pl.col("game_seconds_remaining") >= sec)
               .group_by("game_id", "player_id")
               .agg(pl.col("pts").sum().alias("so_far")))
        s = (pg.join(cum, on=["game_id", "player_id"], how="left")
             .with_columns(pl.col("so_far").fill_null(0.0),
                           pl.lit(sec).alias("sec_left")))
        snaps.append(s.with_columns(
            (pl.col("total") - pl.col("so_far")).alias("remaining")))

    panel = pl.concat(snaps).with_columns(
        (pl.col("sec_left") / 3600).alias("frac_left"))
    return panel.filter(pl.col("proj").is_not_null() & (pl.col("n_prior") >= 3))


def fit_clocked(panel: pl.DataFrame) -> dict:
    """decay, the sigma-by-clock table and the variance function — the
    same three things ingame_model.fit() produces per position."""
    train = panel.filter(pl.col("season").is_in(FIT_YEARS))
    x = (train.get_column("proj") * train.get_column("frac_left")).to_numpy()
    y = train.get_column("remaining").to_numpy()
    decay = float(x @ y / (x @ x))

    xf = (panel.get_column("proj") * panel.get_column("frac_left")).to_numpy()
    panel = panel.with_columns(
        pl.Series("pred", decay * xf),
        pl.Series("resid", panel.get_column("remaining").to_numpy() - decay * xf))
    tr = panel.filter(pl.col("season").is_in(FIT_YEARS))

    by_clock = {}
    for sec in CHECKS[1:]:
        f = tr.filter(pl.col("sec_left") == sec)
        if len(f) < 100:
            continue
        by_clock[str(sec)] = round(float(f.get_column("resid").std(ddof=1)), 3)

    f = tr.filter(pl.col("sec_left") == 3600)
    pr = f.get_column("pred").to_numpy()
    r2 = f.get_column("resid").to_numpy() ** 2
    X = np.column_stack([np.ones_like(pr), pr, pr ** 2])
    beta, *_ = np.linalg.lstsq(X, r2, rcond=None)

    return {"decay": round(decay, 4), "sigma": by_clock,
            "var_fn": [round(float(b), 5) for b in beta], "n": len(tr)}


# ----------------------------------------------------------------- D/ST
def fit_dst(shape: dict) -> dict:
    """Full-game sigma from real weekly D/ST points; clock shape borrowed.

    `shape` is the pooled offensive sigma-by-clock table normalised to
    its own 3600 value, i.e. "how much of a full game's uncertainty is
    still ahead of you at each clock reading."
    """
    df = dst_model.build_dst_weeks().sort_values(["season", "week"])
    df["proj"] = (df.groupby(["season", "d"])["pts"]
                  .transform(lambda s: s.shift(1).ewm(alpha=0.35).mean()))
    df["n_prior"] = df.groupby(["season", "d"])["pts"].transform(
        lambda s: s.shift(1).expanding().count())
    df = df[df.proj.notna() & (df.n_prior >= 3)]
    tr = df[df.season.isin(FIT_YEARS)]

    x, y = tr.proj.to_numpy(), tr.pts.to_numpy()
    decay = float(x @ y / (x @ x))
    pred = decay * x
    resid = y - pred
    sd = float(resid.std(ddof=1))

    X = np.column_stack([np.ones_like(pred), pred, pred ** 2])
    beta, *_ = np.linalg.lstsq(X, resid ** 2, rcond=None)

    sigma = {str(sec): round(sd * shape[str(sec)], 3)
             for sec in CHECKS[1:] if str(sec) in shape}
    return {"decay": round(decay, 4), "sigma": sigma,
            "var_fn": [round(float(b), 5) for b in beta], "n": len(tr)}


def main() -> None:
    params = json.loads(OUT.read_text())

    print("kicker: reading play-by-play ...", flush=True)
    kp = kicker_panel(kicker_plays())
    k = fit_clocked(kp)
    print(f"  n={k['n']}  decay={k['decay']}  sigma(3600)={k['sigma']['3600']}")

    # the borrowed shape: mean over QB/RB/WR/TE of sigma(sec)/sigma(3600)
    off = [params["sigma"][p] for p in ("QB", "RB", "WR", "TE")]
    shape = {sec: float(np.mean([t[sec] / t["3600"] for t in off]))
             for sec in off[0] if all(sec in t for t in off)}

    print("d/st: building weekly defensive scoring ...", flush=True)
    d = fit_dst(shape)
    print(f"  n={d['n']}  decay={d['decay']}  sigma(3600)={d['sigma']['3600']}")

    for pos, fit in (("K", k), ("DST", d)):
        params["decay"][pos] = fit["decay"]
        params["sigma"][pos] = fit["sigma"]
        params["sigma_var_fn"][pos] = fit["var_fn"]

    params["_meta"]["kdst"] = {
        "k": "fit on play-by-play like the other positions",
        "dst": ("full-game sigma fit on weekly D/ST points; the clock "
                "shape is BORROWED from the offensive positions, because "
                "the points-allowed tier is only knowable at game end"),
        "k_scoring": "3/4/5 by distance, 1 PAT, -1 miss",
        "dst_scoring": "dst_model.py tiers (ESPN default-ish)",
    }
    OUT.write_text(json.dumps(params, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
