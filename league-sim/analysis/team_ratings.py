"""Team ratings: do Elo / offense ratings help fantasy projections?

The questions (league-mate's, verbatim-ish): how stable is team Elo
year to year? Does Elo correlate with points scored? Can it tell us a
team has a high-powered offense, or predict a game ("facing a bad
defense -> score more")?

Rather than scraping nfelo.com (their game file is not public), we
compute our own ratings from game results + Vegas lines
(data/market/games.csv, Lee Sharpe/nflverse):

- Standard Elo, 538-style: K=20, home advantage 55, margin-of-victory
  multiplier ln(|margin|+1) * 2.2/(0.001*winner_elo_diff + 2.2),
  1/3 regression to the mean between seasons. Validated against the
  Vegas closing spread (an Elo we can't sanity-check is worthless).
- Per-season offense/defense SRS: least squares on team game points,
  score = mu + off_i - def_j + hfa/2, i.e. opponent-adjusted points
  scored/allowed. "High-powered offense" is off_srs, in points/game
  vs average.

Writes data/market/team_ratings.csv (season, team, elo_end, off_srs,
def_srs, pf_pg) for use as features elsewhere.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "data" / "market"
FIRST, LAST = 2002, 2025


def load_games():
    g = pd.read_csv(MKT / "games.csv")
    g = g[(g.game_type == "REG") & g.home_score.notna()
          & (g.season >= FIRST) & (g.season <= LAST)]
    return g


def run_elo(g):
    """Game-by-game Elo; returns per-game pregame elos + end-of-season
    table."""
    elo = {}
    rows, ends = [], []
    K, HFA = 20.0, 55.0
    cur_season = None
    for r in g.sort_values(["season", "week", "gameday"]).itertuples():
        if r.season != cur_season:
            if cur_season is not None:
                for t, e in elo.items():
                    ends.append((cur_season, t, e))
            for t in list(elo):
                elo[t] = elo[t] * 2 / 3 + 1505.0 / 3
            cur_season = r.season
        eh = elo.setdefault(r.home_team, 1505.0)
        ea = elo.setdefault(r.away_team, 1505.0)
        diff = eh + HFA - ea
        exp_home = 1.0 / (1.0 + 10 ** (-diff / 400))
        margin = r.home_score - r.away_score
        out_home = 0.5 if margin == 0 else float(margin > 0)
        winner_diff = diff if margin > 0 else -diff
        mov = np.log(abs(margin) + 1) * 2.2 / (0.001 * winner_diff + 2.2)
        delta = K * mov * (out_home - exp_home)
        rows.append((r.season, r.week, r.home_team, r.away_team, eh, ea,
                     diff / 25.0, r.spread_line, margin))
        elo[r.home_team] = eh + delta
        elo[r.away_team] = ea - delta
    for t, e in elo.items():
        ends.append((cur_season, t, e))
    per_game = pd.DataFrame(rows, columns=[
        "season", "week", "home", "away", "elo_h", "elo_a",
        "elo_spread", "vegas_spread", "margin"])
    end = pd.DataFrame(ends, columns=["season", "team", "elo_end"])
    return per_game, end


def srs_season(g, season):
    gs = g[g.season == season]
    teams = sorted(set(gs.home_team) | set(gs.away_team))
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    X, y = [], []
    for r in gs.itertuples():
        # home offense vs away defense
        row = np.zeros(2 * n + 2); row[ix[r.home_team]] = 1
        row[n + ix[r.away_team]] = -1; row[2 * n] = 1; row[2 * n + 1] = 0.5
        X.append(row); y.append(r.home_score)
        row = np.zeros(2 * n + 2); row[ix[r.away_team]] = 1
        row[n + ix[r.home_team]] = -1; row[2 * n] = 1; row[2 * n + 1] = -0.5
        X.append(row); y.append(r.away_score)
    X, y = np.array(X), np.array(y, float)
    lam = 1.0
    pen = lam * np.eye(2 * n + 2); pen[2 * n:, 2 * n:] = 0
    beta = np.linalg.solve(X.T @ X + pen, X.T @ y)
    off = beta[:n] - beta[:n].mean()
    dfn = beta[n:2 * n] - beta[n:2 * n].mean()
    pf = {}
    for r in gs.itertuples():
        pf.setdefault(r.home_team, []).append(r.home_score)
        pf.setdefault(r.away_team, []).append(r.away_score)
    return pd.DataFrame({
        "season": season, "team": teams,
        "off_srs": off, "def_srs": dfn,
        "pf_pg": [np.mean(pf[t]) for t in teams]})


def main():
    g = load_games()
    per_game, end = run_elo(g)
    srs = pd.concat([srs_season(g, s) for s in range(FIRST, LAST + 1)])
    out = end.merge(srs, on=["season", "team"])
    out.to_csv(MKT / "team_ratings.csv", index=False)

    # 1. is our Elo sane? vs the Vegas closing spread
    v = per_game.dropna(subset=["vegas_spread"])
    v = v[v.season >= 2007]
    print("=== Elo sanity vs Vegas closing spread (2007-2025) ===")
    print(f"corr(elo spread + hfa, vegas spread): "
          f"{np.corrcoef(v.elo_spread + 2.2, v.vegas_spread)[0,1]:.3f}")
    print(f"MAE elo spread vs margin: "
          f"{np.abs(v.elo_spread + 2.2 - v.margin).mean():.2f}  |  "
          f"vegas vs margin: {np.abs(v.vegas_spread - v.margin).mean():.2f}")

    # 2. stability year over year
    print("\n=== year-over-year stability (2002-2025 pairs) ===")
    m = out.merge(out.assign(season=out.season - 1),
                  on=["season", "team"], suffixes=("", "_next"))
    for col in ("elo_end", "off_srs", "def_srs", "pf_pg"):
        c = np.corrcoef(m[col], m[f"{col}_next"])[0, 1]
        print(f"corr({col}_t, {col}_t+1): {c:.3f}")

    # 3. does rating correlate with points scored?
    print("\n=== ratings vs points scored ===")
    print(f"same season:  corr(elo_end, PF/g) = "
          f"{np.corrcoef(out.elo_end, out.pf_pg)[0,1]:.3f}   "
          f"corr(off_srs, PF/g) = "
          f"{np.corrcoef(out.off_srs, out.pf_pg)[0,1]:.3f}")
    print(f"NEXT season:  corr(elo_t, PF/g_t+1) = "
          f"{np.corrcoef(m.elo_end, m.pf_pg_next)[0,1]:.3f}   "
          f"corr(off_t, PF/g_t+1) = "
          f"{np.corrcoef(m.off_srs, m.pf_pg_next)[0,1]:.3f}   "
          f"corr(PF/g_t, PF/g_t+1) = "
          f"{np.corrcoef(m.pf_pg, m.pf_pg_next)[0,1]:.3f}")

    # 4. within-season: do defenses actually differ vs fantasy scoring,
    #    and does implied total predict team scoring that week?
    v2 = per_game[per_game.season >= 2007].dropna(subset=["vegas_spread"])
    gg = g[g.season >= 2007].dropna(subset=["total_line", "spread_line"])
    imp_h = gg.total_line / 2 + gg.spread_line / 2
    imp_a = gg.total_line / 2 - gg.spread_line / 2
    imp = np.concatenate([imp_h, imp_a])
    act = np.concatenate([gg.home_score, gg.away_score])
    print(f"\nVegas implied team total vs actual team points "
          f"(2007-2025): corr = {np.corrcoef(imp, act)[0,1]:.3f}, "
          f"MAE = {np.abs(imp - act).mean():.1f}")

    # 5. 2025 snapshot (sniff test) for the 2026 environment feature
    top = out[out.season == 2025].sort_values("off_srs", ascending=False)
    print("\n2025 offense SRS, top/bottom 5 "
          "(the '2026 environment' feature):")
    for r in top.head(5).itertuples():
        print(f"  {r.team:4s} off {r.off_srs:+5.1f}  elo {r.elo_end:6.0f}")
    print("  ...")
    for r in top.tail(5).itertuples():
        print(f"  {r.team:4s} off {r.off_srs:+5.1f}  elo {r.elo_end:6.0f}")
    print(f"\nratings table -> data/market/team_ratings.csv "
          f"({len(out)} team-seasons)")


if __name__ == "__main__":
    main()
