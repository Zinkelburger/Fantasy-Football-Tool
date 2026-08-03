"""What is the waiver wire actually worth, in points?

No invented labels. Run the identical drafter through identical seasons
against an identical field, once using the wire and once forbidden from
touching it, and read the difference off the scoreboard.

That difference is the whole answer to "should I draft depth or lean on
the wire" — it is denominated in the only unit that wins games, it
respects churn (a bad add gets dropped next week, exactly as you would),
and every decision inside it is made on information available at the
time (`fa_proj`: production only, no pedigree, no future).

Also reported, since it is what you actually experience at the keyboard:
of the players we claim, how long do we keep them and what do they score
while we hold them.

Run:  venv/bin/python analysis/wire_worth.py
"""

import random
import statistics as st
from collections import defaultdict

from common import SEASONS

from simfl.config import DEFAULT_LEAGUE as LG
from simfl.montecarlo import get_pool
from simfl.season import run_season
from simfl.strategies import make

N_SIMS = 60
SEED = 17
PAIRS = [("pick_value", "pick_value_nowire"),
         ("robust_rb", "robust_rb_nowire"),
         ("bpa", "bpa_nowire")]
SLOTS = ("QB", "RB", "WR", "TE", "FLEX", "K")
LAST_WEEK = 14


def run_one(year, hero, seat, i, pool, table):
    rng = random.Random((SEED, year, i).__hash__() & 0x7FFFFFFF)
    strat = [make("family") for _ in range(LG.n_teams)]
    strat[seat] = make(hero)
    for s in strat:
        s.bind_year(year)
    return run_season(pool, strat, LG, table, rng)


def main():
    print(f"{N_SIMS} sims x {len(SEASONS)} seasons per arm, paired on seed:")
    print("identical draft, identical field, identical schedule -- the only")
    print("difference is whether the hero may use the waiver wire.\n")

    print("=" * 72)
    print("WHAT THE WIRE IS WORTH (season points in the starting lineup)")
    print("=" * 72 + "\n")
    print(f"{'drafter':14s}{'with wire':>11s}{'no wire':>10s}{'gain':>8s}"
          f"{'±95%':>8s}{'all-play':>10s}{'Δ':>7s}{'claims':>8s}")

    slot_delta = {}
    for hero, nowire in PAIRS:
        pf_w, pf_n, ap_w, ap_n, claims = [], [], [], [], []
        sd = defaultdict(list)
        for year in SEASONS:
            pool, table = get_pool(year)
            for i in range(N_SIMS):
                seat = i % LG.n_teams
                a = run_one(year, hero, seat, i, pool, table)
                b = run_one(year, nowire, seat, i, pool, table)
                ta, tb = a.teams[seat], b.teams[seat]
                pf_w.append(ta.points_for)
                pf_n.append(tb.points_for)
                ap_w.append(ta.all_play_pct)
                ap_n.append(tb.all_play_pct)
                claims.append(ta.moves)
                for s in SLOTS:
                    sd[s].append(a.slot_points[seat].get(s, 0.0)
                                 - b.slot_points[seat].get(s, 0.0))
        d = [x - y for x, y in zip(pf_w, pf_n)]
        ci = 1.96 * st.stdev(d) / len(d) ** 0.5
        da = st.mean(ap_w) - st.mean(ap_n)
        print(f"{hero:14s}{st.mean(pf_w):11.0f}{st.mean(pf_n):10.0f}"
              f"{st.mean(d):+8.0f}{ci:8.0f}"
              f"{st.mean(ap_w):10.3f}{da:+7.3f}{st.mean(claims):8.1f}")
        slot_delta[hero] = {s: st.mean(v) for s, v in sd.items()}

    print("\nWhere those points land (season pts by lineup slot, with - without):\n")
    print(f"{'drafter':14s}" + "".join(f"{s:>9s}" for s in SLOTS))
    for hero, _ in PAIRS:
        print(f"{hero:14s}" + "".join(f"{slot_delta[hero][s]:+9.0f}" for s in SLOTS))

    print("\n" + "=" * 72)
    print("WHAT A CLAIM LOOKS LIKE FROM THE KEYBOARD")
    print("(the players we actually add: how long we keep them, what they")
    print(" score for us while we do)")
    print("=" * 72 + "\n")
    held, ppw, dropped_fast = defaultdict(list), defaultdict(list), defaultdict(list)
    for year in SEASONS:
        pool, table = get_pool(year)
        for i in range(N_SIMS):
            seat = i % LG.n_teams
            res = run_one(year, "pick_value", seat, i, pool, table)
            hero = res.teams[seat]
            drop_wk = {}
            for (wk, team, add, drop) in res.transactions:
                if team is hero:
                    drop_wk.setdefault(drop.pid, wk)
            for (wk, team, add, drop) in res.transactions:
                if team is not hero or add.pos not in ("QB", "RB", "WR", "TE"):
                    continue
                end = drop_wk.get(add.pid, LAST_WEEK)
                weeks = [k for k in range(wk + 1, min(end, LAST_WEEK) + 1)]
                if not weeks:
                    continue
                pts = sum(add.points(k) for k in weeks)
                held[add.pos].append(len(weeks))
                ppw[add.pos].append(pts / len(weeks))
                dropped_fast[add.pos].append(len(weeks) <= 2)
    print(f"{'pos':6s}{'adds':>8s}{'wks held':>11s}{'pts/wk held':>14s}"
          f"{'median':>9s}{'p90':>7s}{'cut within 2wk':>17s}")
    for pos in ("QB", "RB", "WR", "TE"):
        v = ppw[pos]
        if not v:
            continue
        sv = sorted(v)
        print(f"{pos:6s}{len(v):8d}{st.mean(held[pos]):11.1f}"
              f"{st.mean(v):14.1f}{st.median(v):9.1f}"
              f"{sv[int(0.9 * len(sv))]:7.1f}"
              f"{st.mean(dropped_fast[pos]):16.0%}")


if __name__ == "__main__":
    main()
