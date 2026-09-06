"""WR archetype backtests, 2020-2025.

Reproduces every number in findings/08, 09, 10:
  - the bad-team-WR1 edge
  - the decline-discount (fallen former stud) trap
  - age effects and their robustness checks

Two modes:
  default  the original mid-round (ADP 36-120) cut the findings were
           written from.
  --full   the same three archetypes re-tested at EVERY price, against
           cost-matched peers. Hit and bust rates are not comparable
           across the board -- a WR who costs pick 10 makes top-24 far
           more often than one who costs pick 150, whatever archetype
           he is -- so the full-board test scores each flagged WR on
           finish-vs-cost (his ADP rank among WRs minus his actual
           finish) and compares him only to unflagged WRs inside the
           same ADP band. That is the number the draft tool quotes, so
           a mark can fire at any price and still cite a result
           measured at that price.

Run:  venv/bin/python scripts/wr_archetypes.py [--full]
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nflreadpy as nfl
import numpy as np
import polars as pl

from simfl.config import DEFAULT_SCORING
from simfl.pool import build_pool

YEARS = range(2020, 2026)
# --full goes back as far as the ADP data does. Each row needs finishes
# from year-1 and year-2 for the fallen-stud flag, and build_pool covers
# 2014 on, so 2016 is the first testable draft.
FULL_YEARS = range(2016, 2026)
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


def build(years=YEARS):
    """One row per priced WR season. Callers filter by ADP band."""
    pools = {y: build_pool(y, DEFAULT_SCORING)
             for y in range(min(years) - 2, max(years) + 1)}
    fin = {}
    for y, pool in pools.items():
        wrs = [p for p in pool if p.pos == "WR"]
        tot = {p.pid: sum(p.week_pts.values()) for p in wrs}
        fin[y] = {p.pid: i + 1 for i, p in
                  enumerate(sorted(wrs, key=lambda p: -tot[p.pid]))}
    rows = []
    for year in years:
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
                "year": year, "name": p.name, "adp": p.adp, "team": p.team,
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


# ------------------------------------------------- full-board re-test
# Round-aligned price bands for a 12-team league, covering the whole
# priced board rather than the 36-120 slice findings 08/09/10 were
# written from.
FULL_BANDS = [("rounds 1-3", (1, 36)), ("rounds 4-7", (37, 84)),
              ("rounds 8-12", (85, 144)), ("rounds 13+", (145, 400))]


def add_resid(rows):
    """Score each WR against what his price alone predicts.

    finish is a rank among every WR who played; adp_rank is a rank among
    only the priced ones, so finish - adp_rank carries a fat offset that
    grows down the board. Fit finish ~ adp_rank within each draft year
    and keep the residual: expected finish minus actual, so positive
    means he beat his price. Per-year because board depth moved (about
    64 priced WRs a year through 2024, 108 in 2025) and a pooled fit
    would read that as late-round WRs busting."""
    for year in {r["year"] for r in rows}:
        yr = [r for r in rows if r["year"] == year]
        slope, icpt = np.polyfit([r["adp_rank"] for r in yr],
                                 [r["finish"] for r in yr], 1)
        for r in yr:
            r["resid"] = (slope * r["adp_rank"] + icpt) - r["finish"]
    return rows


def effect(rows, flag, band, boots=4000, seed=0):
    """Mean price-adjusted finish for flagged WRs minus unflagged WRs
    inside one price band, with a bootstrap 95% CI on the difference."""
    sel = [r for r in rows if band[0] <= r["adp"] <= band[1]]
    hit = [r for r in sel if flag(r)]
    peer = [r for r in sel if not flag(r)]
    if len(hit) < 3 or len(peer) < 3:
        return dict(n=len(hit), npeer=len(peer), diff=None)
    a = [r["resid"] for r in hit]
    b = [r["resid"] for r in peer]
    diff = sum(a) / len(a) - sum(b) / len(b)
    rng = random.Random(seed)
    draws = []
    for _ in range(boots):
        ra = [rng.choice(a) for _ in a]
        rb = [rng.choice(b) for _ in b]
        draws.append(sum(ra) / len(ra) - sum(rb) / len(rb))
    draws.sort()
    out = dict(
        n=len(hit), npeer=len(peer), diff=diff,
        lo=draws[int(.025 * boots)], hi=draws[int(.975 * boots)],
        hit=sum(r["finish"] <= HIT for r in hit) / len(hit),
        bust=sum(r["finish"] > BUST for r in hit) / len(hit),
        peer_hit=sum(r["finish"] <= HIT for r in peer) / len(peer),
        peer_bust=sum(r["finish"] > BUST for r in peer) / len(peer))
    # Mean rank is tail-driven; a drafter cares whether the guy returns
    # startable value at all. Bootstrap the hit- and bust-rate gaps too,
    # since those are the numbers findings 08/09/10 actually quote.
    for key, test in (("hitd", lambda r: r["finish"] <= HIT),
                      ("bustd", lambda r: r["finish"] > BUST)):
        a2 = [1.0 if test(r) else 0.0 for r in hit]
        b2 = [1.0 if test(r) else 0.0 for r in peer]
        d2 = []
        rng2 = random.Random(seed + 1)
        for _ in range(boots):
            ra = [rng2.choice(a2) for _ in a2]
            rb = [rng2.choice(b2) for _ in b2]
            d2.append(sum(ra) / len(ra) - sum(rb) / len(rb))
        d2.sort()
        out[key] = (sum(a2) / len(a2) - sum(b2) / len(b2),
                    d2[int(.025 * boots)], d2[int(.975 * boots)])
    return out


ARCHETYPES = [
    ("08 clear WR1 on a losing team",
     lambda r: r["team_wr1"] and r["bad_team"]),
    ("09 fallen former stud (bounce-back discount)",
     lambda r: r["fallen"]),
    ("10 age 29-30",
     lambda r: r["age"] is not None and 29 <= r["age"] <= 30),
    ("10 age 29+",
     lambda r: r["age"] is not None and r["age"] >= 29),
]


def full_report(rows, title, flag):
    print(f"\n== {title} ==")
    print("  band          n  peers   effect      95% CI            "
          "hit%  peer  hit gap vs peer      bust gap vs peer")
    for label, band in [("whole board", (1, 400))] + FULL_BANDS:
        e = effect(rows, flag, band)
        if e["diff"] is None:
            print(f"  {label:<12} {e['n']:3d} {e['npeer']:5d}   "
                  f"(too few to test)")
            continue
        sig = "  *" if not e["lo"] <= 0 <= e["hi"] else ""
        hd, hlo, hhi = e["hitd"]
        bd, blo, bhi = e["bustd"]
        hsig = "*" if not hlo <= 0 <= hhi else " "
        bsig = "*" if not blo <= 0 <= bhi else " "
        print(f"  {label:<12} {e['n']:3d} {e['npeer']:5d}  "
              f"{e['diff']:+6.1f}  [{e['lo']:+6.1f}, {e['hi']:+6.1f}]{sig:<3} "
              f"{e['hit']:5.0%} {e['peer_hit']:5.0%} "
              f"{hd:+5.0%}[{hlo:+4.0%},{hhi:+4.0%}]{hsig} "
              f"{bd:+5.0%}[{blo:+4.0%},{bhi:+4.0%}]{bsig}")


def stratified(rows, flag, test=None, boots=4000, seed=7):
    """Whole-board outcome-rate gap, standardized to the peers' price mix.

    A raw board-wide hit rate is not an edge: 30% of bad-team WR1s cost a
    top-3-round pick against 18% of other WRs, and two thirds of ANY WR
    at that price finishes top-24. Direct standardization re-weights each
    band's within-band gap by how many peers sit in that band, so what
    survives is the part price cannot explain.

    `test` is any per-row outcome predicate; it defaults to a top-HIT
    finish so callers that only care about hit rate need not pass one."""
    bands = [b for _, b in FULL_BANDS]
    if test is None:
        def test(r):
            return r["finish"] <= HIT

    def gap(sample):
        num = den = 0.0
        for band in bands:
            sel = [r for r in sample if band[0] <= r["adp"] <= band[1]]
            a = [r for r in sel if flag(r)]
            b = [r for r in sel if not flag(r)]
            if not a or not b:
                continue
            g = (sum(test(r) for r in a) / len(a)
                 - sum(test(r) for r in b) / len(b))
            num += g * len(b)
            den += len(b)
        return num / den if den else 0.0

    obs = gap(rows)
    rng = random.Random(seed)
    draws = sorted(gap([rng.choice(rows) for _ in rows]) for _ in range(boots))
    return obs, draws[int(.025 * boots)], draws[int(.975 * boots)]


def upside_report(rows):
    """Ceiling, not just competence.

    Hit rate asks "did he start for me". A drafter reaching for the
    alpha receiver on a bad roster is usually buying the right tail —
    the WR1-overall season that wins a league — and a group can own
    more of that tail while its top-24 rate looks ordinary. So run the
    same price-standardized comparison at progressively harder
    finishes, plus two tail measures that do not depend on a threshold
    at all: how often he beats his price by 20+ WR ranks, and where the
    group's 90th-percentile price-adjusted finish sits."""
    tests = [
        ("top-5 finish", lambda r: r["finish"] <= 5),
        ("top-12 finish", lambda r: r["finish"] <= 12),
        ("top-24 finish", lambda r: r["finish"] <= 24),
        ("beat price by 20+", lambda r: r["resid"] >= 20),
        ("beat price by 40+", lambda r: r["resid"] >= 40),
    ]
    for title, flag in ARCHETYPES:
        sel = [r for r in rows if flag(r)]
        peer = [r for r in rows if not flag(r)]
        print(f"\n== {title} — upside, price-standardized ==")
        print(f"  n={len(sel)} flagged, {len(peer)} peers")
        print("  outcome              flagged  peers   gap (price-matched)")
        for label, test in tests:
            hit_n = sum(test(r) for r in sel)
            s, lo, hi = stratified(rows, flag, test)
            sig = "*" if not lo <= 0 <= hi else " "
            print(f"  {label:<20} {hit_n:3d}/{len(sel):<3d} "
                  f"{sum(test(r) for r in peer):4d}/{len(peer):<4d} "
                  f"{s:+5.1%} [{lo:+5.1%},{hi:+5.1%}]{sig}")
        # Threshold-free: the top of each group's distribution.
        for pct in (75, 90):
            a = sorted(r["resid"] for r in sel)
            b = sorted(r["resid"] for r in peer)
            qa = a[min(len(a) - 1, int(pct / 100 * len(a)))]
            qb = b[min(len(b) - 1, int(pct / 100 * len(b)))]
            print(f"  p{pct} price-adjusted finish: flagged {qa:+6.1f}   "
                  f"peers {qb:+6.1f}   (not price-matched)")


def confound_check(rows):
    print("\n== raw vs price-standardized whole-board hit gap ==")
    print("  archetype                            raw gap   standardized")
    for title, flag in ARCHETYPES:
        e = effect(rows, flag, (1, 400))
        raw, rlo, rhi = e["hitd"]
        s, slo, shi = stratified(rows, flag)
        rs = "*" if not rlo <= 0 <= rhi else " "
        ss = "*" if not slo <= 0 <= shi else " "
        print(f"  {title:<36} {raw:+5.0%}{rs}   "
              f"{s:+5.0%}[{slo:+4.0%},{shi:+4.0%}]{ss}")
    print("  Raw mixes price bands; standardized holds price fixed.")


def survivor_robustness(rows):
    """Everything we can throw at the one archetype that came through the
    price-standardized test. A rule the draft tool fires at every price
    has to survive the choices we made getting here."""
    print("\n== robustness of the one survivor (WR 29+), standardized ==")
    age29 = lambda r: r["age"] is not None and r["age"] >= 29   # noqa: E731

    global HIT, FULL_BANDS
    hit0, bands0 = HIT, FULL_BANDS
    for label, hit, bands in [
        ("as run (top-24, 4 bands)", 24, bands0),
        ("hit = top-36", 36, bands0),
        ("hit = top-12", 12, bands0),
        ("coarse bands (2)", 24, [("early", (1, 84)), ("late", (85, 400))]),
        ("fine bands (6)", 24, [("r1-2", (1, 24)), ("r3-4", (25, 48)),
                                ("r5-7", (49, 84)), ("r8-10", (85, 120)),
                                ("r11-14", (121, 168)), ("r15+", (169, 400))]),
    ]:
        HIT, FULL_BANDS = hit, bands
        s, lo, hi = stratified(rows, age29)
        sig = "*" if not lo <= 0 <= hi else " "
        print(f"  {label:<26} {s:+5.0%} [{lo:+5.0%},{hi:+5.0%}]{sig}")
    HIT, FULL_BANDS = hit0, bands0

    print("  leave-one-year-out (standardized gap without that season):")
    yrs = sorted({r["year"] for r in rows})
    cells = []
    for y in yrs:
        s, _, _ = stratified([r for r in rows if r["year"] != y], age29)
        cells.append(f"-{y}: {s:+4.0%}")
    for i in range(0, len(cells), 5):
        print("   " + "  ".join(cells[i:i + 5]))


def era_check(rows):
    """The same four flags, split in half by era. An archetype that only
    shows up in one half is a period effect, not a rule."""
    print("\n== robustness: does each flag hold in both halves? ==")
    print("  archetype                          early        late")
    lo, hi = min(r["year"] for r in rows), max(r["year"] for r in rows)
    mid = (lo + hi) // 2
    for title, flag in ARCHETYPES:
        cells = []
        for sel in ([r for r in rows if r["year"] <= mid],
                    [r for r in rows if r["year"] > mid]):
            e = effect(sel, flag, (1, 400))
            cells.append("(thin)" if e["diff"] is None
                         else f"{e['diff']:+6.1f} (n={e['n']:3d})")
        print(f"  {title:<34} {cells[0]:<12} {cells[1]}")
    print(f"  early = {lo}-{mid}, late = {mid + 1}-{hi}")


def full_board(rows):
    yrs = sorted({r["year"] for r in rows})
    print(f"Full-board re-test, {yrs[0]}-{yrs[-1]} ({len(rows)} priced WR "
          f"seasons).")
    print("Effect = mean price-adjusted finish (WR ranks beaten against what")
    print("his ADP predicts) for flagged WRs minus unflagged WRs in the same")
    print("band. Positive = the archetype beats its price. * = 95% bootstrap")
    print("CI excludes zero. Hit = top-24 finish, bust = worse than WR45;")
    print("those two are NOT comparable across bands, only against `peer`.")
    for title, flag in ARCHETYPES:
        full_report(rows, title, flag)
    confound_check(rows)
    upside_report(rows)
    survivor_robustness(rows)
    era_check(rows)


if __name__ == "__main__":
    if "--full" in sys.argv:
        full_board(add_resid(build(FULL_YEARS)))
        sys.exit(0)
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
