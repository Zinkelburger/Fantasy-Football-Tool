"""The injury reference model, from real weekly injury reports.

Joins nflverse injury reports (Friday game statuses + practice notes)
to actual fantasy scoring, 2018-2025, fantasy-relevant players only
(QB/RB/WR/TE, >=3 games and >=4 ppg that season).  Answers:

1. P(plays Sunday | Friday report status)
2. When a listed player plays anyway, what does the injury cost?
   (his points that week vs his own unlisted-week baseline)
3. When a listed player sits, how long is he out — by injury type —
   and how often is it season-ending?
4. Rust: first game back vs baseline, by length of the absence.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simfl.config import DEFAULT_SCORING  # noqa: E402
from simfl.data import load_schedule_byes, load_weekly  # noqa: E402

YEARS = range(2018, 2026)
POS = ["QB", "RB", "WR", "TE"]
LISTED = ["Questionable", "Doubtful", "Out"]


def final_week(y):
    return 16 if y < 2021 else 17


def load_joined():
    inj = (pl.read_parquet("data/injuries_2017_2025.parquet")
           .filter(pl.col("position").is_in(POS))
           .with_columns(pl.col("season").cast(pl.Int64),
                         pl.col("week").cast(pl.Int64)))
    frames = []
    for y in YEARS:
        wk = (load_weekly(y, DEFAULT_SCORING)
              .filter(pl.col("position").is_in(POS),
                      pl.col("week") <= final_week(y))
              .select("player_id", "player_display_name", "position",
                      "team", "week", "fpts"))
        # relevance filter: >=3 games and >=4 ppg this season
        rel = (wk.group_by("player_id")
               .agg(pl.len().alias("g"), pl.col("fpts").mean().alias("ppg"))
               .filter(pl.col("g") >= 3, pl.col("ppg") >= 4.0)
               .select("player_id"))
        wk = wk.join(rel, on="player_id", how="inner")
        rep = (inj.filter(pl.col("season") == y, pl.col("week") <= final_week(y))
               .select(pl.col("gsis_id").alias("player_id"), "week",
                       pl.col("position").alias("pos_rep"),
                       "report_status", "report_primary_injury"))
        full = (wk.join(rep, on=["player_id", "week"], how="full", coalesce=True)
                .with_columns(pl.lit(y).alias("year"),
                              pl.coalesce("position", "pos_rep").alias("position")))
        # keep rows for relevant players only (the join added report rows
        # for irrelevant players with null fpts AND null name)
        full = full.join(rel, on="player_id", how="inner")
        frames.append(full)
    return pl.concat(frames)


def p_play(df):
    print("== 1. P(plays | Friday report status) ==")
    d = (df.filter(pl.col("report_status").is_in(LISTED))
         .with_columns(pl.col("fpts").is_not_null().alias("played")))
    out = (d.group_by("report_status").agg(
        pl.len().alias("n"), pl.col("played").mean().alias("P(play)"))
        .sort("P(play)", descending=True))
    print(out)
    q = d.filter(pl.col("report_status") == "Questionable")
    print(q.group_by("position").agg(
        pl.len().alias("n"), pl.col("played").mean().alias("P(play|Q)"))
        .sort("P(play|Q)", descending=True))


def baselines(df):
    """player-year -> mean fpts in unlisted played weeks (>=4 required)."""
    unlisted = df.filter(pl.col("fpts").is_not_null(),
                         ~pl.col("report_status").is_in(LISTED).fill_null(False))
    return (unlisted.group_by("player_id", "year")
            .agg(pl.col("fpts").mean().alias("base"), pl.len().alias("nb"))
            .filter(pl.col("nb") >= 4, pl.col("base") >= 5.0))


def hurt_discount(df):
    print("\n== 2. Playing through it: points vs own healthy baseline ==")
    base = baselines(df)
    # Control: healthy weeks measured the same way (leave-one-out), so
    # the skew of single-week scoring doesn't masquerade as an injury
    # discount — compare listed medians to THIS, not to 1.0.
    unlisted = (df.filter(pl.col("fpts").is_not_null(),
                          ~pl.col("report_status").is_in(LISTED).fill_null(False))
                .join(base.rename({"base": "b", "nb": "n_b"}),
                      on=["player_id", "year"], how="inner")
                .with_columns(((pl.col("b") * pl.col("n_b") - pl.col("fpts"))
                               / (pl.col("n_b") - 1)).alias("loo"))
                .with_columns((pl.col("fpts") / pl.col("loo")).alias("ratio")))
    print(f"healthy-week control: median ratio "
          f"{unlisted['ratio'].median():.2f} (n={len(unlisted)})")
    played_listed = (df.filter(pl.col("fpts").is_not_null(),
                               pl.col("report_status").is_in(LISTED))
                     .join(base, on=["player_id", "year"], how="inner")
                     .with_columns((pl.col("fpts") / pl.col("base")).alias("ratio")))
    print(played_listed.group_by("report_status").agg(
        pl.len().alias("n"), pl.col("ratio").median().alias("median ratio"),
        pl.col("ratio").mean().alias("mean ratio")).sort("n", descending=True))
    q = played_listed.filter(pl.col("report_status") == "Questionable")
    print(q.group_by("position").agg(
        pl.len().alias("n"), pl.col("ratio").median().alias("median ratio"))
        .sort("n", descending=True))


def spells(df):
    """Absence spells: listed Out/Doubtful in week w, didn't play, had
    played earlier that season. Returns one row per spell."""
    byes = {y: load_schedule_byes(y) for y in YEARS}
    rows = []
    for (pid, y), g in df.group_by(["player_id", "year"]):
        g = g.sort("week")
        played_weeks = set(g.filter(pl.col("fpts").is_not_null())["week"])
        if not played_weeks:
            continue
        team = g.filter(pl.col("fpts").is_not_null())["team"].last()
        bye = byes[y].get(team, 0)
        status = {r["week"]: (r["report_status"], r["report_primary_injury"])
                  for r in g.iter_rows(named=True)}
        fw = final_week(y)
        w = min(played_weeks) + 1
        while w <= fw:
            st = status.get(w, (None, None))
            if (w not in played_weeks and w != bye
                    and st[0] in ("Out", "Doubtful")):
                dur, ww = 0, w
                while ww <= fw and ww not in played_weeks:
                    if ww != bye:
                        dur += 1
                    ww += 1
                rows.append({"injury": (st[1] or "unspecified").title(),
                             "dur": dur, "ends_season": ww > fw,
                             "pos": g["position"].drop_nulls().first(),
                             "pid": pid, "year": y, "week": w})
                w = ww + 1
            else:
                w += 1
    return pl.DataFrame(rows)


def absence_table(sp):
    print("\n== 3. Once he sits (Out/Doubtful): weeks missed, by injury ==")
    out = (sp.group_by("injury").agg(
        pl.len().alias("n"),
        pl.col("dur").median().alias("median wks"),
        pl.col("dur").mean().alias("mean wks"),
        pl.col("ends_season").mean().alias("P(done for yr)"))
        .filter(pl.col("n") >= 20).sort("n", descending=True))
    print(out)
    print("all spells:", len(sp), " median", sp["dur"].median(),
          " mean", round(sp["dur"].mean(), 1),
          " P(season-ending)", round(sp["ends_season"].mean(), 2))
    for k in (1, 2, 3):
        c = sp.filter(pl.col("dur") >= k)
        print(f"  given out >={k} wks so far: mean total {c['dur'].mean():.1f}, "
              f"P(done for yr) {c['ends_season'].mean():.2f}")


def rust(df, sp):
    print("\n== 4. Rust: first game back vs baseline, by absence length ==")
    base = baselines(df)
    pts = {(r["player_id"], r["year"], r["week"]): r["fpts"]
           for r in df.filter(pl.col("fpts").is_not_null()).iter_rows(named=True)}
    rows = []
    for r in sp.filter(~pl.col("ends_season")).iter_rows(named=True):
        ret_w = r["week"] + r["dur"]
        # find the actual return week (skip byes)
        for w in range(ret_w, ret_w + 3):
            if (r["pid"], r["year"], w) in pts:
                rows.append({"dur": r["dur"], "pid": r["pid"],
                             "year": r["year"], "fpts": pts[(r["pid"], r["year"], w)]})
                break
    rd = (pl.DataFrame(rows).join(base, left_on=["pid", "year"],
                                  right_on=["player_id", "year"], how="inner")
          .with_columns((pl.col("fpts") / pl.col("base")).alias("ratio")))
    for lo, hi, tag in [(1, 1, "1 wk"), (2, 3, "2-3 wks"), (4, 99, "4+ wks")]:
        d = rd.filter(pl.col("dur").is_between(lo, hi))
        if not len(d):
            continue
        print(f"  out {tag:7s} n={len(d):4d}  first game back: "
              f"median {d['ratio'].median():.2f}x baseline")


if __name__ == "__main__":
    pl.Config.set_tbl_rows(20)
    df = load_joined()
    p_play(df)
    hurt_discount(df)
    sp = spells(df)
    absence_table(sp)
    rust(df, sp)
