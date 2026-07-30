"""QB draft-round sweep: when is the best time to take your QB,
against the calibrated family field?

Fresh baseline included (family vs family) so every number in the
sweep comes from the same engine version. Results land in
results_qb/ as JSON, one file per (strategy, year).

Run:  venv/bin/python scripts/qb_sweep.py
"""

import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results_qb"

HEROES = ["family", "qb_r2", "qb_r3", "qb_r4", "qb_r5", "qb_r6",
          "qb_r8", "qb_r10", "qb_r12"]
YEARS = range(2020, 2026)
N = 120
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
    print(f"{len(jobs)} cells, n={N} each")
    with mp.Pool(max(1, mp.cpu_count() - 1)) as pool:
        for hero, year, ap in pool.imap_unordered(_cell, jobs):
            print(f"  {hero:8s} {year} all-play={ap:.3f}", flush=True)
    print("sweep complete")
