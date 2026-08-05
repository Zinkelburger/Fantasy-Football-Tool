"""Next-season player projection model — "our own ADP list".

Starting point (credited, not ours): Kapania (2012), "Predicting
Fantasy Football Performance with Machine Learning Techniques",
Stanford CS229 final project — linear regression predicting next-season
RB fantasy points from previous-season yards/game and TDs/game, plus a
k-means-then-regress variant. His stated limitations (no age, no
playing-time context, no injuries, single prior season, RBs only) are
this script's starting to-do list.

What we add: 2017-2025 data, all four skill positions, league-exact
scoring, and features he couldn't get:
- usage vs results: targets/g, target share, carries/g, usage-based
  expected fantasy PPG (nflverse ff_opportunity) and the
  efficiency gap (actual - expected), which finding 17 says fades
- TD luck: actual TDs - expected TDs per game (finding 16: regresses)
- age, years of experience, draft capital (log overall pick)
- salary, per the league-mate's idea: upcoming-season cap hit as % of
  the cap, share of the player's own team position room (his cap hit /
  the room's), and league-wide positional cap rank (OverTheCap via
  nflverse contracts, exact per-season cap_number)
- team change flag for the upcoming season (rosters)
- the rookie his team just drafted at his position (draft capital)

Model: per-position ridge regression (standardized), lambda chosen by
nested leave-one-year-out on the training years. Target = next-season
fantasy PPG. Evaluated leave-one-year-out (target years 2019-2025)
against three benchmarks: naive (this year's PPG), the FFC ADP board,
and ADP+model residual stacking. Metric: Spearman rank correlation
with next-season PPG (ranking is what a draft list is for).

EVERY board is scored on the same players: the ones the ADP board
covers. This matters more than it sounds. Scoring the model on the
whole panel while ADP is scored only on its own subset -- what this
script did until 2026-08-05 -- flattered the model by ~+.14 pooled and
produced finding 25's original "beats ADP at QB/WR/TE" claim. Matched,
the model LOSES to ADP at every position and only the ADP+model stack
wins. See finding 25.

Rookies have no season-t features and are out of scope here -- they get
their own model (analysis/rookie_model.py, finding 31). What this model
does know about them is the pick a team spent at a position, which
prices the incumbent's new competition.

Scoring: the whole panel is rebuilt per format (standard, half PPR,
full PPR), so both the features (last season's PPG, expected PPG, the
efficiency gap) and the target are scored the way the reader's league
scores. A PPR board is not a standard board re-sorted -- the model is
refit on PPR points, so receiving volume earns its own weight.

Usage: player_model.py [--list]   (--list prints the 2026 boards only)
"""
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from simfl.pool import build_pool                       # noqa: E402
from simfl.config import DEFAULT_SCORING                # noqa: E402
from simfl.data import norm_name                        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
POSITIONS = ("QB", "RB", "WR", "TE")
SEASONS = list(range(2017, 2026))        # feature seasons
RNG = np.random.default_rng(11)

# (label, points per reception, output file). Standard keeps the
# original filename so existing consumers (analysis/compare_juicebox.py,
# site/build_site.py) don't move.
SCORINGS = (("standard", 0.0, "model_board_2026.csv"),
            ("half PPR", 0.5, "model_board_2026_half.csv"),
            ("full PPR", 1.0, "model_board_2026_ppr.csv"))

FEATURES = [
    "ppg", "games", "ppg_prev", "ep_ppg", "eff_gap", "td_luck_pg",
    "tgt_pg", "tgt_share", "carry_pg", "rush_ypg",
    # age AND seasons in the league: with both present, the TE (and
    # partly QB) decline loads on mileage, not birthdays; RB/WR decline
    # stays on age. Rank accuracy is a wash but the split is real.
    "age", "yrs", "ln_dpick", "cap_pct", "room_share", "cap_rank", "new_team",
    # the rookie his team just drafted on top of him (ln of the earliest
    # pick spent at his position; ln 300 = none). The one piece of
    # depth-chart news that is NOT already read off the ADP board.
    "tm_rook_pick",
    # team environment of the UPCOMING team, rated from season t
    # (analysis/team_ratings.py): does a good offense/team lift its
    # players the following year beyond their own stats?
    "team_off_prev", "team_elo_prev",
    # injury history: share of the last two seasons' games missed
    # (finding 18 says 'injury-prone' barely persists — testing it
    # inside the multivariate model)
    "miss_rate_2yr",
]

_RATINGS = None


def team_rating(season, team):
    global _RATINGS
    if _RATINGS is None:
        t = pd.read_csv(MKT / "team_ratings.csv")
        _RATINGS = {(r.season, r.team): (r.off_srs, r.elo_end)
                    for r in t.itertuples()}
    return _RATINGS.get((season, team), (0.0, 1505.0))


def league_pts(df, ppr=0.0):
    """League-exact weekly points (per-category floors, ESPN std).

    `ppr` is points per reception: 0 standard, 0.5 half, 1.0 full."""
    f = np.floor
    return (f(df.passing_yards / 25) + 4 * df.passing_tds
            - 2 * df.passing_interceptions
            + f(df.rushing_yards / 10) + 6 * df.rushing_tds
            + f(df.receiving_yards / 10) + 6 * df.receiving_tds
            + ppr * df.receptions
            - 2 * df.fumbles_lost_total + 6 * df.special_teams_tds
            + 2 * (df.passing_2pt_conversions + df.rushing_2pt_conversions
                   + df.receiving_2pt_conversions))


_WEEKLY = {}


def weekly_raw(year):
    """Raw weekly rows for a season, cached (each format re-reads them)."""
    if year not in _WEEKLY:
        w = pd.read_parquet(DATA / f"weekly_{year}.parquet")
        _WEEKLY[year] = w[w.position.isin(POSITIONS)]
    return _WEEKLY[year]


def season_stats(year, ppr=0.0):
    w = weekly_raw(year).copy()
    w["pts"] = league_pts(w, ppr)
    g = w.groupby("player_id").agg(
        pos=("position", "first"), name=("player_display_name", "first"),
        team=("team", "last"), games=("week", "nunique"),
        pts=("pts", "sum"),
        tds=("passing_tds", "sum"))
    skill_td = w.groupby("player_id")[["rushing_tds", "receiving_tds",
                                       "passing_tds"]].sum()
    g["all_tds"] = skill_td.sum(axis=1)
    g["rush_yds"] = w.groupby("player_id")["rushing_yards"].sum()
    g["ppg"] = g.pts / g.games
    return g


_ADV = _OPP = None


def usage_stats(year):
    global _ADV
    if _ADV is None:
        _ADV = pd.read_parquet(DATA / "adv_weekly_2017_2025.parquet")
        _ADV["season"] = _ADV.season.astype(int)
    a = _ADV[_ADV.season == year]
    g = a.groupby("player_id").agg(
        tgt=("targets", "sum"), car=("carries", "sum"),
        tshare=("target_share", "mean"), gwk=("week", "nunique"))
    return g


def expected_stats(year, ppr=0.0):
    global _OPP
    if _OPP is None:
        _OPP = pd.read_parquet(DATA / "ff_opportunity_2017_2025.parquet")
        _OPP["season"] = _OPP.season.astype(int)
    o = _OPP[_OPP.season == year]
    ep = (o.get("pass_yards_gained_exp", 0) / 25
          + o.get("pass_touchdown_exp", 0) * 4
          - 2 * o.get("pass_interception_exp", 0)
          + o.get("rush_yards_gained_exp", 0) / 10
          + o.get("rush_touchdown_exp", 0) * 6
          + o.get("rec_yards_gained_exp", 0) / 10
          + o.get("rec_touchdown_exp", 0) * 6
          + ppr * o.get("receptions_exp", 0))
    o = o.assign(ep=ep,
                 td_exp=(o.get("pass_touchdown_exp", 0)
                         + o.get("rush_touchdown_exp", 0)
                         + o.get("rec_touchdown_exp", 0)))
    return o.groupby("player_id").agg(ep=("ep", "sum"),
                                      td_exp=("td_exp", "sum"),
                                      wk=("week", "nunique"))


_CAP = None


def cap_table():
    """(gsis_id, year) -> (cap_number, cap_percent), latest signing wins."""
    global _CAP
    if _CAP is not None:
        return _CAP
    c = pd.read_parquet(MKT / "historical_contracts.parquet")
    rows = {}
    for r in c.itertuples():
        if r.gsis_id is None or r.cols is None:
            continue
        for e in r.cols:
            if not str(e.get("year", "")).isdigit():
                continue          # OTC tables carry a 'Total' row
            y = int(e["year"])
            key = (r.gsis_id, y)
            prev = rows.get(key)
            if prev is None or r.year_signed > prev[2]:
                rows[key] = (e["cap_number"] or 0.0,
                             e["cap_percent"] or 0.0, r.year_signed)
    _CAP = {k: (v[0], v[1]) for k, v in rows.items()}
    return _CAP


def roster(year):
    r = pd.read_parquet(MKT / f"roster_{year}.parquet")
    r = r[r.position.isin(POSITIONS)].dropna(subset=["gsis_id"])
    r = r.drop_duplicates("gsis_id", keep="last")
    return r.set_index("gsis_id")[["team", "position", "birth_date",
                                   "years_exp", "full_name"]]


def draft_table():
    d = pd.read_parquet(MKT / "draft_picks.parquet").dropna(subset=["gsis_id"])
    return d.drop_duplicates("gsis_id").set_index("gsis_id")["pick"]


# ---- the position room ------------------------------------------------
# Moved to analysis/position_room.py when this model was retired: the
# room readout still ships in the draft tool, the projection does not.
# See archive/season-projection-model/README.md.
from position_room import ROOM_COLS, room_standing        # noqa: E402



def build_rows(t, ppr=0.0):
    """Feature rows from season t, describing the player entering t+1."""
    cur = season_stats(t, ppr)
    prev = season_stats(t - 1, ppr) if t > 2017 else None
    use, exp = usage_stats(t), expected_stats(t, ppr)
    cap = cap_table()
    ros_next = roster(t + 1)
    ros_cur = roster(t)
    dpick = draft_table()
    dep = room_standing(t + 1, ppr)
    no_rook = dict(tm_rook_pick=float(np.log(300.0)),
                   **{c: "" for c in ROOM_COLS})

    # position-room cap totals for t+1
    caps_next = {g: cap.get((g, t + 1), (0.0, 0.0))[0] for g in ros_next.index}
    room = ros_next.assign(cap=[caps_next[g] for g in ros_next.index]) \
        .groupby(["team", "position"])["cap"].sum()

    rows = []
    for pid, r in cur.iterrows():
        if r.games < 4 or r.ppg < 2 or pid not in ros_next.index:
            continue
        rn = ros_next.loc[pid]
        u = use.loc[pid] if pid in use.index else None
        e = exp.loc[pid] if pid in exp.index else None
        cnum, cpct = cap.get((pid, t + 1), (0.0, 0.0))
        rm = room.get((rn.team, rn.position), 0.0)
        age = np.nan
        if pd.notna(rn.birth_date):
            age = (pd.Timestamp(f"{t+1}-09-01")
                   - pd.Timestamp(rn.birth_date)).days / 365.25
        rows.append(dict(
            pid=pid, name=r["name"], pos=r.pos, year=t,
            ppg=r.ppg, games=r.games,
            ppg_prev=(prev.loc[pid].ppg
                      if prev is not None and pid in prev.index else np.nan),
            ep_ppg=(e.ep / e.wk) if e is not None and e.wk else np.nan,
            eff_gap=(r.ppg - e.ep / e.wk) if e is not None and e.wk else np.nan,
            td_luck_pg=((r.all_tds - e.td_exp) / r.games)
            if e is not None else np.nan,
            tgt_pg=(u.tgt / u.gwk) if u is not None and u.gwk else 0.0,
            tgt_share=(float(u.tshare)
                       if u is not None and pd.notna(u.tshare) else 0.0),
            carry_pg=(u.car / u.gwk) if u is not None and u.gwk else 0.0,
            rush_ypg=r.rush_yds / r.games,
            age=age,
            yrs=float(rn.years_exp) if pd.notna(rn.years_exp) else np.nan,
            ln_dpick=np.log(dpick.get(pid, 300.0)),
            cap_pct=cpct * 100,
            room_share=cnum / rm if rm > 0 else 0.0,
            cap_rank=0.0,     # filled below (within pos-year)
            new_team=float(pid in ros_cur.index
                           and ros_cur.loc[pid].team != rn.team),
            team_off_prev=team_rating(t, rn.team)[0],
            team_elo_prev=team_rating(t, rn.team)[1],
            miss_rate_2yr=1.0 - (
                r.games + (prev.loc[pid].games
                           if prev is not None and pid in prev.index
                           else r.games)) / (2.0 * (17 if t >= 2021 else 16)),
            **{k: dep.get(pid, no_rook)[k]
               for k in ("tm_rook_pick", *ROOM_COLS)},
        ))
    df = pd.DataFrame(rows)
    for pos in POSITIONS:
        m = df.pos == pos
        df.loc[m, "cap_rank"] = df.loc[m, "cap_pct"].rank(pct=True)
    return df


def targets_for(t, ppr=0.0):
    nxt = season_stats(t + 1, ppr)
    return nxt["ppg"], nxt["games"]


def ridge_fit(X, y, lam):
    Xb = np.column_stack([np.ones(len(X)), X])
    p = Xb.shape[1]
    pen = lam * np.eye(p)
    pen[0, 0] = 0.0
    return np.linalg.solve(Xb.T @ Xb + pen, Xb.T @ y)


def ridge_pred(beta, X):
    return np.column_stack([np.ones(len(X)), X]) @ beta


def standardize(tr, te):
    mu, sd = np.nanmean(tr, axis=0), np.nanstd(tr, axis=0)
    sd[sd == 0] = 1.0
    f = lambda a: np.nan_to_num((a - mu) / sd)
    return f(tr), f(te)


def spearman(a, b):
    ra = pd.Series(a).rank().values
    rb = pd.Series(b).rank().values
    return np.corrcoef(ra, rb)[0, 1]


def build_board(label, ppr, dst, evaluate):
    panel = pd.concat([build_rows(t, ppr) for t in SEASONS[:-1]],
                      ignore_index=True)
    tg = {t: targets_for(t, ppr) for t in SEASONS[:-1] if t < 2025}
    panel["y"] = [tg[r.year][0].get(r.pid, np.nan) if r.year in tg else np.nan
                  for r in panel.itertuples()]
    data = panel.dropna(subset=["y"]).copy()

    if evaluate:
        # ADP benchmark: FFC board for season t+1, joined via the sim pool
        adp = {}
        for y in range(2018, 2026):
            for p in build_pool(y, DEFAULT_SCORING):
                if p.adp is not None:
                    adp[(p.pid, y)] = p.adp
        data["adp_next"] = [adp.get((r.pid, r.year + 1), np.nan)
                            for r in data.itertuples()]

        print(f"panel: {len(data)} player-seasons with targets, "
              f"{len(panel)-len(data)} feature-only; "
              f"{int(data.adp_next.notna().sum())} of them carry an ADP "
              f"— those are the ones every board below is scored on\n")
        print(f"{'pos':4s} {'year':>5s} {'n':>4s}   naive    ADP  model  "
              f"model+ADP")
        agg = {k: [] for k in ("naive", "adp", "model", "stack")}
        for pos in POSITIONS:
            d = data[data.pos == pos]
            yr_rows = []
            for hold in sorted(d.year.unique()):
                tr, te = d[d.year != hold], d[d.year == hold]
                if len(te) < 10:
                    continue
                Xtr_r, Xte_r = tr[FEATURES].values, te[FEATURES].values
                best = (None, -1)
                for lam in (1.0, 10.0, 30.0, 100.0):
                    scs = []
                    for inner in sorted(tr.year.unique()):
                        itr, ite = tr[tr.year != inner], tr[tr.year == inner]
                        if len(ite) < 10:
                            continue
                        a, b = standardize(itr[FEATURES].values,
                                           ite[FEATURES].values)
                        beta = ridge_fit(a, itr.y.values, lam)
                        scs.append(spearman(ridge_pred(beta, b), ite.y.values))
                    if scs and np.mean(scs) > best[1]:
                        best = (lam, np.mean(scs))
                a, b = standardize(Xtr_r, Xte_r)
                beta = ridge_fit(a, tr.y.values, best[0])
                pred = ridge_pred(beta, b)
                # Every board is scored on the SAME players — the ones
                # the ADP board actually covers. Scoring the model on the
                # full panel and ADP only on its own subset flatters the
                # model badly: the extra ~1,000 rows are undrafted deep
                # players (WR 2.9 PPG vs 7.4 for the drafted), and a
                # field that wide is far easier to rank-order.
                m = (~te.adp_next.isna()).values
                yy = te.y.values[m]
                row = dict(
                    naive=spearman(te.ppg.values[m], yy),
                    model=spearman(pred[m], yy),
                    adp=spearman(-te.adp_next.values[m], yy),
                    stack=spearman(
                        pd.Series(-te.adp_next.values[m]).rank().values
                        + 0.5 * pd.Series(pred[m]).rank().values, yy),
                )
                yr_rows.append((hold, int(m.sum()), row))
                for k in agg:
                    agg[k].append(row[k])
            for hold, n, row in yr_rows:
                print(f"{pos:4s} {hold+1:5d} {n:4d}  {row['naive']:6.3f} "
                      f"{row['adp']:6.3f} {row['model']:6.3f}  {row['stack']:6.3f}")
            mean = {k: np.mean([r[k] for _, _, r in yr_rows]) for k in agg}
            print(f"{pos:4s}  mean       {mean['naive']:6.3f} "
                  f"{mean['adp']:6.3f} {mean['model']:6.3f}  "
                  f"{mean['stack']:6.3f}\n")
        print("pooled means: " + "  ".join(
            f"{k}={np.mean(v):.3f}" for k, v in agg.items()))

        # The honest headline: paired against ADP, one pair per
        # position-year. A board only earns a claim if it beats the
        # market on the same players, and the spread across years is
        # wide enough that the mean alone oversells it.
        base = np.array(agg["adp"])
        print(f"\n{'':16s}{'mean diff':>10s}{'se':>8s}{'wins':>8s}")
        for k in ("naive", "model", "stack"):
            d = np.array(agg[k]) - base
            se = d.std(ddof=1) / np.sqrt(len(d))
            print(f"{k + ' - ADP':16s}{d.mean():+10.3f}{se:8.3f}"
                  f"{f'{int((d > 0).sum())}/{len(d)}':>8s}")

        # standardized coefficients on the full panel (interpretation)
        print("\nstandardized ridge coefficients (lam=30), full panel:")
        print(f"{'feature':12s}" + "".join(f"{p:>8s}" for p in POSITIONS))
        betas = {}
        for pos in POSITIONS:
            d = data[data.pos == pos]
            a, _ = standardize(d[FEATURES].values, d[FEATURES].values)
            betas[pos] = ridge_fit(a, d.y.values, 30.0)[1:]
        for i, f in enumerate(FEATURES):
            print(f"{f:12s}" + "".join(f"{betas[p][i]:8.2f}"
                                       for p in POSITIONS))

    # ---- the 2026 board --------------------------------------------
    feat26 = build_rows(2025, ppr)
    print(f"\n=== model board for 2026, {label} scoring (returning "
          f"players; rookies out of scope) ===")
    out = []
    for pos in POSITIONS:
        d = data[data.pos == pos]
        f26 = feat26[feat26.pos == pos]
        a, b = standardize(d[FEATURES].values, f26[FEATURES].values)
        beta = ridge_fit(a, d.y.values, 30.0)
        pred = ridge_pred(beta, b)
        f26 = f26.assign(pred_ppg=pred).sort_values("pred_ppg",
                                                    ascending=False)
        out.append(f26)
        top = 12 if pos in ("QB", "TE") else 25
        print(f"\n{pos}: (pred PPG | 2025 PPG)")
        for i, r in enumerate(f26.head(top).itertuples(), 1):
            print(f"  {i:2d}. {r.name:24s} {r.pred_ppg:5.1f} | {r.ppg:5.1f}")
    full = pd.concat(out).sort_values("pred_ppg", ascending=False)
    full[["name", "pos", "pred_ppg", "ppg", "age", "cap_pct",
          "room_share", *ROOM_COLS]].to_csv(dst, index=False)
    print(f"\nfull board -> {dst.relative_to(ROOT)}")


def main():
    list_only = "--list" in sys.argv
    for label, ppr, fname in SCORINGS:
        # The leave-one-year-out evaluation is reported for standard
        # scoring only -- that is the league this study is written for,
        # and it is the number finding 25 quotes.
        build_board(label, ppr, MKT / fname,
                    evaluate=not list_only and ppr == 0.0)


if __name__ == "__main__":
    main()
