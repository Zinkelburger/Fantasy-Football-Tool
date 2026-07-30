"""Calibration check: simulated family league vs the real one.

Compares (a) draft reach spread / biases and (b) per-seat waiver adds
against the measured Sumfun values, and (c) prints one PickValue draft
for eyeball sanity.
"""

import random
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simfl.config import DEFAULT_LEAGUE, SEASONS
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import make
from simfl.waivers import SEAT_SEASON_ADDS

REAL_SD_BY_BUCKET = {0: 17.0, 1: 11.4, 2: 17.9, 3: 19.9,
                     4: 25.9, 5: 27.4, 6: 33.8, 7: 25.3}
REAL_POS_MEAN = {"QB": 7.0, "RB": 5.1, "WR": 0.4, "TE": 0.9}
REAL_ROOKIE_MEAN = -6.9   # rounds 1-10


def family_league(year, seed, hero=None, seat=0):
    pool, tab = get_pool(year)
    strategies = [make("family") for _ in range(12)]
    if hero:
        strategies[seat] = make(hero)
    for s in strategies:
        s.bind_year(year)
    rng = random.Random(seed)
    return run_season(pool, strategies, DEFAULT_LEAGUE, tab, rng)


def draft_check(n_per_year=8):
    rows = []
    for year in SEASONS:
        pool, _ = get_pool(year)
        by_pid = {p.pid: p for p in pool}
        for i in range(n_per_year):
            res = family_league(year, seed=1000 + i)
            for t in res.teams:
                for pid, rnd in t.drafted_round.items():
                    p = by_pid[pid]
                    if p.adp is None:
                        continue
                    overall = None  # reconstruct from round + draft log? use rnd
                    rows.append({"pos": p.pos, "rookie": p.rookie, "round": rnd,
                                 "adp": p.adp, "team": t.idx})
    print("(draft_check needs overall pick numbers — see draft_log_check)")


def draft_log_check(n_per_year=8):
    """Rerun just drafts via run_season pick log reconstruction: use
    roster order == pick order per team; instead capture via run_draft."""
    from simfl.draft import run_draft
    from simfl.models import Team as T
    rows = []
    for year in SEASONS:
        pool, _ = get_pool(year)
        for i in range(n_per_year):
            rng = random.Random(2000 + i)
            strategies = [make("family") for _ in range(12)]
            for s in strategies:
                s.bind_year(year)
            teams = [T(idx=k, name=str(k), strategy=s)
                     for k, s in enumerate(strategies)]
            log = run_draft(list(pool), teams, DEFAULT_LEAGUE, rng)
            for overall, team, p in log:
                if p.adp is None:
                    continue
                rows.append({"overall": overall, "adp": p.adp, "pos": p.pos,
                             "rookie": p.rookie})
    df = (pl.DataFrame(rows)
          .with_columns((pl.col("overall") - pl.col("adp")).alias("reach"),
                        ((pl.col("overall") - 1) // 24).alias("bucket"),
                        ((pl.col("overall") - 1) // 12 + 1).alias("round")))
    vets = df.filter(~pl.col("rookie"))
    print("== Veteran reach sd by bucket: sim vs real ==")
    sim = vets.group_by("bucket").agg(pl.col("reach").std().round(1).alias("sim_sd"),
                                      pl.col("reach").mean().round(1).alias("sim_mean")).sort("bucket")
    for r in sim.rows(named=True):
        real = REAL_SD_BY_BUCKET.get(r["bucket"], float("nan"))
        print(f"bucket {r['bucket']}: sim sd {r['sim_sd']:>5}  real sd {real:>5}   sim mean {r['sim_mean']}")
    print("\n== Mean reach by pos (all rounds): sim vs real ==")
    for pos in ["QB", "RB", "WR", "TE"]:
        m = vets.filter(pl.col("pos") == pos)["reach"].mean()
        print(f"{pos}: sim {m:+.1f}   real {REAL_POS_MEAN[pos]:+.1f}")
    rk = df.filter(pl.col("rookie"), pl.col("round") <= 10)["reach"].mean()
    print(f"\nrookie mean reach (R1-10): sim {rk:+.1f}   real {REAL_ROOKIE_MEAN:+.1f}")


def waiver_check(n_per_year=4):
    moves = {i: [] for i in range(12)}
    for year in SEASONS:
        for i in range(n_per_year):
            res = family_league(year, seed=3000 + i)
            for t in res.teams:
                moves[t.idx].append(t.moves)
    print("\n== Waiver adds per season by seat: sim vs real ==")
    for i in range(12):
        sim = sum(moves[i]) / len(moves[i])
        print(f"seat {i:>2}: sim {sim:5.1f}   real {SEAT_SEASON_ADDS[i]:5.1f}")
    tot = sum(sum(v) for v in moves.values()) / sum(len(v) for v in moves.values())
    print(f"league avg: sim {tot:.1f}   real 22.3")


def pickvalue_eyeball(year=2023, seat=5):
    pool, _ = get_pool(year)
    res = family_league(year, seed=7, hero="pick_value", seat=seat)
    hero = res.teams[seat]
    by_pid = {p.pid: p for p in pool}
    print(f"\n== One PickValue draft, {year}, seat {seat + 1} ==")
    for pid, rnd in sorted(hero.drafted_round.items(), key=lambda kv: kv[1]):
        p = by_pid[pid]
        tot = sum(p.week_pts.values())
        adp = f"{p.adp:.0f}" if p.adp else "--"
        print(f"R{rnd:<3}{p.name:<24}{p.pos:<4}adp {adp:<5} season {tot:.0f}")
    print(f"finish: {res.standings.index(hero) + 1}, "
          f"record {hero.record}, moves {hero.moves}")


if __name__ == "__main__":
    draft_log_check()
    waiver_check()
    pickvalue_eyeball()
