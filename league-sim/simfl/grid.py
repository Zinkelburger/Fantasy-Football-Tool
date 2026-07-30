"""Parallel backtest grid: every (strategy, season) cell as a separate
process, results saved as JSON under league-sim/results/ so figures and
tables can be rebuilt without re-simulating. Resumable: existing cells
are skipped.

  python -m simfl.grid --years 2020-2025 --heroes all -n 240
"""

import argparse
import json
import multiprocessing as mp
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def _cell(job):
    hero, year, n, seed = job
    from .montecarlo import hero_experiment
    stats = hero_experiment(year, hero, n_sims=n, seed=seed)
    out = RESULTS_DIR / f"{hero}_{year}.json"
    out.write_text(json.dumps(stats.to_dict()))
    return hero, year, stats.summary["all_play"]


def main():
    from .cli import parse_years
    from .strategies import STRATEGIES
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2020-2025")
    ap.add_argument("--heroes", default="all")
    ap.add_argument("-n", type=int, default=240)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=max(1, mp.cpu_count() - 1))
    args = ap.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    years = parse_years(args.years)
    heroes = list(STRATEGIES) if args.heroes == "all" else args.heroes.split(",")
    jobs = [(h, y, args.n, args.seed) for h in heroes for y in years
            if not (RESULTS_DIR / f"{h}_{y}.json").exists()]
    print(f"{len(jobs)} cells to run ({args.jobs} workers, n={args.n})")
    with mp.Pool(args.jobs) as pool:
        for hero, year, ap_ in pool.imap_unordered(_cell, jobs):
            print(f"  done {hero:10s} {year}  all-play={ap_:.3f}", flush=True)
    print("grid complete")


if __name__ == "__main__":
    main()
