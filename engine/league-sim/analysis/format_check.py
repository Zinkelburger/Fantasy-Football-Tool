"""Do findings 15/16/17 survive 0.5PPR and full PPR scoring?

The next-season-signal findings were computed under the family's
standard scoring. This re-runs their headline statistics with the
outcome (and current-season PPG control) scored under each format:

  15  last-3-weeks PPG partial vs next-year PPG (should stay ~0)
  16  TDOE/game partial vs next-year PPG (should stay negative)
  17  WR targets/game partial vs next-year PPG (should stay positive,
      plausibly stronger in PPR — receptions are points there)

Method matches scripts/next_season_signal.py: rosterable players
(TOPN per position by season total), 2017->2025 season pairs, gp >= 8
and next-year gp >= 6, partial r = corr of X and next-year PPG after
residualizing both on current PPG. Point estimates + per-season-pair
sign counts only (the full permutation suite lives in the original
script; directions and magnitudes are what format sensitivity is
about).

Run:  venv/bin/python analysis/format_check.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "analysis"))
from player_model import league_pts, weekly_raw          # noqa: E402

YEARS = list(range(2017, 2026))
FORMATS = {"std": 0.0, "half": 0.5, "ppr": 1.0}
TOPN = {"QB": 24, "RB": 50, "WR": 60, "TE": 24}


def resid(y, x):
    return y - np.polyval(np.polyfit(x, y, 1), x)


def player_seasons(ppr):
    frames = []
    for y in YEARS:
        w = weekly_raw(y).copy()
        w["pts"] = league_pts(w, ppr)
        w["season"] = y
        w["mw"] = w.week.max()
        frames.append(w[["player_id", "position", "season", "week",
                         "pts", "mw"]])
    wk = pd.concat(frames)
    key = ["player_id", "season"]
    ps = wk.groupby(key).agg(position=("position", "first"),
                             gp=("pts", "size"), total=("pts", "sum"),
                             ppg=("pts", "mean")).reset_index()
    last3 = wk[wk.week > wk.mw - 3].groupby(key).pts.agg(["mean", "size"])
    last3.columns = ["ppg_last3", "gp_last3"]
    ps = ps.merge(last3.reset_index(), on=key, how="left")
    nxt = ps[key + ["ppg", "gp"]].copy()
    nxt["season"] -= 1
    ps = ps.merge(nxt.rename(columns={"ppg": "ppg_next", "gp": "gp_next"}),
                  on=key, how="left")
    ps["pos_rank"] = ps.groupby(["season", "position"])["total"].rank(
        ascending=False, method="first")
    ps["relevant"] = ps.pos_rank <= ps.position.map(TOPN)
    return ps


def merged_signals(ps):
    opp = pd.read_parquet(DATA / "ff_opportunity_2017_2025.parquet")
    opp = opp.copy()
    opp["season"] = opp.season.astype(int)
    opp["week"] = opp.week.astype(int)
    opp = opp[opp.week <= np.where(opp.season <= 2020, 17, 18)]
    o = opp.groupby(["player_id", "season"]).agg(
        xtd=("rec_touchdown_exp", "sum"), xtd2=("rush_touchdown_exp", "sum"),
        td=("rec_touchdown", "sum"), td2=("rush_touchdown", "sum")).reset_index()
    o["tdoe"] = (o.td + o.td2) - (o.xtd + o.xtd2)
    adv = pd.read_parquet(DATA / "adv_weekly_2017_2025.parquet")
    adv = adv[adv.season_type == "REG"]
    a = adv.groupby(["player_id", "season"]).agg(
        targets=("targets", "sum")).reset_index()
    m = ps.merge(o[["player_id", "season", "tdoe"]],
                 on=["player_id", "season"], how="left")
    return m.merge(a, on=["player_id", "season"], how="left")


def partial(d, xcol):
    x = resid(d[xcol].values.astype(float), d.ppg.values)
    y = resid(d.ppg_next.values.astype(float), d.ppg.values)
    return np.corrcoef(x, y)[0, 1]


def signs(d, xcol):
    out = []
    for s in range(2017, 2025):
        dd = d[d.season == s]
        if len(dd) >= 25:
            out.append(np.sign(partial(dd, xcol)))
    return f"{int(sum(s > 0 for s in out))}/{len(out)} pairs positive"


def main():
    for fmt, ppr in FORMATS.items():
        ps = player_seasons(ppr)
        m = merged_signals(ps)
        base = m[m.relevant & m.season.lt(2025) & (m.gp >= 8)
                 & (m.gp_next >= 6) & m.ppg_next.notna()]

        d = base[(base.gp_last3 >= 2)].dropna(subset=["ppg_last3"])
        r15 = partial(d, "ppg_last3")

        sk = base[base.position.isin(["RB", "WR", "TE"])].dropna(
            subset=["tdoe"]).copy()
        sk["tdoe_pg"] = sk.tdoe / sk.gp
        r16 = partial(sk, "tdoe_pg")

        wr = base[base.position == "WR"].dropna(subset=["targets"]).copy()
        wr["tpg"] = wr.targets / wr.gp
        r17 = partial(wr, "tpg")

        print(f"{fmt:>4}:  f15 last3 {r15:+.3f}   "
              f"f16 TDOE {r16:+.3f} ({signs(sk.assign(tdoe_pg=sk.tdoe_pg), 'tdoe_pg')})   "
              f"f17 WR tgt {r17:+.3f} ({signs(wr, 'tpg')})")


if __name__ == "__main__":
    main()
