"""Is an EWMA over EXPECTED points (opportunity) a better weekly
projection than the current EWMA over ACTUAL points?

Same structure everywhere -- row[w] = blend*ewma + (1-blend)*prior,
blend = min(1, games_seen/5), alpha = 0.35 -- only the series the EWMA
runs over changes:

  actual : this season's realized (floored, STD) points   [status quo]
  ep     : expected points from nflverse ff_opportunity, rescored under
           league rules (pass 1/25 + 4TD - 2INT, rush/rec 1/10 + 6TD)
  mix    : 0.5*actual + 0.5*ep per week

Leak-free: week W uses only weeks < W. Kickers excluded (no opportunity
model for kicking). Metrics are decision-shaped: within-week Spearman
(who do I start), lineup regret vs hindsight (points a greedy
projection lineup leaves on the table), and MAE.

Run:  venv/bin/python analysis/ep_projections.py
"""

import statistics as st
from collections import defaultdict

import polars as pl

from common import SEASONS

from simfl.data import DATA_DIR
from simfl.montecarlo import get_pool

ALPHA = 0.35
PRIOR_GAMES = 5
POS = ("QB", "RB", "WR", "TE")
STARTER_N = {"QB": 12, "RB": 30, "WR": 30, "TE": 12}  # league-wide slots
MAX_WEEK = 17


def load_ep(year: int) -> dict[str, dict[int, float]]:
    """pid -> week -> expected points under LEAGUE scoring."""
    df = (pl.read_parquet(DATA_DIR / "ff_opportunity_2017_2025.parquet")
          .filter(pl.col("season") == str(year),
                  pl.col("position").is_in(list(POS))))
    ep = (pl.col("pass_yards_gained_exp") / 25
          + pl.col("pass_touchdown_exp") * 4
          + pl.col("pass_interception_exp") * -2
          + pl.col("rush_yards_gained_exp") / 10
          + pl.col("rush_touchdown_exp") * 6
          + pl.col("rec_yards_gained_exp") / 10
          + pl.col("rec_touchdown_exp") * 6
          + (pl.col("pass_two_point_conv_exp") + pl.col("rec_two_point_conv_exp")
             + pl.col("rush_two_point_conv_exp")) * 2)
    df = df.with_columns(ep.fill_null(0.0).alias("ep"))
    out: dict[str, dict[int, float]] = {}
    for r in df.select("player_id", "week", "ep").iter_rows():
        out.setdefault(r[0], {})[int(r[1])] = r[2]
    return out


def project(p, series: dict[int, float]) -> list[float]:
    """row[w] for w in 0..MAX_WEEK from the given weekly series,
    identical structure to ProjectionTable."""
    row = [p.prior_ppg] * (MAX_WEEK + 1)
    ewma, seen = 0.0, 0
    for w in range(1, MAX_WEEK + 1):
        if seen:
            blend = min(1.0, seen / PRIOR_GAMES)
            row[w] = blend * ewma + (1 - blend) * p.prior_ppg
        if w in series:
            x = series[w]
            ewma = x if not seen else ALPHA * x + (1 - ALPHA) * ewma
            seen += 1
    return row


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos_, i in enumerate(order):
            r[i] = pos_
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def main():
    variants = ("actual", "ep", "mix")
    mae = {v: [] for v in variants}
    rho = {v: [] for v in variants}
    regret = {v: defaultdict(float) for v in variants}   # v -> year -> pts
    hindsight = defaultdict(float)
    coverage_num = coverage_den = 0

    for year in SEASONS:
        pool, _ = get_pool(year)
        epd = load_ep(year)
        players = [p for p in pool if p.pos in POS]
        rows = {}
        for p in players:
            ep_series = {}
            for w in p.week_pts:            # only weeks he actually played
                coverage_den += 1
                if p.pid in epd and w in epd[p.pid]:
                    ep_series[w] = epd[p.pid][w]
                    coverage_num += 1
                else:
                    ep_series[w] = p.week_pts[w]   # fallback: actual
            mix_series = {w: 0.5 * p.week_pts[w] + 0.5 * ep_series[w]
                          for w in p.week_pts}
            rows[p.pid] = {"actual": project(p, p.week_pts),
                           "ep": project(p, ep_series),
                           "mix": project(p, mix_series)}

        for w in range(3, 15):              # weeks the sim actually decides
            for pos in POS:
                act = [p for p in players if p.pos == pos and p.played(w)]
                if len(act) < 5:
                    continue
                real = [p.points(w) for p in act]
                n = STARTER_N[pos]
                best = sum(sorted(real, reverse=True)[:n])
                hindsight[year] += best
                for v in variants:
                    proj = [rows[p.pid][v][w] for p in act]
                    rho[v].append(spearman(proj, real))
                    picked = sorted(range(len(act)), key=lambda i: -proj[i])[:n]
                    regret[v][year] += best - sum(real[i] for i in picked)
                    for p, pr in zip(act, proj):
                        if p.adp is not None and p.adp <= 180:
                            mae[v].append(abs(pr - p.points(w)))

    print(f"EP coverage of played weeks (QB/RB/WR/TE): "
          f"{coverage_num/coverage_den:.1%}  (misses fall back to actual)\n")
    print(f"{'variant':9s}{'MAE (adp<=180)':>15s}{'Spearman':>10s}"
          f"{'lineup regret/yr':>18s}")
    for v in variants:
        reg = st.mean([regret[v][y] for y in SEASONS])
        print(f"{v:9s}{st.mean(mae[v]):15.2f}{st.mean(rho[v]):10.3f}{reg:18.0f}")
    print(f"\n(hindsight league-wide starter points/yr: "
          f"{st.mean([hindsight[y] for y in SEASONS]):.0f}; regret = points a"
          f" greedy lineup on that projection leaves on the table)")

    print("\nby position, Spearman:")
    rho_pos = {v: defaultdict(list) for v in variants}
    # cheap second pass over stored lists is overkill; recompute inline instead
    for year in SEASONS:
        pool, _ = get_pool(year)
        epd = load_ep(year)
        players = [p for p in pool if p.pos in POS]
        rows = {}
        for p in players:
            ep_series = {w: epd.get(p.pid, {}).get(w, p.week_pts[w])
                         for w in p.week_pts}
            mix_series = {w: 0.5 * p.week_pts[w] + 0.5 * ep_series[w]
                          for w in p.week_pts}
            rows[p.pid] = {"actual": project(p, p.week_pts),
                           "ep": project(p, ep_series),
                           "mix": project(p, mix_series)}
        for w in range(3, 15):
            for pos in POS:
                act = [p for p in players if p.pos == pos and p.played(w)]
                if len(act) < 5:
                    continue
                real = [p.points(w) for p in act]
                for v in variants:
                    proj = [rows[p.pid][v][w] for p in act]
                    rho_pos[v][pos].append(spearman(proj, real))
    print(f"{'variant':9s}" + "".join(f"{pos:>8s}" for pos in POS))
    for v in variants:
        print(f"{v:9s}" + "".join(f"{st.mean(rho_pos[v][pos]):8.3f}" for pos in POS))


if __name__ == "__main__":
    main()
