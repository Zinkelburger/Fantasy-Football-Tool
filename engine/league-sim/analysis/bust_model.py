"""Can we predict who busts, beyond what the draft price already says?

The board already shows a price. The question this script answers is
whether anything we know in August — age, TD luck, last year's usage,
last year's health — moves the bust probability *after* the price has
had its say. If it doesn't, the honest product is a calibrated bust
number that depends on draft slot alone, which is still worth showing:
"every pick is a coin flip of some weight, here is the weight."

Design notes:
  - every feature is preseason-knowable; nothing peeks at the season
  - leave-one-year-out: fit on 7 seasons, predict the 8th, pool the
    out-of-sample predictions. No model ever grades its own training year
  - nested comparison M0 (base rate) -> M1 (price) -> M2 (+age) ->
    M3 (+everything). A feature set earns its place only by beating the
    one below it out of sample
  - three bust definitions, because the answer shouldn't hinge on one
    arbitrary cutoff

Run:  venv/bin/python analysis/bust_model.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "analysis"))
from round_profile import build as build_picks, YEARS, STARTER  # noqa: E402

RNG = np.random.default_rng(11)
INJ_PANEL = ROOT.parent.parent / "research" / "injury_predictor" / "panel_position_age.parquet"


# ---------------------------------------------------------------- features
def prior_season_features():
    """Last year's TD luck, scoring rate and usage, keyed (year, pid).

    Indexed by the season you'd be drafting *for*, so year 2023 carries
    2022's numbers — that's what a drafter actually has in August.
    """
    opp = pd.read_parquet(DATA / "ff_opportunity_2017_2025.parquet")
    opp = opp[opp.position.isin(STARTER)]
    for c in ("pass_touchdown", "rec_touchdown", "rush_touchdown",
              "pass_touchdown_exp", "rec_touchdown_exp", "rush_touchdown_exp"):
        opp[c] = pd.to_numeric(opp[c], errors="coerce").fillna(0)
    opp["tds"] = opp.pass_touchdown + opp.rec_touchdown + opp.rush_touchdown
    opp["td_exp"] = (opp.pass_touchdown_exp + opp.rec_touchdown_exp
                     + opp.rush_touchdown_exp)
    g = opp.groupby(["season", "player_id"], as_index=False).agg(
        tds=("tds", "sum"), td_exp=("td_exp", "sum"),
        games=("week", "nunique"))
    g = g[g.games >= 4]
    g["td_luck_pg"] = (g.tds - g.td_exp) / g.games
    g["prior_games"] = g.games
    g["season"] = g.season.astype(int) + 1        # shift to the draft year
    return g[["season", "player_id", "td_luck_pg", "prior_games"]].rename(
        columns={"season": "year", "player_id": "pid"})


def prior_injury_features():
    """Games missed to injury last season, from the position/age panel."""
    if not INJ_PANEL.exists():
        return None
    p = pd.read_parquet(INJ_PANEL)
    ps = p.groupby(["season", "gsis_id"], as_index=False).agg(
        missed=("injury_absence", "sum"), tg=("week", "count"))
    ps = ps[ps.tg >= 14]
    ps["year"] = ps.season.astype(int) + 1
    return ps[["year", "gsis_id", "missed"]].rename(
        columns={"gsis_id": "pid", "missed": "prior_missed"})


def prior_points():
    """Last season's STD points per game, keyed to the draft year."""
    from player_model import league_pts, weekly_raw
    rows = []
    for y in range(2017, 2025):
        w = weekly_raw(y)
        w = w.to_pandas() if hasattr(w, "to_pandas") else w
        w = w[w.position.isin(STARTER)]
        w["pts"] = league_pts(w, 0.0)
        g = w.groupby("player_id", as_index=False).agg(
            pts=("pts", "sum"), gp=("week", "nunique"))
        g = g[g.gp >= 4]
        g["ppg_prior"] = g.pts / g.gp
        g["year"] = y + 1
        rows.append(g[["year", "player_id", "ppg_prior"]].rename(
            columns={"player_id": "pid"}))
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------ bust targets
def add_targets(df):
    """Three ways to say 'he did not return his draft price'."""
    df = df.copy()
    # positional draft rank: RB8 etc.
    df["pos_rank"] = df.groupby(["year", "pos"]).adp.rank(method="first")

    # (1) finished worse than twice his positional draft rank.
    #     no season at all = bust.
    fin = df.fin_std
    df["bust_2x"] = fin.isna() | (fin > 2 * df.pos_rank)

    # (2) missed the starter cut for his position (top-12 QB/TE, top-24 RB/WR).
    #     Only fair for picks drafted inside that cut.
    cut = df.pos.map(STARTER)
    df["bust_starter"] = (fin.isna() | (fin > cut)).astype(float)
    df.loc[df.pos_rank > cut, "bust_starter"] = np.nan   # not applicable

    # (3) finished a full tier-and-a-half below price
    df["bust_1_5x"] = fin.isna() | (fin > 1.5 * df.pos_rank + 3)

    # (4) the product framing: did he give you a startable season at all?
    #     Applies to every pick, not just the ones drafted inside the cut.
    df["not_startable"] = (fin.isna() | (fin > cut)).astype(float)
    return df


# --------------------------------------------------------- tiny logistic
def fit_logit(X, y, l2=1.0, iters=60):
    """IRLS with an L2 ridge; intercept column assumed to be X[:, 0]."""
    n, k = X.shape
    b = np.zeros(k)
    pen = np.eye(k) * l2
    pen[0, 0] = 0.0
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1 / (1 + np.exp(-eta))
        W = np.clip(p * (1 - p), 1e-6, None)
        z = eta + (y - p) / W
        A = X.T @ (X * W[:, None]) + pen
        try:
            b_new = np.linalg.solve(A, X.T @ (W * z))
        except np.linalg.LinAlgError:
            break
        if np.max(np.abs(b_new - b)) < 1e-8:
            b = b_new
            break
        b = b_new
    return b


def predict(X, b):
    return 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))


def auc(y, p):
    y = np.asarray(y, dtype=bool)
    if y.all() or not y.any():
        return np.nan
    order = np.argsort(p)
    ranks = np.empty(len(p), float)
    ranks[order] = np.arange(1, len(p) + 1)
    # average ranks over ties
    s = pd.Series(p)
    ranks = s.rank(method="average").values
    n1, n0 = y.sum(), (~y).sum()
    return (ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def log_loss(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


# ------------------------------------------------------------ model specs
def design(df, spec):
    """Build the X matrix for a named feature set."""
    n = len(df)
    cols = [np.ones(n)]
    names = ["const"]

    def add(v, nm):
        v = np.asarray(v, float)
        miss = ~np.isfinite(v)
        if miss.any():
            v = v.copy()
            v[miss] = np.nanmedian(v[~miss]) if (~miss).any() else 0.0
            cols.append(miss.astype(float))
            names.append(f"{nm}_missing")
        mu, sd = v.mean(), v.std()
        cols.append((v - mu) / (sd if sd > 1e-9 else 1.0))
        names.append(nm)

    if spec == "M0":
        pass
    if spec in ("M1", "M2", "M3") or spec.startswith("M1+"):
        add(np.log(df.adp.values), "log_adp")
        for p in ("RB", "WR", "TE"):
            cols.append((df.pos == p).astype(float).values)
            names.append(f"pos_{p}")
    if spec in ("M2", "M3"):
        add(df.age.values, "age")
    if spec == "M3":
        cols.append(df.rookie.astype(float).values)
        names.append("rookie")
        add(df.td_luck_pg.values, "td_luck")
        add(df.ppg_prior.values, "ppg_prior")
        add(df.prior_missed.values, "prior_missed")
        add(df.tgt_pg.values, "tgt_pg")
        add(df.car_pg.values, "car_pg")
    # single-feature ablations: price plus exactly one candidate signal,
    # so a real feature can't be washed out by the kitchen sink
    if spec.startswith("M1+"):
        f = spec[3:]
        if f == "rookie":
            cols.append(df.rookie.astype(float).values)
            names.append("rookie")
        else:
            add(df[f].values, f)
    return np.column_stack(cols), names


def loyo(df, target, spec):
    """Leave-one-year-out out-of-sample predictions."""
    sub = df[df[target].notna()].copy()
    y = sub[target].astype(float).values
    X, names = design(sub, spec)
    oos = np.full(len(sub), np.nan)
    for yr in sorted(sub.year.unique()):
        te = (sub.year == yr).values
        tr = ~te
        if te.sum() < 5 or y[tr].std() == 0:
            continue
        b = fit_logit(X[tr], y[tr])
        oos[te] = predict(X[te], b)
    ok = np.isfinite(oos)
    return sub[ok].assign(p=oos[ok]), y[ok], names


def main():
    picks = build_picks()
    picks = picks[picks.pos.isin(STARTER)]
    print(f"drafted player-seasons: {len(picks)}")

    picks = picks.merge(prior_season_features(), on=["year", "pid"], how="left")
    picks = picks.merge(prior_points(), on=["year", "pid"], how="left")
    inj = prior_injury_features()
    if inj is not None:
        picks = picks.merge(inj, on=["year", "pid"], how="left")
    else:
        picks["prior_missed"] = np.nan
    picks = add_targets(picks)

    for t in ("bust_2x", "bust_starter", "bust_1_5x"):
        v = picks[t].dropna()
        print(f"  {t}: base rate {v.mean():.1%}  (n={len(v)})")

    results = {}
    for target in ("bust_2x", "bust_starter", "bust_1_5x", "not_startable"):
        print(f"\n{'='*66}\n=== TARGET: {target} ===")
        rows = []
        for spec in ("M0", "M1", "M2", "M3"):
            d, y, names = loyo(picks, target, spec)
            rows.append({"model": spec, "n": len(d),
                         "AUC": round(auc(y, d.p.values), 4),
                         "Brier": round(float(((d.p - y) ** 2).mean()), 4),
                         "logloss": round(log_loss(y, d.p.values), 4)})
        tbl = pd.DataFrame(rows)
        print(tbl.to_string(index=False))
        results[target] = tbl.to_dict("records")

        # is M3 - M1 real? paired bootstrap on the same out-of-sample rows
        d1, y1, _ = loyo(picks, target, "M1")
        d3, y3, _ = loyo(picks, target, "M3")
        key = ["year", "pid"]
        m = d1[key + ["p"]].merge(d3[key + ["p"]], on=key,
                                  suffixes=("_1", "_3"))
        m = m.merge(picks[key + [target]], on=key)
        yy = m[target].astype(float).values
        diffs = []
        for _ in range(2000):
            idx = RNG.integers(0, len(m), len(m))
            a1 = auc(yy[idx], m.p_1.values[idx])
            a3 = auc(yy[idx], m.p_3.values[idx])
            if np.isfinite(a1) and np.isfinite(a3):
                diffs.append(a3 - a1)
        diffs = np.array(diffs)
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        obs = auc(yy, m.p_3.values) - auc(yy, m.p_1.values)
        verdict = "REAL" if lo * hi > 0 else "noise"
        print(f"  M3 - M1 AUC: {obs:+.4f}  CI [{lo:+.4f},{hi:+.4f}]  {verdict}")
        results[f"{target}_M3_minus_M1"] = {
            "delta_auc": round(float(obs), 4),
            "ci": [round(float(lo), 4), round(float(hi), 4)],
            "verdict": verdict}

        # per-year signs: does the edge show up in most held-out seasons?
        signs = []
        for yr in sorted(m.year.unique()):
            s = m[m.year == yr]
            yv = s[target].astype(float).values
            a1, a3 = auc(yv, s.p_1.values), auc(yv, s.p_3.values)
            if np.isfinite(a1) and np.isfinite(a3):
                signs.append((int(yr), round(float(a3 - a1), 3)))
        pos_years = sum(1 for _, v in signs if v > 0)
        print(f"  per-year M3-M1: {signs}  ({pos_years}/{len(signs)} positive)")
        results[f"{target}_per_year"] = signs

    # ---- one feature at a time, against price ---------------------------
    print(f"\n{'='*66}\n=== SINGLE-FEATURE ABLATIONS vs price-only (M1) ===")
    print("    (does any one signal beat the price on its own?)")
    abl = []
    for target in ("bust_2x", "not_startable"):
        d1, y1, _ = loyo(picks, target, "M1")
        base = auc(y1, d1.p.values)
        for f in ("age", "td_luck_pg", "prior_missed", "ppg_prior",
                  "rookie", "tgt_pg", "car_pg"):
            d2, y2, _ = loyo(picks, target, f"M1+{f}")
            m = d1[["year", "pid", "p"]].merge(
                d2[["year", "pid", "p"]], on=["year", "pid"],
                suffixes=("_1", "_2")).merge(
                picks[["year", "pid", target]], on=["year", "pid"])
            yy = m[target].astype(float).values
            obs = auc(yy, m.p_2.values) - auc(yy, m.p_1.values)
            diffs = np.array([
                auc(yy[i], m.p_2.values[i]) - auc(yy[i], m.p_1.values[i])
                for i in (RNG.integers(0, len(m), len(m))
                          for _ in range(1500))])
            diffs = diffs[np.isfinite(diffs)]
            lo, hi = np.percentile(diffs, [2.5, 97.5])
            abl.append({"target": target, "feature": f,
                        "base_AUC": round(float(base), 4),
                        "delta_AUC": round(float(obs), 4),
                        "ci_lo": round(float(lo), 4),
                        "ci_hi": round(float(hi), 4),
                        "verdict": "REAL" if lo * hi > 0 else "noise"})
    abl = pd.DataFrame(abl)
    print(abl.to_string(index=False))
    results["ablations"] = abl.to_dict("records")

    # ---- calibration of the model we would actually ship ----------------
    print(f"\n{'='*66}\n=== CALIBRATION (M1, price-only, target bust_2x) ===")
    d, y, _ = loyo(picks, "bust_2x", "M1")
    d = d.assign(actual=y)
    d["bin"] = pd.cut(d.p, [0, .2, .3, .4, .5, .6, .7, .8, 1.0])
    cal = d.groupby("bin", observed=True).agg(
        n=("p", "size"), predicted=("p", "mean"), actual=("actual", "mean"))
    print((cal.assign(predicted=lambda x: (x.predicted * 100).round(1),
                      actual=lambda x: (x.actual * 100).round(1))).to_string())
    results["calibration_M1"] = cal.reset_index().astype(str).to_dict("records")

    print(f"\n{'='*66}\n=== CALIBRATION (M1, price-only, target not_startable) ===")
    dn, yn, _ = loyo(picks, "not_startable", "M1")
    dn = dn.assign(actual=yn)
    dn["bin"] = pd.cut(dn.p, [0, .2, .4, .6, .75, .85, .95, 1.0])
    caln = dn.groupby("bin", observed=True).agg(
        n=("p", "size"), predicted=("p", "mean"), actual=("actual", "mean"))
    print((caln.assign(predicted=lambda x: (x.predicted * 100).round(1),
                       actual=lambda x: (x.actual * 100).round(1))).to_string())
    results["calibration_not_startable"] = caln.reset_index().astype(
        str).to_dict("records")

    print(f"\n=== bust rate by round (what price alone already tells you) ===")
    by_rnd = picks.groupby("rnd").agg(
        n=("bust_2x", "size"), bust_2x=("bust_2x", "mean"),
        not_startable=("not_startable", "mean"))
    print(by_rnd.assign(bust_2x=lambda x: (x.bust_2x * 100).round(1),
                        not_startable=lambda x: (x.not_startable * 100).round(1)
                        ).to_string())

    print(f"\n=== does age separate busts INSIDE a price band? ===")
    for lo_r, hi_r in [(1, 3), (4, 8), (9, 15)]:
        band = picks[(picks.rnd >= lo_r) & (picks.rnd <= hi_r)]
        for pos in ("RB", "WR", "TE", "QB"):
            s = band[(band.pos == pos) & band.age.notna()]
            if len(s) < 40:
                continue
            young = s[s.age < s.age.median()]
            old = s[s.age >= s.age.median()]
            print(f"  R{lo_r}-{hi_r} {pos}: young {young.bust_2x.mean():.0%} "
                  f"(n={len(young)}) vs old {old.bust_2x.mean():.0%} "
                  f"(n={len(old)})  gap {old.bust_2x.mean()-young.bust_2x.mean():+.0%}")

    out = ROOT / "results" / "bust_model.json"
    out.parent.mkdir(exist_ok=True)
    json.dump(results, open(out, "w"), indent=1, default=str)
    picks.to_parquet(ROOT / "data" / "bust_panel.parquet")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
