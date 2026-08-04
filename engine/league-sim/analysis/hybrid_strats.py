"""Hybrid strategies in the calibrated family room, paired seeds.
rb3_pv = RB-RB-RB then pick_value; pv_late_qb = pick_value, no QB < r6."""
import statistics as st
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from common import SEASONS
from simfl.montecarlo import hero_experiment

HEROES = ("robust_rb", "pick_value", "rb3_pv", "pv_late_qb")
N = 72

per_hero = {h: {"ap": [], "ti": [], "po": [], "pf": [], "wins": [],
                "aps": []} for h in HEROES}
for hero in HEROES:
    for year in SEASONS:
        s = hero_experiment(year, hero, n_sims=N, seed=3)
        d = s.summary
        per_hero[hero]["ap"].append(d["all_play"])
        per_hero[hero]["ti"].append(d["title_pct"])
        per_hero[hero]["po"].append(d["playoff_pct"])
        per_hero[hero]["pf"].append(d["avg_pf"])
        per_hero[hero]["wins"].append(d["avg_wins"])
        per_hero[hero]["aps"].extend(s.all_plays)
    print(f"done {hero}", flush=True)

print(f"\n{'hero':12s}{'record':>9s}{'PF/yr':>8s}{'all-play':>10s}"
      f"{'playoffs':>10s}{'title':>8s}")
for hero in HEROES:
    r = {k: st.mean(v) for k, v in per_hero[hero].items() if k != "aps"}
    print(f"{hero:12s}{r['wins']:5.1f}-{14-r['wins']:.1f}{r['pf']:8.0f}"
          f"{r['ap']:10.3f}{r['po']:10.0%}{r['ti']:8.0%}")

print("\npaired diffs (all-play, 95% CI):")
base = per_hero["pick_value"]["aps"]
for hero in ("rb3_pv", "pv_late_qb", "robust_rb"):
    diffs = [a - b for a, b in zip(per_hero[hero]["aps"], base)]
    ci = 1.96 * st.stdev(diffs) / len(diffs) ** 0.5
    print(f"  {hero:12s} - pick_value: {st.mean(diffs):+.4f} ± {ci:.4f}")
base = per_hero["robust_rb"]["aps"]
for hero in ("rb3_pv", "pv_late_qb"):
    diffs = [a - b for a, b in zip(per_hero[hero]["aps"], base)]
    ci = 1.96 * st.stdev(diffs) / len(diffs) ** 0.5
    print(f"  {hero:12s} - robust_rb:  {st.mean(diffs):+.4f} ± {ci:.4f}")
