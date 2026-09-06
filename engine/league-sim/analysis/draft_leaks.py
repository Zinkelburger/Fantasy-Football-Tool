"""Audit any league's drafts for the leaks the findings already settled.

Point it at ESPN league exports and it answers one question per team per
season: did this draft break a rule we tested elsewhere, and what did the
draft return? It names no one -- teams are reported as anonymous rows and
only aggregates are printed -- so the output is safe to publish.

The five rules audited, each settled in its own write-up, none of them
invented here:

  TE dead zone   first TE in rounds 5-9              finding 33
  QB timing      first QB later than round 5         finding 36 / 14
  discipline     mean (pick - ADP) below zero        finding 03 / 32
  RB opening     fewer than 2 RB in rounds 1-4       finding 36
  TE2            a second TE at any price            finding 36

**This is descriptive, and deliberately so.** Finding 36 showed that
observational draft-shape gaps are endogenous -- "late RBs win" vanished
the moment the sim *forced* the timing, because good drafters take late
RBs when a good late RB is there. The same trap applies to every row
below. So the haul column reports what violating drafts returned, not
what the violation caused. The causal claims live in the findings named
above; this script only measures how often real drafters break them and
whether the descriptive gap points the same way.

"Haul" = the points a drafted roster would score with a perfect lineup
every week. It is an upper bound that strips out waivers and lineup
skill, so it grades the draft and nothing else. Hauls are z-scored
within each season, because league-wide scoring moves year to year.

Run from league-sim root:
  venv/bin/python analysis/draft_leaks.py
  venv/bin/python analysis/draft_leaks.py --years 2023 2024 2025
"""
import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nflreadpy as nfl
import polars as pl

from simfl.config import DEFAULT_SCORING
from simfl.data import norm_name
from simfl.pool import build_pool

ESPN_DIR = Path(__file__).resolve().parent.parent / "data" / "espn"
TE_DEAD_ZONE = (5, 9)      # finding 33
QB_LATE_AFTER = 5          # finding 36: "QB by round 5"
RB_OPEN_MIN = 2            # finding 36: "open 2-3 RB in rounds 1-4"
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1}   # + RB/WR flex

_ids = nfl.load_ff_playerids().filter(pl.col("espn_id").is_not_null())
ESPN_MAP = {int(r["espn_id"]): (r["name"], r["position"], r["gsis_id"])
            for r in _ids.select(["espn_id", "name", "position", "gsis_id"])
            .iter_rows(named=True)}


def resolve(pick, by_gsis, by_name):
    """ESPN pick -> PlayerSeason, via gsis id then name+position."""
    pid = pick["playerId"]
    if pid < 0:
        return None                      # D/ST, not modeled
    name, pos, gsis = ESPN_MAP.get(pid, (f"espn:{pid}", "?", None))
    return by_gsis.get(gsis) or by_name.get((norm_name(name), pos))


def perfect_lineup_points(roster, weeks=range(1, 18)):
    """Points a roster would score with a perfect lineup every week."""
    total = 0.0
    for w in weeks:
        active = sorted([p for p in roster if p.played(w)],
                        key=lambda p: -p.points(w))
        used, got = set(), []
        for pos, n in STARTERS.items():
            take = [p for p in active if p.pos == pos and p.pid not in used][:n]
            used.update(p.pid for p in take)
            got += take
        got += [p for p in active
                if p.pos in ("RB", "WR") and p.pid not in used][:1]
        total += sum(p.points(w) for p in got)
    return total


def team_seasons(years):
    """One row per team per season: the levers, plus the haul."""
    rows = []
    for year in years:
        path = ESPN_DIR / f"league_{year}.json"
        if not path.exists():
            print(f"  (no export for {year}, skipping)")
            continue
        d = json.load(open(path))
        if isinstance(d, list):
            d = d[0]
        pool = build_pool(year, DEFAULT_SCORING)
        by_gsis = {p.pid: p for p in pool}
        by_name = {(norm_name(p.name), p.pos): p for p in pool}

        picks = sorted(d["draftDetail"]["picks"],
                       key=lambda p: p["overallPickNumber"])
        teams = {}
        for pk in picks:
            ps = resolve(pk, by_gsis, by_name)
            if ps is None:
                continue
            teams.setdefault(pk["teamId"], []).append(
                (pk["roundId"], pk["overallPickNumber"], ps))

        for tid, got in teams.items():
            roster = [ps for _, _, ps in got]
            counts = {}
            for _, _, ps in got:
                counts[ps.pos] = counts.get(ps.pos, 0) + 1
            first = {}
            for rd, _, ps in got:
                first.setdefault(ps.pos, rd)
            deltas = [no - ps.adp for _, no, ps in got if ps.adp]
            rows.append(dict(
                year=year, team=tid,
                haul=perfect_lineup_points(roster),
                te_round=first.get("TE"), qb_round=first.get("QB"),
                rb_open=sum(1 for rd, _, ps in got
                            if rd <= 4 and ps.pos == "RB"),
                n_wr=counts.get("WR", 0), n_rb=counts.get("RB", 0),
                n_te=counts.get("TE", 0),
                discipline=statistics.mean(deltas) if deltas else None))
    # z-score hauls inside each season
    for year in {r["year"] for r in rows}:
        yr = [r for r in rows if r["year"] == year]
        mu = statistics.mean(r["haul"] for r in yr)
        sd = statistics.pstdev(r["haul"] for r in yr) or 1.0
        for r in yr:
            r["z"] = (r["haul"] - mu) / sd
    return rows


def boot_gap(rows, flag, boots=4000, seed=3):
    """Mean haul-z of violating drafts minus compliant ones, with a
    bootstrap 95% CI. Descriptive -- see the module docstring."""
    a = [r["z"] for r in rows if flag(r)]
    b = [r["z"] for r in rows if not flag(r)]
    if len(a) < 3 or len(b) < 3:
        return len(a), None, None, None
    obs = statistics.mean(a) - statistics.mean(b)
    rng = random.Random(seed)
    draws = sorted(
        statistics.mean([rng.choice(a) for _ in a])
        - statistics.mean([rng.choice(b) for _ in b]) for _ in range(boots))
    return len(a), obs, draws[int(.025 * boots)], draws[int(.975 * boots)]


RULES = [
    ("TE taken in rounds 5-9", "33",
     lambda r: r["te_round"] is not None
     and TE_DEAD_ZONE[0] <= r["te_round"] <= TE_DEAD_ZONE[1]),
    ("first QB after round 5", "36/14",
     lambda r: r["qb_round"] is not None and r["qb_round"] > QB_LATE_AFTER),
    ("bought above market (mean pick-ADP < 0)", "03/32",
     lambda r: r["discipline"] is not None and r["discipline"] < 0),
    ("fewer than 2 RB in rounds 1-4", "36",
     lambda r: r["rb_open"] < RB_OPEN_MIN),
    ("drafted a 2nd TE", "36",
     lambda r: r["n_te"] >= 2),
    ("more WR than RB drafted", "07/02",
     lambda r: r["n_wr"] > r["n_rb"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int,
                    default=list(range(2020, 2026)))
    a = ap.parse_args()

    rows = team_seasons(a.years)
    print(f"\n{len(rows)} team-seasons, {min(r['year'] for r in rows)}"
          f"-{max(r['year'] for r in rows)}\n")

    print("How often real drafters break each tested rule, and what those")
    print("drafts returned. Haul gap is in season-standardized units (SD of")
    print("draft haul within that year); DESCRIPTIVE, not causal.\n")
    print(f"  {'rule':<42}{'finding':<9}{'broke it':>10}{'haul gap':>11}"
          f"{'   95% CI':<18}")
    for label, fnd, flag in RULES:
        n, gap, lo, hi = boot_gap(rows, flag)
        pct = n / len(rows)
        if gap is None:
            print(f"  {label:<42}{fnd:<9}{n:>4} ({pct:3.0%})   (too few)")
            continue
        sig = "*" if not lo <= 0 <= hi else " "
        print(f"  {label:<42}{fnd:<9}{n:>4} ({pct:3.0%}){gap:>+9.2f}"
              f"   [{lo:+.2f}, {hi:+.2f}]{sig}")

    print("\n  * = 95% bootstrap CI excludes zero.")

    # How the TE dead zone splits out, since it is the most-broken rule.
    print("\nFirst TE taken, by round band (all team-seasons):")
    bands = [("rounds 1-4", 1, 4), ("rounds 5-9 (dead zone)", 5, 9),
             ("round 10+", 10, 99)]
    for nm, lo, hi in bands:
        sel = [r for r in rows if r["te_round"] and lo <= r["te_round"] <= hi]
        if not sel:
            continue
        print(f"  {nm:<26} n={len(sel):<4} mean haul z "
              f"{statistics.mean(r['z'] for r in sel):+.2f}")
    none_te = [r for r in rows if not r["te_round"]]
    if none_te:
        print(f"  {'no TE drafted':<26} n={len(none_te):<4} mean haul z "
              f"{statistics.mean(r['z'] for r in none_te):+.2f}")

    print("\nDrafted WR count vs haul (the shape question):")
    for lo, hi in [(0, 4), (5, 5), (6, 6), (7, 20)]:
        sel = [r for r in rows if lo <= r["n_wr"] <= hi]
        if len(sel) < 3:
            continue
        lab = f"{hi} WR or fewer" if lo == 0 else (
            f"{lo}+ WR" if hi == 20 else f"{lo} WR")
        print(f"  {lab:<26} n={len(sel):<4} mean haul z "
              f"{statistics.mean(r['z'] for r in sel):+.2f}")


if __name__ == "__main__":
    main()
