"""Leakage-free historical model boards, for the draft-value sim.

For each sim season Y (2020-2025) this refits the player model
(player_model.py, standard scoring) with the (Y-1 -> Y) year-pair held
out of training — the same fold the leave-one-year-out eval grades —
and predicts every player entering season Y from his Y-1 features. So
the sim's ModelBoard hero drafts season Y from a list the model could
genuinely have produced before that season, never from a fit that saw
the answer.

Output: data/market/model_board_hist.csv
        (year, pid, name, pos, pred) — pid is the nflverse gsis id,
        which is also the sim pool's pid, so the join is exact.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import player_model as pm                                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "data" / "market"
SIM_YEARS = range(2020, 2026)
LAM = 30.0


def main():
    feats = {t: pm.build_rows(t, 0.0) for t in pm.SEASONS[:-1]}  # 2017-24
    tg = {t: pm.targets_for(t, 0.0) for t in feats}
    panel = pd.concat(feats.values(), ignore_index=True)
    panel["y"] = [tg[r.year][0].get(r.pid, np.nan)
                  for r in panel.itertuples()]
    data = panel.dropna(subset=["y"])

    out = []
    for year in SIM_YEARS:
        hold = year - 1                       # feature season for Y
        for pos in pm.POSITIONS:
            tr = data[(data.pos == pos) & (data.year != hold)]
            te = feats[hold][feats[hold].pos == pos]
            a, b = pm.standardize(tr[pm.FEATURES].values,
                                  te[pm.FEATURES].values)
            beta = pm.ridge_fit(a, tr.y.values, LAM)
            pred = pm.ridge_pred(beta, b)
            for r, p in zip(te.itertuples(), pred):
                out.append(dict(year=year, pid=r.pid, name=r.name,
                                pos=pos, pred=round(float(p), 2)))
        n = sum(1 for r in out if r["year"] == year)
        print(f"{year}: {n} players predicted (features {hold}, "
              f"pair {hold}->{year} held out)")

    dst = MKT / "model_board_hist.csv"
    pd.DataFrame(out).to_csv(dst, index=False)
    print(f"wrote {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
