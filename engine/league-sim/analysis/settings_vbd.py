"""How league settings move the draft board, by value-based drafting.

Settings do not change how good players are. They change *who the worst
startable player is* — and value is measured from there. So a knob
matters in proportion to how steep a position's curve is at the point
where it drags replacement level. That one sentence is the whole model,
and it explains every result below.

Three steps, per setting:

1. Points per game at each positional finish rank, 2020-2025
   (`curve`) — the same construction as finding 07.
2. Fill every starting slot in the league greedily, including flex and
   superflex. Replacement at a position is the best player NOBODY
   starts (`replacement`).
3. Value = points - replacement. Sort all four positions together and
   a player's row on that board is his "recommended pick"  (`board`).

This is DESCRIPTION of an idealised market, not a simulation, and it
inherits VBD's blind spot: it assumes replacement level is actually
*obtainable*. Findings 06 and 22 measured that assumption against an
emergent waiver wire and it fails hardest at QB — in two of six seasons
the wire held no startable quarterback at all. So treat the QB rows
here as the market's theoretical price, not as advice, and prefer
finding 36 wherever the two disagree.

Written to answer "does a Subvertadown VBD study transfer to our
league?" (finding 37). The unresolved piece is B17 in BACKLOG.md: this
reproduces three of that study's four results on our curves but not its
claim that QBs should be drafted later as a 1QB league grows.

Usage: settings_vbd.py           (prints every table below)
"""
import sys
from dataclasses import replace
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simfl.config import DEFAULT_SCORING, SEASONS      # noqa: E402
from simfl.data import load_weekly                     # noqa: E402

POSITIONS = ("QB", "RB", "WR", "TE")
MAX_RANK = 70          # deep enough for QB replacement in a 14-team superflex
MIN_GAMES = 6          # finding 07's filter: drops cameo distortion
BASE_SLOTS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}


def curve(ppr: float = 0.0) -> dict[str, dict[int, float]]:
    """pos -> {finish rank: avg PPG}, 2020-2025, at the given PPR."""
    sc = replace(DEFAULT_SCORING, reception=ppr)
    frames = []
    for year in SEASONS:
        wk = load_weekly(year, sc).filter(
            pl.col("position").is_in(POSITIONS), pl.col("week") <= 17)
        tot = (wk.group_by("player_id", "position")
               .agg(pl.col("fpts").sum().alias("tot"), pl.len().alias("g"))
               .filter(pl.col("g") >= MIN_GAMES)
               .with_columns((pl.col("tot") / pl.col("g")).alias("ppg")))
        frames.append(tot.with_columns(
            pl.col("ppg").rank("ordinal", descending=True)
            .over("position").alias("r")).select("position", "r", "ppg"))
    agg = (pl.concat(frames).filter(pl.col("r") <= MAX_RANK)
           .group_by("position", "r").agg(pl.col("ppg").mean()).sort("position", "r"))
    return {p: {int(r): v for _, r, v in agg.filter(pl.col("position") == p).iter_rows()}
            for p in POSITIONS}


def replacement(cv, teams: int, slots: dict, flex: int = 1, superflex: int = 0):
    """Fill the league's starting slots; return (replacement ppg, n started).

    Fixed slots first, then flex greedily by whoever is best on the
    board. Doing the flex greedily rather than by an assumed RB/WR split
    is what lets superflex work: QBs outscore everyone in raw points, so
    a QB-eligible slot goes to QB, which is exactly why superflex
    collapses QB replacement.
    """
    taken = {p: teams * slots.get(p, 0) for p in POSITIONS}
    for _ in range(teams * flex):                       # RB/WR flex
        taken[max(("RB", "WR"), key=lambda p: cv[p].get(taken[p] + 1, 0))] += 1
    for _ in range(teams * superflex):                  # QB-eligible flex
        taken[max(POSITIONS, key=lambda p: cv[p].get(taken[p] + 1, 0))] += 1
    return {p: cv[p].get(taken[p] + 1, 0.0) for p in POSITIONS}, taken


def board(cv, rep, depth: int = 48) -> dict[tuple[str, int], int]:
    """(pos, positional rank) -> overall pick, sorted by value over replacement."""
    rows = sorted(((p, r, cv[p][r] - rep[p])
                   for p in POSITIONS for r in range(1, depth) if r in cv[p]),
                  key=lambda t: -t[2])
    return {(p, r): i + 1 for i, (p, r, _) in enumerate(rows)}


def show(label, cv, teams, slots=None, flex=1, superflex=0, ranks=(1, 2, 3, 5, 8, 12)):
    rep, taken = replacement(cv, teams, slots or BASE_SLOTS, flex, superflex)
    bd = board(cv, rep)
    print(f"\n{label}")
    print("  replacement: " + "   ".join(
        f"{p}{taken[p] + 1} ({rep[p]:.1f})" for p in POSITIONS))
    for p in POSITIONS:
        cells = "  ".join(f"{p}{r}:{bd.get((p, r), '--'):>3}" for r in ranks)
        print(f"  {p:>2} -> overall pick   {cells}")


def main() -> None:
    std = curve(0.0)
    print("== Positional PPG by finish rank, 2020-2025, standard (finding 07) ==")
    for p in POSITIONS:
        print(f"  {p:>2}  " + "  ".join(
            f"#{r}:{std[p][r]:5.1f}" for r in (1, 6, 12, 24, 30, 40) if r in std[p]))

    print("\n\n### Knob 1: league size, 1QB ###")
    for t in (8, 10, 12, 14):
        show(f"{t}-team 1QB, 2RB/2WR/TE/FLEX", std, t)

    print("\n\n### Knob 2: league size, SUPERFLEX ###")
    for t in (8, 10, 12, 14):
        show(f"{t}-team superflex", std, t, flex=0, superflex=1)

    print("\n\n### Knob 3: PPR ###")
    for ppr, name in ((0.0, "standard"), (0.5, "half PPR"), (1.0, "full PPR")):
        show(f"12-team {name}", curve(ppr), 12)

    print("\n\n### Knob 4: roster slots (12-team full PPR) ###")
    ppr = curve(1.0)
    show("2WR + flex", ppr, 12, {"QB": 1, "RB": 2, "WR": 2, "TE": 1})
    show("3WR + flex", ppr, 12, {"QB": 1, "RB": 2, "WR": 3, "TE": 1})
    show("4WR + flex", ppr, 12, {"QB": 1, "RB": 2, "WR": 4, "TE": 1})
    show("4WR, no flex", ppr, 12, {"QB": 1, "RB": 2, "WR": 4, "TE": 1}, flex=0)
    show("3RB + flex", ppr, 12, {"QB": 1, "RB": 3, "WR": 2, "TE": 1})


if __name__ == "__main__":
    main()
