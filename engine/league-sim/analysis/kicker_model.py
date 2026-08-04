"""Weekly kicker projection model (site products 3/4; finding 28).

Design informed by subvertadown's published K work: kickers are the
least predictable position ("predictability ~ individual WR1s"; mean
~7.5, typical error +/-3); PATs are the predictable component, FGs the
hard part; "sum of all FGs" is the best single predictor; his model's
stated inputs include win chance, coaching aggressiveness (4th-down
tendencies suppress FG attempts), and dome/wind. His baseline for a
"normal" kicker model is the betting line.

Ours:
- target: weekly K fantasy points, ESPN std (FG 0-39=3, 40-49=4,
  50+=5, PAT=1), from the weekly stat parquets
- Vegas: own-team implied total + devigged moneyline win prob
- weather: dome, wind >= 15
- team traits (season-to-date, 4-game prior-season blend): share of
  drives ending in a FG attempt (the stall/coach-aggressiveness
  trait), share ending in TD (steals PATs from FGs)
- kicker form: season-to-date fantasy ppg and FG attempts/game

LOYO 2018-2025; within-week Spearman + pooled Pearson.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
SEASONS = list(range(2018, 2026))
PRIOR_G = 4.0


def k_points(w):
    return (3 * (w.fg_made_0_19 + w.fg_made_20_29 + w.fg_made_30_39)
            + 4 * w.fg_made_40_49 + 5 * (w.fg_made_50_59 + w.fg_made_60_)
            + w.pat_made)


def game_info():
    g = pd.read_csv(MKT / "games.csv")
    g = g[(g.game_type == "REG") & g.season.isin(SEASONS)]
    out = {}
    for r in g.itertuples():
        if pd.isna(r.total_line) or pd.isna(r.spread_line):
            continue
        dome = float(r.roof in ("dome", "closed"))
        wind = float((r.wind if pd.notna(r.wind) else 0) >= 15 and not dome)

        def wp(own_ml, opp_ml):
            if pd.isna(own_ml) or pd.isna(opp_ml):
                return 0.5
            po = 100 / (own_ml + 100) if own_ml > 0 else -own_ml / (-own_ml + 100)
            pp = 100 / (opp_ml + 100) if opp_ml > 0 else -opp_ml / (-opp_ml + 100)
            return po / (po + pp)
        out[(r.season, r.week, r.home_team)] = (
            r.total_line / 2 - r.spread_line / 2, dome, wind,
            wp(r.home_moneyline, r.away_moneyline))
        out[(r.season, r.week, r.away_team)] = (
            r.total_line / 2 + r.spread_line / 2, dome, wind,
            wp(r.away_moneyline, r.home_moneyline))
    return out


def drive_traits():
    """(season, team) full-season + per-week cumulative FG-attempt and
    TD share of drives."""
    rows = []
    for y in SEASONS:
        p = pd.read_parquet(
            MKT / f"pbp_{y}.parquet",
            columns=["season", "week", "season_type", "posteam",
                     "fixed_drive", "fixed_drive_result"])
        p = p[(p.season_type == "REG") & p.posteam.notna()]
        d = p.drop_duplicates(["week", "posteam", "fixed_drive"])
        d = d.assign(
            fga=d.fixed_drive_result.isin(["Field goal",
                                           "Missed field goal"]),
            td=d.fixed_drive_result == "Touchdown")
        wk = d.groupby(["week", "posteam"]).agg(
            drives=("fixed_drive", "size"), fga=("fga", "sum"),
            td=("td", "sum")).reset_index()
        wk["season"] = y
        rows.append(wk)
    return pd.concat(rows, ignore_index=True)


def build_panel():
    gi = game_info()
    dt = drive_traits()
    prior = {}
    for (y, t), grp in dt.groupby(["season", "posteam"]):
        prior[(y, t)] = (grp.fga.sum() / grp.drives.sum(),
                         grp.td.sum() / grp.drives.sum())
    rows = []
    for y in SEASONS:
        w = pd.read_parquet(DATA / f"weekly_{y}.parquet")
        w = w[w.position == "K"].copy()
        w["pts"] = k_points(w)
        w["fga"] = (w.fg_made_0_19 + w.fg_made_20_29 + w.fg_made_30_39
                    + w.fg_made_40_49 + w.fg_made_50_59 + w.fg_made_60_
                    + w.fg_missed)
        dts = dt[dt.season == y]
        cum = {}       # team -> [drives, fga, td]
        kcum = {}      # kicker -> [pts, fga, games]
        for wk in sorted(w.week.unique()):
            cur = w[w.week == wk]
            for r in cur.itertuples():
                info = gi.get((y, r.week, r.team))
                if info is None:
                    continue
                imp, dome, wind, winp = info
                c = cum.get(r.team, [0.0, 0.0, 0.0])
                pv = prior.get((y - 1, r.team))
                pd_, pf, pt_ = (c[0] + (PRIOR_G * 11 if pv else 0),
                                c[1] + (pv[0] * PRIOR_G * 11 if pv else 0),
                                c[2] + (pv[1] * PRIOR_G * 11 if pv else 0))
                fga_share = pf / pd_ if pd_ else 0.13
                td_share = pt_ / pd_ if pd_ else 0.22
                kc = kcum.get(r.player_id, [0.0, 0.0, 0])
                k_ppg = kc[0] / kc[2] if kc[2] >= 2 else 7.5
                k_fga = kc[1] / kc[2] if kc[2] >= 2 else 1.8
                rows.append(dict(
                    season=y, week=wk, pid=r.player_id, pts=r.pts,
                    imp=imp, winp=winp, dome=dome, wind=wind,
                    fga_share=fga_share, td_share=td_share,
                    k_ppg=k_ppg, k_fga=k_fga))
            for r in cur.itertuples():
                kc = kcum.setdefault(r.player_id, [0.0, 0.0, 0])
                kc[0] += r.pts; kc[1] += r.fga; kc[2] += 1
            wkdt = dts[dts.week == wk]
            for r in wkdt.itertuples():
                c = cum.setdefault(r.posteam, [0.0, 0.0, 0.0])
                c[0] += r.drives; c[1] += r.fga; c[2] += r.td
    return pd.DataFrame(rows)


LADDER = {
    "naive (kicker ppg)":  ["k_ppg"],
    "vegas (imp + winp)":  ["imp", "winp"],
    "+ weather":           ["imp", "winp", "dome", "wind"],
    "+ team traits":       ["imp", "winp", "dome", "wind",
                            "fga_share", "td_share"],
    "full (+ kicker form)": ["imp", "winp", "dome", "wind",
                             "fga_share", "td_share", "k_ppg", "k_fga"],
}


def ols(X, y):
    return np.linalg.lstsq(np.column_stack([np.ones(len(X)), X]), y,
                           rcond=None)[0]


def main():
    df = build_panel()
    print(f"{len(df)} kicker-weeks, {len(SEASONS)} seasons, mean "
          f"{df.pts.mean():.1f} (sd {df.pts.std():.1f})\n")
    print(f"{'model':22s}{'spearman':>9s}{'pearson':>9s}{'MAE':>6s}")
    for name, feats in LADDER.items():
        sp, pe, mae = [], [], []
        for hold in SEASONS:
            tr, te = df[df.season != hold], df[df.season == hold]
            b = ols(tr[feats].values, tr.pts.values)
            pr = np.column_stack([np.ones(len(te)), te[feats].values]) @ b
            t2 = te.assign(pred=pr)
            s = [np.corrcoef(g.pred.rank(), g.pts.rank())[0, 1]
                 for _, g in t2.groupby("week")
                 if len(g) >= 10 and g.pred.nunique() > 1]
            sp.append(np.nanmean(s))
            pe.append(np.corrcoef(pr, te.pts)[0, 1])
            mae.append(np.abs(pr - te.pts).mean())
        print(f"{name:22s}{np.mean(sp):9.3f}{np.mean(pe):9.3f}"
              f"{np.mean(mae):6.2f}")
    b = ols(df[LADDER["full (+ kicker form)"]].values, df.pts.values)
    print("\nfull-model coefficients:")
    for f, c in zip(LADDER["full (+ kicker form)"], b[1:]):
        print(f"  {f:10s} {c:+.2f}")


if __name__ == "__main__":
    main()
