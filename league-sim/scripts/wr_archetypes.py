"""Mid-round WR archetype backtests, 2020-2025.

Reproduces every number in findings/08, 09, 10:
  - the bad-team-WR1 edge
  - the decline-discount (fallen former stud) trap
  - age effects and their robustness checks

Run:  venv/bin/python scripts/wr_archetypes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nflreadpy as nfl
import polars as pl

from simfl.config import DEFAULT_SCORING
from simfl.pool import build_pool

YEARS = range(2020, 2026)
BAND = (36, 120)          # overall ADP window ~ rounds 4-10 in a 12-team
HIT, BUST = 24, 45        # positional finish thresholds
ALIAS = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

_players = nfl.load_players()
_bcol = next(c for c in _players.columns if "birth" in c)
BIRTH = {r["gsis_id"]: r[_bcol] for r in
         _players.select(["gsis_id", _bcol]).drop_nulls().iter_rows(named=True)}


def age_at(pid, year):
    b = BIRTH.get(pid)
    if b is None:
        return None
    y, m, d = str(b)[:10].split("-")
    return year - int(y) - (1 if (int(m), int(d)) > (9, 1) else 0)


def team_wins(year):
    s = nfl.load_schedules([year]).filter(pl.col("game_type") == "REG")
    w = {}
    for r in s.iter_rows(named=True):
        if r["home_score"] is None:
            continue
        for t, mine, theirs in [(r["home_team"], r["home_score"], r["away_score"]),
                                (r["away_team"], r["away_score"], r["home_score"])]:
            a, b = w.get(t, (0, 0))
            w[t] = (a + (mine > theirs), b + 1)
    return {t: a / b for t, (a, b) in w.items()}


def build():
    """One row per drafted mid-round WR season."""
    pools = {y: build_pool(y, DEFAULT_SCORING) for y in range(2018, 2026)}
    fin = {}
    for y, pool in pools.items():
        wrs = [p for p in pool if p.pos == "WR"]
        tot = {p.pid: sum(p.week_pts.values()) for p in wrs}
        fin[y] = {p.pid: i + 1 for i, p in
                  enumerate(sorted(wrs, key=lambda p: -tot[p.pid]))}
    rows = []
    for year in YEARS:
        prev_w = team_wins(year - 1)
        adp_wrs = sorted([p for p in pools[year] if p.pos == "WR" and p.adp],
                         key=lambda p: p.adp)
        wr1 = {}
        for p in adp_wrs:
            if p.team and p.team not in wr1:
                wr1[p.team] = p.pid
        adp_rank = {p.pid: i + 1 for i, p in enumerate(adp_wrs)}
        for p in adp_wrs:
            two, last = fin[year - 2].get(p.pid), fin[year - 1].get(p.pid)
            rows.append({
                "year": year, "name": p.name, "adp": p.adp,
                "adp_rank": adp_rank[p.pid], "finish": fin[year][p.pid],
                "age": age_at(p.pid, year),
                "team_wr1": wr1.get(p.team) == p.pid,
                "bad_team": prev_w.get(ALIAS.get(p.team, p.team), 0.5) <= 0.45,
                "fallen": two is not None and two <= 20 and (last is None or last > 35),
            })
    return rows


def rate(rows, band=BAND, bust=BUST):
    sel = [r for r in rows if band[0] <= r["adp"] <= band[1]]
    n = len(sel)
    if not n:
        return "n=0"
    return (f"n={n:3d}  top-{HIT} {sum(r['finish'] <= HIT for r in sel)/n:4.0%}  "
            f"bust(>{bust}) {sum(r['finish'] > bust for r in sel)/n:4.0%}  "
            f"avg finish vs cost {sum(r['adp_rank'] - r['finish'] for r in sel)/n:+5.1f}")


if __name__ == "__main__":
    rows = build()
    mid = [r for r in rows if BAND[0] <= r["adp"] <= BAND[1]]

    print("== bad-team-WR1 edge ==")
    print("  WR1+bad team :", rate([r for r in mid if r["team_wr1"] and r["bad_team"]]))
    print("  WR1, decent  :", rate([r for r in mid if r["team_wr1"] and not r["bad_team"]]))
    print("  not WR1, bad :", rate([r for r in mid if not r["team_wr1"] and r["bad_team"]]))
    print("  neither      :", rate([r for r in mid if not r["team_wr1"] and not r["bad_team"]]))

    print("\n== decline discount (fallen former studs) ==")
    print("  fallen       :", rate([r for r in mid if r["fallen"]]))
    print("  not fallen   :", rate([r for r in mid if not r["fallen"]]))

    print("\n== age buckets ==")
    for lo, hi in [(0, 24), (25, 26), (27, 28), (29, 30), (31, 99)]:
        print(f"  {lo:2d}-{hi:2d}       :",
              rate([r for r in mid if r["age"] is not None and lo <= r["age"] <= hi]))

    print("\n== robustness of the 29-30 cell ==")
    aged = [r for r in rows if r["age"] is not None]
    for label, sel, band, bust in [
        ("era 2020-22", [r for r in aged if r["year"] <= 2022], BAND, BUST),
        ("era 2023-25", [r for r in aged if r["year"] >= 2023], BAND, BUST),
        ("band 30-130", aged, (30, 130), BUST),
        ("band 48-108", aged, (48, 108), BUST),
        ("bust >40   ", aged, BAND, 40),
        ("bust >50   ", aged, BAND, 50),
    ]:
        v = [r for r in sel if 29 <= r["age"] <= 30]
        o = [r for r in sel if r["age"] <= 28]
        print(f"  {label}:  29-30 {rate(v, band, bust)}")
        print(f"  {label}:  <=28  {rate(o, band, bust)}")
