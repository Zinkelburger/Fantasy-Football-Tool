"""Three tests behind the decision-tree rules:

1. Handcuffs: when an ADP top-72 starter RB misses weeks, what does
   HIS OWN backup (next RB on the same NFL team by ADP) actually score
   in those weeks, vs weeks the starter plays, vs RB replacement?
2. ADP variance: within the same draft range, do high-stdev players
   (market disagreement, e.g. Croskey-Merritt) out- or under-perform
   the E[pts | ADP] curve?
3. QB structure: how often does PickValue end up with 2 QBs, and in
   which rounds does it take them?
"""

import math
import random

import numpy as np
import polars as pl

from common import SEASONS, season_totals, weekly
from simfl.data import load_adp, norm_name


def handcuffs():
    print("== 1. Handcuff payoff, 2020-2025 ==")
    rows = []
    for y in SEASONS:
        adp = sorted(load_adp(y), key=lambda p: p["adp"])
        rbs = [p for p in adp if p["pos"] == "RB"]
        wk = weekly(y).filter(pl.col("position") == "RB")
        pts = {(r["nname"], r["week"]): r["fpts"] for r in wk.rows(named=True)}
        played = {}
        for r in wk.rows(named=True):
            played.setdefault(r["nname"], set()).add(r["week"])
        seen_teams = set()
        for s in rbs:
            if s["adp"] > 72 or s["team"] in seen_teams:
                continue
            seen_teams.add(s["team"])
            cuffs = [p for p in rbs if p["team"] == s["team"]
                     and p["adp"] > s["adp"]]
            if not cuffs:
                continue
            h = cuffs[0]
            sn, hn = norm_name(s["name"]), norm_name(h["name"])
            s_weeks = played.get(sn, set())
            h_weeks = played.get(hn, set())
            out = [w for w in range(1, 18) if w not in s_weeks and w in h_weeks]
            inn = [w for w in range(1, 18) if w in s_weeks and w in h_weeks]
            if not out and not inn:
                continue
            rows.append({
                "year": y, "starter": s["name"], "cuff": h["name"],
                "cuff_adp": h["adp"],
                "starter_missed": len([w for w in range(1, 18) if w not in s_weeks]),
                "cuff_ppg_starter_out": (sum(pts.get((hn, w), 0) for w in out) / len(out)) if out else None,
                "cuff_ppg_starter_in": (sum(pts.get((hn, w), 0) for w in inn) / len(inn)) if inn else None,
            })
    df = pl.DataFrame(rows)
    both = df.filter(pl.col("cuff_ppg_starter_out").is_not_null())
    print(f"starter-seasons with an ADP-listed handcuff: {len(df)}, "
          f"with starter-missed weeks: {len(both)}")
    print(f"handcuff ppg, starter OUT : {both['cuff_ppg_starter_out'].mean():.1f}")
    inn = df.filter(pl.col("cuff_ppg_starter_in").is_not_null())
    print(f"handcuff ppg, starter IN  : {inn['cuff_ppg_starter_in'].mean():.1f}")
    print("(RB replacement/waiver level ~6.5 ppw; RB12 ~9.9; RB24 ~7.6)")
    good = both.filter(pl.col("cuff_ppg_starter_out") >= 9.9)
    print(f"handcuffs that were RB1-level when starter out: "
          f"{len(good)}/{len(both)} ({len(good)/len(both):.0%})")
    print("\nthe 2025 case you played:")
    print(df.filter(pl.col("year") == 2025,
                    pl.col("starter").str.contains("Irving") |
                    pl.col("cuff").str.contains("Rachaad")))


def adp_variance():
    print("\n== 2. High ADP-stdev vs the curve (pooled 2020-2025, skill pos) ==")
    rows = []
    for y in SEASONS:
        tot = {r["nname"]: r["total"] for r in season_totals(y).rows(named=True)}
        for p in load_adp(y):
            if p["pos"] == "K" or p.get("stdev") is None:
                continue
            rows.append({"pos": p["pos"], "adp": p["adp"], "sd": p["stdev"],
                         "total": tot.get(norm_name(p["name"]), 0.0)})
    df = pl.DataFrame(rows)
    # residual vs per-position log fit
    parts = []
    for pos in ["QB", "RB", "WR", "TE"]:
        d = df.filter(pl.col("pos") == pos)
        x = np.log(d["adp"].to_numpy())
        b, a = np.polyfit(x, d["total"].to_numpy(), 1)
        parts.append(d.with_columns(
            (pl.col("total") - (a + b * pl.col("adp").log())).alias("resid")))
    df = pl.concat(parts).with_columns(
        ((pl.col("adp") - 1) // 24).alias("bucket"))
    # relative sd within bucket -> quartile
    df = df.with_columns(
        (pl.col("sd").rank("ordinal").over("bucket") /
         pl.col("sd").count().over("bucket")).alias("sd_pctl"))
    out = (df.with_columns(
        pl.when(pl.col("sd_pctl") <= 0.25).then(pl.lit("Q1 low-sd"))
        .when(pl.col("sd_pctl") <= 0.5).then(pl.lit("Q2"))
        .when(pl.col("sd_pctl") <= 0.75).then(pl.lit("Q3"))
        .otherwise(pl.lit("Q4 high-sd")).alias("q"))
        .group_by("q").agg(pl.col("resid").mean().round(1).alias("mean_resid"),
                           pl.col("resid").median().round(1).alias("median_resid"),
                           pl.len().alias("n")).sort("q"))
    print(out)


def qb_structure(n=30):
    print("\n== 3. PickValue QB structure across seeded drafts ==")
    import sys
    from simfl.config import DEFAULT_LEAGUE
    from simfl.draft import run_draft
    from simfl.models import Team as T
    from simfl.montecarlo import get_pool
    from simfl.strategies import make
    two_qb, qb_rounds = 0, []
    total = 0
    for y in SEASONS:
        pool, _ = get_pool(y)
        for i in range(n // 6 + 1):
            rng = random.Random(9000 + i)
            strats = [make("family") for _ in range(12)]
            seat = (i * 5) % 12
            strats[seat] = make("pick_value")
            for s in strats:
                s.bind_year(y)
            teams = [T(idx=k, name=str(k), strategy=s)
                     for k, s in enumerate(strats)]
            run_draft(list(pool), teams, DEFAULT_LEAGUE, rng)
            hero = teams[seat]
            by_pid = {p.pid: p for p in pool}
            rounds = sorted(t for pid, t in hero.drafted_round.items()
                            if by_pid[pid].pos == "QB")
            total += 1
            if len(rounds) >= 2:
                two_qb += 1
            qb_rounds.append(rounds)
    print(f"drafts with 2 QBs: {two_qb}/{total}")
    firsts = [r[0] for r in qb_rounds if r]
    seconds = [r[1] for r in qb_rounds if len(r) > 1]
    print(f"first QB round: median {sorted(firsts)[len(firsts)//2]}, range {min(firsts)}-{max(firsts)}")
    if seconds:
        print(f"second QB round: median {sorted(seconds)[len(seconds)//2]}, range {min(seconds)}-{max(seconds)}")


if __name__ == "__main__":
    handcuffs()
    adp_variance()
    qb_structure()
