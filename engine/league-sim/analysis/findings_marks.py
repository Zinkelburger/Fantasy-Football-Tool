"""Per-player draft marks derived from the findings.

Findings 08/09/10 (mid-round WR archetypes), 15 (hot finishes), 16 (TD
luck), 17 (targets over efficiency) and 18 (the injury-prone label)
each imply a rule you can run against one season's stats. This script
runs those rules two ways:

  default   apply to 2025 stats + the 2026 ADP board and write
            data/market/findings_marks_2026.csv — one row per
            (player, finding): buy / fade / watch plus a plain-English
            note carrying the player's own numbers. Consumed by
            webapp/build_data.py (draft-tool note pane + tooltip).
  --grade   apply the SAME rules one season earlier (2024 stats, 2025
            ADP board) and print every flagged player's actual 2025
            outcome — the honesty check the findings promise. Writes
            nothing.

Thresholds are the ones the findings tested, not tuned here: pooled
TDOE quintiles on 8+ game seasons (16), WR target-excess quintiles
(17), a 4-PPG last-3-week surge (15, the top-quartile boundary), the
36-120 ADP band (08/09/10), and 2+ weeks Out (18). Myth-buster
findings (15, 18 at QB/WR) mark as "watch"/"buy" context — they adjust
the price you should pay, not the projection.

Run from league-sim root:
  venv/bin/python analysis/findings_marks.py [--grade]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
sys.path.insert(0, str(ROOT / "scripts"))
import next_season_signal as nss                    # noqa: E402

BAND = (36, 120)          # scripts/wr_archetypes.py mid-round window
SURGE = 4.0               # ~top/bottom-quartile last-3 surge, in PPG
ALIAS = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "JAC": "JAX"}
_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv|v)\.?$")


def norm(name):
    n = name.lower().strip().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", _SUFFIX.sub("", n))


def mark(name, pos, team, finding, direction, note, pid=None):
    return dict(name=name, pos=pos, team=team or "", finding=finding,
                dir=direction, note=note, pid=pid)


# ---------------------------------------------------------- aux tables
def team_records(year):
    g = pd.read_csv(MKT / "games.csv", low_memory=False)
    g = g[(g.season == year) & (g.game_type == "REG")].dropna(
        subset=["home_score"])
    rec = {}
    for r in g.itertuples():
        for t, mine, theirs in ((r.home_team, r.home_score, r.away_score),
                                (r.away_team, r.away_score, r.home_score)):
            w, l, d = rec.get(t, (0, 0, 0))
            rec[t] = (w + (mine > theirs), l + (mine < theirs),
                      d + (mine == theirs))
    return rec


def ages_at_sept(year):
    """normalized name -> age at Sept 1, roster birthdates (same
    convention as scripts/wr_archetypes.py age_at)."""
    r = pd.read_parquet(MKT / f"roster_{year}.parquet")[
        ["full_name", "birth_date"]].dropna()
    out = {}
    for x in r.itertuples():
        y, mo, dy = str(x.birth_date)[:10].split("-")
        out[norm(x.full_name)] = (year - int(y)
                                  - (1 if (int(mo), int(dy)) > (9, 1) else 0))
    return out


def adp_wrs(draft_year):
    """Every WR with an ADP that draft year, sorted by ADP."""
    if draft_year == 2026:
        a = pd.read_csv(MKT / "adp_2026.csv")
        a["adp"] = a.espn.fillna(a.ffc_std)   # both are overall picks
        rows = [dict(name=r.player, team=r.team, adp=float(r.adp))
                for r in a[a.pos == "WR"].dropna(subset=["adp"]).itertuples()]
    else:
        rows = [dict(name=x["name"], team=x["team"], adp=float(x["adp"]))
                for x in json.load(open(DATA / f"adp_{draft_year}.json"))
                if x["pos"] == "WR" and x.get("adp")]
    return sorted(rows, key=lambda r: r["adp"])


def wr_finishes(ps, season):
    d = ps[(ps.season == season) & (ps.position == "WR")]
    return {norm(r.name): int(r.pos_rank) for r in d.itertuples()}


def season_teams(adv, season):
    a = adv[(adv.season == season)
            & (adv.season_type == "REG")].sort_values("week")
    return a.groupby("player_id").team.last().to_dict()


def target_shares(adv, season):
    a = adv[(adv.season == season) & (adv.season_type == "REG")]
    g = a.groupby("player_id").agg(
        share=("target_share", "mean"),
        name=("player_display_name", "first"))
    return {norm(r.name): r.share for r in g.itertuples()
            if pd.notna(r.share)}


# ------------------------------------------------------ per-rule marks
def f16_td_luck(m, season, team):
    out = []
    d = m[m.relevant & (m.season == season) & (m.gp >= 8)
          & m.position.isin(["RB", "WR", "TE"])].dropna(subset=["tdoe"])
    hi, lo = d.tdoe.quantile(0.8), d.tdoe.quantile(0.2)
    for r in d.itertuples():
        if r.tdoe >= hi:
            out.append(mark(
                r.name, r.position, team.get(r.player_id), 16, "fade",
                f"Scored {r.td:.0f} touchdowns on chances worth {r.xtd:.0f} "
                f"in {season}. That extra scoring is luck, and it doesn't "
                f"carry over — don't pay the TD-inflated price (finding 16).",
                r.player_id))
        elif r.tdoe <= lo:
            out.append(mark(
                r.name, r.position, team.get(r.player_id), 16, "buy",
                f"Scored only {r.td:.0f} touchdowns on chances worth "
                f"{r.xtd:.0f} in {season}. The missing scores usually come "
                f"back the next year (finding 16).", r.player_id))
    q = m[m.relevant & (m.season == season) & (m.gp >= 8)
          & (m.position == "QB")].dropna(subset=["a_pass_td"]).copy()
    q["ptdoe"] = q.a_pass_td - q.x_pass_td
    for r in q.nlargest(5, "ptdoe").itertuples():
        out.append(mark(
            r.name, "QB", team.get(r.player_id), 16, "fade",
            f"Threw {r.a_pass_td:.0f} touchdowns on chances worth "
            f"{r.x_pass_td:.0f} in {season}. Passing-TD luck regresses "
            f"the same way, on a smaller sample (finding 16).",
            r.player_id))
    for r in q.nsmallest(5, "ptdoe").itertuples():
        out.append(mark(
            r.name, "QB", team.get(r.player_id), 16, "buy",
            f"Threw {r.a_pass_td:.0f} touchdowns on chances worth "
            f"{r.x_pass_td:.0f} in {season} — the short end of passing-TD "
            f"luck, which tends to bounce back (finding 16).", r.player_id))
    return out


def f17_targets(m, season, team):
    out = []
    wr = m[m.relevant & (m.season == season) & (m.gp >= 8)
           & (m.position == "WR")].dropna(subset=["targets"]).copy()
    wr["tpg"] = wr.targets / wr.gp
    wr["excess"] = nss.resid(wr.tpg.values, wr.ppg.values)
    hi, lo = wr.excess.quantile(0.8), wr.excess.quantile(0.2)
    for r in wr.itertuples():
        if r.excess >= hi:
            out.append(mark(
                r.name, "WR", team.get(r.player_id), 17, "buy",
                f"Saw {r.tpg:.1f} passes a game thrown his way but scored "
                f"only {r.ppg:.1f} PPG in {season}. Targets predict next "
                f"season better than points do — volume like that usually "
                f"pays off (finding 17).", r.player_id))
        elif r.excess <= lo:
            out.append(mark(
                r.name, "WR", team.get(r.player_id), 17, "fade",
                f"His {r.ppg:.1f} PPG in {season} came on just {r.tpg:.1f} "
                f"targets a game. Points built on efficiency instead of "
                f"volume tend not to repeat (finding 17).", r.player_id))
    return out


def f15_momentum(ps, season, team):
    out = []
    rel = ps[ps.relevant & (ps.season == season) & (ps.gp >= 8)
             & (ps.gp_last3 >= 2)].copy()
    rel["surge"] = rel.ppg_last3 - rel.ppg
    for r in rel.itertuples():
        if r.surge >= SURGE:
            out.append(mark(
                r.name, r.position, team.get(r.player_id), 15, "watch",
                f"Finished {season} on fire — {r.ppg_last3:.1f} PPG over "
                f"his last three games against {r.ppg:.1f} for the season. "
                f"A hot finish predicts nothing about next year; price the "
                f"full season, not the streak (finding 15).", r.player_id))
        elif r.surge <= -SURGE:
            out.append(mark(
                r.name, r.position, team.get(r.player_id), 15, "watch",
                f"Limped to the finish — {r.ppg_last3:.1f} PPG over his "
                f"last three games against {r.ppg:.1f} for the season. A "
                f"cold finish predicts nothing either, so don't discount "
                f"him for it (finding 15).", r.player_id))
    return out


def f18_injury_label(im, season, team):
    out = []
    d = im[im.relevant & (im.season == season) & (im.gp >= 8)
           & (im.wk_out >= 2)]
    for r in d.itertuples():
        wk = int(r.wk_out)
        if r.position in ("QB", "WR"):
            out.append(mark(
                r.name, r.position, team.get(r.player_id), 18, "buy",
                f"Listed Out or Doubtful {wk} weeks in {season}. At "
                f"{'quarterback' if r.position == 'QB' else 'receiver'} "
                f"injury history doesn't carry over at all — if his price "
                f"bakes in an injury-prone discount, take the discount "
                f"(finding 18).", r.player_id))
        elif r.position == "TE":
            out.append(mark(
                r.name, "TE", team.get(r.player_id), 18, "watch",
                f"Listed Out or Doubtful {wk} weeks in {season}, and tight "
                f"end is the one position where missed time does tend to "
                f"repeat (finding 18).", r.player_id))
        else:
            out.append(mark(
                r.name, "RB", team.get(r.player_id), 18, "watch",
                f"Listed Out or Doubtful {wk} weeks in {season}. At "
                f"running back the carryover is real but weak — a small "
                f"caution, not a veto (finding 18).", r.player_id))
    return out


def wr_cohort_marks(ps, adv, draft_year):
    """Findings 08/09/10: rules over the draft year's mid-round WRs."""
    out = []
    cohort = adp_wrs(draft_year)
    rec = team_records(draft_year - 1)
    winpct = {t: (w + 0.5 * d) / max(1, w + l + d)
              for t, (w, l, d) in rec.items()}
    fin2 = wr_finishes(ps, draft_year - 2)
    fin1 = wr_finishes(ps, draft_year - 1)
    shares = target_shares(adv, draft_year - 1)
    ages = ages_at_sept(draft_year)
    wr1 = {}
    for c in cohort:                       # sorted by ADP
        wr1.setdefault(c["team"], c["name"])
    for c in cohort:
        if not (BAND[0] <= c["adp"] <= BAND[1]):
            continue
        n, team = norm(c["name"]), ALIAS.get(c["team"], c["team"])
        if wr1.get(c["team"]) == c["name"] and winpct.get(team, .5) <= .45:
            w, l, d = rec[team]
            out.append(mark(
                c["name"], "WR", c["team"], 8, "buy",
                f"The clear top receiver on a team that went {w}-{l}"
                f"{f'-{d}' if d else ''} — mid-round receivers with that "
                f"profile hit top-24 at 43%, against 25% for the rest. Bad "
                f"teams still throw to somebody (finding 08)."))
        two, last = fin2.get(n), fin1.get(n)
        if two is not None and two <= 20 and (last is None or last > 35):
            tell = shares.get(n, 0) or 0
            out.append(mark(
                c["name"], "WR", c["team"], 9, "fade",
                f"A top-20 receiver in {draft_year - 2} who collapsed "
                f"{'to WR' + str(last) if last else 'off the map'} in "
                f"{draft_year - 1}. The bounce-back-discount profile busted "
                f"53% of the time, and youth didn't save it (finding 09)."
                + (f" The one hopeful tell: he kept {tell:.0%} of his "
                   f"team's targets through the down year, which the rare "
                   f"bounce-backs shared." if tell >= .20 else "")))
        if ages.get(n) in (29, 30):
            out.append(mark(
                c["name"], "WR", c["team"], 10, "watch",
                f"A {ages[n]}-year-old receiver at a mid-round price — the "
                f"29-30 cell busted most often in our six-year test, though "
                f"the sample is thin (finding 10)."))
    return out


# ------------------------------------------------------------- driver
def all_marks(ps, m, im, adv, season):
    team = season_teams(adv, season)
    return (f15_momentum(ps, season, team) + f16_td_luck(m, season, team)
            + f17_targets(m, season, team) + f18_injury_label(im, season, team)
            + wr_cohort_marks(ps, adv, season + 1))


def grade(ps, m, im, adv):
    """Apply the rules to 2024 (2025 draft board) and print 2025 truth.

    Each rule is graded on the thing it claims: PPG change for 15/16/17,
    next-season weeks Out for 18, finish vs cost for 08/09/10."""
    marks = all_marks(ps, m, im, adv, 2024)
    nxt = {r.player_id: (r.ppg, r.ppg_next, r.gp_next)
           for r in ps[ps.season == 2024].itertuples()}
    out_nx = {r.player_id: r.wk_out_nx
              for r in im[im.season == 2024].itertuples()}
    fin25 = wr_finishes(ps, 2025)
    cohort_rank = {norm(c["name"]): i + 1
                   for i, c in enumerate(adp_wrs(2025))}
    healthy_base = im[im.relevant & (im.season == 2024) & (im.gp >= 8)
                      & (im.wk_out == 0)].groupby("position").wk_out_nx.mean()
    for f in sorted({mk["finding"] for mk in marks}):
        print(f"\n===== finding {f:02d}: flagged after 2024 -> 2025 truth =====")
        if f == 15:   # grade hot and cold finishers separately
            groups = [("watch", "hot"), ("watch", "cold")]
        else:
            groups = [("buy", None), ("fade", None), ("watch", None)]
        for direction, half in groups:
            sel = [mk for mk in marks
                   if mk["finding"] == f and mk["dir"] == direction
                   and (half is None
                        or (half == "hot") == ("on fire" in mk["note"]))]
            if not sel:
                continue
            print(f"-- {direction}{f' ({half} finish)' if half else ''} "
                  f"({len(sel)})")
            if f == 18:
                wks = []
                for mk in sel:
                    w = out_nx.get(mk["pid"])
                    if w is None or pd.isna(w):
                        print(f"   {mk['name']:<24} (no 2025 row)")
                        continue
                    wks.append(w)
                    print(f"   {mk['name']:<24} 2025 weeks Out: {int(w)}")
                if wks:
                    pos_in = sorted({mk["pos"] for mk in sel})
                    base = ", ".join(f"{p} {healthy_base.get(p, 0):.1f}"
                                     for p in pos_in)
                    print(f"   mean 2025 weeks Out {sum(wks) / len(wks):.1f} "
                          f"over {len(wks)} graded (players with zero 2024 "
                          f"weeks Out averaged: {base})")
                continue
            chgs = []
            for mk in sel:
                if f in (8, 9, 10):
                    fin = fin25.get(norm(mk["name"]))
                    cost = cohort_rank.get(norm(mk["name"]), "?")
                    verdict = ("HIT top-24" if fin and fin <= 24 else
                               "bust (>45)" if (fin is None or fin > 45)
                               else f"middling")
                    print(f"   {mk['name']:<24} cost WR{cost:<3} -> "
                          f"finish {'WR' + str(fin) if fin else 'none':<6} "
                          f"{verdict}")
                else:
                    ppg, nx, gpn = nxt.get(mk["pid"], (None, None, None))
                    if ppg is None or pd.isna(nx) or (gpn or 0) < 6:
                        print(f"   {mk['name']:<24} {ppg or 0:5.1f} -> "
                              f"  (out of sample in 2025)")
                        continue
                    chgs.append(nx - ppg)
                    print(f"   {mk['name']:<24} {ppg:5.1f} -> {nx:5.1f} "
                          f"PPG ({nx - ppg:+.1f})")
            if chgs:
                print(f"   mean change {sum(chgs) / len(chgs):+.2f} PPG "
                      f"over {len(chgs)} graded")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", action="store_true",
                    help="grade the 2024-flagged names on 2025, write nothing")
    args = ap.parse_args()
    adv, opp, inj = nss.load_or_fetch()
    ps = nss.build_player_seasons()
    m = nss.build_merged(ps, adv, opp)
    im = nss.build_injuries(ps, inj)
    if args.grade:
        grade(ps, m, im, adv)
        return
    marks = all_marks(ps, m, im, adv, 2025)
    df = pd.DataFrame(marks).drop(columns=["pid"])
    df = df.sort_values(["finding", "dir", "name"])
    p = MKT / "findings_marks_2026.csv"
    df.to_csv(p, index=False)
    print(f"{p} written: {len(df)} marks on {df.name.nunique()} players")
    print(df.groupby(["finding", "dir"]).size().to_string())


if __name__ == "__main__":
    main()
