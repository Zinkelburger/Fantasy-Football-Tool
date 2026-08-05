"""Where, if anywhere, does disagreeing with ADP pay?

Finding 32 showed that re-ranking or tilting the board by our model
loses. That is a verdict on the whole board at once. This asks the
sharper question: when our model disagrees with the market about a
specific player, does the disagreement point the right way?

Method, per sim season 2020-2025 (leakage-free model boards from
analysis/export_model_history.py, i.e. that year held out):

    d      = ADP position rank - model position rank
             (positive = we like him MORE than the market does)
    resid  = actual PPG - E[PPG | his ADP position rank]
             where E[.] is a within-position-season LOESS-free fit:
             the mean actual PPG of players at nearby ADP ranks
             (log-linear fit, matching pick_value's a + b*ln(rank))

If our disagreements carry information, corr(d, resid) > 0.

Reported pooled, per position, and split by where on the board the
disagreement happens (early / middle / late), because finding 24 says
market error concentrates in rounds 4-8.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import player_model as pm                                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
YEARS = range(2020, 2026)
POSITIONS = ("QB", "RB", "WR", "TE")


def norm(name):
    import re
    n = str(name).lower().strip().replace(".", "").replace("'", "")
    n = re.sub(r"\s+(?:jr|sr|ii|iii|iv|v)$", "", n)
    return re.sub(r"\s+", " ", n)


def adp_pos_ranks(year):
    p = DATA / f"adp_{year}.json"
    if not p.exists():
        return {}
    rows = json.loads(p.read_text())
    by = {}
    for e in rows:
        if e.get("adp") is None:
            continue
        by.setdefault(e["pos"], []).append((float(e["adp"]), norm(e["name"])))
    out = {}
    for pos, lst in by.items():
        for i, (_, n) in enumerate(sorted(lst), 1):
            out[(pos, n)] = i
    return out


def main():
    hist = pd.read_csv(MKT / "model_board_hist.csv")
    rows = []
    for year in YEARS:
        adp = adp_pos_ranks(year)
        actual = pm.season_stats(year, 0.0)          # the season drafted for
        h = hist[hist.year == year]
        for pos in POSITIONS:
            sub = h[h.pos == pos].copy()
            sub["adp_rank"] = [adp.get((pos, norm(n))) for n in sub.name]
            sub = sub.dropna(subset=["adp_rank"])
            if len(sub) < 12:
                continue
            # actual PPG for the season being drafted (0 if never played)
            sub["ppg"] = [float(actual.loc[p].ppg) if p in actual.index
                          else 0.0 for p in sub.pid]
            # model position rank among these same players
            sub["mdl_rank"] = sub.pred.rank(ascending=False)
            sub["adp_rank"] = sub.adp_rank.rank()      # dense within subset
            # E[ppg | adp rank]: log-linear, the pick_value shape
            x = np.log(sub.adp_rank.values)
            b, a = np.polyfit(x, sub.ppg.values, 1)
            sub["resid"] = sub.ppg.values - (a + b * x)
            sub["d"] = sub.adp_rank - sub.mdl_rank
            sub["band"] = pd.cut(sub.adp_rank, [0, 12, 30, 999],
                                 labels=["early", "middle", "late"])
            rows.append(sub[["year", "pos", "d", "resid", "band", "ppg"]])

    df = pd.concat(rows, ignore_index=True)
    print(f"n = {len(df)} player-seasons, {YEARS.start}-{YEARS.stop - 1}\n")

    def rep(label, sub):
        if len(sub) < 30:
            print(f"{label:22s} n={len(sub):5d}   (too few)")
            return
        r = np.corrcoef(sub.d.values, sub.resid.values)[0, 1]
        # se of a correlation ~ 1/sqrt(n-3)
        se = 1 / np.sqrt(len(sub) - 3)
        flag = "  <-- clears 2se" if abs(r) > 2 * se else ""
        print(f"{label:22s} n={len(sub):5d}   corr(d, resid) = "
              f"{r:+.3f} ± {se:.3f}{flag}")

    rep("ALL", df)
    print()
    for pos in POSITIONS:
        rep(pos, df[df.pos == pos])
    print()
    for band in ("early", "middle", "late"):
        rep(f"board {band}", df[df.band == band])
    print()
    for pos in POSITIONS:
        for band in ("early", "middle", "late"):
            rep(f"{pos} {band}", df[(df.pos == pos) & (df.band == band)])

    # The late-board result is the only one that clears its error bar,
    # and it was found by looking at these same seasons — so check it
    # is not one lucky year before anyone builds on it.
    print("\nLate board (pos rank > 30), year by year:")
    late = df[df.band == "late"]
    pos_years = 0
    for year in YEARS:
        sub = late[late.year == year]
        if len(sub) < 20:
            print(f"  {year}   n={len(sub):4d}   (too few)")
            continue
        r = np.corrcoef(sub.d.values, sub.resid.values)[0, 1]
        pos_years += r > 0
        print(f"  {year}   n={len(sub):4d}   corr = {r:+.3f}")
    print(f"  positive in {pos_years} of {len(list(YEARS))} seasons")

    # Practical version: the players we disagree on MOST
    print("\nBiggest disagreements (|d| >= 15), mean residual PPG:")
    big = df[df.d.abs() >= 15]
    up = big[big.d > 0]
    dn = big[big.d < 0]
    print(f"  we like him MORE  n={len(up):4d}  mean resid "
          f"{up.resid.mean():+.2f} PPG")
    print(f"  we like him LESS  n={len(dn):4d}  mean resid "
          f"{dn.resid.mean():+.2f} PPG")
    print("  (positive = outscored what his draft price implied)")


if __name__ == "__main__":
    main()
