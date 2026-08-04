"""SUPERSEDED by analysis/wire_sim.py -- see finding 22.

This script drains the undrafted pool by the league's real claim volume
but never puts anyone back, while the real league drops as many players
as it adds (1,605 acquisitions vs 1,634 drops, 2020-25) and clears
roster spots when a player is out for the year. Its levels are
therefore biased low, most severely late in the season, and its "TE
dries up" conclusion was an artifact of that. Kept for the ESPN
claim-volume extraction and the room-behavior bracket, which stand.

What is REALLY on the waiver wire, once eleven other managers have
picked it over?

`waiver_pool.py` measures the ceiling: the best undrafted player, as if
he were always yours for the taking. This measures the floor you can
actually stand on, by depleting the pool week by week at the real
league's observed claim volume.

Grounded in the league's own history:
  - the exact post-draft free-agent pool     (picks.parquet, 192 real picks/yr)
  - the exact number of claims made each week (ESPN matchupAcquisitionTotals,
    ~19/week across the 12 teams)

Modeled (because ESPN's export records claim *counts*, never *which
player*): the rule managers use to choose. We bracket it with three
rules rather than pick one, so the answer is a range, not a guess:

  chaser   - claim last week's biggest scorers (the calibrated family
             behavior, waivers.PointsChaser)
  sharp    - claim the best rest-of-season player available (hindsight;
             an unrealistically efficient room = pessimistic for you)
  random   - claim uniformly at random (an inattentive room = optimistic)

Reported: the best player still available at each position, by week,
under each rule -- i.e. the honest replacement level a drafter should
assume when valuing his own bench.

Run:  venv/bin/python analysis/wire_contention.py
"""

import json
import random
import statistics as st

import polars as pl

from common import ROOT, SEASONS, league_drafted, weekly

WEEKS = range(1, 15)          # regular season
POS = ("QB", "RB", "WR", "TE")
RULES = ("chaser", "sharp", "random")
N_SEEDS = 20                  # random rule is stochastic; average it


def claims_per_week(year: int) -> dict[int, int]:
    """Real league-wide claim count per scoring period, from ESPN."""
    d = json.loads((ROOT / "data" / "espn" / f"league_{year}.json").read_text())
    out: dict[int, int] = {}
    for t in d["teams"]:
        for wk, n in (t["transactionCounter"].get("matchupAcquisitionTotals") or {}).items():
            out[int(wk)] = out.get(int(wk), 0) + int(n)
    return out


def pool_frames(year: int):
    """(points[pid][week], pos[pid], ros_total[pid]) for undrafted players."""
    drafted = league_drafted(year)
    wk = weekly(year).filter(~pl.col("nname").is_in(list(drafted)),
                             pl.col("position").is_in(POS))
    pts: dict[str, dict[int, float]] = {}
    pos: dict[str, str] = {}
    for r in wk.select("player_id", "position", "week", "fpts").iter_rows(named=True):
        pts.setdefault(r["player_id"], {})[r["week"]] = float(r["fpts"])
        pos[r["player_id"]] = r["position"]
    ros = {p: sum(v for w, v in d.items() if w >= 4) for p, d in pts.items()}
    return pts, pos, ros


def simulate(year: int, rule: str, rng: random.Random):
    """Deplete the FA pool week by week; record the best available at
    each position going into each week."""
    pts, pos, ros = pool_frames(year)
    claims = claims_per_week(year)
    available = set(pts)
    best: dict[int, dict[str, float]] = {}

    for w in WEEKS:
        # What the pool offers THIS week, before this week's claims.
        cur: dict[str, float] = {}
        for pid in available:
            p = pts[pid].get(w)
            if p is not None:
                cur[pos[pid]] = max(cur.get(pos[pid], 0.0), p)
        best[w] = cur

        n = claims.get(w, 0)
        if not n or not available:
            continue
        if rule == "chaser":            # last week's big scorers
            key = lambda pid: pts[pid].get(w - 1, 0.0)
        elif rule == "sharp":           # best rest-of-season (hindsight)
            key = lambda pid: ros.get(pid, 0.0)
        else:                           # random
            key = lambda pid: rng.random()
        taken = sorted(available, key=key, reverse=True)[:n]
        available.difference_update(taken)
    return best


def realized(year: int, rule: str, rng: random.Random, queue: int = 1):
    """What a manager actually GETS, not what was theoretically there.

    Identical depletion, but the weekly pick is made on leak-free
    projection (the sim's own `fa_proj`) and scored on what he then
    really did. This is the number comparable to a rostered starter's
    output; `simulate()`'s max-over-pool is a hindsight ceiling.

    `queue` is this manager's waiver priority that week: with queue=1 he
    gets first look at everything that survived earlier weeks; with
    queue=k the k-1 teams ahead of him claim first (by the room's rule).
    Reverse-standings priority means a real manager cycles through these,
    so the truth is a band, not the queue=1 row.
    """
    from simfl.data import norm_name
    from simfl.montecarlo import get_pool

    pool, table = get_pool(year)
    drafted = league_drafted(year)
    fas = {p.pid: p for p in pool
           if p.pos in POS and norm_name(p.name) not in drafted}
    ros = {pid: sum(v for w, v in p.week_pts.items() if w >= 4)
           for pid, p in fas.items()}
    claims = claims_per_week(year)
    available = set(fas)
    got: dict[int, dict[str, float]] = {}

    for w in WEEKS:
        if rule == "chaser":
            key = lambda pid: fas[pid].points(w - 1) if w > 1 else 0.0
        elif rule == "sharp":
            key = lambda pid: ros.get(pid, 0.0)
        else:
            key = lambda pid: rng.random()
        ranked = sorted(available, key=key, reverse=True)

        # Teams ahead of me in the queue claim before I do.
        ahead = set(ranked[:max(0, queue - 1)])
        mine = available - ahead
        cur: dict[str, float] = {}
        for pos in POS:
            cands = [fas[pid] for pid in mine
                     if fas[pid].pos == pos and fas[pid].played(w)]
            if cands:
                pick = max(cands, key=lambda p: table.fa_proj(p, w))
                cur[pos] = pick.points(w)
        got[w] = cur

        n = claims.get(w, 0)
        if not n or not available:
            continue
        available.difference_update(ranked[:n])
    return got


def starter_baseline():
    """Mean weekly points of the rostered starter tier, same convention."""
    from simfl.montecarlo import get_pool
    out = {}
    for pos, ntier in (("QB", 12), ("RB", 24), ("WR", 24), ("TE", 12)):
        vals = []
        for y in SEASONS:
            pool, _ = get_pool(y)
            tier = sorted([p for p in pool if p.pos == pos and p.adp is not None],
                          key=lambda p: p.adp)[:ntier]
            for w in WEEKS:
                v = [p.points(w) for p in tier if p.played(w)]
                if v:
                    vals.append(st.mean(v))
        out[pos] = st.mean(vals)
    return out


def main():
    print("Best available free agent by position and week, after the real")
    print("league's claim volume drains the real undrafted pool.\n")

    # weeks bucketed, since week-to-week is noisy
    buckets = [("wk 1-4", range(1, 5)), ("wk 5-9", range(5, 10)),
               ("wk 10-14", range(10, 15))]
    for pos in POS:
        print(f"-- {pos}  (points of the best FA available that week)")
        print(f"{'rule':10s}" + "".join(f"{b:>10s}" for b, _ in buckets))
        for rule in RULES:
            cells = []
            for _, rng_wk in buckets:
                vals = []
                seeds = N_SEEDS if rule == "random" else 1
                for s in range(seeds):
                    rng = random.Random(s)
                    for y in SEASONS:
                        b = simulate(y, rule, rng)
                        vals += [b[w].get(pos, 0.0) for w in rng_wk]
                cells.append(st.mean(vals))
            print(f"{rule:10s}" + "".join(f"{c:10.1f}" for c in cells))
        print()

    print("=" * 62)
    print("WHAT YOU ACTUALLY GET: pick by leak-free projection, after")
    print("depletion; scored on what he really did. Comparable to a starter.")
    print("=" * 62 + "\n")
    base = starter_baseline()
    for pos in POS:
        print(f"-- {pos}  (rostered starter tier = {base[pos]:.1f} pts/wk)")
        print(f"{'rule':10s}" + "".join(f"{b:>10s}" for b, _ in buckets)
              + f"{'as % of starter (late)':>24s}")
        for rule in RULES:
            cells = []
            for _, rng_wk in buckets:
                vals = []
                seeds = N_SEEDS if rule == "random" else 1
                for s in range(seeds):
                    rng = random.Random(s)
                    for y in SEASONS:
                        g = realized(y, rule, rng)
                        vals += [g[w].get(pos, 0.0) for w in rng_wk]
                cells.append(st.mean(vals))
            pct = cells[-1] / base[pos]
            print(f"{rule:10s}" + "".join(f"{c:10.1f}" for c in cells)
                  + f"{pct:23.0%}")
        print()

    print("=" * 62)
    print("DOES WAIVER PRIORITY MATTER? same chaser room, my queue slot")
    print("varies (reverse-standings priority cycles a real manager")
    print("through all of these).")
    print("=" * 62 + "\n")
    print(f"{'pos':6s}{'starter':>9s}" + "".join(f"{'q=' + str(q):>9s}" for q in (1, 4, 8, 12)))
    for pos in POS:
        cells = []
        for q in (1, 4, 8, 12):
            vals = []
            for y in SEASONS:
                g = realized(y, "chaser", random.Random(0), queue=q)
                vals += [g[w].get(pos, 0.0) for w in WEEKS]
            cells.append(st.mean(vals))
        print(f"{pos:6s}{base[pos]:9.1f}" + "".join(f"{c:9.1f}" for c in cells))
    print()

    print("Claim volume actually observed (league-wide adds per season):")
    for y in SEASONS:
        c = claims_per_week(y)
        tot = sum(c.values())
        print(f"  {y}: {tot:3d} adds, weeks 1-14 avg {tot / 14:4.1f}/wk")


if __name__ == "__main__":
    main()
