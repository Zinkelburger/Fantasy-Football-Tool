#!/usr/bin/env python3
"""Compare our 2026 projection board against JuiceBoxOne's public projections.

Ours (analysis/player_model.py -> data/market/model_board_2026.csv) predicts
next-season fantasy PPG from usage/age/capital/salary features, LOYO-validated.
JuiceBoxOne's cheat sheet publishes season-total projections per scoring format.

Two independent projections agreeing is weak evidence both are sane; the
disagreements are where a draft edge would live, so those get listed.
Comparison is by rank within position (a draft board is a ranking) since our
target is PPG and theirs is a season total.
"""

import pathlib
import re
import warnings

import pandas as pd
from scipy.stats import spearmanr

# pandas 2.3 raises ChainedAssignmentError FutureWarnings for plain column
# assignment on freshly-copied frames; nothing here assigns through a chain.
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
warnings.filterwarnings("ignore", message=".*ChainedAssignment.*")

ROOT = pathlib.Path(__file__).resolve().parent.parent
OURS = ROOT / "data" / "market" / "model_board_2026.csv"
THEIRS = ROOT.parent / "2026" / "data" / "juicebox_cheatsheet_Combined.csv"
ADP = ROOT / "data" / "market" / "adp_2026.csv"

SUFFIX_RE = re.compile(r"\s+(?:Jr\.|Sr\.|II|III|IV|V)$", re.IGNORECASE)


def key(name: str) -> str:
    n = SUFFIX_RE.sub("", str(name)).strip().lower()
    return re.sub(r"[^a-z]", "", n)


def main():
    ours = pd.read_csv(OURS).copy()
    ours["k"] = ours["name"].map(key)

    theirs = pd.read_csv(THEIRS, header=1)
    theirs = theirs.copy()
    theirs.columns = [str(c).strip() for c in theirs.columns]
    theirs = theirs[theirs["Player"].notna()].reset_index(drop=True).copy()
    theirs["k"] = theirs["Player"].map(key)
    theirs["proj"] = pd.to_numeric(theirs["Proj Std"], errors="coerce")

    m = ours.merge(theirs[["k", "Player", "Pos", "proj"]], on="k", how="inner")
    m = m.dropna(subset=["proj", "pred_ppg"]).reset_index(drop=True).copy()
    print(f"ours: {len(ours)} players | JuiceBoxOne: {len(theirs)} | matched: {len(m)}")

    rho, p = spearmanr(m["pred_ppg"], m["proj"])
    print(f"\noverall rank correlation (all matched): rho={rho:.3f} (p={p:.1g})")

    print("\nby position:")
    for pos, g in m.groupby("pos"):
        if len(g) < 5:
            continue
        r, _ = spearmanr(g["pred_ppg"], g["proj"])
        print(f"  {pos}: n={len(g):3d}  rho={r:.3f}")

    # Where do they disagree? Compare within-position rank of each source.
    m["our_rank"] = m.groupby("pos")["pred_ppg"].rank(ascending=False)
    m["their_rank"] = m.groupby("pos")["proj"].rank(ascending=False)
    m["gap"] = m["their_rank"] - m["our_rank"]   # + => we like him more

    print("\nWE like far more than JuiceBoxOne (our rank much better):")
    for r in m.nlargest(10, "gap").itertuples():
        print(f"  {r.name:24s} {r.pos}  ours #{r.our_rank:.0f} vs theirs #{r.their_rank:.0f}"
              f"  (pred {r.pred_ppg:.1f} ppg)")

    print("\nJuiceBoxOne likes far more than WE do:")
    for r in m.nsmallest(10, "gap").itertuples():
        print(f"  {r.name:24s} {r.pos}  ours #{r.our_rank:.0f} vs theirs #{r.their_rank:.0f}"
              f"  (pred {r.pred_ppg:.1f} ppg)")

    # Do either beat market ADP as an ordering? (agreement with ADP, not accuracy)
    if ADP.exists():
        adp = pd.read_csv(ADP)
        namecol = next((c for c in adp.columns if c.lower() in ("name", "player")), None)
        adpcol = next((c for c in adp.columns
                       if "adp" in c.lower() or c.lower() in ("rank", "avg")), None)
        if namecol and adpcol:
            adp["k"] = adp[namecol].map(key)
            a = m.merge(adp[["k", adpcol]], on="k", how="inner")
            a = a.dropna(subset=[adpcol])
            if len(a) > 10:
                r_ours, _ = spearmanr(a["pred_ppg"], -pd.to_numeric(a[adpcol], errors="coerce"))
                r_theirs, _ = spearmanr(a["proj"], -pd.to_numeric(a[adpcol], errors="coerce"))
                print(f"\nagreement with market ADP (n={len(a)}):")
                print(f"  our model vs ADP:     rho={r_ours:.3f}")
                print(f"  JuiceBoxOne vs ADP:   rho={r_theirs:.3f}")
                print("  (higher = closer to consensus, NOT more accurate)")


if __name__ == "__main__":
    main()
