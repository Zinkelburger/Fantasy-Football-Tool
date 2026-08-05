"""Leakage-free historical rookie boards, for the draft-value sim.

For each sim season Y (2020-2025) this refits the rookie model
(rookie_model.py, standard scoring) with class Y held out of training,
then predicts class Y — the same fold the leave-one-class-out eval
grades. So the sim's rookie-aware hero drafts season Y's rookies from
a list the model could genuinely have produced before that season.

Output: data/market/rookie_board_hist.csv
        (year, pid, name, pos, pred) — pid is the nflverse gsis id,
        which is also the sim pool's pid, so the join is exact.
        Rows without a gsis id (never signed) are dropped: the sim
        cannot draft them anyway.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import player_model as pm                                # noqa: E402
import rookie_model as rm                                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "data" / "market"
SIM_YEARS = range(2020, 2026)
LAM = 30.0


def main():
    drafts = rm.draft_classes()
    comb = rm.combine_table()
    cap = pm.cap_table()

    panels = {t: rm.build_class(t, drafts, comb, cap) for t in rm.CLASSES}
    data = pd.concat(panels.values(), ignore_index=True)
    tg = {t: rm.targets(t, 0.0) for t in rm.CLASSES}
    data["y"] = [tg[r.year].get(r.pid, 0.0) for r in data.itertuples()]

    out = []
    for year in SIM_YEARS:
        for pos in rm.POSITIONS:
            tr = data[(data.pos == pos) & (data.year != year)]
            te = panels[year][panels[year].pos == pos]
            if te.empty:
                continue
            pred = rm.fit_predict(tr, te, LAM)
            for r, p in zip(te.itertuples(), pred):
                if r.pid:
                    out.append(dict(year=year, pid=r.pid, name=r.name,
                                    pos=pos, pred=round(float(p), 2)))
        n = sum(1 for r in out if r["year"] == year)
        print(f"{year}: {n} rookies predicted (class {year} held out)")

    dst = MKT / "rookie_board_hist.csv"
    pd.DataFrame(out).to_csv(dst, index=False)
    print(f"wrote {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
