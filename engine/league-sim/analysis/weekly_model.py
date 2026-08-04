"""Next-WEEK player projection: does opponent + Vegas beat pure form?

The league-mate's question: "if they are facing a team with a bad
defense they will probably score more points" — can we build a weekly
model from that? Tested with nested models, leave-one-season-out:

  M1: player form only        (EWMA of actual pts, alpha=.35 — what the
                               sim's lineup logic already uses)
  M2: + usage expectation     (EWMA of usage-based expected pts)
  M3: + opponent              (defense-vs-position pts allowed rating,
                               shrunk, through week w-1)
  M4: + Vegas                 (implied team total from closing
                               spread/total, + home flag)

Target: the player's fantasy points in week w (league scoring),
players with >=2 prior appearances that season. Metrics: MAE and mean
within-(position, week) Spearman — the start/sit decision is a weekly
ranking problem, so rank quality is what matters.

Data: weekly parquets + ff_opportunity (usage expectation) +
data/market/games.csv (opponent map, closing lines).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
sys.path.insert(0, str(ROOT / "analysis"))
from player_model import league_pts                      # noqa: E402

SEASONS = list(range(2018, 2026))
POSITIONS = ("QB", "RB", "WR", "TE")
ALPHA = 0.35
SHRINK = 4.0          # games of prior weight for def-vs-pos rating

M_FEATS = {
    "M1 form":        ["ewma_pts"],
    "M2 +usage":      ["ewma_pts", "ewma_ep"],
    "M3 +opponent":   ["ewma_pts", "ewma_ep", "opp_dvp"],
    "M4 +vegas":      ["ewma_pts", "ewma_ep", "opp_dvp", "imp_total",
                       "home"],
    "M5 +weather":    ["ewma_pts", "ewma_ep", "opp_dvp", "imp_total",
                       "home", "dome", "cold", "wind"],
}


def game_map():
    g = pd.read_csv(MKT / "games.csv")
    g = g[(g.game_type == "REG") & g.total_line.notna()]
    rows = {}
    for r in g.itertuples():
        ih = r.total_line / 2 + r.spread_line / 2
        ia = r.total_line / 2 - r.spread_line / 2
        dome = float(r.roof in ("dome", "closed"))
        temp = r.temp if not dome and pd.notna(r.temp) else 60.0
        wind = r.wind if not dome and pd.notna(r.wind) else 0.0
        cold = max(0.0, 45.0 - temp)
        wx = (dome, cold, wind)
        rows[(r.season, r.week, r.home_team)] = (r.away_team, ih, 1.0) + wx
        rows[(r.season, r.week, r.away_team)] = (r.home_team, ia, 0.0) + wx
    return rows


def weekly_ep():
    o = pd.read_parquet(DATA / "ff_opportunity_2017_2025.parquet")
    o["season"] = o.season.astype(int)
    ep = (o.get("pass_yards_gained_exp", 0) / 25
          + o.get("pass_touchdown_exp", 0) * 4
          - 2 * o.get("pass_interception_exp", 0)
          + o.get("rush_yards_gained_exp", 0) / 10
          + o.get("rush_touchdown_exp", 0) * 6
          + o.get("rec_yards_gained_exp", 0) / 10
          + o.get("rec_touchdown_exp", 0) * 6)
    o = o.assign(ep=ep)
    return {(r.season, int(r.week), r.player_id): r.ep
            for r in o.itertuples()}


def build_panel():
    gm = game_map()
    epw = weekly_ep()
    rows = []
    for season in SEASONS:
        w = pd.read_parquet(DATA / f"weekly_{season}.parquet")
        w = w[w.position.isin(POSITIONS)].copy()
        w["pts"] = league_pts(w)
        w = w.sort_values("week")
        # defense-vs-position: points allowed to pos, cumulative
        opp = w.apply(lambda r: gm.get((season, r.week, r.team),
                                       (None,))[0], axis=1)
        w["opp"] = opp
        w = w[w.opp.notna()]
        allowed = w.groupby(["opp", "position", "week"])["pts"].sum() \
            .reset_index()
        # league average allowed per defense-week to pos
        lg_avg = allowed.groupby(["position", "week"])["pts"].mean() \
            .rename("lg").reset_index()
        allowed = allowed.merge(lg_avg, on=["position", "week"])
        allowed["diff"] = allowed.pts - allowed.lg
        # cumulative rating through week w-1
        dvp = {}
        for (d, p), grp in allowed.groupby(["opp", "position"]):
            grp = grp.sort_values("week")
            cum, n = 0.0, 0
            for r in grp.itertuples():
                dvp[(d, p, r.week)] = (cum / n) * (n / (n + SHRINK)) \
                    if n else 0.0
                cum += r.diff
                n += 1
        # player trailing EWMAs
        hist = {}
        for r in w.sort_values("week").itertuples():
            key = r.player_id
            e_pts, e_ep, n = hist.get(key, (None, None, 0))
            g = gm.get((season, r.week, r.team))
            if n >= 2 and g is not None:
                rows.append(dict(
                    season=season, week=r.week, pos=r.position,
                    pid=key, y=r.pts, ewma_pts=e_pts,
                    ewma_ep=e_ep if e_ep is not None else e_pts,
                    opp_dvp=dvp.get((g[0], r.position, r.week), 0.0),
                    imp_total=g[1], home=g[2],
                    dome=g[3], cold=g[4], wind=g[5]))
            ep = epw.get((season, int(r.week), key), r.pts)
            e_pts = r.pts if e_pts is None else ALPHA * r.pts + (1 - ALPHA) * e_pts
            e_ep = ep if e_ep is None else ALPHA * ep + (1 - ALPHA) * e_ep
            hist[key] = (e_pts, e_ep, n + 1)
    return pd.DataFrame(rows)


def ols(X, y):
    Xb = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(Xb, y, rcond=None)[0]


def pred(beta, X):
    return np.column_stack([np.ones(len(X)), X]) @ beta


def week_spear(df, col):
    """mean Spearman within (week, pos) between col and y."""
    out = []
    for _, grp in df.groupby(["week", "pos"]):
        if len(grp) < 8:
            continue
        ra = grp[col].rank(); rb = grp.y.rank()
        out.append(np.corrcoef(ra, rb)[0, 1])
    return np.mean(out)


def main():
    panel = build_panel()
    print(f"panel: {len(panel)} player-weeks, {panel.season.nunique()} "
          f"seasons\n")

    # descriptive: the league-mate's claim, directly
    print("facing a bad defense -> more points? (avg pts by opponent "
          "dvp quartile)")
    for pos in POSITIONS:
        d = panel[panel.pos == pos].copy()
        d["q"] = pd.qcut(d.opp_dvp, 4, labels=False)
        m = d.groupby("q")["y"].mean()
        print(f"  {pos}: vs stingiest {m[0]:5.1f} -> vs softest {m[3]:5.1f}"
              f"   (spread {m[3]-m[0]:+.1f} pts)")

    # weather: 'snow games make RBs unstoppable'? avg pts (and delta
    # vs each player's own trailing EWMA, which removes who-plays bias)
    print("\nweather buckets, avg pts and (pts - own EWMA):")
    conds = [("dome", panel.dome == 1),
             ("mild outdoor", (panel.dome == 0) & (panel.cold < 5)
              & (panel.wind < 15)),
             ("cold <=32F", panel.cold >= 13),
             ("windy >=15mph", panel.wind >= 15)]
    for label, mask in conds:
        parts = []
        for pos in POSITIONS:
            d = panel[(panel.pos == pos) & mask]
            parts.append(f"{pos} {d.y.mean():4.1f} "
                         f"({(d.y - d.ewma_pts).mean():+.2f})")
        print(f"  {label:14s} n={mask.sum():5d}  " + "  ".join(parts))

    print(f"\n{'model':14s}" + "".join(f"{p:>14s}" for p in POSITIONS)
          + "   (rank corr | MAE, LOYO)")
    for name, feats in M_FEATS.items():
        cells = []
        for pos in POSITIONS:
            d = panel[panel.pos == pos]
            sp, mae = [], []
            for hold in SEASONS:
                tr, te = d[d.season != hold], d[d.season == hold]
                if len(te) < 50:
                    continue
                beta = ols(tr[feats].values, tr.y.values)
                p = pred(beta, te[feats].values)
                te2 = te.assign(pred=p)
                sp.append(week_spear(te2, "pred"))
                mae.append(np.abs(p - te.y.values).mean())
            cells.append(f"{np.mean(sp):5.3f}|{np.mean(mae):4.1f}")
        print(f"{name:14s}" + "".join(f"{c:>14s}" for c in cells))

    # coefficient sniff on the full panel (M4)
    print("\nM4 coefficients (per position, unstandardized):")
    print(f"{'':6s}{'ewma_pts':>9s}{'ewma_ep':>9s}{'opp_dvp':>9s}"
          f"{'imp_total':>10s}{'home':>6s}")
    for pos in POSITIONS:
        d = panel[panel.pos == pos]
        beta = ols(d[M_FEATS["M4 +vegas"]].values, d.y.values)
        print(f"{pos:6s}" + "".join(f"{b:9.2f}" for b in beta[1:4])
              + f"{beta[4]:10.2f}{beta[5]:6.2f}")


if __name__ == "__main__":
    main()
