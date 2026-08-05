"""Export usage-based opportunity numbers for the user-facing surfaces.

The engine has treated usage-based expected points as its top weekly
signal since finding 26 (and finding 17 before it: targets repeat,
efficiency doesn't), but no export carried the numbers — the site and
draft tool never saw them. This script closes that gap with two CSVs
under data/market/:

  opportunity_<year>.csv        one row per player-season: expected PPG
                                from usage (nflverse ff_opportunity
                                rescored to league rules, per scoring
                                format), actual PPG over the same games,
                                the gap, TD luck, targets/carries per
                                game. Consumed by site/build_site.py
                                (board columns) and webapp/build_data.py
                                (draft-tool badges).
  opportunity_weekly_<year>.csv one row per player-week (STD scoring):
                                week EP, actual points, and trailing
                                EWMAs of both (alpha .35, the weekly
                                model's form inputs). Nothing consumes
                                this yet — it is the feed for the
                                September waiver spike list and the
                                week-in-review (EP jump = the buy
                                signal, finding 17 / backlog B4).

Actual and expected are aggregated over the SAME player-weeks (inner
join on player_id+week, regular season only), so gap = ppg - ep_ppg is
exact. Note ff_opportunity also carries playoff weeks 19-22 and ~10% of
played weeks lack an EP row; both are excluded here.

Run from league-sim root:  venv/bin/python analysis/export_opportunity.py
In-season 2026: rerun with --year 2026 after each week's data fetch.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
sys.path.insert(0, str(ROOT / "analysis"))
from player_model import POSITIONS, league_pts, weekly_raw   # noqa: E402

ALPHA = 0.35          # same EWMA as weekly_model / ep_projections
FORMATS = {"std": 0.0, "half": 0.5, "ppr": 1.0}


def weekly_ep(year):
    """Per player-week expected points under league scoring, one column
    per format, regular season only. Same rescoring as
    player_model.expected_stats (no 2pt terms — they round to zero at
    the weekly level and the season model omits them too)."""
    o = pd.read_parquet(DATA / "ff_opportunity_2017_2025.parquet")
    o = o[(o.season.astype(int) == year) & o.position.isin(POSITIONS)]
    last_reg = 18 if year >= 2021 else 17
    o = o[o.week <= last_reg].fillna({c: 0.0 for c in (
        "pass_yards_gained_exp", "pass_touchdown_exp",
        "pass_interception_exp", "rush_yards_gained_exp",
        "rush_touchdown_exp", "rec_yards_gained_exp",
        "rec_touchdown_exp", "receptions_exp")})
    base = (o.pass_yards_gained_exp / 25 + o.pass_touchdown_exp * 4
            - 2 * o.pass_interception_exp
            + o.rush_yards_gained_exp / 10 + o.rush_touchdown_exp * 6
            + o.rec_yards_gained_exp / 10 + o.rec_touchdown_exp * 6)
    out = o[["player_id", "week"]].copy()
    out["week"] = out.week.astype(int)
    for fmt, ppr in FORMATS.items():
        out[f"ep_{fmt}"] = base + ppr * o.receptions_exp
    out["td_exp"] = (o.pass_touchdown_exp + o.rush_touchdown_exp
                     + o.rec_touchdown_exp)
    return out


def matched_weeks(year):
    """Inner join of actual weekly stats and weekly EP."""
    w = weekly_raw(year).copy()
    for fmt, ppr in FORMATS.items():
        w[f"pts_{fmt}"] = league_pts(w, ppr)
    w["tds"] = w.passing_tds + w.rushing_tds + w.receiving_tds
    keep = ["player_id", "player_display_name", "position", "team",
            "week", "tds"] + [f"pts_{f}" for f in FORMATS]
    return w[keep].merge(weekly_ep(year), on=["player_id", "week"])


def usage_pg(year):
    a = pd.read_parquet(DATA / "adv_weekly_2017_2025.parquet")
    a = a[(a.season.astype(int) == year) & (a.season_type == "REG")]
    g = a.groupby("player_id").agg(
        tgt=("targets", "sum"), car=("carries", "sum"),
        tshare=("target_share", "mean"), gwk=("week", "nunique"))
    return dict(tgt_pg=g.tgt / g.gwk, carry_pg=g.car / g.gwk,
                tgt_share=g.tshare)


def build_season(year):
    m = matched_weeks(year)
    g = m.groupby("player_id").agg(
        name=("player_display_name", "first"), pos=("position", "first"),
        team=("team", "last"), games=("week", "nunique"),
        tds=("tds", "sum"), td_exp=("td_exp", "sum"),
        **{f"pts_{f}": (f"pts_{f}", "sum") for f in FORMATS},
        **{f"ep_{f}": (f"ep_{f}", "sum") for f in FORMATS})
    g = g[g.games >= 2]
    for f in FORMATS:
        g[f"ppg_{f}"] = (g[f"pts_{f}"] / g.games).round(2)
        g[f"ep_{f}"] = (g[f"ep_{f}"] / g.games).round(2)
        g[f"gap_{f}"] = (g[f"ppg_{f}"] - g[f"ep_{f}"]).round(2)
    g["td_luck_pg"] = ((g.tds - g.td_exp) / g.games).round(3)
    # Centered gap: raw gap minus the position's median (players with 8+
    # games). Actual scoring has per-category floors and fumble/2pt terms
    # that EP lacks, which shifts whole positions (QBs run ~-1.3 raw), so
    # "ran hot/cold" calls must be made against the position baseline —
    # threshold on gapc_*, display gap only alongside it.
    for f in FORMATS:
        med = g[g.games >= 8].groupby("pos")[f"gap_{f}"].median()
        g[f"gapc_{f}"] = (g[f"gap_{f}"] - g.pos.map(med)).round(2)
    for col, s in usage_pg(year).items():
        g[col] = s.reindex(g.index).fillna(0.0).round(2)
    cols = (["name", "pos", "team", "games"]
            + [f"{c}_{f}" for f in FORMATS for c in ("ep", "ppg", "gap", "gapc")]
            + ["td_luck_pg", "tgt_pg", "tgt_share", "carry_pg"])
    return g.reset_index()[["player_id"] + cols]


def build_weekly(year):
    """STD-scoring weekly series with trailing EWMAs (state AFTER each
    row's week; the weekly model uses the entering-week value). Missing
    EP falls back to actual, mirroring lineup.py's blend fallback."""
    m = matched_weeks(year).sort_values(["player_id", "week"])
    rows = []
    for pid, d in m.groupby("player_id"):
        e_pts = e_ep = None
        for r in d.itertuples():
            ep = r.ep_std if pd.notna(r.ep_std) else r.pts_std
            e_pts = r.pts_std if e_pts is None else \
                ALPHA * r.pts_std + (1 - ALPHA) * e_pts
            e_ep = ep if e_ep is None else ALPHA * ep + (1 - ALPHA) * e_ep
            rows.append(dict(
                player_id=pid, name=r.player_display_name, pos=r.position,
                team=r.team, week=r.week, ep=round(ep, 2),
                pts=round(r.pts_std, 2), ewma_ep=round(e_ep, 2),
                ewma_pts=round(e_pts, 2)))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2025)
    args = ap.parse_args()
    season = build_season(args.year)
    p = MKT / f"opportunity_{args.year}.csv"
    season.to_csv(p, index=False)
    print(f"{p} written: {len(season)} players")
    weekly = build_weekly(args.year)
    pw = MKT / f"opportunity_weekly_{args.year}.csv"
    weekly.to_csv(pw, index=False)
    print(f"{pw} written: {len(weekly)} player-weeks")


if __name__ == "__main__":
    main()
