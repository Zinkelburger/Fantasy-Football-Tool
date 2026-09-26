"""Does scoring above or below expected points persist?

A from-scratch re-examination of findings 16, 17 and 39. It asks one
question several ways: when a player's actual fantasy points differ from
the points his usage was worth (the "gap"), does that gap carry forward,
vanish, or reverse ("he's due")?

Two independent expected-points (xFP) models, both in standard scoring:

  nflverse   ff_opportunity play-level model, 2017-2025. Not fitted by us.
             Standard = PPR total minus receptions (and the expected
             versions of both).
  ours       engine/weekly/ep_model.py usage model, 2021-2025, refit
             leave-one-season-out so no season is scored by coefficients
             fitted on its own outcomes.

Regular season only. Every interval is a player-cluster bootstrap: a
player's games (or seasons) are resampled together, because the same
player appearing many times is not many independent observations.

Run: .venv-league-sim/bin/python research/regression-to-expected/analyze.py
Writes results.json beside this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "weekly"))
OUT = Path(__file__).with_name("results.json")
POS = ["QB", "RB", "WR", "TE"]
B = 400                      # bootstrap resamples
RNG = np.random.default_rng(20260924)
ALPHA = 0.35                 # the production EWMA weight on the newest game


# ---------------------------------------------------------------- data

def load_nflverse() -> pl.DataFrame:
    d = pl.read_parquet(ROOT / "engine/league-sim/data/ff_opportunity_2017_2025.parquet")
    d = d.with_columns(pl.col("season").cast(pl.Int32), pl.col("week").cast(pl.Int32))
    d = d.filter(pl.col("position").is_in(POS)
                 & (pl.col("week") <= pl.when(pl.col("season") <= 2020).then(17).otherwise(18)))
    f = lambda c: pl.col(c).fill_null(0.0)
    td_gap = 6 * (f("rush_touchdown_diff") + f("rec_touchdown_diff")) + 4 * f("pass_touchdown_diff")
    return d.select(
        "season", "week", "player_id", pl.col("full_name").alias("name"),
        pl.col("position").alias("pos"), pl.col("posteam").alias("team"),
        (f("total_fantasy_points") - f("receptions")).alias("y"),
        (f("total_fantasy_points_exp") - f("receptions_exp")).alias("x"),
        td_gap.alias("td_gap"),
        f("rec_attempt").alias("tgt"), f("receptions").alias("rec"),
        f("receptions_exp").alias("rec_exp"),
        f("rush_attempt").alias("car"),
    ).with_columns((pl.col("y") - pl.col("x")).alias("gap")) \
     .with_columns((pl.col("gap") - pl.col("td_gap")).alias("nontd_gap"))


def load_ours() -> pl.DataFrame:
    import ep_model
    frames = {s: ep_model.panel(s) for s in range(2021, 2026)}
    out = []
    for s, test in frames.items():
        train = pl.concat([f for t, f in frames.items() if t != s])
        for pos in POS:
            feats = ep_model.FEATURES[pos]
            coef = ep_model._fit(train.filter(pl.col("position") == pos), feats, "pts_std")
            te = test.filter(pl.col("position") == pos)
            beta = np.array([coef["_intercept"]] + [coef[k] for k in feats])
            x = np.maximum(ep_model._design(te, feats) @ beta, 0.0)   # production floors at zero
            out.append(te.select("season", "week", "player_id", "name",
                                 pl.col("position").alias("pos"), "team",
                                 pl.col("pts_std").alias("y"), pl.col("tgt"),
                                 pl.col("rush_att").alias("car"))
                       .with_columns(pl.Series("x", x)))
    d = pl.concat(out).with_columns(pl.col("season").cast(pl.Int32), pl.col("week").cast(pl.Int32))
    return d.with_columns((pl.col("y") - pl.col("x")).alias("gap"))


def sanity(nv: pl.DataFrame) -> dict:
    """nflverse 'standard' must equal box-score standard points, and xFP
    should be roughly calibrated (mean gap near zero) every season."""
    import ep_model
    chk = {}
    a = ep_model.actuals(pl.read_parquet(ROOT / "engine/weekly/cache/player_stats_2024.parquet")) \
        .select("player_id", "week", pl.col("pts_std").alias("box"))
    j = nv.filter(pl.col("season") == 2024).join(a, on=["player_id", "week"], how="inner")
    chk["std_vs_boxscore_2024_mean_abs_diff"] = float((j["y"] - j["box"]).abs().mean())
    chk["std_vs_boxscore_2024_share_within_0.5"] = float(((j["y"] - j["box"]).abs() <= 0.5).mean())
    chk["mean_gap_by_season"] = {int(r["season"]): round(r["gap"], 3) for r in
                                 nv.group_by("season").agg(pl.col("gap").mean()).sort("season").to_dicts()}
    return chk


# ---------------------------------------------------------------- helpers

def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    X1 = np.column_stack([np.ones(len(y)), X])
    return np.linalg.lstsq(X1, y, rcond=None)[0]


def cluster_boot(groups: np.ndarray, stat, b: int = B) -> tuple[float, float]:
    """95% percentile interval of stat(idx) resampling whole clusters."""
    uniq, inv = np.unique(groups, return_inverse=True)
    members = np.split(np.argsort(inv, kind="stable"), np.cumsum(np.bincount(inv))[:-1])
    vals = []
    for _ in range(b):
        pick = RNG.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([members[i] for i in pick])
        vals.append(stat(idx))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def fmt_ci(est, ci):
    return f"{est:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]"


# ---------------------------------------------------------------- in-season, game to game

def prior_features(d: pl.DataFrame) -> pl.DataFrame:
    """For each player-game: what was known before it, from the same
    season (season-to-date means and the production EWMA), plus last
    season's per-game gap."""
    d = d.sort("player_id", "season", "week")
    g = ["player_id", "season"]
    d = d.with_columns(
        pl.col("x").cum_count().over(g).alias("_n"),
    ).with_columns((pl.col("_n") - 1).alias("n_prior"))
    for c in ("x", "y", "gap"):
        d = d.with_columns(
            ((pl.col(c).cum_sum().over(g) - pl.col(c)) / pl.col("n_prior")).alias(f"prior_{c}"))
    # EWMA (alpha on newest game), season-to-date, known before the game.
    d = d.with_columns([
        pl.col(c).ewm_mean(alpha=ALPHA, adjust=False).shift(1).over(g).alias(f"ewma_{c}")
        for c in ("x", "y")])
    last = (d.group_by("player_id", "season", "pos")
             .agg(pl.len().alias("g_last"), pl.col("gap").mean().alias("gap_last"),
                  pl.col("x").mean().alias("x_last"))
             .with_columns((pl.col("season") + 1).alias("season")))
    d = d.join(last, on=["player_id", "season", "pos"], how="left")
    return d.filter(pl.col("n_prior") >= 1)


def reliability(d: pl.DataFrame, min_games: int = 8) -> dict:
    """Per-game intraclass correlation of the gap within a season:
    rho = true between-player variance / (that + per-game noise).
    After n games the observed average gap deserves n*rho/(1+(n-1)rho)
    of full weight (the classic shrinkage / Spearman-Brown factor)."""
    out = {}
    for pos in POS:
        s = (d.filter(pl.col("pos") == pos)
              .group_by("player_id", "season")
              .agg(pl.len().alias("n"), pl.col("gap").mean().alias("m"),
                   pl.col("gap").var().alias("v"))
              .filter(pl.col("n") >= min_games))
        within = float(s["v"].mean())
        between_obs = float(s["m"].var())
        true_var = max(between_obs - float((s["v"] / s["n"]).mean()), 0.0)
        rho = true_var / (true_var + within)
        out[pos] = {"player_seasons": s.height, "sd_true_gap": round(true_var ** 0.5, 2),
                    "sd_game_noise": round(within ** 0.5, 2), "rho": round(rho, 4),
                    **{f"keep_after_{n}": round(n * rho / (1 + (n - 1) * rho), 3)
                       for n in (1, 2, 4, 8, 17, 34, 51)}}
    return out


def carryover(d: pl.DataFrame) -> dict:
    """Regress next-game actual points on season-to-date expected points and
    season-to-date gap. Coefficient on the gap = share of the observed gap
    that shows up again next game (0 = full regression to expected,
    1 = fully persists, negative = he is 'due' the other way).
    Also split into: does the gap predict next-game usage (x) or
    next-game efficiency (gap)?"""
    res = {}
    bins = [(1, 1), (2, 3), (4, 7), (8, 17)]
    for pos in POS:
        p = d.filter(pl.col("pos") == pos)
        res[pos] = {}
        for lo, hi in bins:
            q = p.filter(pl.col("n_prior").is_between(lo, hi))
            X = q.select("prior_x", "prior_gap").to_numpy()
            ids = q["player_id"].to_numpy()
            row = {"n": q.height}
            for name, target in (("next_points", "y"), ("next_usage", "x"), ("next_gap", "gap")):
                y = q[target].to_numpy()
                est = ols(X, y)[2]
                ci = cluster_boot(ids, lambda i: ols(X[i], y[i])[2])
                row[name] = (round(float(est), 3), [round(ci[0], 3), round(ci[1], 3)])
            res[pos][f"{lo}-{hi}"] = row
    return res


def with_history(d: pl.DataFrame) -> dict:
    """Early season (1-3 games in) for players with 8+ games last season:
    how much weight do this season's gap and last season's gap each get?"""
    res = {}
    for pos in POS:
        q = d.filter((pl.col("pos") == pos) & pl.col("n_prior").is_between(1, 3)
                     & (pl.col("g_last") >= 8))
        X = q.select("prior_x", "prior_gap", "gap_last").to_numpy()
        y = q["y"].to_numpy()
        ids = q["player_id"].to_numpy()
        est = ols(X, y)
        res[pos] = {"n": q.height,
                    "this_season_gap": (round(float(est[2]), 3),
                                        [round(v, 3) for v in cluster_boot(ids, lambda i: ols(X[i], y[i])[2])]),
                    "last_season_gap": (round(float(est[3]), 3),
                                        [round(v, 3) for v in cluster_boot(ids, lambda i: ols(X[i], y[i])[3])])}
    return res


def ewma_vs_actual(d: pl.DataFrame) -> dict:
    """Finding 39's claim: predicting next week, is the EWMA of expected
    points better than the EWMA of actual points? And what blend is best?
    pred(w) = ewma_x + w * (ewma_y - ewma_x). w=0 is usage only, w=1 is
    points only. MAE of the raw EWMA, no refitting, no rescaling."""
    res = {}
    ws = np.round(np.arange(0, 1.01, 0.1), 1)
    for pos in POS:
        q = d.filter((pl.col("pos") == pos) & pl.col("ewma_x").is_not_null())
        ex, ey, y = (q[c].to_numpy() for c in ("ewma_x", "ewma_y", "y"))
        ids = q["player_id"].to_numpy()
        mae = {float(w): float(np.abs(ex + w * (ey - ex) - y).mean()) for w in ws}
        best = min(mae, key=mae.get)
        diff = lambda i: float(np.abs(ex[i] - y[i]).mean() - np.abs(ey[i] - y[i]).mean())
        res[pos] = {"n": q.height,
                    "corr_usage": round(float(np.corrcoef(ex, y)[0, 1]), 3),
                    "corr_points": round(float(np.corrcoef(ey, y)[0, 1]), 3),
                    "mae_usage": round(mae[0.0], 3), "mae_points": round(mae[1.0], 3),
                    "mae_usage_minus_points": (round(diff(np.arange(len(y))), 3),
                                               [round(v, 3) for v in cluster_boot(ids, diff)]),
                    "best_blend_w": best, "mae_best": round(mae[best], 3),
                    "mae_by_w": {k: round(v, 3) for k, v in mae.items()}}
    return res


# ---------------------------------------------------------------- season to season

def seasons(nv: pl.DataFrame, min_games: int = 8) -> pl.DataFrame:
    adv = pl.read_parquet(ROOT / "engine/league-sim/data/adv_weekly_2017_2025.parquet") \
        .filter(pl.col("season_type") == "REG") \
        .group_by("player_id", "season").agg(
            pl.col("receiving_yards_after_catch").fill_null(0).sum().alias("yac"),
            pl.col("receptions").fill_null(0).sum().alias("adv_rec")) \
        .with_columns(pl.col("season").cast(pl.Int32))
    s = (nv.group_by("player_id", "name", "season", "pos")
           .agg(pl.len().alias("g"), pl.col("y").mean().alias("ppg"), pl.col("x").mean().alias("xpg"),
                pl.col("gap").mean().alias("gap"), pl.col("td_gap").mean().alias("td_gap"),
                pl.col("nontd_gap").mean().alias("nontd_gap"), pl.col("tgt").mean().alias("tpg"),
                pl.col("car").mean().alias("cpg"), pl.col("tgt").sum().alias("tgt_tot"),
                pl.col("rec").sum().alias("rec_tot"), pl.col("rec_exp").sum().alias("rec_exp_tot"))
           .filter(pl.col("g") >= min_games)
           .join(adv, on=["player_id", "season"], how="left")
           .with_columns((pl.col("yac") / pl.col("rec_tot")).alias("yac_per_rec"),
                         ((pl.col("rec_tot") - pl.col("rec_exp_tot")) / pl.col("tgt_tot")).alias("croe")))
    nxt = s.select("player_id", "pos", (pl.col("season") - 1).alias("season"),
                   pl.col("ppg").alias("ppg_n"), pl.col("gap").alias("gap_n"),
                   pl.col("td_gap").alias("td_gap_n"), pl.col("nontd_gap").alias("nontd_gap_n"),
                   pl.col("xpg").alias("xpg_n"))
    return s.join(nxt, on=["player_id", "pos", "season"], how="inner")


def season_tests(p: pl.DataFrame) -> dict:
    res = {}
    for pos in POS:
        q = p.filter(pl.col("pos") == pos)
        ids = q["player_id"].to_numpy()
        r = {"pairs": q.height}
        # 1) Does each part of the gap repeat next season? (slope of next on this)
        for part in ("gap", "td_gap", "nontd_gap"):
            x, y = q[part].to_numpy(), q[f"{part}_n"].to_numpy()
            est = ols(x[:, None], y)[1]
            r[f"persist_{part}"] = (round(float(est), 3),
                                   [round(v, 3) for v in cluster_boot(ids, lambda i: ols(x[i, None], y[i])[1])])
        # 2) Next-year points from expected points and the gap, split by part.
        X = q.select("xpg", "td_gap", "nontd_gap").to_numpy()
        y = q["ppg_n"].to_numpy()
        est = ols(X, y)
        for k, name in ((2, "td_gap"), (3, "nontd_gap")):
            r[f"next_ppg_weight_{name}"] = (round(float(est[k]), 3),
                                           [round(v, 3) for v in cluster_boot(ids, lambda i, k=k: ols(X[i], y[i])[k])])
        r["next_ppg_weight_xpg"] = round(float(est[1]), 3)
        # 3) Finding 16 as stated: TD luck -> next-year PPG, holding PPG fixed.
        X16 = q.select("ppg", "td_gap").to_numpy()
        e16 = ols(X16, y)[2]
        r["f16_tdgap_given_ppg"] = (round(float(e16), 3),
                                    [round(v, 3) for v in cluster_boot(ids, lambda i: ols(X16[i], y[i])[2])])
        per = []
        for s in sorted(q["season"].unique().to_list()):
            qs = q.filter(pl.col("season") == s)
            if qs.height > 20:
                per.append(round(float(ols(qs.select("ppg", "td_gap").to_numpy(), qs["ppg_n"].to_numpy())[2]), 2))
        r["f16_by_season_pair"] = per
        # 4) Finding 17: volume and efficiency beyond this year's PPG.
        for feat, cond in (("tpg", None), ("cpg", None),
                           ("yac_per_rec", pl.col("rec_tot") >= 30), ("croe", pl.col("tgt_tot") >= 50)):
            if pos == "QB" and feat != "cpg":
                continue
            qq = q.filter(cond) if cond is not None else q
            qq = qq.filter(pl.col(feat).is_not_null() & pl.col(feat).is_finite())
            if qq.height < 40:
                continue
            Xf = qq.select("ppg", feat).to_numpy()
            yf = qq["ppg_n"].to_numpy()
            sd = float(qq[feat].std())
            est = ols(Xf, yf)[2] * sd
            ci = cluster_boot(qq["player_id"].to_numpy(), lambda i: ols(Xf[i], yf[i])[2] * sd)
            r[f"f17_{feat}_per_sd_given_ppg"] = (round(float(est), 3), [round(v, 3) for v in ci], qq.height)
        res[pos] = r
    return res


# ---------------------------------------------------------------- main

def main():
    nv = load_nflverse()
    ours = load_ours()
    out = {"sanity": sanity(nv)}
    for label, d in (("nflverse_2017_2025", nv), ("ours_2021_2025_loso", ours)):
        pf = prior_features(d)
        out[label] = {
            "reliability": reliability(d),
            "carryover": carryover(pf),
            "with_last_season": with_history(pf),
            "ewma_vs_actual": ewma_vs_actual(pf),
        }
    out["season_to_season_nflverse"] = season_tests(seasons(nv))
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
