"""WR/CB matchup proxy: is directional matchup data worth anything?

Context: FantasyPoints' WR/CB matchup report (site since taken down)
charted WR alignment (LWR/slot/RWR) vs individual CB assignments and
quality. True CB coverage assignment is proprietary charting data —
not reproducible from free sources. What IS buildable from nflverse
play-by-play is the directional reduced form:

- a WR's target mix by pass_location (left/middle/right) — a proxy
  for where he lines up,
- a defense's fantasy points allowed to WRs by direction, relative to
  league average, cumulative through week w-1 (shrunk),
- their dot product = a directional matchup score, the poor man's
  version of their "Matchup Score."

Two tests decide if the concept can work at this resolution:
1. RELIABILITY: split-half (odd vs even weeks) correlation of a
   defense's directional allowance. If "their left side is stingy"
   doesn't even persist within a season, no matchup report built on
   it can predict anything.
2. VALUE: leave-one-season-out weekly WR prediction, baseline
   (trailing form + team-level defense-vs-WR) vs + directional
   matchup score. Within-week Spearman and MAE.

pbp 2022-2025 (~48k targets to WRs). Caveats: pass_location is where
the throw went, not where the WR aligned; shadow coverage (the
McLaurin case) is precisely the situation this proxy cannot see —
that requires charting data.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
sys.path.insert(0, str(ROOT / "analysis"))

SEASONS = (2022, 2023, 2024, 2025)
DIRS = ("left", "middle", "right")
SHRINK = 4.0
ALPHA = 0.35


def wr_positions():
    pos = {}
    for y in SEASONS:
        w = pd.read_parquet(DATA / f"weekly_{y}.parquet",
                            columns=["player_id", "position"])
        pos.update(dict(zip(w.player_id, w.position)))
    return pos


def load_targets():
    pos = wr_positions()
    frames = []
    for y in SEASONS:
        f = MKT / f"pbp_{y}.parquet"
        if not f.exists():          # ~20MB/season; gitignored (public repo)
            import urllib.request
            urllib.request.urlretrieve(
                "https://github.com/nflverse/nflverse-data/releases/"
                f"download/pbp/play_by_play_{y}.parquet", f)
        p = pd.read_parquet(
            f,
            columns=["season", "week", "season_type", "posteam", "defteam",
                     "pass_location", "receiver_player_id",
                     "complete_pass", "yards_gained", "pass_touchdown"])
        p = p[(p.season_type == "REG") & p.pass_location.notna()
              & p.receiver_player_id.notna()]
        p["wr"] = p.receiver_player_id.map(pos) == "WR"
        p = p[p.wr]
        p["fp"] = (np.where(p.complete_pass == 1, p.yards_gained, 0) / 10.0
                   + 6.0 * p.pass_touchdown)
        frames.append(p)
    return pd.concat(frames, ignore_index=True)


def main():
    t = load_targets()
    print(f"{len(t)} WR targets with direction, {len(SEASONS)} seasons")

    # ---- 1. reliability of defensive directional allowance ----------
    half = t.groupby(["season", "defteam", "pass_location",
                      t.week % 2])["fp"].sum().unstack(fill_value=0)
    games = t.groupby(["season", "defteam", t.week % 2])["week"] \
        .nunique().unstack(fill_value=1)
    per_g = half.copy()
    for h in (0, 1):
        idx = per_g.index.droplevel("pass_location")
        per_g[h] = half[h].values / games[h].reindex(idx).values
    print("\nsplit-half (odd/even weeks) reliability of defense FP "
          "allowed to WRs:")
    for d in DIRS:
        sub = per_g.xs(d, level="pass_location")
        print(f"  direction {d:7s}: r = "
              f"{np.corrcoef(sub[0], sub[1])[0,1]:.3f}")
    tot = per_g.groupby(["season", "defteam"]).sum()
    print(f"  all directions   : r = "
          f"{np.corrcoef(tot[0], tot[1])[0,1]:.3f}  (team-level DvP)")

    # ---- 2. does the directional score add weekly predictive value? -
    wk = t.groupby(["season", "week", "receiver_player_id", "posteam",
                    "defteam"]).agg(
        fp=("fp", "sum"), n=("fp", "size"),
        **{f"n_{d}": ("pass_location", lambda s, d=d: (s == d).sum())
           for d in DIRS}).reset_index()

    rows = []
    for season in SEASONS:
        ws = wk[wk.season == season].sort_values("week")
        lg_dir = {d: 0.0 for d in DIRS}
        # cumulative state
        def_dir = {}   # (team, dir) -> [fp_sum, games]
        def_tot = {}
        wr_hist = {}   # pid -> (ewma, n, dir counts)
        lg_cum = {d: [0.0, 0] for d in DIRS}
        for week in sorted(ws.week.unique()):
            cur = ws[ws.week == week]
            lgavg = {d: (lg_cum[d][0] / lg_cum[d][1] if lg_cum[d][1] else 0)
                     for d in DIRS}
            for r in cur.itertuples():
                e, n, mix = wr_hist.get(r.receiver_player_id,
                                        (None, 0, {d: 1.0 for d in DIRS}))
                if n >= 2:
                    tot_mix = sum(mix.values())
                    m_dir = m_tot = 0.0
                    for d in DIRS:
                        s_, g_ = def_dir.get((r.defteam, d), (0.0, 0))
                        rating = ((s_ / g_) - lgavg[d]) * (g_ / (g_ + SHRINK)) \
                            if g_ else 0.0
                        m_dir += (mix[d] / tot_mix) * rating
                    s_, g_ = def_tot.get(r.defteam, (0.0, 0))
                    lg_t = sum(lgavg.values())
                    m_tot = ((s_ / g_) - lg_t) * (g_ / (g_ + SHRINK)) \
                        if g_ else 0.0
                    rows.append(dict(season=season, week=week,
                                     ewma=e, dvp_team=m_tot,
                                     dvp_dir=m_dir, y=r.fp))
            # update state after the week
            for r in cur.itertuples():
                e, n, mix = wr_hist.get(r.receiver_player_id,
                                        (None, 0, {d: 1.0 for d in DIRS}))
                e = r.fp if e is None else ALPHA * r.fp + (1 - ALPHA) * e
                for d in DIRS:
                    mix[d] += getattr(r, f"n_{d}")
                wr_hist[r.receiver_player_id] = (e, n + 1, mix)
            for (dt,), grp in cur.groupby(["defteam"]):
                s_, g_ = def_tot.get(dt, (0.0, 0))
                def_tot[dt] = (s_ + grp.fp.sum(), g_ + 1)
                for d in DIRS:
                    s2, g2 = def_dir.get((dt, d), (0.0, 0))
                    fpd = t[(t.season == season) & (t.week == week)
                            & (t.defteam == dt)
                            & (t.pass_location == d)].fp.sum()
                    def_dir[(dt, d)] = (s2 + fpd, g2 + 1)
                    lg_cum[d][0] += fpd
                    lg_cum[d][1] += 1
        print(f"built {season}", flush=True)
    panel = pd.DataFrame(rows)
    print(f"\npanel: {len(panel)} WR-weeks (>=2 prior appearances)")

    def ols(X, y):
        Xb = np.column_stack([np.ones(len(X)), X])
        return np.linalg.lstsq(Xb, y, rcond=None)[0]

    def ev(feats):
        sp, mae = [], []
        for hold in SEASONS:
            tr, te = panel[panel.season != hold], panel[panel.season == hold]
            b = ols(tr[feats].values, tr.y.values)
            p = np.column_stack([np.ones(len(te)), te[feats].values]) @ b
            te2 = te.assign(pred=p)
            s = [np.corrcoef(g.pred.rank(), g.y.rank())[0, 1]
                 for _, g in te2.groupby("week") if len(g) >= 12]
            sp.append(np.mean(s))
            mae.append(np.abs(p - te.y.values).mean())
        return np.mean(sp), np.mean(mae)

    print("\nLOYO weekly WR prediction (receiving FP):")
    for name, feats in (("form only", ["ewma"]),
                        ("+ team DvP", ["ewma", "dvp_team"]),
                        ("+ directional", ["ewma", "dvp_team", "dvp_dir"])):
        s, m = ev(feats)
        print(f"  {name:15s} rank corr {s:.3f}   MAE {m:.2f}")


if __name__ == "__main__":
    main()
