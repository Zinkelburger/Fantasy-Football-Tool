"""Weekly D/ST projection model (site product 3/6; finding 27).

Design follows what subvertadown has published about D/ST
predictability (subvertadown.com, "Attempting to Find a More
Predictable D/ST Scoring Scheme"): points-allowed is mostly the
opponent (= Vegas), sacks/turnovers regress hard, and the one stable
defensive trait is yards-allowed. His full model reaches ~0.42
correlation — the public benchmark for this position.

Structure:
- target: weekly D/ST fantasy points, ESPN-default-ish scoring,
  computed from play-by-play 2018-2025 + final scores
- opponent side (dominant): Vegas implied points for the OFFENSE the
  defense faces, opponent giveaways/game, opponent sacks-allowed per
  dropback (the O-line angle), all season-to-date with prior-season
  blend for early weeks
- defense side: own yards-allowed per game vs league (the stable
  trait), own trailing D/ST ppg (naive anchor)
- context: home, wind >= 15mph

LOYO by season; metrics = within-week Spearman + Pearson vs actual.
Model ladder isolates what each input family adds, subvertadown-style.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "data" / "market"
SEASONS = list(range(2018, 2026))
PRIOR_G = 4.0          # prior-season pseudo-games for early-week blend

PA_TIERS = [(0, 0, 5), (1, 6, 4), (7, 13, 3), (14, 17, 1), (18, 21, 0),
            (22, 27, -1), (28, 34, -3), (35, 45, -5), (46, 99, -6)]


def pa_pts(pa):
    for lo, hi, p in PA_TIERS:
        if lo <= pa <= hi:
            return p
    return 0


Q538 = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}


def qb_values():
    """(season, gameday, team) -> starting QB value (nfelo qb_elos)."""
    q = pd.read_csv(MKT / "qb_elos.csv")
    q = q[q.season >= min(SEASONS)]
    out = {}
    for r in q.itertuples():
        for i in (1, 2):
            t = getattr(r, f"team{i}")
            t = Q538.get(t, t)
            v = getattr(r, f"qb{i}_value_pre")
            if pd.notna(v):
                out[(r.season, r.date, t)] = v
    return out


def build_dst_weeks():
    """(season, week, def, off) rows with DST pts + raw components."""
    qv = qb_values()
    g = pd.read_csv(MKT / "games.csv")
    g = g[(g.game_type == "REG") & g.home_score.notna()
          & (g.season.isin(SEASONS))]
    score = {}
    for r in g.itertuples():
        qb_h = qv.get((r.season, r.gameday, r.home_team), np.nan)
        qb_a = qv.get((r.season, r.gameday, r.away_team), np.nan)
        score[(r.season, r.week, r.home_team)] = (r.away_team,
                                                  r.away_score, 1.0,
                                                  r.total_line,
                                                  r.spread_line, r.wind,
                                                  qb_a)
        score[(r.season, r.week, r.away_team)] = (r.home_team,
                                                  r.home_score, 0.0,
                                                  r.total_line,
                                                  r.spread_line, r.wind,
                                                  qb_h)
    rows = []
    for y in SEASONS:
        p = pd.read_parquet(
            MKT / f"pbp_{y}.parquet",
            columns=["season", "week", "season_type", "posteam", "defteam",
                     "sack", "interception", "fumble_lost", "safety",
                     "touchdown", "td_team", "yards_gained", "qb_dropback"])
        p = p[(p.season_type == "REG") & p.posteam.notna()]
        agg = p.groupby(["week", "defteam", "posteam"]).agg(
            sacks=("sack", "sum"), ints=("interception", "sum"),
            fum=("fumble_lost", "sum"), safety=("safety", "sum"),
            yds_allowed=("yards_gained", "sum"),
            dropbacks=("qb_dropback", "sum")).reset_index()
        dtd = p[(p.touchdown == 1) & (p.td_team == p.defteam)] \
            .groupby(["week", "defteam"]).size()
        for r in agg.itertuples():
            info = score.get((y, r.week, r.defteam))
            if info is None or info[0] != r.posteam:
                continue
            opp, pa, home, total, spread, wind, opp_qb = info
            td = dtd.get((r.week, r.defteam), 0)
            pts = (r.sacks + 2 * r.ints + 2 * r.fum + 2 * r.safety
                   + 6 * td + pa_pts(int(pa)))
            imp_off = (total / 2 - spread / 2) if home else \
                (total / 2 + spread / 2)
            rows.append(dict(
                season=y, week=r.week, d=r.defteam, o=r.posteam,
                pts=pts, sacks=r.sacks, giveaways=r.ints + r.fum,
                yds_allowed=r.yds_allowed, dropbacks=r.dropbacks,
                home=home, wind=float((wind or 0) >= 15),
                opp_qb=opp_qb / 100.0,
                imp_off=imp_off if pd.notna(total) else np.nan))
    return pd.DataFrame(rows)


def add_features(df):
    """Season-to-date rates with prior-season blend, leak-free."""
    df = df.sort_values(["season", "week"]).copy()
    feats = []
    prior = {}   # (season, team) -> dict of full-season rates
    for y in SEASONS:
        d = df[df.season == y]
        team_prior_off = {}
        team_prior_def = {}
        for t in set(d.o) | set(d.d):
            pv = prior.get((y - 1, t))
            team_prior_off[t] = pv["off"] if pv else None
            team_prior_def[t] = pv["def"] if pv else None
        cum_off = {}    # offense o -> [giveaways, sacked, dropbacks, games]
        cum_def = {}    # defense d -> [yds_allowed, dst_pts, games]
        lg_ya = []
        for wk in sorted(d.week.unique()):
            cur = d[d.week == wk]
            lg_mean_ya = np.mean(lg_ya) if lg_ya else 340.0
            for r in cur.itertuples():
                co = cum_off.get(r.o, [0.0, 0.0, 0.0, 0])
                po = team_prior_off.get(r.o)
                n_o = co[3] + (PRIOR_G if po else 0)
                give = ((co[0] + (po["give"] * PRIOR_G if po else 0))
                        / n_o) if n_o else 1.4
                sackr = ((co[1] + (po["sackr"] * PRIOR_G if po else 0))
                         / n_o) if n_o else 2.5
                cd = cum_def.get(r.d, [0.0, 0.0, 0])
                pdf = team_prior_def.get(r.d)
                n_d = cd[2] + (PRIOR_G if pdf else 0)
                ya = ((cd[0] + (pdf["ya"] * PRIOR_G if pdf else 0))
                      / n_d) if n_d else lg_mean_ya
                dst_ppg = ((cd[1] + (pdf["ppg"] * PRIOR_G if pdf else 0))
                           / n_d) if n_d else 5.0
                feats.append(dict(
                    idx=r.Index, opp_give=give, opp_sacked=sackr,
                    own_ya=lg_mean_ya - ya, own_ppg=dst_ppg))
            for r in cur.itertuples():
                co = cum_off.setdefault(r.o, [0.0, 0.0, 0.0, 0])
                co[0] += r.giveaways; co[1] += r.sacks
                co[2] += r.dropbacks; co[3] += 1
                cd = cum_def.setdefault(r.d, [0.0, 0.0, 0])
                cd[0] += r.yds_allowed; cd[1] += r.pts; cd[2] += 1
                lg_ya.append(r.yds_allowed)
        for t, co in cum_off.items():
            prior.setdefault((y, t), {})["off"] = dict(
                give=co[0] / co[3], sackr=co[1] / co[3])
        for t, cd in cum_def.items():
            prior.setdefault((y, t), {}).setdefault("def", dict(
                ya=cd[0] / cd[2], ppg=cd[1] / cd[2]))
    f = pd.DataFrame(feats).set_index("idx")
    return df.join(f)


LADDER = {
    "naive (own DST ppg)": ["own_ppg"],
    "vegas only":          ["imp_off"],
    "+ opp O-line/gives":  ["imp_off", "opp_give", "opp_sacked"],
    "+ own defense":       ["imp_off", "opp_give", "opp_sacked",
                            "own_ya", "own_ppg"],
    "full (+home/wind)":   ["imp_off", "opp_give", "opp_sacked",
                            "own_ya", "own_ppg", "home", "wind"],
    "full + opp QB-Elo":   ["imp_off", "opp_give", "opp_sacked",
                            "own_ya", "own_ppg", "home", "wind",
                            "opp_qb"],
}


def ols(X, y):
    Xb = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(Xb, y, rcond=None)[0]


def main():
    df = add_features(build_dst_weeks().reset_index(drop=True))
    df = df.dropna(subset=["imp_off", "opp_qb"])
    print(f"{len(df)} defense-weeks, {len(SEASONS)} seasons, "
          f"mean DST pts {df.pts.mean():.1f} (sd {df.pts.std():.1f})\n")

    print(f"{'model':22s}{'spearman':>9s}{'pearson':>9s}{'MAE':>6s}"
          f"   (LOYO, within-week rank)")
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

    b = ols(df[LADDER["full (+home/wind)"]].values, df.pts.values)
    print("\nfull-model coefficients:")
    for f, c in zip(LADDER["full (+home/wind)"], b[1:]):
        print(f"  {f:12s} {c:+.2f}")
    print(f"  (intercept {b[0]:+.1f}; imp_off in points, so each Vegas "
          f"point off the opponent's total ~ {abs(b[1]):.2f} DST pts)")


if __name__ == "__main__":
    main()
