"""Second-QB / second-TE sweep (backlog B10, extended to TE).

Question: is a roster better off spending a late pick on a backup
QB/TE — a dart throw you can start on byes, in matchups, or if he
breaks out — than on another RB/WR bench body?

Design: the intervention is a forced pick at a fixed round (or a hard
ban), bolted onto two different base drafters via the SecondArm mixin,
which never touches scoring. Every cell shares the engine, the seeds
and the family field, so within-base comparisons are apples-to-apples
and per-sim results are *paired* (same seed -> same field, same seat).

Run:  venv/bin/python scripts/stash_sweep.py
"""

import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results_stash"

# Both bases get a control rerun in this same batch, so nothing is
# compared across engine versions (see finding 13's version table).
BASE_ARMS = ["bpa",
             "te2_never", "te2_r10", "te2_r12", "te2_r14", "te_darts", "te_punt_only",
             "qb2_never", "qb2_r10", "qb2_r12", "qb2_r14",
             "both_late"]
PV_ARMS = ["pick_value",
           "pv_te2_never", "pv_te2_r12",
           "pv_qb2_never", "pv_qb2_r12", "pv_both"]
HEROES = BASE_ARMS + PV_ARMS

YEARS = range(2020, 2026)
N = 240
SEED = 7


def _cell(job):
    hero, year = job
    from simfl.montecarlo import hero_experiment
    stats = hero_experiment(year, hero, n_sims=N, seed=SEED)
    (OUT / f"{hero}_{year}.json").write_text(json.dumps(stats.to_dict()))
    return hero, year, stats.summary["all_play"]


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    jobs = [(h, y) for h in HEROES for y in YEARS
            if not (OUT / f"{h}_{y}.json").exists()]
    print(f"{len(jobs)} cells, n={N} each ({len(jobs) * N} seasons)")
    with mp.Pool(max(1, mp.cpu_count() - 1)) as pool:
        for hero, year, ap in pool.imap_unordered(_cell, jobs):
            print(f"  {hero:14s} {year} all-play={ap:.3f}", flush=True)
    print("sweep complete")
