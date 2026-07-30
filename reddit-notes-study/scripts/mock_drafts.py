"""Step 3: mock-draft backtest — do the notes improve actual drafting?

Simulates the Go tool's workflow: at every pick you see the next 10
players by ADP plus their note files. Five hero strategies differ ONLY
in how they use note tone inside that window; each plays 240 full
seasons (snake draft at a rotating seat vs 11 family-calibrated bots,
week-by-week season, waivers, playoffs) per year on league-sim.

  bpa         pure ADP order, sane need-filling      (control)
  notes_hard  always take the best-noted of next 10  (notes as override)
  notes_soft  tone nudges perceived rank 8%/point    (notes as tiebreak)
  notes_anti  always take the WORST-noted of next 10 (sign control)
  rand_10     random legal pick from next 10         (deviation-cost control)

Common random numbers: hero strategies consume no RNG in scoring, so
every hero faces the IDENTICAL sequence of rooms and the per-sim paired
delta vs bpa is exact. (rand_10 draws RNG, breaking pairing slightly —
its CI is still valid, just not variance-reduced.)

Run:  ../../league-sim/venv/bin/python mock_drafts.py 240 > ../results/mock_draft_output.txt
"""
import sys, json, re, unicodedata
from pathlib import Path
import pandas as pd

STUDY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY.parent / "league-sim"))
DATA = STUDY / "data"

from simfl import strategies as st
from simfl.montecarlo import hero_experiment, get_pool

def norm(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    n = n.lower().replace(".", "").replace("'", "").replace("-", " ")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()

# sentiment maps {year: {norm_name: s}} — scores are year-keyed
sc = pd.read_csv(DATA / "sentiment_scores.csv")
SMAPS = {}
for y in (2024, 2025):
    j = pd.read_csv(DATA / f"joined_{y}.csv")
    j = j.merge(sc[sc.year == y][["note_name", "s"]], on="note_name")
    SMAPS[y] = dict(zip(j.key, j.s))

class NotesBase(st.DraftStrategy):
    window = 10   # the 'next 10' list the Go tool displays
    def bind_year(self, year):
        self.smap = SMAPS.get(year, {})
    def _s(self, p):
        return self.smap.get(norm(p.name), 0)

class NotesHard(NotesBase):
    name, label = "notes_hard", "Notes: best of next 10"
    def score(self, p, rnd, team, state, rng):
        return super().score(p, rnd, team, state, rng) - 1e6 * self._s(p)

class NotesSoft(NotesBase):
    name, label = "notes_soft", "Notes: nudge (8%/point)"
    def score(self, p, rnd, team, state, rng):
        return super().score(p, rnd, team, state, rng) * (1 - 0.08 * self._s(p))

class NotesAnti(NotesBase):
    name, label = "notes_anti", "Anti-notes: worst of next 10"
    def score(self, p, rnd, team, state, rng):
        return super().score(p, rnd, team, state, rng) + 1e6 * self._s(p)

class RandWindow(st.DraftStrategy):
    """Deviation-cost control: random legal pick from the next 10."""
    name, label, window = "rand_10", "Random of next 10", 10
    def score(self, p, rnd, team, state, rng):
        return rng.random()

for cls in (NotesHard, NotesSoft, NotesAnti, RandWindow):
    st.STRATEGIES[cls.name] = cls

for y in (2024, 2025):
    pool, _ = get_pool(y)
    board = sorted([p for p in pool if p.adp is not None], key=lambda p: p.adp)[:150]
    hit = sum(1 for p in board if norm(p.name) in SMAPS[y])
    nz = sum(1 for p in board if SMAPS[y].get(norm(p.name), 0) != 0)
    print(f"{y}: top-150 ADP board -> {hit} have note files, {nz} with nonzero tone")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 240
HEROES = ["bpa", "notes_hard", "notes_soft", "notes_anti", "rand_10"]
results = {}
for hero in HEROES:
    for y in (2024, 2025):
        stats = hero_experiment(y, hero, n_sims=N, seed=0)
        results[(hero, y)] = stats
        s = stats.summary
        print(f"{hero:11s} {y}: wins {s['avg_wins']:.2f}  PF {s['avg_pf']:.0f}  "
              f"all-play {s['all_play']:.3f}  playoffs {s['playoff_pct']:.0%}  "
              f"titles {s['title_pct']:.1%}  avg finish {s['avg_finish']:.2f}")

import statistics as stat
print("\n=== Paired vs pure-ADP control (same rooms, same seeds) ===")
for hero in HEROES[1:]:
    for y in (2024, 2025):
        b, h = results[("bpa", y)], results[(hero, y)]
        dpf = [x - y2 for x, y2 in zip(h.pfs, b.pfs)]
        dap = [x - y2 for x, y2 in zip(h.all_plays, b.all_plays)]
        mpf = stat.mean(dpf); se = stat.stdev(dpf) / len(dpf) ** 0.5
        map_ = stat.mean(dap); sea = stat.stdev(dap) / len(dap) ** 0.5
        print(f"{hero:11s} {y}: dPF {mpf:+7.1f} +/- {1.96*se:5.1f}   "
              f"dAllPlay {map_:+.3f} +/- {1.96*sea:.3f}   "
              f"better/worse rooms: {sum(d > 0 for d in dpf)}/{sum(d < 0 for d in dpf)}")

json.dump({f"{h}_{y}": results[(h, y)].to_dict() for h, y in results},
          open(DATA / "mock_results.json", "w"))
