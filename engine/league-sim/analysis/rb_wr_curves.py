"""RB vs WR value curves, done with real statistics (finding 23).

Question: what is a positional-rank (the market's RB1, RB2, ... WR1,
WR2, ... by ADP) worth in 14-week STD points, and where do the curves
cross?

Methods:
- Unit of analysis: player-season, 2018-2025 (every year with ADP).
  X = positional ADP rank k (market's projection ordering, immune to
  cross-position ADP arbitrariness), y = weeks 1-14 points.
- Mean curves: OLS  E[y] = a + b*ln(k), per position. Uncertainty by
  CLUSTER bootstrap over seasons (years are the correlated unit —
  resampling players would understate error). 4000 reps.
- Functional form justified by leave-one-year-out CV against a
  Nadaraya-Watson kernel smoother and an isotonic (PAV) fit: if the
  parametric curve matches the nonparametrics out of sample, use it.
- Crossover rank k* solved per bootstrap rep -> full CI, not a point.
- Same-ADP premium: y ~ ln(ADP) x position with year fixed effects
  (within transformation), premium(p) = bRB + bRBxln(p), cluster CI.
- Floor/ceiling: kernel-weighted conditional quantiles (p25/p50/p75)
  along k, bootstrap bands. Availability vs talent: the same FE model
  on games played and on active PPG separately.

Output: printed tables + figures/rb_wr_curves.png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simfl.config import DEFAULT_SCORING
from simfl.pool import build_pool

YEARS = list(range(2018, 2026))
WKS = range(1, 15)
KMAX = 40          # ranks entering the fits
RNG = np.random.default_rng(7)
B = 4000           # bootstrap reps for parametric fits
BQ = 800           # bootstrap reps for kernel quantiles


def assemble() -> pd.DataFrame:
    rows = []
    for year in YEARS:
        pool = build_pool(year, DEFAULT_SCORING)
        for pos in ("RB", "WR"):
            ps = sorted((p for p in pool if p.pos == pos and p.adp),
                        key=lambda p: p.adp)
            for k, p in enumerate(ps, start=1):
                g = sum(1 for w in WKS if p.played(w))
                pts = sum(p.points(w) for w in WKS if p.played(w))
                rows.append(dict(year=year, pos=pos, adp=p.adp, k=k,
                                 pts=pts, games=g,
                                 ppg=pts / g if g >= 4 else np.nan))
    return pd.DataFrame(rows)


def ols(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def fit_loglin(df):
    """{pos: (a, b)} for E[pts] = a + b ln k."""
    out = {}
    for pos in ("RB", "WR"):
        d = df[(df.pos == pos) & (df.k <= KMAX)]
        X = np.column_stack([np.ones(len(d)), np.log(d.k.values)])
        out[pos] = ols(X, d.pts.values)
    return out


def cluster_boot(df, fit_fn, reps=B):
    """fit_fn(resampled df) -> flat np.array; resamples whole seasons."""
    years = df.year.unique()
    stats = []
    for _ in range(reps):
        pick = RNG.choice(years, size=len(years), replace=True)
        boot = pd.concat([df[df.year == y] for y in pick], ignore_index=True)
        stats.append(fit_fn(boot))
    return np.array(stats)


# ---------------------------------------------------------------- nonparam
def nw_predict(xtr, ytr, xte, h=0.35):
    """Nadaraya-Watson on ln(k), gaussian kernel."""
    lx, lt = np.log(xtr), np.log(xte)
    w = np.exp(-0.5 * ((lt[:, None] - lx[None, :]) / h) ** 2)
    return (w @ ytr) / w.sum(axis=1)


def pav_decreasing(xtr, ytr, xte):
    """Isotonic non-increasing fit via pool-adjacent-violators."""
    order = np.argsort(xtr)
    x, y = xtr[order], ytr[order].astype(float)
    vals, wts, idx = [], [], []
    for i, v in enumerate(y):
        vals.append(v); wts.append(1.0); idx.append([i])
        while len(vals) > 1 and vals[-2] < vals[-1]:
            v2, w2 = vals.pop(), wts.pop()
            vals[-1] = (vals[-1] * wts[-1] + v2 * w2) / (wts[-1] + w2)
            wts[-1] += w2
            idx[-2].extend(idx.pop())
    yhat = np.empty_like(y)
    for v, ii in zip(vals, idx):
        yhat[ii] = v
    return np.interp(xte, x, yhat)


def loyo_cv(df):
    """Leave-one-year-out MAE per position and model."""
    res = {m: {"RB": [], "WR": []} for m in ("loglin", "kernel", "isotonic")}
    for pos in ("RB", "WR"):
        d = df[(df.pos == pos) & (df.k <= KMAX)]
        for y in YEARS:
            tr, te = d[d.year != y], d[d.year == y]
            X = np.column_stack([np.ones(len(tr)), np.log(tr.k.values)])
            a, b = ols(X, tr.pts.values)
            preds = {
                "loglin": a + b * np.log(te.k.values),
                "kernel": nw_predict(tr.k.values, tr.pts.values, te.k.values),
                "isotonic": pav_decreasing(tr.k.values, tr.pts.values,
                                           te.k.values),
            }
            for m, pr in preds.items():
                res[m][pos].append(np.mean(np.abs(pr - te.pts.values)))
    return {m: {p: float(np.mean(v)) for p, v in d.items()}
            for m, d in res.items()}


def kquantile(d, grid, q, h=0.30):
    """Kernel-weighted quantile of pts along ln(k)."""
    lk = np.log(d.k.values)
    out = np.empty(len(grid))
    for i, g in enumerate(grid):
        w = np.exp(-0.5 * ((np.log(g) - lk) / h) ** 2)
        order = np.argsort(d.pts.values)
        cw = np.cumsum(w[order]) / w.sum()
        out[i] = d.pts.values[order][np.searchsorted(cw, q)]
    return out


# ----------------------------------------------------------------- FE model
def fe_premium(df, ycol, adp_max=150):
    """Within-year OLS: y ~ ln(adp) + RB + RB:ln(adp).
    Returns (b_lnadp, b_rb, b_rb_lnadp)."""
    d = df[(df.adp <= adp_max)].dropna(subset=[ycol]).copy()
    d["lnadp"] = np.log(d.adp)
    d["rb"] = (d.pos == "RB").astype(float)
    d["rbl"] = d.rb * d.lnadp
    cols = ["lnadp", "rb", "rbl", ycol]
    dm = d[cols + ["year"]].copy()
    for c in cols:
        dm[c] = dm[c] - dm.groupby("year")[c].transform("mean")
    X = dm[["lnadp", "rb", "rbl"]].values
    return ols(X, dm[ycol].values)


def main():
    df = assemble()
    n = df[(df.k <= KMAX)].groupby("pos").size()
    print(f"player-seasons entering rank fits (k<=%d): "
          f"RB %d, WR %d, %d seasons\n" % (KMAX, n["RB"], n["WR"], len(YEARS)))

    # 1. mean curves ---------------------------------------------------
    fits = fit_loglin(df)

    def flat(d):
        f = fit_loglin(d)
        aR, bR = f["RB"]; aW, bW = f["WR"]
        lk = (aW - aR) / (bR - bW) if bR < bW else np.inf
        return np.array([aR, bR, aW, bW,
                         np.exp(lk) if np.isfinite(lk) else np.inf])

    bs = cluster_boot(df, flat)
    lo, hi = np.percentile(bs[:, :4], [2.5, 97.5], axis=0)
    (aR, bR), (aW, bW) = fits["RB"], fits["WR"]
    print("mean curves, E[pts14] = a + b*ln(rank), cluster-boot 95% CI:")
    print(f"  RB: a = {aR:6.1f} [{lo[0]:.1f}, {hi[0]:.1f}]   "
          f"b = {bR:6.1f} [{lo[1]:.1f}, {hi[1]:.1f}]")
    print(f"  WR: a = {aW:6.1f} [{lo[2]:.1f}, {hi[2]:.1f}]   "
          f"b = {bW:6.1f} [{lo[3]:.1f}, {hi[3]:.1f}]")

    ks = bs[:, 4]
    fin = ks[np.isfinite(ks)]
    print(f"\ncrossover rank k* (RB curve falls below WR):")
    print(f"  point {np.exp((aW-aR)/(bR-bW)):.0f}, boot median {np.median(fin):.0f}, "
          f"90% CI [{np.percentile(fin,5):.0f}, {np.percentile(fin,95):.0f}]")
    for kk in (12, 18, 24, 30, 36):
        print(f"  P(k* <= {kk}) = {np.mean(ks <= kk):.2f}")

    grid = np.arange(1, 37)
    dR = aR + bR * np.log(grid) - (aW + bW * np.log(grid))
    dboot = (bs[:, 0:1] + bs[:, 1:2] * np.log(grid)[None, :]
             - bs[:, 2:3] - bs[:, 3:4] * np.log(grid)[None, :])
    dlo, dhi = np.percentile(dboot, [2.5, 97.5], axis=0)
    print("\nsame-rank premium RB_k - WR_k (95% CI):")
    for kk in (1, 3, 6, 12, 18, 24, 30, 36):
        i = kk - 1
        print(f"  k={kk:>2d}: {dR[i]:+6.1f}  [{dlo[i]:+6.1f}, {dhi[i]:+6.1f}]")

    # per-year slope stability
    print("\nper-year slopes b (stability):")
    for pos in ("RB", "WR"):
        bs_y = []
        for y in YEARS:
            d = df[(df.pos == pos) & (df.k <= KMAX) & (df.year == y)]
            X = np.column_stack([np.ones(len(d)), np.log(d.k.values)])
            bs_y.append(ols(X, d.pts.values)[1])
        print(f"  {pos}: " + " ".join(f"{b:6.1f}" for b in bs_y))

    # R2 / residual sd (honesty)
    for pos in ("RB", "WR"):
        d = df[(df.pos == pos) & (df.k <= KMAX)]
        a, b = fits[pos]
        r = d.pts.values - (a + b * np.log(d.k.values))
        ss = 1 - r.var() / d.pts.values.var()
        print(f"  {pos}: R^2 {ss:.2f}, residual sd {r.std():.0f} pts")

    # 2. functional form -----------------------------------------------
    cv = loyo_cv(df)
    print("\nleave-one-year-out MAE (pts): model adequacy")
    for m, d in cv.items():
        print(f"  {m:9s} RB {d['RB']:5.1f}   WR {d['WR']:5.1f}")

    # 3. same-ADP premium with year FE ---------------------------------
    bl, brb, brbl = fe_premium(df, "pts")
    def prem_fn(d):
        return np.array(fe_premium(d, "pts"))
    pbs = cluster_boot(df, prem_fn, reps=B // 2)
    print("\nsame-ADP RB premium (year FE), premium(p) = "
          f"{brb:.1f} + {brbl:.1f}*ln(p):")
    for p in (6, 12, 24, 36, 48, 72, 100):
        pt = brb + brbl * np.log(p)
        bvals = pbs[:, 1] + pbs[:, 2] * np.log(p)
        lo_, hi_ = np.percentile(bvals, [2.5, 97.5])
        print(f"  pick {p:>3d}: {pt:+6.1f}  [{lo_:+6.1f}, {hi_:+6.1f}]")
    dec = pbs[:, 2] < -1e-9    # premium must be decreasing to hit zero
    pstar = np.exp(np.clip(pbs[dec, 1] / -pbs[dec, 2], None, 12.0))
    print(f"  premium hits zero at pick ~{np.exp(brb/-brbl):.0f} "
          f"(boot median {np.median(pstar):.0f})")

    # decomposition: availability vs talent
    for ycol, label in (("games", "games played (wks 1-14)"),
                        ("ppg", "active PPG")):
        _, b2, b3 = fe_premium(df, ycol)
        print(f"  {label:26s}: RB effect at pick 12 = "
              f"{b2 + b3*np.log(12):+.2f}, at pick 48 = {b2 + b3*np.log(48):+.2f}")

    # 4. kernel quantiles + crossover of the floor ---------------------
    qcurves = {}
    for pos in ("RB", "WR"):
        d = df[(df.pos == pos) & (df.k <= KMAX)]
        qcurves[pos] = {q: kquantile(d, grid, q) for q in (0.25, 0.5, 0.75)}
    floor_diff = qcurves["RB"][0.25] - qcurves["WR"][0.25]
    xf = next((int(g) for g, v in zip(grid, floor_diff)
               if v < 0 and g > 5), None)
    print(f"\nfloor (p25) crossover: RB floor drops below WR floor at "
          f"k ~ {xf}")

    boots = {pos: [] for pos in ("RB", "WR")}
    for _ in range(BQ):
        pick = RNG.choice(YEARS, size=len(YEARS), replace=True)
        bdf = pd.concat([df[df.year == y] for y in pick], ignore_index=True)
        for pos in ("RB", "WR"):
            d = bdf[(bdf.pos == pos) & (bdf.k <= KMAX)]
            boots[pos].append(kquantile(d, grid, 0.25))
    q25lo = {p: np.percentile(np.array(boots[p]), 5, axis=0) for p in boots}
    q25hi = {p: np.percentile(np.array(boots[p]), 95, axis=0) for p in boots}

    # 5. figure --------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    colors = {"RB": "#c0392b", "WR": "#2471a3"}
    ax = axes[0]
    for pos in ("RB", "WR"):
        d = df[(df.pos == pos) & (df.k <= 36)]
        ax.scatter(d.k, d.pts, s=8, alpha=0.25, color=colors[pos])
        a, b = fits[pos]
        mu = a + b * np.log(grid)
        cb = (bs[:, 0:1] + bs[:, 1:2] * np.log(grid)[None, :]) if pos == "RB" \
            else (bs[:, 2:3] + bs[:, 3:4] * np.log(grid)[None, :])
        mlo, mhi = np.percentile(cb, [2.5, 97.5], axis=0)
        ax.plot(grid, mu, color=colors[pos], lw=2, label=f"{pos}: "
                f"{a:.0f} {b:.0f}·ln k")
        ax.fill_between(grid, mlo, mhi, color=colors[pos], alpha=0.18)
    ax.set_xlabel("positional ADP rank k"); ax.set_ylabel("pts, weeks 1-14")
    ax.set_title("mean value by market rank (2018-25)"); ax.legend()

    ax = axes[1]
    for pos in ("RB", "WR"):
        ax.plot(grid, qcurves[pos][0.5], color=colors[pos], lw=2,
                label=f"{pos} median")
        ax.fill_between(grid, qcurves[pos][0.25], qcurves[pos][0.75],
                        color=colors[pos], alpha=0.15)
        ax.plot(grid, q25lo[pos], color=colors[pos], ls=":", lw=1)
        ax.plot(grid, q25hi[pos], color=colors[pos], ls=":", lw=1)
    ax.set_xlabel("positional ADP rank k")
    ax.set_title("p25-p75 bands (dotted: 90% CI on the floor)")
    ax.legend()

    ax = axes[2]
    ax.plot(grid, dR, color="#7d3c98", lw=2)
    ax.fill_between(grid, dlo, dhi, color="#7d3c98", alpha=0.2)
    ax.axhline(0, color="k", lw=0.8)
    if xf:
        ax.axvline(xf, color="gray", ls="--", lw=1)
        ax.text(xf + 0.4, ax.get_ylim()[0] * 0.5, f"floor flips k~{xf}",
                fontsize=8)
    ax.set_xlabel("positional ADP rank k")
    ax.set_title("RB_k − WR_k, 95% cluster-boot band")

    fig.tight_layout()
    out = Path(__file__).resolve().parent.parent / "figures"
    out.mkdir(exist_ok=True)
    fig.savefig(out / "rb_wr_curves.png", dpi=140, bbox_inches="tight")
    print(f"\nfigure -> figures/rb_wr_curves.png")


if __name__ == "__main__":
    main()
