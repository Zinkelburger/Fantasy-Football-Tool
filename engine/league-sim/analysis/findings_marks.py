"""Per-player draft marks derived from the findings.

Findings 10 (WR age), 16 (TD luck), 17 (targets over efficiency) and 18
(the injury-prone label) each imply a rule you can run against one
season's stats. This script runs those rules two ways:

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
(17), and 2+ weeks Out (18).

**A mark has to change what you do.** A row that reports a real number
and then explains it means nothing is not neutral — it costs attention
on the clock, and readers reasonably assume anything shown is meant to
be acted on. Four rules were dropped on that test, not because the
research was wrong but because it came back null:

  15  dropped. "A hot finish predicts nothing" is the finding's own
      conclusion, and --grade agrees (hot finishers -0.79 PPG the next
      season, cold -0.32 — noise). Nothing to act on either way.
  08  dropped. Re-run at every price over ten drafts
      (scripts/wr_archetypes.py --full), its raw board-wide edge (+15
      points of hit rate) turns out to be price mix: bad-team WR1s are
      disproportionately early picks, and any WR that early hits
      often. Standardized to the peers' price mix it is +7 [-4, +20].
  09  dropped. No penalty at any price — standardized +2 [-11, +15]
      over 44 fallen studs. The bounce-back discount is neither a trap
      nor a bargain.
  30  dropped. Its team-level half is one of the strongest results we
      have (the preseason win line predicts offense in 23 of 23
      seasons), but the player-level half is the one a mark would sit
      on, and that is the null: over 1,414 close-ADP pairs the better
      offense won nothing, because the board already charged for it.

10 came through that same re-test and got stronger: it generalizes
past the old "29-30 death zone" to all WRs 29+, about 8 points of
top-24 rate below same-priced peers (95% CI -15 to -1), stable across
hit thresholds, band schemes, both eras and every leave-one-year-out.
It no longer stops at the old 36-120 ADP band — it fires at any price.

Findings 13/14/33 add price-band rules: those were settled by the sims
and same-pick tests in their own write-ups, so the mark just tells you
where this player sits against the tested band.

The retractions live in findings/08, /09, /15 and /30 — the write-ups
are the record, the marks are only what survived.

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

TEAMS = 12                # league size the round-band findings were run at
_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv|v)\.?$")


def rnd(adp):
    """Draft round an ADP lands in, in a 12-team league."""
    return max(1, -(-int(round(float(adp))) // TEAMS))


def norm(name):
    n = name.lower().strip().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", _SUFFIX.sub("", n))


_SLUGS = {}


def slug(finding):
    """Site post id for a finding (e.g. 16 -> 16-td-luck-regresses), so
    the draft tool can link each mark to its write-up."""
    if finding not in _SLUGS:
        p = next(iter((ROOT / "findings").glob(f"{finding:02d}-*.md")), None)
        _SLUGS[finding] = p.stem if p else f"{finding:02d}"
    return _SLUGS[finding]


MAX_NOTE = 90


def mark(name, pos, team, finding, direction, note, pid=None):
    """One row for the draft tool.

    `note` is a fragment, not an argument. The chip beside it links to
    the write-up, so the note's whole job is this player's own numbers
    and the shortest possible reason — "30 years old — lower ceiling at
    this price", not the sentence explaining what ten drafts showed.
    Anything longer gets read on the clock, or more likely doesn't.
    The cap is asserted rather than commented because the last two
    passes over this file both drifted long."""
    if len(note) > MAX_NOTE:
        raise ValueError(
            f"finding {finding} note is {len(note)} chars, max {MAX_NOTE}: "
            f"{note!r}")
    return dict(name=name, pos=pos, team=team or "", finding=finding,
                slug=slug(finding), dir=direction, note=note, pid=pid)


# ---------------------------------------------------------- aux tables
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


def adp_board(draft_year, pos=None):
    """Every priced player that draft year, sorted by ADP. `pos` filters
    to one position; None returns the whole board."""
    if draft_year == 2026:
        a = pd.read_csv(MKT / "adp_2026.csv")
        a["adp"] = a.espn.fillna(a.ffc_std)   # both are overall picks
        if pos:
            a = a[a.pos == pos]
        rows = [dict(name=r.player, team=r.team, pos=r.pos, adp=float(r.adp))
                for r in a.dropna(subset=["adp"]).itertuples()]
    else:
        rows = [dict(name=x["name"], team=x["team"], pos=x["pos"],
                     adp=float(x["adp"]))
                for x in json.load(open(DATA / f"adp_{draft_year}.json"))
                if (pos is None or x["pos"] == pos) and x.get("adp")]
    return sorted(rows, key=lambda r: r["adp"])


def adp_wrs(draft_year):
    """Every WR with an ADP that draft year, sorted by ADP."""
    return adp_board(draft_year, "WR")


def wr_finishes(ps, season):
    d = ps[(ps.season == season) & (ps.position == "WR")]
    return {norm(r.name): int(r.pos_rank) for r in d.itertuples()}


def season_teams(adv, season):
    a = adv[(adv.season == season)
            & (adv.season_type == "REG")].sort_values("week")
    return a.groupby("player_id").team.last().to_dict()


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
                f"{r.td:.0f} TDs on chances worth {r.xtd:.0f}.",
                r.player_id))
        elif r.tdoe <= lo:
            out.append(mark(
                r.name, r.position, team.get(r.player_id), 16, "buy",
                f"Only {r.td:.0f} TDs on chances worth {r.xtd:.0f}.",
                r.player_id))
    q = m[m.relevant & (m.season == season) & (m.gp >= 8)
          & (m.position == "QB")].dropna(subset=["a_pass_td"]).copy()
    q["ptdoe"] = q.a_pass_td - q.x_pass_td
    for r in q.nlargest(5, "ptdoe").itertuples():
        out.append(mark(
            r.name, "QB", team.get(r.player_id), 16, "fade",
            f"{r.a_pass_td:.0f} pass TDs on chances worth "
            f"{r.x_pass_td:.0f}.", r.player_id))
    for r in q.nsmallest(5, "ptdoe").itertuples():
        out.append(mark(
            r.name, "QB", team.get(r.player_id), 16, "buy",
            f"{r.a_pass_td:.0f} pass TDs on chances worth "
            f"{r.x_pass_td:.0f}.", r.player_id))
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
                f"{r.tpg:.1f} targets a game, only {r.ppg:.1f} PPG.",
                r.player_id))
        elif r.excess <= lo:
            out.append(mark(
                r.name, "WR", team.get(r.player_id), 17, "fade",
                f"{r.ppg:.1f} PPG on just {r.tpg:.1f} targets a game.",
                r.player_id))
    return out


# Finding 15 used to mark here — a "watch" row on every player who
# closed the season 4+ PPG above or below his own average, 48 of them.
# It is gone, and it is the clearest case for the rule that removed it:
# the finding's own title is "a hot finish predicts nothing", --grade
# agrees (hot finishers -0.79 PPG the next year, cold -0.32, both
# noise), and no wording survives that. Written as a warning it reads
# as though a strong close were a mark against the player, which is
# not what the research says; written neutrally it is a stat with a
# sentence explaining it does not matter. Neither earns a line on the
# clock. The myth-buster still runs in findings/15 and in the
# round-by-round guide, where advice about a bias belongs.


def f18_injury_label(im, season, team):
    out = []
    d = im[im.relevant & (im.season == season) & (im.gp >= 8)
           & (im.wk_out >= 2)]
    for r in d.itertuples():
        wk = int(r.wk_out)
        if r.position in ("QB", "WR"):
            out.append(mark(
                r.name, r.position, team.get(r.player_id), 18, "buy",
                f"Out {wk} weeks in {season}.", r.player_id))
        elif r.position == "TE":
            out.append(mark(
                r.name, "TE", team.get(r.player_id), 18, "watch",
                f"Out {wk} weeks in {season} — repeats at tight end.",
                r.player_id))
        else:
            out.append(mark(
                r.name, "RB", team.get(r.player_id), 18, "watch",
                f"Out {wk} weeks in {season}.", r.player_id))
    return out


def wr_age_marks(draft_year):
    """Finding 10, the only WR archetype left standing.

    08 and 09 used to mark here too. The board-wide re-test
    (scripts/wr_archetypes.py --full) could not reproduce either one —
    08's apparent edge is price mix, 09 shows no penalty at any price —
    so neither gets a row. A mark exists to change what you do; a row
    that says "this changes nothing" is just something else to read on
    the clock. The retraction lives in the write-ups, which is where a
    reader who wants the history should find it."""
    out = []
    ages = ages_at_sept(draft_year)
    for c in adp_wrs(draft_year):
        age = ages.get(norm(c["name"]))
        if age is not None and age >= 29:
            out.append(mark(
                c["name"], "WR", c["team"], 10, "fade",
                f"{age} years old — lower ceiling at this price."))
    return out


def f33_te_timing(draft_year):
    """Finding 33: rounds 1-4 TEs beat the WR/RB taken at the same pick
    69% of the time; rounds 5-9 is the trap band both 33 and 05 found."""
    out = []
    for c in adp_board(draft_year, "TE"):
        r = rnd(c["adp"])
        if r <= 4:
            out.append(mark(
                c["name"], "TE", c["team"], 33, "buy",
                f"Round {r} — early tight end pays off."))
        elif r <= 9:
            out.append(mark(
                c["name"], "TE", c["team"], 33, "fade",
                f"Round {r} — the tight end dead zone."))
    return out


def f14_qb_timing(draft_year):
    """Finding 14's round sweep: 4-6 peaks, 2-8 is nearly as good,
    waiting past 10 costs about 4 points of all-play."""
    out = []
    for c in adp_board(draft_year, "QB"):
        r = rnd(c["adp"])
        if 4 <= r <= 6:
            out.append(mark(
                c["name"], "QB", c["team"], 14, "buy",
                f"Round {r} — the tested sweet spot."))
        elif r <= 3:
            out.append(mark(
                c["name"], "QB", c["team"], 14, "watch",
                f"Round {r} — fairly priced, not a bargain."))
        elif r >= 11:
            # Finding 14 is about when you take your FIRST quarterback,
            # not about the player. A round-12 QB is a perfectly good
            # second one, so this cannot be a fade on him — the mark has
            # to say which of the two situations it is talking about.
            out.append(mark(
                c["name"], "QB", c["team"], 14, "watch",
                f"Round {r} — fine as your QB2, too late for your QB1."))
    return out


def f13_handcuff(draft_year, rooms):
    """Finding 13: the backup behind a workhorse is real insurance and
    fairly priced. Worth naming, never worth reaching for."""
    out = []
    for c in adp_board(draft_year, "RB"):
        rm = rooms.get((norm(c["name"]), "RB"))
        if not rm or not rm.get("ahead") or rm.get("ahead_gap") is None:
            continue
        # Only a real handcuff: the starter costs a lot more than he does.
        if rm["ahead_gap"] < 60:
            continue
        out.append(mark(
            c["name"], "RB", c["team"], 13, "watch",
            f"Backup to {rm['ahead']}, {rm['ahead_gap']} picks cheaper. "
            f"Insurance, fairly priced."))
    return out


# Finding 30 used to mark here too, on all 63 players attached to a
# top-five or bottom-five offense by Vegas's implied points. Same null,
# same removal: finding 30's team-level half is strongly true (the win
# line predicts offense in 23 of 23 seasons) but its player-level half
# is the null that matters here — across 1,414 close-ADP pairs the
# better offense won nothing, because the board already charged for it.
# So the row could only ever end "and this is not a reason to move
# him", which is the shape we are no longer willing to print.


def load_rooms():
    """(normalized name, pos) -> who is priced ahead of him in his own
    team's position room. analysis/position_room.py writes it; only the
    STD board is needed, since the handcuff rule is about roles."""
    p = MKT / "position_room_2026.csv"
    if not p.exists():
        print(f"WARNING: no {p.name} — finding 13 marks skipped "
              "(run analysis/position_room.py)")
        return {}
    out = {}
    for r in pd.read_csv(p).itertuples():
        gap = r.room_ahead_gap
        out[(norm(r.name), r.pos)] = {
            "ahead": r.room_ahead if isinstance(r.room_ahead, str) else None,
            "ahead_gap": None if pd.isna(gap) else int(gap),
        }
    return out


# ------------------------------------------------------------- driver
def all_marks(ps, m, im, adv, season):
    team = season_teams(adv, season)
    draft_year = season + 1
    out = (f16_td_luck(m, season, team)
           + f17_targets(m, season, team) + f18_injury_label(im, season, team)
           + wr_age_marks(draft_year))
    # 13/14/30/33 read this year's board and this year's betting lines,
    # and none of them is a stat rule --grade could score: each was
    # settled by a sim or a same-pick test in its own write-up, so the
    # mark only reports which tested band the player falls in. Skip them
    # when replaying an older draft.
    if draft_year == 2026:
        out += (f33_te_timing(draft_year) + f14_qb_timing(draft_year)
                + f13_handcuff(draft_year, load_rooms()))
    return out


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
        for direction in ("buy", "fade", "watch"):
            sel = [mk for mk in marks
                   if mk["finding"] == f and mk["dir"] == direction]
            if not sel:
                continue
            print(f"-- {direction} ({len(sel)})")
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
