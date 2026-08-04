"""Backtest the nfelo ecosystem (github.com/greerreNFL) for usable
fantasy relationships.

Data (all public, cached in data/market/):
- nfelo_games.csv: their model's per-game ratings + projected lines
  (open/close) — lets us benchmark nfelo vs our simple Elo vs Vegas.
- qb_elos.csv (nfeloqb): the continued FiveThirtyEight QB-Elo — a
  rolling per-QB value in Elo points, 1920-2026.
- win_totals_sos.csv (nfl-win-total-data): preseason Vegas win-total
  lines + implied ratings, 2003-2022 — the "market's preseason team
  projection" we flagged as missing in finding 26.

Questions:
A. Is nfelo actually better than our simple Elo at predicting games?
   (If not, no reason to prefer their ratings as features.)
B. Do nfelo ratings predict next-season team scoring any better than
   our ratings / naive PF (finding 26 said ~0.4 ceiling)?
C. QB-Elo: does a QB's rolling value track fantasy PPG, and does his
   value at the START of a season (prior info only) predict that
   season's fantasy PPG beyond last year's PPG?
D. Do preseason win-total lines (the market's offseason-aware team
   projection) beat last year's PF at predicting this year's PF?
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


def corr(a, b):
    m = pd.notna(a) & pd.notna(b)
    return np.corrcoef(a[m], b[m])[0, 1]


# ---------------------------------------------------------------- A + B
def games_tests():
    n = pd.read_csv(MKT / "nfelo_games.csv")
    parts = n.game_id.str.split("_", expand=True)
    n["season"] = parts[0].astype(int)
    n["week"] = parts[1].astype(int)
    n["away"], n["home"] = parts[2], parts[3]

    g = pd.read_csv(MKT / "games.csv")
    g = g[g.game_type == "REG"][["game_id", "result", "spread_line"]]
    n = n.merge(g, on="game_id", how="inner").dropna(
        subset=["result", "spread_line", "nfelo_home_line_close"])
    # nfelo lines are quoted as home lines (negative = home favored);
    # nflverse result = home margin, spread_line = home margin pred.
    mae_nfelo = np.abs(-n.nfelo_home_line_close - n.result).mean()
    mae_vegas = np.abs(n.spread_line - n.result).mean()
    print("A. game prediction, overlapping games "
          f"({n.season.min()}-{n.season.max()}, n={len(n)}):")
    print(f"   MAE vs actual margin: nfelo {mae_nfelo:.2f}   "
          f"vegas close {mae_vegas:.2f}   (our simple elo was 10.75 "
          "on 2007-2025; see finding 26)")
    print(f"   corr(nfelo line, vegas line): "
          f"{corr(-n.nfelo_home_line_close, n.spread_line):.3f}")

    # end-of-season team nfelo -> stability + next-season team scoring
    last = []
    for (s, t), grp in pd.concat([
            n[["season", "week", "home", "starting_nfelo_home"]]
            .rename(columns={"home": "team",
                             "starting_nfelo_home": "nfelo"}),
            n[["season", "week", "away", "starting_nfelo_away"]]
            .rename(columns={"away": "team",
                             "starting_nfelo_away": "nfelo"}),
    ]).groupby(["season", "team"]):
        last.append((s, t, grp.sort_values("week").nfelo.iloc[-1]))
    nf = pd.DataFrame(last, columns=["season", "team", "nfelo"])
    tr = pd.read_csv(MKT / "team_ratings.csv")
    nf = nf.merge(tr, on=["season", "team"])
    m = nf.merge(nf.assign(season=nf.season - 1), on=["season", "team"],
                 suffixes=("", "_next"))
    print(f"\nB. team nfelo (end of season), {nf.season.min()}-"
          f"{nf.season.max()}:")
    print(f"   stability y-o-y: {corr(m.nfelo, m.nfelo_next):.3f} "
          "(our elo: 0.594)")
    print(f"   vs same-season PF/g: {corr(nf.nfelo, nf.pf_pg):.3f}   "
          f"vs NEXT-season PF/g: {corr(m.nfelo, m.pf_pg_next):.3f} "
          "(ours: 0.377; naive PF 0.419)")


# ------------------------------------------------------------------- C
def qb_tests():
    q = pd.read_csv(MKT / "qb_elos.csv")
    q = q[(q.season >= 2018) & (q.season <= 2025) & (q.playoff != 1)]
    rows = []
    for i in (1, 2):
        rows.append(q[["season", "date", f"qb{i}", f"qb{i}_value_pre"]]
                    .rename(columns={f"qb{i}": "qb",
                                     f"qb{i}_value_pre": "value"}))
    qs = pd.concat(rows).dropna(subset=["qb", "value"])
    season_val = qs.groupby(["season", "qb"]).agg(
        val_mean=("value", "mean"),
        val_first=("value", lambda s: s.iloc[0]),
        starts=("value", "size")).reset_index()
    season_val = season_val[season_val.starts >= 6]

    def norm(s):
        return s.lower().replace(".", "").replace("'", "").strip()

    ppg = []
    for y in range(2018, 2026):
        w = pd.read_parquet(DATA / f"weekly_{y}.parquet")
        w = w[w.position == "QB"].copy()
        w["pts"] = league_pts(w)
        gg = w.groupby("player_display_name").agg(
            pts=("pts", "sum"), g=("week", "nunique")).reset_index()
        gg = gg[gg.g >= 6]
        gg["season"], gg["ppg"] = y, gg.pts / gg.g
        gg["key"] = gg.player_display_name.map(norm)
        ppg.append(gg[["season", "key", "ppg"]])
    ppg = pd.concat(ppg)
    season_val["key"] = season_val.qb.map(norm)
    j = season_val.merge(ppg, on=["season", "key"])
    jl = j.merge(j.assign(season=j.season - 1), on=["key", "season"],
                 suffixes=("", "_next"))
    print(f"\nC. QB-Elo vs fantasy ({len(j)} QB-seasons matched):")
    print(f"   same season:  corr(mean QB value, fantasy PPG) = "
          f"{corr(j.val_mean, j.ppg):.3f}")
    print(f"   predictive:   corr(value at season START, that season's "
          f"PPG) = {corr(j.val_first, j.ppg):.3f}")
    print(f"   baseline:     corr(last season PPG, next PPG) = "
          f"{corr(jl.ppg, jl.ppg_next):.3f}")
    print(f"                 corr(value_first_next, next PPG) = "
          f"{corr(jl.val_first_next, jl.ppg_next):.3f}")
    # does start-of-season QB value add beyond last year's PPG?
    m = jl.dropna(subset=["ppg", "ppg_next", "val_first_next"])
    X = np.column_stack([np.ones(len(m)), m.ppg])
    r1 = m.ppg_next - X @ np.linalg.lstsq(X, m.ppg_next, rcond=None)[0]
    X2 = np.column_stack([np.ones(len(m)), m.val_first_next])
    r2 = m.val_first_next - X2[:, :1] @ np.linalg.lstsq(
        X2[:, :1], m.val_first_next, rcond=None)[0]
    print(f"   partial (QB value | last-year PPG): "
          f"{corr(pd.Series(r1.values), pd.Series(m.val_first_next.values)):.3f}"
          f"   (n={len(m)})")


# ------------------------------------------------------------------- D
def win_total_tests():
    wt = pd.read_csv(MKT / "win_totals_sos.csv")
    tr = pd.read_csv(MKT / "team_ratings.csv")
    # win-total file uses nflverse-style abbrs in 'team'? inspect overlap
    j = wt.merge(tr, on=["season", "team"], how="inner")
    if len(j) < 100:
        print(f"\nD. win totals: JOIN FAILED ({len(j)} rows) — team "
              f"codes: {sorted(wt.team.unique())[:8]}")
        return
    prev = tr.rename(columns={"pf_pg": "pf_prev"})[
        ["season", "team", "pf_prev"]].assign(season=lambda d: d.season + 1)
    j = j.merge(prev, on=["season", "team"])
    print(f"\nD. preseason win totals ({j.season.min()}-{j.season.max()},"
          f" n={len(j)} team-seasons):")
    print(f"   corr(win-total line, that season's PF/g)   = "
          f"{corr(j.line_adj if 'line_adj' in j else j.line, j.pf_pg):.3f}")
    print(f"   corr(last season's PF/g, this PF/g)        = "
          f"{corr(j.pf_prev, j.pf_pg):.3f}")
    print(f"   corr(wt implied rating, this PF/g)         = "
          f"{corr(j.wt_rating, j.pf_pg):.3f}")
    print(f"   corr(win-total line, actual wins)          = "
          f"{corr(j.line_adj if 'line_adj' in j else j.line, j.wins):.3f}")


if __name__ == "__main__":
    games_tests()
    qb_tests()
    win_total_tests()
