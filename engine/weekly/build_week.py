"""Build everything public for the current NFL week.

    python build_week.py            # current week (Sleeper state)
    python build_week.py --week 3   # a specific week of the current season
    python build_week.py --offline  # recompute from the cache, no fetches

Steps, all deterministic given the fetched inputs:
  1. lines      -> data/weekly/lines_<season>.csv        (Vegas, live + lookahead)
  2. opportunity-> data/weekly/opportunity_<season>*.csv (expected points)
  3. injuries   -> data/weekly/injuries_<season>.csv, depth_<season>.csv
  4. ecr        -> data/weekly/ecr_<season>_wkNN.csv     (only with an API key)
  5. latest.json + week_<season>_wkNN.json               (what the site reads)

The GitHub workflow runs this Tuesday and Saturday mornings and commits
data/weekly/; Cloudflare Pages rebuilds foss.football from the commit.
"""
from __future__ import annotations

import argparse
import json
import sys

import polars as pl

from common import DATA, FORMATS, MODEL, SKILL, TEAMS, nfl_state, now_iso, week_key
import fantasypros
import injuries as inj_mod
import lines as lines_mod
import opportunity

TOP_PER_POS = {"QB": 40, "RB": 70, "WR": 90, "TE": 40}


def skill_rows(tbl: pl.DataFrame, weekly: pl.DataFrame, lines_wk: pl.DataFrame,
               inj_wk: pl.DataFrame) -> list[dict]:
    line_by_team = {r["team"]: r for r in lines_wk.iter_rows(named=True)}
    inj_by_id = {r["gsis_id"]: r for r in inj_wk.iter_rows(named=True)} if inj_wk.height else {}
    out = []
    per_pos = {p: 0 for p in SKILL}
    for r in tbl.iter_rows(named=True):
        pos = r["pos"]
        if pos not in per_pos or per_pos[pos] >= TOP_PER_POS[pos]:
            continue
        per_pos[pos] += 1
        line = line_by_team.get(r["team"])
        ij = inj_by_id.get(r["player_id"])
        out.append({
            "id": r["player_id"], "name": r["name"], "pos": pos, "team": r["team"],
            "games": r["games"] or 0,
            "ewma": {f: round(r[f"ewma_ep_{f}"], 1) for f in FORMATS},
            "ep": {f: (round(r[f"ep_{f}"], 1) if r.get(f"ep_{f}") is not None else None) for f in FORMATS},
            "pts": {f: (round(r[f"pts_{f}"], 1) if r.get(f"pts_{f}") is not None else None) for f in FORMATS},
            "last": {"week": r.get("last_week"),
                     "ep": {f: (round(r[f"last_ep_{f}"], 1) if r.get(f"last_ep_{f}") is not None else None) for f in FORMATS},
                     "pts": {f: (round(r[f"last_pts_{f}"], 1) if r.get(f"last_pts_{f}") is not None else None) for f in FORMATS}},
            "usage": {k: (round(r[f"{k}_pg"], 1) if r.get(f"{k}_pg") is not None else None)
                      for k in ("rush_att", "tgt", "rush_rz", "tgt_rz", "tgt_ez", "air_yds", "pass_att")},
            "opp": line["opp"] if line else None,
            "home": line["home"] if line else None,
            "imp_own": line["imp_own"] if line else None,
            "imp_opp": line["imp_opp"] if line else None,
            "injury": ({"status": ij.get("report_status"), "injury": ij.get("report_primary_injury"),
                        "practice": ij.get("practice_status")} if ij else None),
        })
    return out


def build(season: int, week: int, refresh: bool = True) -> dict:
    print(f"» lines {season} wk{week}")
    ln = lines_mod.build(season, week, refresh)
    print(f"» opportunity {season}")
    weekly, tbl = opportunity.write(season, refresh)
    print(f"» injuries/depth {season}")
    inj_all, depth = inj_mod.build(season, refresh)
    inj_wk = inj_all.filter(pl.col("week") == week)
    print("» fantasypros ECR")
    ecr = None
    try:
        ecr = fantasypros.fetch(season, week) if refresh else fantasypros.load(season, week)
    except Exception as e:  # noqa: BLE001 - optional feed
        print(f"  ECR skipped: {e}", file=sys.stderr)
    lines_wk = ln.filter(pl.col("week") == week)
    ranks = lines_mod.rankings(ln, week)
    coef = json.loads((MODEL / "ep_coefficients.json").read_text())
    played_games = int(lines_wk.filter(pl.col("played")).height // 2)
    out = {
        "season": season, "week": week, "generated": now_iso(),
        "label": f"{season} Week {week}",
        "lines": lines_wk.to_dicts(),
        "dst": ranks["dst"], "k": ranks["k"],
        "skill": skill_rows(tbl, weekly, lines_wk, inj_wk),
        "injuries": [{"team": r["team"], "name": r["full_name"], "pos": r["position"],
                      "status": r["report_status"], "injury": r["report_primary_injury"],
                      "practice": r["practice_status"]}
                     for r in inj_wk.iter_rows(named=True)
                     if r["position"] in ("QB", "RB", "WR", "TE", "K")],
        "ecr_available": bool(ecr),
        "games_played_this_week": played_games,
        "model": {"fitted": coef["fitted"], "fit_seasons": coef["fit_seasons"],
                  "holdout": coef["holdout"], "eval": coef["eval"]},
        "teams": TEAMS,
    }
    (DATA / "latest.json").write_text(json.dumps(out, separators=(",", ":")))
    (DATA / f"week_{week_key(season, week)}.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote data/weekly/latest.json: {len(out['skill'])} skill rows, "
          f"{len(out['dst'])} teams with lines, {len(out['injuries'])} injury rows")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int)
    ap.add_argument("--season", type=int)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    st = nfl_state()
    season = a.season or st["season"]
    week = a.week or st["week"]
    build(season, week, refresh=not a.offline)


if __name__ == "__main__":
    main()
