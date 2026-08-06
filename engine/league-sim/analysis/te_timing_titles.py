"""Does buying an early TE raise your *title* odds, or just your points?

Finding 33 measured season points: an early TE beat the WR/RB taken at
the same pick 69% of the time. Points are not trophies — a strategy can
add points to a team that was already winning that week and add nothing
to its championship equity. This script runs the missing test.

Design: `te_rN` (simfl/strategies.py) refuses a TE before round N, then
buys the best one left at N — the sim version of "take McBride at his
price". Sweeping N from 2 to 12 walks the elite door (2-4), the hallway
(5-9) and the wait door (10-12) against an identical field.

Every arm runs the same seed sequence, so sim i of year Y faces the same
room, the same seat and the same injuries in every arm. Differences are
taken *within* the pair, which is what makes a 1-point all-play gap
readable at this n. Title rate is a rare binary event and is far noisier
than all-play — the report prints its paired standard error so the
honest "cannot resolve" verdict is visible rather than implied.

Nothing is read from results/: those cells predate the current engine
(season.py changed 2026-08-05), and finding 13's rule is never to
compare across engine versions. Control and arms all run fresh here.

Run:  venv/bin/python analysis/te_timing_titles.py [-n 600]
Feeds finding 33's title-odds section.
"""
import argparse
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

YEARS = range(2020, 2026)
CONTROL = "bpa"
ARMS = ["te_r2", "te_r3", "te_r4", "te_r5", "te_r6", "te_r8",
        "te_r10", "te_r12", "te_r10_stream"]
DOOR = {"te_r2": "elite", "te_r3": "elite", "te_r4": "elite",
        "te_r5": "hallway", "te_r6": "hallway", "te_r8": "hallway",
        "te_r10": "wait", "te_r12": "wait", "te_r10_stream": "wait+stream"}
OUT = ROOT / "data" / "market" / "te_timing_titles.json"


def _cell(job):
    arm, year, n, seed = job
    from simfl.montecarlo import hero_experiment
    s = hero_experiment(year, arm, n_sims=n, seed=seed)
    d = s.to_dict()
    return arm, year, (list(d["all_plays"]), list(d["title_flags"]),
                       list(d["pfs"]))


def run(n, seed, jobs):
    cells = [(a, y, n, seed) for a in [CONTROL] + ARMS for y in YEARS]
    print(f"{len(cells)} cells ({len(ARMS) + 1} arms x {len(list(YEARS))} "
          f"seasons x {n} sims), {jobs} workers")
    got = {}
    with mp.Pool(jobs) as pool:
        for i, (arm, year, payload) in enumerate(
                pool.imap_unordered(_cell, cells), 1):
            got.setdefault(arm, {})[year] = payload
            print(f"  [{i}/{len(cells)}] {arm} {year}", flush=True)
    # concatenate years in a fixed order so arms stay paired sim-for-sim
    out = {}
    for arm, per_year in got.items():
        ap, ti, pf = [], [], []
        for y in YEARS:
            a, t, p = per_year[y]
            ap += a
            ti += t
            pf += p
        out[arm] = dict(all_play=ap, titles=ti, pf=pf)
    return out


def reach_report():
    """How far above market each arm buys its TE — the confound.

    Forcing a TE at round 2 means taking the TE1 ~10 picks before the
    board says he goes, so that arm is partly measuring finding 03's
    reaching penalty rather than the position itself. Round 3 lands him
    at par, which is the clean "take McBride at his ADP" test; rounds
    4+ take him at a discount. Read the sweep through this table.
    """
    import random

    from simfl.config import DEFAULT_LEAGUE, DEFAULT_SCORING
    from simfl.draft import run_draft
    from simfl.models import Team
    from simfl.montecarlo import get_pool
    from simfl.strategies import make

    print(f"\n{'-' * 74}\nPrice paid for the TE (+ = reached above "
          "market, - = got him at a discount)")
    for arm in ARMS + [CONTROL]:
        gaps, names = [], []
        for year in YEARS:
            pool, table = get_pool(year, DEFAULT_SCORING)
            for i in range(12):
                rng = random.Random((0, year, i).__hash__() & 0x7FFFFFFF)
                seat = i % 12
                strat = [make("family") for _ in range(12)]
                strat[seat] = make(arm)
                for s in strat:
                    s.bind_year(year)
                teams = [Team(idx=j, name=f"t{j}", strategy=strat[j])
                         for j in range(12)]
                log = run_draft(list(pool), teams, DEFAULT_LEAGUE, rng)
                t = teams[seat]
                tes = [(t.drafted_round[p.pid], p) for p in t.roster
                       if p.pos == "TE"]
                if not tes:
                    continue
                _, p = min(tes, key=lambda x: x[0])
                pk = next(o for o, _tm, pl in log if pl is p)
                gaps.append(p.draft_rank - pk)
                names.append(p.name)
        top = max(set(names), key=names.count)
        print(f"  {arm:<15} {np.mean(gaps):+6.1f} picks   "
              f"(most often: {top})")


def paired(a, b):
    """mean paired difference and its standard error."""
    d = np.asarray(a) - np.asarray(b)
    se = d.std(ddof=1) / np.sqrt(len(d))
    return d.mean(), se


def report(data):
    ctl = data[CONTROL]
    n = len(ctl["titles"])
    print(f"\n{'=' * 74}\nTE TIMING vs CONTROL ({CONTROL}), paired, "
          f"n={n} seasons per arm")
    print(f"control: all-play {np.mean(ctl['all_play']):.4f}  "
          f"titles {np.mean(ctl['titles']):.3%}  "
          f"pf {np.mean(ctl['pf']):.0f}")
    print(f"\n{'arm':<15}{'door':<13}{'all-play':>9}{'vs ctl':>9}"
          f"{'±se':>7}   {'titles':>7}{'vs ctl':>8}{'±se':>7}  verdict")
    for arm in ARMS:
        d = data[arm]
        dap, sap = paired(d["all_play"], ctl["all_play"])
        dti, sti = paired(d["titles"], ctl["titles"])
        t = dap / sap if sap else 0.0
        verdict = ("all-play SIGNIF" if abs(t) >= 2 else "within noise")
        print(f"{arm:<15}{DOOR[arm]:<13}"
              f"{np.mean(d['all_play']):>9.4f}{dap:>+9.4f}{sap:>7.4f}   "
              f"{np.mean(d['titles']):>7.2%}{dti:>+8.2%}{sti:>7.2%}  "
              f"{verdict}")

    print(f"\n{'-' * 74}\nHead-to-head: elite door vs wait door "
          "(the actual decision)")
    for a, b in (("te_r2", "te_r10_stream"), ("te_r3", "te_r10_stream"),
                 ("te_r2", "te_r12"), ("te_r6", "te_r10_stream")):
        dap, sap = paired(data[a]["all_play"], data[b]["all_play"])
        dti, sti = paired(data[a]["titles"], data[b]["titles"])
        print(f"  {a:<14} - {b:<14} all-play {dap:+.4f} ± {sap:.4f}"
              f"   titles {dti:+.2%} ± {sti:.2%}")

    reach_report()

    # What a title-rate difference would have to be to be visible here.
    se_ti = paired(data["te_r2"]["titles"], ctl["titles"])[1]
    print(f"\nResolution check: the paired standard error on title rate "
          f"is {se_ti:.2%},\nso this run can only resolve title swings "
          f"bigger than ~{2 * se_ti:.1%}. Smaller true effects are "
          f"invisible\nat this n — read those cells as 'unresolved', "
          f"not 'zero'.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=600, help="sims per year/arm")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=max(1, mp.cpu_count() - 1))
    ap.add_argument("--reuse", action="store_true",
                    help="report from the saved json instead of re-running")
    a = ap.parse_args()

    if a.reuse and OUT.exists():
        data = json.loads(OUT.read_text())
    else:
        data = run(a.n, a.seed, a.jobs)
        OUT.write_text(json.dumps(data))
        print(f"\nraw per-sim arrays -> {OUT}")
    report(data)


if __name__ == "__main__":
    main()
