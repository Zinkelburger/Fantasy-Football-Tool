"""Does a hot/cold opportunity gap predict the NEXT season?

Backtest for the board's "ran hot / ran cold" tags (export_opportunity's
gapc_std at the shipped thresholds: 8+ games, |gapc| >= 1.5). For every
season pair 2017->2018 ... 2024->2025, players with 8+ matched games in
year t and 4+ games in t+1.

Results (run 2026-08-04, n = 2,147 player-season pairs):

  next-season PPG change:  hot (n=282) -1.83 | mid -0.28 | cold (n=160) -0.01

  partial r of gapc with next-year PPG, controlling this-year PPG
  (negative = hot fades / cold rebounds):
      WR -0.189 (p ~ 0)      TE -0.158 (p = .0007)   <- real signal
      RB -0.028 (p = .51)    QB -0.033 (p = .61)     <- nothing
      pooled -0.152, negative in 8 of 8 season pairs

So the tags are a verdict at WR/TE and only context at RB/QB (sticky
goal-line roles mean an RB's extra finishing partly repeats — matches
finding 25's ~0 ridge weight on RB TD luck). Both UIs render them
accordingly: colored chips WR/TE, gray context chips RB/QB.

Run from league-sim root: venv/bin/python analysis/gap_regression_check.py
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from export_opportunity import build_season                 # noqa: E402
from player_model import league_pts, weekly_raw             # noqa: E402

FLAG = 1.5        # shipped STD-scoring threshold on gapc_std
MIN_G, MIN_G_NEXT = 8, 4


def ppg(year):
    w = weekly_raw(year).copy()
    w["pts"] = league_pts(w)
    g = w.groupby("player_id").agg(g=("week", "nunique"), pts=("pts", "sum"))
    return g.pts / g.g, g.g


def pairs():
    rows = []
    for t in range(2017, 2025):
        s = build_season(t).set_index("player_id")
        nxt, ng = ppg(t + 1)
        s = s[s.games >= MIN_G]
        s["ppg_next"] = nxt.reindex(s.index)
        s["g_next"] = ng.reindex(s.index)
        s = s.dropna(subset=["ppg_next"])
        s = s[s.g_next >= MIN_G_NEXT]
        s["year"] = t
        rows.append(s.reset_index())
    return pd.concat(rows)


def partial(dd):
    """Correlation of gapc with next-year PPG after regressing both on
    this-year PPG. Fisher-z normal approximation for the p-value."""
    x, y, c = dd.gapc_std.values, dd.ppg_next.values, dd.ppg_std.values
    rx = x - np.polyval(np.polyfit(c, x, 1), c)
    ry = y - np.polyval(np.polyfit(c, y, 1), c)
    r = float(np.corrcoef(rx, ry)[0, 1])
    n = len(dd)
    z = 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(n - 3)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return dict(n=n, partial_r=round(r, 3), p=round(p, 5))


def main():
    d = pairs()
    d["chg"] = d.ppg_next - d.ppg_std
    d["flag"] = np.where(d.gapc_std >= FLAG, "hot",
                         np.where(d.gapc_std <= -FLAG, "cold", "mid"))
    print(f"n = {len(d)} player-season pairs 2017->2025\n")
    print("next-season PPG change by tag (pooled):")
    print(d.groupby("flag").agg(n=("chg", "size"), mean_chg=("chg", "mean"),
                                med_chg=("chg", "median")).round(2), "\n")
    print("by position, mean next-season PPG change:")
    print(d.pivot_table(index="pos", columns="flag", values="chg",
                        aggfunc="mean").round(2)[["hot", "mid", "cold"]],
          "\n")
    print("partial r of gapc with next-year PPG, controlling this-year PPG")
    for pos, g in d.groupby("pos"):
        print(f"  {pos}: {partial(g)}")
    print(f"  pooled: {partial(d)}")
    yr = {t: partial(g)["partial_r"] for t, g in d.groupby("year")}
    neg = sum(v < 0 for v in yr.values())
    print(f"  per-year: { {k: round(v, 2) for k, v in yr.items()} } "
          f"— negative in {neg} of {len(yr)} years")


if __name__ == "__main__":
    main()
