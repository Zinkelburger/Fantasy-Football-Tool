"""Should you draft a TE at all — and when? The same-pick test.

Not "TE over replacement" in isolation: for every TE drafted 2018-2025
(ADP boards, 12-team rounds), compare his season to the WR/RBs drafted
within +/-6 picks of the same ADP slot, under all three scoring
formats. The common currency is season points over the year's
last-starter season at the pick's own position (QB12/TE12, RB30/WR30
by season total). Whichever position you skip at the pick you fill
from the draft's later dregs, so the *difference* in those numbers is
the season points the pick decision actually moved.

Sections printed:
  1. per-pick head-to-head: every early TE (ADP rounds 1-4) vs the
     WR/RBs at his slot, all three formats
  2. bucket means: TE minus same-pick WR/RB, by round band x format
  3. the Kelce split (he is ~a quarter of the early-TE sample)
  4. boom/bust rates: early TEs vs the WR/RBs at the same picks
  5. the cliff: top-3/top-6 TE finish odds by ADP band — why rounds
     5-9 are dominated by just waiting

Figures written to figures/ (feed finding 33): te_same_pick.png,
te_when.png, te_cliff.png, te_boom_bust.png.

Run:  venv/bin/python analysis/te_same_pick.py
"""
import json
import math
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIGS = ROOT / "figures"
sys.path.insert(0, str(ROOT / "analysis"))
from player_model import league_pts, weekly_raw   # noqa: E402
from round_profile import FORMATS, YEARS, norm, roster_ids  # noqa: E402

REPL = {"QB": 12, "RB": 30, "WR": 30, "TE": 12}   # last starter w/ flex
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
WINDOW = 6            # "the same pick" = ADP within +/-6 overall picks
BANDS = [(1, 2), (3, 4), (5, 6), (7, 9), (10, 13)]
EARLY = 4             # "paying up" = ADP rounds 1-4
BOOM, BUST = 25, -25  # season pts over/under the last-starter season

# figure chrome (dataviz reference palette, light mode)
SURFACE, INK, SEC, MUT = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASE = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
FMT_COLOR = {"std": BLUE, "half": ORANGE, "ppr": AQUA}


def last_name(name):
    parts = [p for p in name.split()
             if p.lower().rstrip(".") not in SUFFIXES]
    return parts[-1]


def season_table(year):
    """format -> DataFrame[pid] with pos, total, finish (weeks 1-17)."""
    w = weekly_raw(year)
    w = w[w.week <= 17]
    out = {}
    for fmt, ppr in FORMATS.items():
        g = pd.DataFrame({"pid": w.player_id, "pos": w.position,
                          "pts": league_pts(w, ppr)}).groupby("pid").agg(
            pos=("pos", "first"), total=("pts", "sum"))
        g["fin"] = g.groupby("pos").total.rank(ascending=False,
                                               method="first")
        out[fmt] = g
    return out


def build():
    """One row per drafted QB/RB/WR/TE pick with per-format season VOR
    (season total minus the year's last-starter total at his position)."""
    rows = []
    for year in YEARS:
        ids = roster_ids(year)
        tables = season_table(year)
        repl = {(fmt, pos): g[g.pos == pos].total.nlargest(
                    REPL[pos]).iloc[-1]
                for fmt, g in tables.items() for pos in REPL}
        for e in json.load(open(DATA / f"adp_{year}.json")):
            if e.get("pos") not in REPL or not e.get("adp"):
                continue
            hit = ids.get(norm(e["name"]))
            if hit is None:
                continue
            pid = hit[0]
            row = dict(year=year, name=e["name"], pos=e["pos"],
                       adp=float(e["adp"]),
                       rnd=min(15, math.ceil(float(e["adp"]) / 12)),
                       kelce="kelce" in norm(e["name"]))
            for fmt, g in tables.items():
                total = g.total.get(pid, 0.0)   # never played = 0, not NaN
                row[f"vor_{fmt}"] = total - repl[(fmt, e["pos"])]
                fin = g.fin.get(pid)
                row[f"fin_{fmt}"] = int(fin) if pd.notna(fin) else 99
            rows.append(row)
    return pd.DataFrame(rows)


def matched(df, te_row):
    """WR/RB picks at the TE's slot: same year, ADP within +/-WINDOW."""
    return df[(df.year == te_row.year) & df.pos.isin(("RB", "WR"))
              & (df.adp - te_row.adp).abs().le(WINDOW)]


def head_to_head(df):
    """Early-TE per-pick table with the matched WR/RB means attached."""
    te = df[(df.pos == "TE") & (df.rnd <= EARLY)].sort_values(
        ["year", "adp"]).copy()
    for fmt in FORMATS:
        te[f"near_{fmt}"] = [matched(df, r)[f"vor_{fmt}"].mean()
                             for r in te.itertuples()]
    te["near_n"] = [len(matched(df, r)) for r in te.itertuples()]
    return te


def section_perpick(te):
    print("== 1. early TEs (ADP R1-4) vs the WR/RBs at the same slot ==")
    print("   (vor = season pts over the year's last-starter season; "
          "delta = TE vor minus the matched WR/RB mean)")
    for fmt in FORMATS:
        wins = (te[f"vor_{fmt}"] > te[f"near_{fmt}"]).sum()
        ex = te[~te.kelce]
        exw = (ex[f"vor_{fmt}"] > ex[f"near_{fmt}"]).sum()
        d_all = (te[f"vor_{fmt}"] - te[f"near_{fmt}"]).mean()
        d_ex = (ex[f"vor_{fmt}"] - ex[f"near_{fmt}"]).mean()
        print(f"  {fmt:>4}: TE beat the same-slot WR/RB mean in "
              f"{wins}/{len(te)} picks ({wins / len(te):.0%}), "
              f"net {d_all:+.0f} pts/pick; "
              f"ex-Kelce {exw}/{len(ex)} ({exw / len(ex):.0%}), "
              f"net {d_ex:+.0f}")
    print(f"  {'year':<5}{'player':<18}{'pk':>4}  "
          + "".join(f"{'d_' + f:>8}" for f in FORMATS)
          + f"{'TE vor':>8}{'WRRB':>7}{'n':>3}   (std vor cols)")
    for r in te.itertuples():
        print(f"  {r.year:<5}{last_name(r.name):<18}{r.adp:>4.0f}  "
              + "".join(f"{getattr(r, 'vor_' + f) - getattr(r, 'near_' + f):>+8.0f}"
                        for f in FORMATS)
              + f"{r.vor_std:>8.0f}{r.near_std:>7.0f}{r.near_n:>3}")


def section_buckets(df):
    print("\n== 2. TE minus same-pick WR/RB, by ADP band x format ==")
    out = {}
    for lo, hi in BANDS:
        te = df[(df.pos == "TE") & df.rnd.between(lo, hi)]
        cells = []
        for fmt in FORMATS:
            deltas = [getattr(r, f"vor_{fmt}") -
                      matched(df, r)[f"vor_{fmt}"].mean()
                      for r in te.itertuples()]
            out[(lo, hi, fmt)] = np.mean(deltas)
            cells.append(f"{np.mean(deltas):+6.0f}")
        print(f"  R{lo}-{hi:<3} n={len(te):3d}  " + " ".join(cells)
              + "   (std/half/ppr)")
    return out


def section_kelce(te):
    print("\n== 3. the Kelce split (early TEs, ADP R1-4) ==")
    kel, ex = te[te.kelce], te[~te.kelce]
    for fmt in FORMATS:
        print(f"  {fmt:>4}: all {te[f'vor_{fmt}'].mean():+5.0f} | "
              f"Kelce (n={len(kel)}) {kel[f'vor_{fmt}'].mean():+5.0f} | "
              f"ex-Kelce (n={len(ex)}) {ex[f'vor_{fmt}'].mean():+5.0f} | "
              f"same-slot WR/RB vs ex-Kelce "
              f"{ex[f'near_{fmt}'].mean():+5.0f}")


def boom_bust_rows(df, te):
    """Rows for section 4 / fig 4: label -> vor_std series (early picks)."""
    near = pd.concat([matched(df, r) for r in te.itertuples()])
    near = near.drop_duplicates(subset=["year", "name"])
    return {"Early TE, all": te.vor_std,
            "Early TE, no Kelce": te[~te.kelce].vor_std,
            "Same-pick WR": near[near.pos == "WR"].vor_std,
            "Same-pick RB": near[near.pos == "RB"].vor_std}


def section_boombust(rows):
    print("\n== 4. boom/bust, early picks (std) ==")
    print(f"   (boom = {BOOM}+ season pts over the last-starter season; "
          f"bust = {BUST} or worse)")
    shares = {}
    for label, v in rows.items():
        b = (v >= BOOM).mean()
        s = (v <= BUST).mean()
        shares[label] = (b, 1 - b - s, s)
        print(f"  {label:<20} n={len(v):3d}  boom {b:4.0%}  "
              f"middle {1 - b - s:4.0%}  bust {s:4.0%}")
    return shares


def section_cliff(df):
    print("\n== 5. the cliff: TE finish odds by ADP band ==")
    print("   (finish by season total; top-6 = the 'smash' cut of "
          "finding 29)")
    out = {}
    for lo, hi in BANDS:
        te = df[(df.pos == "TE") & df.rnd.between(lo, hi)]
        cells = []
        for fmt in FORMATS:
            t6 = (te[f"fin_{fmt}"] <= 6).mean()
            out[(lo, hi, fmt)] = t6
            cells.append(f"top3 {(te[f'fin_{fmt}'] <= 3).mean():4.0%} "
                         f"top6 {t6:4.0%}")
        miss = (te.fin_std > 12).mean()
        print(f"  R{lo}-{hi:<3} n={len(te):3d}  " + " | ".join(cells)
              + f" | outside top-12 (std) {miss:4.0%}")
    return out


# ---------------------------------------------------------------- figures

def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.tick_params(colors=MUT, labelsize=8.5, length=0)


def fig_same_pick(te):
    """Fig 1 — per-pick diverging bars: TE minus same-slot WR/RB (std)."""
    te = te.sort_values(["year", "adp"], ascending=[False, False])
    delta = te.vor_std.values - te.near_std.values
    labels = [f"{r.year}  {last_name(r.name)}  pk {r.adp:.0f}"
              for r in te.itertuples()]
    fig, ax = plt.subplots(figsize=(8, 0.30 * len(te) + 1.6), dpi=120)
    fig.set_facecolor(SURFACE)
    y = np.arange(len(te))
    ax.barh(y, delta, height=0.52,
            color=[BLUE if d > 0 else RED for d in delta])
    ax.set_yticks(y, labels)
    for tick, r in zip(ax.get_yticklabels(), te.itertuples()):
        tick.set_color(INK if r.kelce else SEC)
        tick.set_fontweight("bold" if r.kelce else "normal")
    keep = set(np.argsort(delta)[:3]) | set(np.argsort(delta)[-3:])
    for i in keep:
        d = delta[i]
        ax.annotate(f"{d:+.0f}", (d, y[i]), textcoords="offset points",
                    xytext=(6 if d > 0 else -6, 0),
                    ha="left" if d > 0 else "right", va="center",
                    fontsize=8, color=SEC)
    ax.axvline(0, color=BASE, lw=1)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    style(ax)
    ax.set_xlabel("season points gained by taking the TE instead "
                  "(standard scoring)", color=SEC, fontsize=9)
    ax.set_title("Every early TE pick, 2018–2025, vs the WR/RBs drafted "
                 "at the same spot\n(Kelce seasons in bold; ADP rounds "
                 "1–4)", color=INK, fontsize=11, loc="left", pad=12)
    ax.legend(handles=[Patch(color=BLUE, label="TE returned more"),
                       Patch(color=RED, label="same-pick WR/RB returned "
                                              "more")],
              loc="lower right", frameon=False, fontsize=8.5,
              labelcolor=SEC)
    fig.tight_layout()
    fig.savefig(FIGS / "te_same_pick.png", facecolor=SURFACE)
    plt.close(fig)


def grouped_bars(data, ylab, title, fname, pct=False):
    """Figs 2 & 3 — bands x the three formats."""
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
    fig.set_facecolor(SURFACE)
    x = np.arange(len(BANDS))
    for j, fmt in enumerate(FORMATS):
        vals = [data[(lo, hi, fmt)] for lo, hi in BANDS]
        bars = ax.bar(x + (j - 1) * 0.16, vals, width=0.13,
                      color=FMT_COLOR[fmt],
                      label={"std": "standard", "half": "0.5 PPR",
                             "ppr": "full PPR"}[fmt])
        if fmt == "std":                      # label the league's format
            for b, v in zip(bars, vals):
                ax.annotate(f"{v:.0%}" if pct else f"{v:+.0f}",
                            (b.get_x() + b.get_width() / 2, v),
                            textcoords="offset points",
                            xytext=(0, 4 if v >= 0 else -12),
                            ha="center", fontsize=8, color=SEC)
    ax.set_xticks(x, [f"R{lo}–{hi}" for lo, hi in BANDS])
    ax.axhline(0, color=BASE, lw=1)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    style(ax)
    if pct:
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_ylabel(ylab, color=SEC, fontsize=9)
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=12)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=SEC,
              loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGS / fname, facecolor=SURFACE)
    plt.close(fig)


def fig_boom_bust(shares):
    """Fig 4 — diverging stacked shares: boom / middle / bust."""
    fig, ax = plt.subplots(figsize=(8, 2.7), dpi=120)
    fig.set_facecolor(SURFACE)
    labels = list(shares)
    y = np.arange(len(labels))[::-1]
    for i, label in enumerate(labels):
        boom, mid, bust = shares[label]
        left = 0
        for share, color in ((boom, BLUE), (mid, GRID), (bust, RED)):
            ax.barh(y[i], share, left=left, height=0.5, color=color,
                    edgecolor=SURFACE, linewidth=2)
            left += share
        ax.annotate(f"{boom:.0%}", (0.01, y[i]), va="center", fontsize=8.5,
                    color="white", fontweight="bold")
        ax.annotate(f"{bust:.0%}", (0.99, y[i]), va="center", ha="right",
                    fontsize=8.5, color="white", fontweight="bold")
    ax.set_yticks(y, labels)
    for tick in ax.get_yticklabels():
        tick.set_color(SEC)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(
        matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.grid(False)
    style(ax)
    ax.set_title("Early picks (ADP rounds 1–4): how often they boom or "
                 "bust — standard scoring", color=INK, fontsize=11,
                 loc="left", pad=12)
    ax.legend(handles=[
        Patch(color=BLUE, label=f"boom (+{BOOM} pts or more)"),
        Patch(color=GRID, label="in between"),
        Patch(color=RED, label=f"bust ({BUST} pts or worse)")],
        loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3,
        frameon=False, fontsize=8.5, labelcolor=SEC)
    fig.tight_layout()
    fig.savefig(FIGS / "te_boom_bust.png", facecolor=SURFACE,
                bbox_inches="tight")
    plt.close(fig)


def main():
    df = build()
    te = head_to_head(df)
    section_perpick(te)
    deltas = section_buckets(df)
    section_kelce(te)
    shares = section_boombust(boom_bust_rows(df, te))
    cliff = section_cliff(df)

    fig_same_pick(te)
    grouped_bars(deltas,
                 "season points, TE minus same-pick WR/RB",
                 "Net value of taking the TE over the WR/RB at the same "
                 "pick, by ADP round", "te_when.png")
    grouped_bars(cliff, "share finishing top-6 at TE",
                 "The cliff: odds a drafted TE finishes top-6, by ADP "
                 "round", "te_cliff.png", pct=True)
    fig_boom_bust(shares)
    print(f"\nfigures written to {FIGS}/te_*.png — feed finding 33")


if __name__ == "__main__":
    main()
