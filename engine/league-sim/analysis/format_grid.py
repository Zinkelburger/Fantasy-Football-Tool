"""Every draft strategy, re-run under standard, half-PPR and full-PPR.

The site's draft advice was measured in one format: the family league's
12-team standard scoring. Most readers don't play in one. This runs the
same strategy arms against the same field in all three formats so the
plan can say what actually changes when receptions score.

Two things move together when a league turns on PPR, and both are in
here:

  1. Scoring. Receptions are worth 0, 0.5 or 1 point, which rescores
     every player week and every projection the lineup and waiver
     policies read (simfl/data.load_expected_points takes the reception
     term too — usage is worth more in PPR, not just results).
  2. The draft board. Real PPR drafters price receivers differently, so
     each arm drafts off that format's own FantasyFootballCalculator
     board rather than a standard one. Simulating PPR scoring off a
     standard board measures a mispriced room, not a PPR league.

All three arms take their board from FFC, including standard — the
published standard findings use a deeper archived FantasyPros board for
2025, and a board that runs deeper in one arm changes what the late
rounds see. Comparing formats needs one source across them, so read the
`std` arm here as this sweep's own baseline rather than as a restatement
of the headline standard numbers.

`ppr_teflex` is a fourth arm, not a format: full-PPR scoring plus a
TE-eligible flex, which is how most real PPR leagues are set up. It is
separate so that a format difference never gets confused with a lineup
difference.

  venv/bin/python analysis/format_grid.py --jobs 5
  venv/bin/python analysis/format_grid.py --report
"""

import argparse
import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simfl.config import SCORING_FORMATS, DEFAULT_LEAGUE, TE_FLEX_LEAGUE  # noqa: E402

RESULTS = ROOT / "results_fmt"
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

# fmt key -> (scoring, FFC board, league)
ARMS = {
    "std":  (SCORING_FORMATS["std"],  "standard", DEFAULT_LEAGUE),
    "half": (SCORING_FORMATS["half"], "half-ppr", DEFAULT_LEAGUE),
    "ppr":  (SCORING_FORMATS["ppr"],  "ppr",      DEFAULT_LEAGUE),
    "ppr_teflex": (SCORING_FORMATS["ppr"], "ppr", TE_FLEX_LEAGUE),
}

# The strategies the published draft plan actually rests on. Not the
# full 70: the model-board and rookie arms answer "is our projection
# better than the market", which is a different question and doesn't
# need re-asking per format.
CORE = ["bpa", "family", "robust_rb", "zero_rb", "hero_rb", "wr_heavy",
        "pick_value", "dual_wrrb", "punt_te"]
QB_SWEEP = ["qb_r4", "qb_r6", "qb_r8", "qb_r10", "qb_r12"]
TE_SWEEP = ["te_r3", "te_r5", "te_r8", "te_r10", "te_r12"]

HEROES = {
    "std":  CORE + QB_SWEEP + TE_SWEEP,
    "half": CORE + QB_SWEEP + TE_SWEEP,
    "ppr":  CORE + QB_SWEEP + TE_SWEEP,
    # The TE-flex arm exists to size one lineup change, so it only runs
    # the strategies whose answer could plausibly turn on it.
    "ppr_teflex": CORE + TE_SWEEP,
}


def cell_path(fmt: str, hero: str, year: int) -> Path:
    return RESULTS / f"{fmt}__{hero}_{year}.json"


def _run(job):
    fmt, hero, year, n, seed = job
    from simfl.montecarlo import hero_experiment
    sc, board, league = ARMS[fmt]
    stats = hero_experiment(year, hero, n_sims=n, seed=seed, sc=sc,
                            league=league, adp_fmt=board)
    d = stats.to_dict()
    d["format"] = fmt
    cell_path(fmt, hero, year).write_text(json.dumps(d))
    return fmt, hero, year, stats.summary["title_pct"]


def run(args):
    RESULTS.mkdir(exist_ok=True)
    jobs = [(f, h, y, args.n, args.seed)
            for f in args.formats for h in HEROES[f] for y in YEARS
            if not cell_path(f, h, y).exists()]
    done = sum(len(HEROES[f]) * len(YEARS) for f in args.formats) - len(jobs)
    print(f"{len(jobs)} cells to run, {done} already cached "
          f"({args.jobs} workers, n={args.n}/cell)", flush=True)
    if not jobs:
        return
    with mp.Pool(args.jobs) as pool:
        for i, (f, h, y, t) in enumerate(pool.imap_unordered(_run, jobs), 1):
            print(f"  [{i}/{len(jobs)}] {f:11s} {h:10s} {y}  "
                  f"title={t:.3f}", flush=True)
    print("format grid complete", flush=True)


# ------------------------------------------------------------- reporting
def load(fmt: str, hero: str) -> dict | None:
    """Pool one strategy's cells across seasons, weighting seasons
    equally. Returns None if any season is missing, so a half-finished
    grid can't quietly report a three-season average as a six."""
    cells = []
    for y in YEARS:
        p = cell_path(fmt, hero, y)
        if not p.exists():
            return None
        cells.append(json.loads(p.read_text()))
    n = sum(c["summary"]["n"] for c in cells)
    keys = ("title_pct", "playoff_pct", "all_play", "avg_pf", "avg_finish",
            "avg_wins")
    out = {k: sum(c["summary"][k] for c in cells) / len(cells) for k in keys}
    out["n"] = n
    # 95% interval on the title rate, from the pooled per-sim flags.
    flags = [f for c in cells for f in c["title_flags"]]
    p_hat = sum(flags) / len(flags)
    out["title_ci"] = 1.96 * (p_hat * (1 - p_hat) / len(flags)) ** 0.5
    return out


def report(args):
    formats = args.formats
    rows = []
    for hero in dict.fromkeys(sum(HEROES.values(), [])):
        vals = {f: load(f, hero) for f in formats}
        if all(v is None for v in vals.values()):
            continue
        rows.append((hero, vals))

    for metric, label, scale in (("title_pct", "title %", 100),
                                 ("all_play", "all-play", 100),
                                 ("avg_pf", "points for", 1)):
        print(f"\n=== {label} ===")
        head = f"{'strategy':12s}" + "".join(f"{f:>13s}" for f in formats)
        print(head)
        print("-" * len(head))
        for hero, vals in rows:
            line = f"{hero:12s}"
            for f in formats:
                v = vals[f]
                if v is None:
                    line += f"{'--':>13s}"
                elif metric == "title_pct":
                    line += (f"{v[metric] * scale:>8.1f}"
                             f"±{v['title_ci'] * scale:<4.1f}")
                else:
                    line += f"{v[metric] * scale:>13.1f}"
            print(line)
    print(f"\nSeasons per cell: "
          f"{rows[0][1][formats[0]]['n'] if rows else 0} per strategy-format")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--formats", default="std,half,ppr,ppr_teflex")
    ap.add_argument("-n", type=int, default=240,
                    help="sims per (strategy, season, format) cell")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=max(1, mp.cpu_count() - 3))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    args.formats = args.formats.split(",")
    if args.report:
        report(args)
    else:
        run(args)


if __name__ == "__main__":
    main()
