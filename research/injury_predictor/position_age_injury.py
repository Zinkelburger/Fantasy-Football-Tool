"""Injury risk by position, age, and week of season.

Findings 18 and 21 measured repeat-injury carryover and what a Friday tag is
worth. Neither measured the thing people actually argue about: the *baseline*
rate. Does a drafted RB miss more games than a drafted WR, does the risk climb
as the season wears on, and does it climb with age?

The trap: players placed on IR fall off the NFL injury report entirely (Nick
Chubb 2023 has zero injury-report rows after his week-2 knee). Measuring games
missed from the injury report alone therefore erases exactly the season-ending
injuries we care about. So "did he play" comes from snap counts, and "was it
injury" comes from weekly roster status (RES/PUP/NFI) plus the report.

Population is ex-ante: the ~179 draftable players by ADP each season, so there
is no survivorship from conditioning on how the season turned out.

Outputs a JSON blob of every table to results_position_age.json.
"""

import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import nflreadpy as nfl

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "engine" / "league-sim" / "data"
OUT = Path(__file__).resolve().parent

SEASONS = list(range(2018, 2026))
POS = ["QB", "RB", "WR", "TE"]

# Roster status codes that mean "unavailable because of health".
# RES = injured reserve, PUP = physically unable to perform, NON = non-football injury.
IR_CODES = {"RES", "PUP", "NON", "R01", "R02", "R05", "R23", "R47", "R48", "NFI"}


def load_rosters():
    r = nfl.load_rosters_weekly(SEASONS).to_pandas()
    r = r[r.game_type == "REG"]
    r = r[r.position.isin(POS)]
    keep = ["season", "week", "team", "position", "full_name", "gsis_id",
            "pfr_id", "birth_date", "status", "years_exp"]
    return r[keep]


def load_snaps():
    s = nfl.load_snap_counts(SEASONS).to_pandas()
    s = s[s.game_type == "REG"]
    return s[["season", "week", "pfr_player_id", "offense_snaps"]].rename(
        columns={"pfr_player_id": "pfr_id"})


def load_injury_reports():
    inj = pd.read_parquet(SIM / "injuries_2017_2025.parquet")
    inj = inj[(inj.game_type == "REG") & (inj.season.isin(SEASONS))]
    inj["season"] = inj.season.astype(int)
    inj["week"] = inj.week.astype(int)
    # One row per player-week; a player can be listed twice in a week.
    inj = inj.sort_values("date_modified").groupby(
        ["season", "week", "gsis_id"], as_index=False).last()
    return inj[["season", "week", "gsis_id", "report_status",
                "practice_status", "report_primary_injury"]]


def load_schedule_weeks():
    """team -> set of regular-season weeks with a game (so byes drop out)."""
    sch = nfl.load_schedules(SEASONS).to_pandas()
    sch = sch[sch.game_type == "REG"]
    rows = []
    for _, g in sch.iterrows():
        rows.append((int(g.season), int(g.week), g.home_team))
        rows.append((int(g.season), int(g.week), g.away_team))
    return pd.DataFrame(rows, columns=["season", "week", "team"]).drop_duplicates()


def load_adp_pool():
    """Ex-ante draftable pool: everyone with an ADP, by season."""
    rows = []
    for yr in SEASONS:
        f = SIM / f"adp_{yr}.json"
        if not f.exists():
            continue
        for p in json.load(open(f)):
            if p.get("pos") in POS:
                rows.append({"season": yr, "name": p["name"],
                             "pos": p["pos"], "adp": p["adp"]})
    return pd.DataFrame(rows)


def norm(s):
    return (s.str.lower()
             .str.replace(r"[.'\-]", "", regex=True)
             .str.replace(r"\s+(jr|sr|ii|iii|iv|v)$", "", regex=True)
             .str.strip())


def fantasy_points_std():
    """Standard (non-PPR) weekly fantasy points, matching the family league."""
    frames = []
    for yr in SEASONS:
        f = SIM / f"weekly_{yr}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f))
    w = pd.concat(frames, ignore_index=True)
    w = w[w.position.isin(POS)]
    pts = (w.passing_yards.fillna(0) / 25 + w.passing_tds.fillna(0) * 4
           - w.passing_interceptions.fillna(0) * 2
           + w.rushing_yards.fillna(0) / 10 + w.rushing_tds.fillna(0) * 6
           + w.receiving_yards.fillna(0) / 10 + w.receiving_tds.fillna(0) * 6
           - w.fumbles_lost_total.fillna(0) * 2
           + (w.passing_2pt_conversions.fillna(0)
              + w.rushing_2pt_conversions.fillna(0)
              + w.receiving_2pt_conversions.fillna(0)) * 2)
    out = w[["player_id", "season", "week", "position"]].copy()
    out["pts"] = pts
    out["season"] = out.season.astype(int)
    out["week"] = out.week.astype(int)
    return out.rename(columns={"player_id": "gsis_id"})


def build_panel():
    rosters = load_rosters()
    snaps = load_snaps()
    reports = load_injury_reports()
    sched = load_schedule_weeks()
    adp = load_adp_pool()

    # --- resolve ADP names to gsis_id via that season's rosters -------------
    rst = rosters.copy()
    rst["nkey"] = norm(rst.full_name)
    ids = (rst.sort_values("week")
              .groupby(["season", "nkey", "position"], as_index=False)
              .agg(gsis_id=("gsis_id", "first"),
                   pfr_id=("pfr_id", "first"),
                   birth_date=("birth_date", "first")))
    adp["nkey"] = norm(adp.name)
    pool = adp.merge(ids, left_on=["season", "nkey", "pos"],
                     right_on=["season", "nkey", "position"], how="left")
    matched = pool.dropna(subset=["gsis_id"])
    print(f"ADP pool: {len(pool)} player-seasons, matched {len(matched)} "
          f"({len(matched)/len(pool):.0%})")

    # --- expand to every week the player's team had a game ------------------
    # Team can change mid-season (trades), so take weeks from the roster rows.
    rteam = rosters[["season", "week", "team", "gsis_id", "status"]]
    panel = matched[["season", "gsis_id", "pos", "adp", "birth_date"]].merge(
        rteam, on=["season", "gsis_id"], how="left")
    panel = panel.merge(sched, on=["season", "week", "team"], how="inner")

    # --- did he play? -------------------------------------------------------
    panel = panel.merge(snaps, on=["season", "week", "pfr_id"], how="left") \
        if "pfr_id" in panel.columns else panel
    return panel, matched, rosters, snaps, reports, sched


def main():
    rosters = load_rosters()
    snaps = load_snaps()
    reports = load_injury_reports()
    sched = load_schedule_weeks()
    adp = load_adp_pool()

    rst = rosters.copy()
    rst["nkey"] = norm(rst.full_name)
    ids = (rst.sort_values("week")
              .groupby(["season", "nkey", "position"], as_index=False)
              .agg(gsis_id=("gsis_id", "first"),
                   pfr_id=("pfr_id", "first"),
                   birth_date=("birth_date", "first")))
    adp["nkey"] = norm(adp.name)
    pool = adp.merge(ids, left_on=["season", "nkey", "pos"],
                     right_on=["season", "nkey", "position"], how="left")
    matched = pool.dropna(subset=["gsis_id"]).copy()
    print(f"ADP pool {len(pool)} player-seasons; matched {len(matched)} "
          f"({len(matched)/len(pool):.0%})")

    # age at Sept 1 of that season
    bd = pd.to_datetime(matched.birth_date, errors="coerce")
    sept = pd.to_datetime(matched.season.astype(str) + "-09-01")
    matched["age"] = (sept - bd).dt.days / 365.25

    # every (player, week) his team actually had a game
    rteam = rosters[["season", "week", "team", "gsis_id", "status", "pfr_id"]]
    panel = matched[["season", "gsis_id", "pos", "adp", "age"]].merge(
        rteam, on=["season", "gsis_id"], how="inner")
    panel = panel.merge(sched, on=["season", "week", "team"], how="inner")
    panel = panel.drop_duplicates(subset=["season", "week", "gsis_id"])

    # ground truth on playing
    panel = panel.merge(snaps, on=["season", "week", "pfr_id"], how="left")
    panel["played"] = panel.offense_snaps.fillna(0) > 0

    # injury signals
    panel = panel.merge(reports, on=["season", "week", "gsis_id"], how="left")
    panel["on_ir"] = panel.status.isin(IR_CODES)
    panel["ruled_out"] = panel.report_status.isin(["Out", "Doubtful"])
    panel["questionable"] = panel.report_status.eq("Questionable")
    panel["injury_absence"] = (~panel.played) & (panel.on_ir | panel.ruled_out)

    panel = panel.sort_values(["season", "gsis_id", "week"])
    panel.to_parquet(OUT / "panel_position_age.parquet")
    print(f"panel: {len(panel):,} player-weeks, "
          f"{panel.groupby(['season','gsis_id']).ngroups:,} player-seasons")

    res = {"meta": {
        "seasons": [min(SEASONS), max(SEASONS)],
        "player_weeks": int(len(panel)),
        "player_seasons": int(panel.groupby(["season", "gsis_id"]).ngroups),
        "pool": "ADP-draftable, ex-ante",
        "played_source": "snap counts (offense_snaps > 0)",
        "injury_source": "weekly roster IR status + Out/Doubtful report",
    }}

    # ---- 1. games missed to injury, by position ---------------------------
    ps = panel.groupby(["season", "gsis_id", "pos"], as_index=False).agg(
        team_games=("week", "count"),
        played=("played", "sum"),
        missed_inj=("injury_absence", "sum"),
        q_weeks=("questionable", "sum"),
        age=("age", "first"),
        adp=("adp", "first"))
    ps = ps[ps.team_games >= 14]  # full-season members of the pool

    tbl = []
    for p in POS:
        g = ps[ps.pos == p]
        tbl.append({
            "pos": p, "n": int(len(g)),
            "mean_missed": round(float(g.missed_inj.mean()), 2),
            "median_missed": float(g.missed_inj.median()),
            "pct_zero_missed": round(float((g.missed_inj == 0).mean()) * 100, 1),
            "pct_1plus": round(float((g.missed_inj >= 1).mean()) * 100, 1),
            "pct_4plus": round(float((g.missed_inj >= 4).mean()) * 100, 1),
            "pct_8plus": round(float((g.missed_inj >= 8).mean()) * 100, 1),
            "pct_of_games_missed": round(
                float(g.missed_inj.sum() / g.team_games.sum()) * 100, 1),
        })
    res["missed_by_position"] = tbl
    print("\n=== games missed to injury per season, by position ===")
    print(pd.DataFrame(tbl).to_string(index=False))

    # ---- 2. weekly hazard: new absences by week of season ------------------
    pw = panel.copy()
    pw["is_new"] = pw.injury_absence & ~pw.groupby(
        ["season", "gsis_id"]).injury_absence.shift(1).fillna(False)
    haz = []
    for p in POS:
        g = pw[pw.pos == p]
        # at risk = available (not already absent) that week
        avail = g[~g.injury_absence | g.is_new]
        by_wk = avail.groupby("week").agg(
            at_risk=("gsis_id", "count"), new=("is_new", "sum"))
        by_wk["rate"] = by_wk.new / by_wk.at_risk * 100
        haz.append({"pos": p, "weeks": {int(w): round(float(r), 2)
                                        for w, r in by_wk.rate.items()}})
    res["weekly_hazard"] = haz

    # thirds of the season, easier to read
    thirds = []
    for p in POS:
        g = pw[pw.pos == p]
        avail = g[~g.injury_absence | g.is_new]
        for lo, hi, lbl in [(1, 6, "wk 1-6"), (7, 12, "wk 7-12"), (13, 18, "wk 13-18")]:
            s = avail[(avail.week >= lo) & (avail.week <= hi)]
            if len(s):
                thirds.append({"pos": p, "span": lbl,
                               "new_absence_rate": round(float(s.is_new.mean()) * 100, 2),
                               "at_risk": int(len(s))})
    res["hazard_by_third"] = thirds
    print("\n=== new injury absences per available player-week (%) ===")
    print(pd.DataFrame(thirds).pivot(index="pos", columns="span",
                                     values="new_absence_rate").to_string())

    # ---- 3. season-ending: absent from week W through the finale ----------
    se = []
    for p in POS:
        g = ps[ps.pos == p]
        ids_ = set(zip(g.season, g.gsis_id))
        sub = panel[panel.set_index(["season", "gsis_id"]).index.isin(ids_)]
        ended = 0
        for (s, pid), grp in sub.groupby(["season", "gsis_id"]):
            grp = grp.sort_values("week")
            if not grp.played.any():
                continue
            last_played = grp[grp.played].week.max()
            after = grp[grp.week > last_played]
            # ended the season hurt: 4+ missed games to injury, none played after
            if len(after) >= 4 and after.injury_absence.sum() >= 4:
                ended += 1
        n = g.gsis_id.nunique() if False else len(g)
        se.append({"pos": p, "n": int(n), "season_ending_pct":
                   round(ended / max(n, 1) * 100, 1), "count": int(ended)})
    res["season_ending"] = se
    print("\n=== season-ending injuries (lost final 4+ games) ===")
    print(pd.DataFrame(se).to_string(index=False))

    # ---- 4. questionable-tag rate, by position ----------------------------
    q = []
    for p in POS:
        g = panel[(panel.pos == p) & ~panel.injury_absence]
        listed = panel[(panel.pos == p)]
        q.append({
            "pos": p,
            "questionable_rate": round(float(g.questionable.mean()) * 100, 1),
            "any_report_rate": round(
                float(listed.report_status.notna().mean()) * 100, 1),
            "limited_practice_rate": round(float(
                listed.practice_status.eq("Limited Participation in Practice")
                .mean()) * 100, 1),
        })
    res["tag_rates"] = q
    print("\n=== injury-report presence per player-week (%) ===")
    print(pd.DataFrame(q).to_string(index=False))

    # ---- 5. age curves -----------------------------------------------------
    def age_bucket(a, pos):
        if pd.isna(a):
            return None
        if pos == "RB":
            edges = [(0, 23, "≤22"), (23, 25, "23-24"), (25, 27, "25-26"),
                     (27, 29, "27-28"), (29, 99, "29+")]
        else:
            edges = [(0, 24, "≤23"), (24, 26, "24-25"), (26, 28, "26-27"),
                     (28, 30, "28-29"), (30, 99, "30+")]
        for lo, hi, lbl in edges:
            if lo <= a < hi:
                return lbl
        return None

    ps["age_bucket"] = [age_bucket(a, p) for a, p in zip(ps.age, ps.pos)]
    age_tbl = []
    for p in POS:
        g = ps[(ps.pos == p) & ps.age_bucket.notna()]
        for b, grp in g.groupby("age_bucket"):
            if len(grp) < 15:
                continue
            age_tbl.append({
                "pos": p, "age": b, "n": int(len(grp)),
                "mean_missed": round(float(grp.missed_inj.mean()), 2),
                "pct_zero": round(float((grp.missed_inj == 0).mean()) * 100, 1),
                "pct_4plus": round(float((grp.missed_inj >= 4).mean()) * 100, 1),
            })
    res["age_curves"] = age_tbl
    print("\n=== games missed by age ===")
    print(pd.DataFrame(age_tbl).to_string(index=False))

    # age as a continuous slope, controlling for position and draft cost
    slopes = []
    for p in POS:
        g = ps[(ps.pos == p) & ps.age.notna()]
        if len(g) < 60:
            continue
        X = np.column_stack([np.ones(len(g)), g.age.values, np.log(g.adp.values)])
        y = g.missed_inj.values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        dof = len(g) - X.shape[1]
        se_b = np.sqrt(np.diag(np.linalg.pinv(X.T @ X)) * (resid @ resid) / dof)
        slopes.append({"pos": p, "n": int(len(g)),
                       "games_missed_per_year_of_age": round(float(beta[1]), 3),
                       "se": round(float(se_b[1]), 3),
                       "t": round(float(beta[1] / se_b[1]), 2)})
    res["age_slopes"] = slopes
    print("\n=== extra games missed per year of age (controls for ADP) ===")
    print(pd.DataFrame(slopes).to_string(index=False))

    # ---- 6. production while carrying a tag --------------------------------
    fp = fantasy_points_std()
    pp = panel[panel.played].merge(
        fp[["season", "week", "gsis_id", "pts"]],
        on=["season", "week", "gsis_id"], how="inner")
    # each player's own clean-week baseline, so this isn't a talent comparison
    clean = pp[pp.report_status.isna() &
               pp.practice_status.isin(["Full Participation in Practice", None])]
    base = clean.groupby(["season", "gsis_id"], as_index=False).agg(
        base_pts=("pts", "mean"), base_n=("pts", "count"))
    pp = pp.merge(base, on=["season", "gsis_id"], how="inner")
    pp = pp[(pp.base_n >= 4) & (pp.base_pts > 3)]
    pp["ratio"] = pp.pts / pp.base_pts

    prod = []
    for p in POS:
        g = pp[pp.pos == p]
        for lbl, mask in [
            ("clean", g.report_status.isna()),
            ("questionable", g.report_status.eq("Questionable")),
            ("limited practice", g.practice_status.eq(
                "Limited Participation in Practice")),
            ("DNP in practice", g.practice_status.eq(
                "Did Not Participate In Practice")),
        ]:
            s = g[mask]
            if len(s) < 40:
                continue
            prod.append({"pos": p, "state": lbl, "n": int(len(s)),
                         "pct_of_own_normal": round(float(s.ratio.mean()) * 100, 1)})
    res["production_when_tagged"] = prod
    print("\n=== points as % of that player's own healthy average ===")
    print(pd.DataFrame(prod).pivot(index="pos", columns="state",
                                   values="pct_of_own_normal").to_string())

    # ---- 7. first game back --------------------------------------------
    pp2 = panel.merge(fp[["season", "week", "gsis_id", "pts"]],
                      on=["season", "week", "gsis_id"], how="left")
    pp2 = pp2.sort_values(["season", "gsis_id", "week"])
    pp2["prev_absent"] = pp2.groupby(["season", "gsis_id"]).injury_absence.shift(1)
    ret = pp2[pp2.played & pp2.prev_absent.fillna(False)]
    ret = ret.merge(base, on=["season", "gsis_id"], how="inner")
    ret = ret[(ret.base_n >= 4) & (ret.base_pts > 3)]
    ret["ratio"] = ret.pts / ret.base_pts
    res["first_game_back"] = [
        {"pos": p, "n": int((ret.pos == p).sum()),
         "pct_of_own_normal": round(float(ret[ret.pos == p].ratio.mean()) * 100, 1)}
        for p in POS if (ret.pos == p).sum() >= 30]
    print("\n=== first game back, % of own normal ===")
    print(pd.DataFrame(res["first_game_back"]).to_string(index=False))

    json.dump(res, open(OUT / "results_position_age.json", "w"), indent=1)
    print(f"\nwrote {OUT/'results_position_age.json'}")


if __name__ == "__main__":
    main()
