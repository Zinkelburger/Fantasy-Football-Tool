"""How accurate is the rookie model, in points — not rank correlation.

Finding 31 graded the rookie board by rank correlation and concluded
it ties NFL draft order. That says nothing about whether the PPG
NUMBERS on the board mean anything, which is what a reader actually
sees. This checks:

1. Error: mean absolute error and bias (pred - actual) of predicted
   rookie-year PPG, per class and position, against two baselines —
   predicting the class mean, and predicting from draft order alone
   (a log fit on overall pick, refit leave-one-class-out).
2. Calibration: what a player projected at N PPG actually averaged,
   bucketed. A board that says "7.2" should be right about 7.2.
3. Usefulness: of the model's top 10 rookies each class, how many
   became a startable fantasy season, vs the same count for the
   NFL's top 10 picks.
4. Receipts: the model's top 5 per class and what they actually did.

All predictions are leave-one-class-out
(analysis/export_rookie_history.py), so no class grades its own fit.

Usage: rookie_accuracy.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rookie_model as rm                                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "data" / "market"
YEARS = range(2020, 2026)
POSITIONS = ("QB", "RB", "WR", "TE")
# "startable" = this many points per scheduled game. A 12-team standard
# league starts ~30 RB/WR, and the RB30/WR30 line sits near 7 PPG.
STARTABLE = 7.0


def load():
    hist = pd.read_csv(MKT / "rookie_board_hist.csv")
    drafts = rm.draft_classes()
    pick = {}
    for r in drafts.itertuples():
        if pd.notna(r.gsis_id):
            pick[(r.season, r.gsis_id)] = int(r.pick)
    rows = []
    for year in YEARS:
        actual = rm.targets(year, 0.0)
        sub = hist[hist.year == year].copy()
        sub["actual"] = [actual.get(p, 0.0) for p in sub.pid]
        sub["pick"] = [pick.get((year, p), np.nan) for p in sub.pid]
        rows.append(sub)
    return pd.concat(rows, ignore_index=True).dropna(subset=["pick"])


def draft_order_baseline(df):
    """Leave-one-class-out log fit: actual PPG ~ a + b*ln(pick).
    The fair 'just use draft position' number-predictor."""
    out = np.full(len(df), np.nan)
    for year in YEARS:
        tr = df[df.year != year]
        te = df.year == year
        for pos in POSITIONS:
            trp = tr[tr.pos == pos]
            tep = te & (df.pos == pos)
            if len(trp) < 20 or not tep.any():
                continue
            b, a = np.polyfit(np.log(trp["pick"].values),
                              trp["actual"].values, 1)
            out[tep.values] = a + b * np.log(df.loc[tep, "pick"].values)
    return out


def block(label, err):
    err = err[~np.isnan(err)]
    print(f"  {label:22s} MAE {np.abs(err).mean():5.2f}   "
          f"bias {err.mean():+5.2f}   RMSE {np.sqrt((err**2).mean()):5.2f}")


def main():
    df = load()
    df["base_mean"] = df.groupby(["year", "pos"]).actual.transform("mean")
    df["base_pick"] = draft_order_baseline(df)
    df = df.dropna(subset=["base_pick"])
    print(f"n = {len(df)} drafted rookies, classes "
          f"{YEARS.start}-{YEARS.stop - 1}, standard scoring, "
          f"points per SCHEDULED game\n")

    print("ERROR vs actual rookie-year PPG (lower MAE better, "
          "bias>0 = board too optimistic)")
    block("our model", (df.pred - df.actual).values)
    block("draft order (log fit)", (df.base_pick - df.actual).values)
    block("class mean", (df.base_mean - df.actual).values)

    print("\nBy position:")
    for pos in POSITIONS:
        d = df[df.pos == pos]
        print(f"  {pos}  n={len(d):3d}")
        block("    our model", (d.pred - d.actual).values)
        block("    draft order", (d.base_pick - d.actual).values)

    print("\nBy class:")
    for year in YEARS:
        d = df[df.year == year]
        e = (d.pred - d.actual).values
        eb = (d.base_pick - d.actual).values
        print(f"  {year}  n={len(d):3d}   model MAE {np.abs(e).mean():5.2f} "
              f"(bias {e.mean():+5.2f})   draft-order MAE "
              f"{np.abs(eb).mean():5.2f}")

    print("\nCALIBRATION — what the board promised vs what they scored:")
    bins = [-99, 2, 4, 6, 8, 99]
    lab = ["<2", "2-4", "4-6", "6-8", "8+"]
    df["bucket"] = pd.cut(df.pred, bins, labels=lab)
    print(f"  {'projected':10s} {'n':>4s}  {'mean proj':>9s}  "
          f"{'mean actual':>11s}  {'% startable':>11s}")
    for b in lab:
        d = df[df.bucket == b]
        if not len(d):
            continue
        print(f"  {b:10s} {len(d):4d}  {d.pred.mean():9.1f}  "
              f"{d.actual.mean():11.1f}  "
              f"{(d.actual >= STARTABLE).mean():10.0%}")

    print(f"\nUSEFULNESS — hits (>= {STARTABLE} PPG) in each list's "
          f"top 10, per class:")
    print(f"  {'class':6s} {'model top10':>12s} {'NFL top10 picks':>16s} "
          f"{'total hits':>11s}")
    tm = tn = 0
    for year in YEARS:
        d = df[df.year == year]
        m = d.nlargest(10, "pred")
        n = d.nsmallest(10, "pick")
        hm = int((m.actual >= STARTABLE).sum())
        hn = int((n.actual >= STARTABLE).sum())
        tm += hm
        tn += hn
        print(f"  {year:<6d} {hm:12d} {hn:16d} "
              f"{int((d.actual >= STARTABLE).sum()):11d}")
    print(f"  {'TOTAL':6s} {tm:12d} {tn:16d}")

    # ---- Is the tier information an EDGE, or just draft position? ----
    # Calibration only says our numbers are honest. It says nothing
    # about whether anyone needed US to know it. Test: how well does
    # each score separate startable rookies from the rest (AUC — the
    # chance a random hit is scored above a random non-hit; 0.5 = coin
    # flip)? If draft position alone matches us, the tiers carry no
    # information the NFL draft did not already publish.
    y = (df.actual >= STARTABLE).values.astype(float)

    def auc(score, mask=None):
        s, yy = np.asarray(score, float), y
        if mask is not None:
            s, yy = s[mask], y[mask]
        ok = ~np.isnan(s)
        s, yy = s[ok], yy[ok]
        npos, nneg = yy.sum(), (1 - yy).sum()
        if npos < 3 or nneg < 3:
            return np.nan, int(npos + nneg)
        r = pd.Series(s).rank().values
        return ((r[yy == 1].sum() - npos * (npos + 1) / 2)
                / (npos * nneg)), int(npos + nneg)

    print(f"\nEDGE CHECK — separating startable (>= {STARTABLE} PPG) "
          f"rookies, AUC (0.5 = coin flip):")
    for label, sc in (("our model projection", df.pred.values),
                      ("draft-order log fit", df.base_pick.values),
                      ("raw draft pick (negated)", -df["pick"].values)):
        a, n = auc(sc)
        print(f"  {label:26s} AUC {a:.3f}   n={n}")

    # ...and on the subset the fantasy market actually priced, add ADP
    # (rookie_model.market_adp_rank expects a build_class frame; this
    # table carries the PFR column names, so do the join here)
    adp_vals = np.full(len(df), np.nan)
    for year in YEARS:
        priced_by = {(rm._norm(e["name"]), e["pos"]): float(e["adp"])
                     for e in rm.adp_rows(year) if e.get("adp") is not None}
        m = (df.year == year).values
        adp_vals[m] = [priced_by.get((rm._norm(n), p), np.nan)
                       for n, p in zip(df.loc[m, "name"], df.loc[m, "pos"])]
    priced = ~np.isnan(adp_vals)
    print(f"\n  on the {int(priced.sum())} rookies the fantasy market "
          f"priced:")
    for label, sc in (("our model projection", df.pred.values),
                      ("draft-order log fit", df.base_pick.values),
                      ("rookie ADP (negated)", -adp_vals)):
        a, n = auc(sc, priced)
        print(f"    {label:24s} AUC {a:.3f}   n={n}")

    # Paired bootstrap on that subset: is draft position really a
    # better hit/bust separator than the fantasy market's own rookie
    # prices, or is 0.808 vs 0.700 just 151 players of noise?
    idx = np.where(priced)[0]
    rng = np.random.default_rng(7)
    diffs = []
    for _ in range(4000):
        take = rng.choice(idx, size=len(idx), replace=True)
        yy = y[take]
        if yy.sum() < 3 or (1 - yy).sum() < 3:
            continue

        def _auc(s):
            s = np.asarray(s, float)[take]
            ok = ~np.isnan(s)
            ss, yb = s[ok], yy[ok]
            npos, nneg = yb.sum(), (1 - yb).sum()
            if npos < 3 or nneg < 3:
                return np.nan
            r = pd.Series(ss).rank().values
            return ((r[yb == 1].sum() - npos * (npos + 1) / 2)
                    / (npos * nneg))

        diffs.append(_auc(df.base_pick.values) - _auc(-adp_vals))
    diffs = np.array([d for d in diffs if not np.isnan(d)])
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"    paired bootstrap, draft order - rookie ADP: "
          f"{diffs.mean():+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  "
          f"{'excludes 0' if lo > 0 or hi < 0 else 'includes 0'}")

    # Pooling positions can fake that: rookie QBs are startable far
    # more often than rookie TEs, so any score correlated with position
    # mix gets credit for it. Re-check inside each position.
    print("    within position (priced rookies only):")
    for pos in POSITIONS:
        m = priced & (df.pos == pos).values
        a_d, n = auc(df.base_pick.values, m)
        a_a, _ = auc(-adp_vals, m)
        a_m, _ = auc(df.pred.values, m)
        if np.isnan(a_d) or np.isnan(a_a):
            print(f"      {pos}  n={n:3d}   (too few)")
            continue
        print(f"      {pos}  n={n:3d}   draft order {a_d:.3f}   "
              f"rookie ADP {a_a:.3f}   model {a_m:.3f}   "
              f"diff {a_d - a_a:+.3f}")

    # Tier tables side by side: ours vs draft round
    print("\n  same tiers, built from draft ROUND instead of our model:")
    print(f"    {'round':10s} {'n':>4s}  {'mean actual':>11s}  "
          f"{'% startable':>11s}")
    for rnd, lo, hi in (("1", 1, 32), ("2", 33, 64), ("3", 65, 100),
                        ("4-5", 101, 175), ("6-7", 176, 999)):
        d = df[(df["pick"] >= lo) & (df["pick"] <= hi)]
        if not len(d):
            continue
        print(f"    rd {rnd:7s} {len(d):4d}  {d.actual.mean():11.1f}  "
              f"{(d.actual >= STARTABLE).mean():10.0%}")

    print("\nRECEIPTS — the model's top 5 each class, and what happened:")
    for year in YEARS:
        d = df[df.year == year].nlargest(5, "pred")
        print(f"  {year}:")
        for r in d.itertuples():
            flag = "  <-- hit" if r.actual >= STARTABLE else ""
            print(f"    {r.name:24s} {r.pos:2s} pk{int(r.pick):3d}  "
                  f"proj {r.pred:5.1f}  actual {r.actual:5.1f}{flag}")


if __name__ == "__main__":
    main()
