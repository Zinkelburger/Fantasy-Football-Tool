"""Paired significance test for two draft-strategy arms.

`simfl compare` prints pooled means, which is enough to see a big gap
(the pure model board) but not a small one. Every arm runs on the same
seed sequence, so the per-simulation results are paired: sim i of year
Y faces the same room, the same seat and the same injury draws in both
arms. Differencing within the pair removes almost all the variance
that makes the pooled means look noisy.

Reports mean paired difference in all-play, points-for and title rate
with a standard error, so "0.598 vs 0.595" gets an honest verdict.

Usage: paired_arm_test.py <arm> [<baseline>]     (default baseline bpa)
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from simfl.montecarlo import hero_experiment          # noqa: E402

YEARS = range(2020, 2026)
N_SIMS = 300
SEED = 0


def collect(hero):
    ap, pf, ti = [], [], []
    for year in YEARS:
        s = hero_experiment(year, hero, n_sims=N_SIMS, seed=SEED)
        d = s.to_dict()
        ap += list(d["all_plays"])
        pf += list(d["pfs"])
        ti += list(d["title_flags"])
    return np.array(ap), np.array(pf), np.array(ti)


def main():
    arm = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else "bpa"
    print(f"{arm} vs {base}: {len(list(YEARS))} seasons x {N_SIMS} sims, "
          f"paired on seed {SEED}\n")

    a_ap, a_pf, a_ti = collect(arm)
    b_ap, b_pf, b_ti = collect(base)

    for label, a, b, fmt in (("all-play", a_ap, b_ap, "+.4f"),
                             ("points-for", a_pf, b_pf, "+.1f"),
                             ("title rate", a_ti, b_ti, "+.4f")):
        d = a - b
        se = d.std(ddof=1) / np.sqrt(len(d))
        t = d.mean() / se if se else 0.0
        verdict = ("SIGNIFICANT" if abs(t) >= 2
                   else "within noise")
        print(f"{label:11s} {arm}={a.mean():8.4f}  {base}={b.mean():8.4f}  "
              f"diff={d.mean():{fmt}} ± {se:.4f}  (t={t:+.2f}) {verdict}")


if __name__ == "__main__":
    main()
