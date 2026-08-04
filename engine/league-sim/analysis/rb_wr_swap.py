"""The cleanest RB-vs-WR test the sim can run: identical disciplined
drafter, identical seeds, but at exactly one early round the pick is
forced RB vs forced WR. Paired diff = the season-long worth of that one
positional call, waivers/injuries/lineups included."""
import random
import statistics as st
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from common import SEASONS
from simfl import strategies as S
from simfl.montecarlo import hero_experiment, get_pool
from simfl.config import DEFAULT_LEAGUE as LG
from simfl.models import Team
from simfl.draft import run_draft
from simfl.strategies import make

N = 72


def register(pos, rnd_t):
    name = f"force_{pos.lower()}_r{rnd_t}"

    def banned(self, p, rnd, team, state, _pos=pos, _r=rnd_t):
        if rnd == _r and p.pos != _pos:
            return True
        return S.DraftStrategy.banned(self, p, rnd, team, state)

    S.STRATEGIES[name] = type(name, (S.DraftStrategy,), {
        "name": name, "label": name, "banned": banned})
    return name


variants = {(pos, r): register(pos, r)
            for r in (1, 2, 3) for pos in ("RB", "WR")}

aps = {}
for (pos, r), name in variants.items():
    acc = []
    for year in SEASONS:
        s = hero_experiment(year, name, n_sims=N, seed=3)
        acc.extend(s.all_plays)
    aps[(pos, r)] = acc
    print(f"done {name}", flush=True)

print("\nforced RB vs forced WR at one pick (same seeds, all else equal):")
for r in (1, 2, 3):
    diffs = [a - b for a, b in zip(aps[("RB", r)], aps[("WR", r)])]
    ci = 1.96 * st.stdev(diffs) / len(diffs) ** 0.5
    m_rb = st.mean(aps[("RB", r)])
    m_wr = st.mean(aps[("WR", r)])
    print(f"  round {r}: RB {m_rb:.3f}  WR {m_wr:.3f}  "
          f"paired diff {st.mean(diffs):+.4f} ± {ci:.4f}")

# context: who actually gets taken at the forced pick
print("\nwho the forced pick buys (median positional rank by ADP):")
for r in (1, 2, 3):
    for pos in ("RB", "WR"):
        ranks = []
        for year in SEASONS:
            pool, _ = get_pool(year)
            posrank = {}
            for p in sorted([q for q in pool if q.pos == pos and q.adp],
                            key=lambda q: q.adp):
                posrank[p.pid] = len(posrank) + 1
            for i in range(12):
                rng = random.Random(year * 29 + i)
                strat = [make("family") for _ in range(12)]
                seat = i % 12
                strat[seat] = make(variants[(pos, r)])
                for s in strat:
                    s.bind_year(year)
                teams = [Team(idx=j, name=str(j), strategy=s)
                         for j, s in enumerate(strat)]
                run_draft(pool, teams, LG, rng)
                t = teams[seat]
                by = {p.pid: p for p in t.roster}
                for pid, rnd in t.drafted_round.items():
                    if rnd == r and by[pid].pos == pos:
                        ranks.append(posrank.get(pid, 99))
        print(f"  round {r} {pos}: median {pos}{int(st.median(ranks))} "
              f"(p25 {pos}{int(sorted(ranks)[len(ranks)//4])}, "
              f"p75 {pos}{int(sorted(ranks)[3*len(ranks)//4])})")
