"""Presentation figures. Writes PNGs into league-sim/figures/.

  python -m simfl.plots            # all available figures
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analysis import _pools, _ppg, _ros, _games_after, MIN_GAMES, scarcity, streaming_supply
from .config import SEASONS
from .grid import RESULTS_DIR

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)

COLORS = {"QB": "#d62728", "RB": "#2ca02c", "WR": "#1f77b4",
          "TE": "#ff7f0e", "K": "#7f7f7f"}
plt.rcParams.update({"figure.dpi": 150, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG_DIR / name)


def fig_scarcity():
    curves = scarcity()
    fig, ax = plt.subplots(figsize=(8, 5))
    for pos, c in curves.items():
        ax.plot(range(1, len(c) + 1), c, label=pos, color=COLORS[pos], lw=2)
    # last-starter depth in a 12-team league (QB12, RB~30, WR~30, TE12, K12)
    for pos, depth in [("QB", 12), ("RB", 30), ("WR", 30), ("TE", 12)]:
        c = curves[pos]
        if depth <= len(c):
            ax.plot(depth, c[depth - 1], "o", color=COLORS[pos], ms=7,
                    mfc="white", mew=2)
    ax.set_xlabel("Positional rank (season PPG)")
    ax.set_ylabel("Points per game (standard scoring)")
    ax.set_title("What a starter is worth, 2020–2025 averages\n"
                 "circles = the last starter a 12-team league absorbs")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    _save(fig, "fig1_scarcity.png")


def fig_kickers():
    xs, ys = [], []
    for y, pool in _pools(SEASONS).items():
        ks = [p for p in pool if p.pos == "K"]
        early = sorted([k for k in ks if sum(1 for w in k.week_pts if w <= 4) >= 3],
                       key=lambda p: -_ppg(p, range(1, 5)))
        ros = sorted([k for k in ks if _games_after(k, 4) >= MIN_GAMES],
                     key=lambda p: -_ros(p, 4))
        ros_idx = {p.pid: i + 1 for i, p in enumerate(ros)}
        for i, p in enumerate(early[:20]):
            if p.pid in ros_idx:
                xs.append(i + 1)
                ys.append(ros_idx[p.pid])
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.scatter(xs, ys, alpha=0.55, color="#7f7f7f", s=30)
    ax.plot([1, 20], [1, 20], "--", color="#d62728", lw=1,
            label="perfect persistence")
    ax.set_xlabel("Kicker rank, weeks 1–4")
    ax.set_ylabel("Kicker rank, rest of season")
    ax.set_title("The 'hot kicker' does not stay hot (2020–2025)\n"
                 "if early rank predicted anything, points would hug the line")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    _save(fig, "fig2_kicker_persistence.png")


def fig_te_supply():
    rows = streaming_supply("TE", after=3)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for i, r in enumerate(rows):
        for j, (name, ppg, tag) in enumerate(r["ros_top_names"]):
            if tag == "FA":
                color, m = "#d62728", "D"
            elif float(tag[3:]) >= 90:
                color, m = "#ff7f0e", "o"
            else:
                color, m = "#1f77b4", "o"
            ax.scatter(i, ppg, color=color, marker=m, s=45, zorder=3)
    ax.set_xticks(range(len(rows)), [r["year"] for r in rows])
    ax.set_ylabel("Rest-of-season PPG (after week 3)")
    ax.set_title("Where the top-8 TEs actually come from\n"
                 "blue = early pick (ADP<90) · orange = late pick (ADP 90+) · red ◆ = free agent")
    ax.grid(alpha=0.25, axis="y")
    _save(fig, "fig3_te_supply.png")


def _load_grid():
    cells = {}
    for f in RESULTS_DIR.glob("*.json"):
        d = json.loads(f.read_text())
        cells.setdefault(d["strategy"], {})[d["year"]] = d
    return cells


def fig_strategies():
    from .strategies import STRATEGIES
    cells = _load_grid()
    if not cells:
        print("no grid results yet; skipping strategy figures")
        return
    names, aps, errs, titles, terrs = [], [], [], [], []
    for s, by_year in cells.items():
        vals = [v for y in by_year.values() for v in y["all_plays"]]
        n = len(vals)
        m = sum(vals) / n
        sd = (sum((v - m) ** 2 for v in vals) / (n - 1)) ** 0.5
        t = sum(y["titles"] for y in by_year.values())
        names.append(STRATEGIES[s].label)
        aps.append(m)
        errs.append(1.96 * sd / n ** 0.5)
        titles.append(t / n)
        terrs.append(1.96 * (t / n * (1 - t / n) / n) ** 0.5)
    order = sorted(range(len(names)), key=lambda i: aps[i])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    ypos = range(len(names))
    ax1.barh(ypos, [aps[i] - 0.5 for i in order], left=0.5,
             xerr=[errs[i] for i in order], color="#1f77b4", alpha=0.85)
    ax1.axvline(0.5, color="k", lw=1)
    ax1.set_yticks(ypos, [names[i] for i in order])
    ax1.set_xlabel("All-play win % vs family field")
    ax1.set_title("Weekly strength")
    ax2.barh(ypos, [titles[i] for i in order],
             xerr=[terrs[i] for i in order], color="#2ca02c", alpha=0.85)
    ax2.axvline(1 / 12, color="k", lw=1, ls="--")
    ax2.set_xlabel("Championship rate (dashed = 1/12 baseline)")
    ax2.set_title("Titles")
    fig.suptitle("Strategy backtest, 2020–2025 · each vs 11 family drafters · 95% CI",
                 y=1.02)
    _save(fig, "fig4_strategies.png")


def fig_heatmap():
    from .strategies import STRATEGIES
    cells = _load_grid()
    if not cells:
        return
    strategies = sorted(cells, key=lambda s: -sum(
        y["summary"]["all_play"] for y in cells[s].values()) / len(cells[s]))
    years = SEASONS
    grid = [[cells[s][y]["summary"]["all_play"] if y in cells[s] else float("nan")
             for y in years] for s in strategies]
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(grid, cmap="RdYlGn", vmin=0.40, vmax=0.60, aspect="auto")
    ax.set_xticks(range(len(years)), years)
    ax.set_yticks(range(len(strategies)), [STRATEGIES[s].label for s in strategies])
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            if v == v:  # skip NaN
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, label="all-play win %")
    ax.set_title("No strategy wins every year — but some never lose big\n"
                 "all-play vs family field, by season")
    _save(fig, "fig5_heatmap.png")


def fig_qb_cost():
    xs, ys = [], []
    for y, pool in _pools(SEASONS).items():
        for p in pool:
            if p.pos == "QB" and p.adp is not None and len(p.week_pts) >= MIN_GAMES:
                xs.append(p.adp)
                ys.append(_ppg(p, range(1, 18)))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(xs, ys, alpha=0.45, color="#d62728", s=28)
    bins = [(0, 40), (40, 70), (70, 100), (100, 140), (140, 200)]
    bx, by = [], []
    for lo, hi in bins:
        vals = sorted(v for x, v in zip(xs, ys) if lo <= x < hi)
        if vals:
            bx.append((lo + hi) / 2)
            by.append(vals[len(vals) // 2])
    ax.plot(bx, by, "-o", color="#111111", lw=2, label="median by ADP range")
    ax.set_xlabel("Overall ADP (draft cost)")
    ax.set_ylabel("Season PPG")
    ax.set_title("What a QB costs vs what he returns, 2020–2025\n"
                 "early QBs really do score more — the sim asks if it's worth the picks")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    _save(fig, "fig6_qb_cost.png")


def main():
    fig_scarcity()
    fig_kickers()
    fig_te_supply()
    fig_qb_cost()
    fig_strategies()
    fig_heatmap()


if __name__ == "__main__":
    main()
