"""Read results_stash/ and report the second-QB / second-TE sweep.

Every arm shares its base drafter's seed sequence, so sim i of arm A
and sim i of arm B saw the same field from the same seat. Differences
are therefore *paired*, which kills most of the season-to-season
variance that swamps unpaired all-play CIs at this sample size.

Run:  venv/bin/python scripts/stash_report.py
"""

import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RES = ROOT / "results_stash"
YEARS = range(2020, 2026)

BASE = ["bpa", "te2_never", "te2_r10", "te2_r12", "te2_r14", "te_punt_only", "te_darts",
        "qb2_never", "qb2_r10", "qb2_r12", "qb2_r14", "both_late"]
PV = ["pick_value", "pv_te2_never", "pv_te2_r12",
      "pv_qb2_never", "pv_qb2_r12", "pv_both"]
LABELS = {
    "bpa": "control (base drafter)", "te2_never": "never a 2nd TE",
    "te2_r10": "2nd TE @ r10", "te2_r12": "2nd TE @ r12",
    "te2_r14": "2nd TE @ r14", "te_darts": "punt TE, 2 darts (r10+r12)",
    "te_punt_only": "punt TE to r10, single TE",
    "qb2_never": "never a 2nd QB", "qb2_r10": "2nd QB @ r10",
    "qb2_r12": "2nd QB @ r12", "qb2_r14": "2nd QB @ r14",
    "both_late": "2nd TE r12 + 2nd QB r13",
    "pick_value": "control (pick_value)",
    "pv_te2_never": "never a 2nd TE", "pv_te2_r12": "2nd TE @ r12",
    "pv_qb2_never": "never a 2nd QB", "pv_qb2_r12": "2nd QB @ r12",
    "pv_both": "2nd TE r12 + 2nd QB r13",
}


def load(hero):
    ap, playoffs, titles, n, fin = [], 0, 0, 0, []
    for y in YEARS:
        d = json.loads((RES / f"{hero}_{y}.json").read_text())
        ap += d["all_plays"]
        fin += d["finishes"]
        playoffs += d["playoffs"]
        titles += d["titles"]
        n += d["summary"]["n"]
    return {"ap": ap, "n": n, "playoff": playoffs / n, "title": titles / n,
            "finish": statistics.mean(fin)}


def table(arms, control):
    c = load(control)
    rows = []
    for h in arms:
        a = load(h)
        d = [x - y for x, y in zip(a["ap"], c["ap"])]
        m = statistics.mean(d)
        ci = 1.96 * statistics.stdev(d) / math.sqrt(len(d)) if h != control else 0.0
        rows.append((h, a, m * 100, ci * 100))
    print(f"{'arm':30s}{'all-play':>10s}{'vs ctrl':>10s}{'±95%':>8s}"
          f"{'playoff':>10s}{'title':>8s}{'finish':>8s}")
    print("-" * 84)
    for h, a, m, ci in rows:
        star = "" if h == control else ("  *" if abs(m) > ci else "")
        print(f"{LABELS[h]:30s}{statistics.mean(a['ap']):10.3f}"
              f"{m:+10.2f}{ci:8.2f}{a['playoff']:10.1%}{a['title']:8.1%}"
              f"{a['finish']:8.2f}{star}")
    print(f"n = {rows[0][1]['n']} seasons per arm; 'vs ctrl' is paired "
          f"all-play in points (x100). * = CI excludes 0.")


def contrast(a_name, b_name, note):
    """The clean A/B: forced-two minus never-two, paired."""
    a, b = load(a_name), load(b_name)
    d = [x - y for x, y in zip(a["ap"], b["ap"])]
    m = statistics.mean(d) * 100
    ci = 1.96 * statistics.stdev(d) / math.sqrt(len(d)) * 100
    verdict = "REAL" if abs(m) > ci else "noise"
    print(f"  {note:44s}{m:+7.2f} ± {ci:.2f}   {verdict}"
          f"   titles {a['title']:.1%} vs {b['title']:.1%}")


if __name__ == "__main__":
    print("\n### Base drafter\n")
    table(BASE, "bpa")
    print("\n### On top of pick_value (the wait-cost drafter)\n")
    table(PV, "pick_value")
    print("\n### Head-to-head: forcing the 2nd vs banning it (paired)\n")
    contrast("te2_r12", "te2_never", "TE2 @ r12  -  no TE2      [base]")
    contrast("qb2_r12", "qb2_never", "QB2 @ r12  -  no QB2      [base]")
    contrast("pv_te2_r12", "pv_te2_never", "TE2 @ r12  -  no TE2      [pick_value]")
    contrast("pv_qb2_r12", "pv_qb2_never", "QB2 @ r12  -  no QB2      [pick_value]")
    contrast("te_darts", "te_punt_only", "2nd dart  -  single TE, both punting to r10")
    contrast("te_punt_only", "bpa", "punt TE1 to r10  -  normal TE1 timing")
    print()
