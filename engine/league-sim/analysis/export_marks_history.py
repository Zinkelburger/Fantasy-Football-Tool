"""Historical buy/fade marks, for the draft-value sim.

Finding 32 tested our projection model as a whole-board REPLACEMENT and
a uniform tilt. Both lost. But our research edges were never global
re-rankings — they are narrow, conditional profile calls (findings 16
and 17: a WR/TE who scored far above the points his targets and
carries were worth gives it back next season; one who scored far below
holds his value). This exports those marks per season so the sim can
test the marks THEMSELVES, at the shape they were actually found in.

Mark rule (finding 25's corrected caveat: the gap predicts at WR/TE
only, so QB/RB are deliberately unmarked):
    position-centered gap = (actual PPG - usage-expected PPG),
    centered on the position-season median; >= +1.5 -> fade,
    <= -1.5 -> buy; requires 8+ games.

Leakage note that belongs with any result: the threshold and the
WR/TE-only restriction were chosen on 2017-25 data, which INCLUDES the
sim's target seasons. This arm is therefore the friendliest possible
test of our own findings — if it still fails to beat ADP, that is a
strong negative, not a marginal one.

Output: data/market/marks_hist.csv (year, pid, name, pos, dir, gapc)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import player_model as pm                                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "data" / "market"
SIM_YEARS = range(2020, 2026)
SIGNAL_POS = ("WR", "TE")
GAP_FLAG = 1.5          # standard scoring, matches the site's threshold
MIN_GAMES = 8


def main():
    out = []
    for year in SIM_YEARS:
        t = year - 1                      # features from the prior season
        df = pm.build_rows(t, 0.0)
        df = df[df.pos.isin(SIGNAL_POS)].copy()
        # centre the raw gap within position: actual scoring carries
        # floors/fumbles that expected points lacks, so the raw gap is
        # shifted per position (see export_opportunity.py)
        df["gapc"] = df.groupby("pos").eff_gap.transform(
            lambda s: s - s.median())
        hit = df[(df.games >= MIN_GAMES) & (df.gapc.abs() >= GAP_FLAG)]
        for r in hit.itertuples():
            out.append(dict(year=year, pid=r.pid, name=r.name, pos=r.pos,
                            dir="fade" if r.gapc > 0 else "buy",
                            gapc=round(float(r.gapc), 2)))
        n = sum(1 for r in out if r["year"] == year)
        nb = sum(1 for r in out if r["year"] == year and r["dir"] == "buy")
        print(f"{year}: {n} marks ({nb} buy, {n - nb} fade) from {t}")

    dst = MKT / "marks_hist.csv"
    pd.DataFrame(out).to_csv(dst, index=False)
    print(f"wrote {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
