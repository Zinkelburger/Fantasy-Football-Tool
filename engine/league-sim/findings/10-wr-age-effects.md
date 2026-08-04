# 10 — WR age effects: what survives scrutiny and what was overfit

**Confidence: Low-Medium** — this file exists partly to document how a
too-clean story fell apart under robustness checks. Read it as a
lesson in method as much as a finding.

## TL;DR

Our first pass found a tidy story: mid-round WRs aged 29–30 are a
death zone (17% hit, 61% bust) while 31+ veterans bounce back. Then
we stress-tested it and only half survived: **WRs 29 and older do
underperform younger ones as a group**, with 29–30 the worst ages in
most versions of the test — but the "31+ rebound" turned out to be
noise, and one reasonable way of slicing the data softens even the
29–30 dip. Use age as a tiebreaker, not a rule. (This file doubles
as a lesson in how a too-clean story falls apart when checked.)

## The first-pass data (the seductive version)

Mid-round WRs (ADP 36–120), 2020–2025, age at Sept 1:

| Age | n | Top-24 | Bust (>45) | Avg vs cost |
|---|---|---|---|---|
| ≤24 | 85 | 34% | 45% | −14.5 |
| 25–26 | 42 | 38% | 33% | −5.3 |
| 27–28 | 38 | 32% | 34% | −15.6 |
| **29–30** | 23 | **17%** | **61%** | −23.8 |
| 31+ | 16 | 38% | 44% | −17.7 |

A valley at 29–30 with a rebound at 31+, plus a neat mechanism ("the
market reprices at 31, not 29"). Too neat — so we stress-tested it.

## The robustness checks (what "is it overfit?" means concretely)

Overfitting risk here: with ~200 player-seasons sliced into 5 age
buckets × several outcome definitions, *some* cell will look extreme
by chance, and we then invent a story for it. The cure is checking
whether the pattern holds when you change things that shouldn't
matter: the era, the ADP band, the bust threshold.

| Specification | 29–30 bust | ≤28 bust | 29–30 n |
|---|---|---|---|
| Base (2020–25, ADP 36–120, bust >45) | 61% | 39% | 23 |
| Era 2020–2022 only | 62% | 34% | 8 |
| Era 2023–2025 only | 60% | 45% | 15 |
| Wider band (ADP 30–130) | 58% | 40% | 26 |
| **Narrow band (ADP 48–108)** | **36%** | 37% | 14 |
| Bust >40 | 61% | 45% | 23 |
| Bust >50 | 48% | 33% | 23 |

And the 31+ "rebound" under an era split: 2020–22 → 14% hit (n=7);
2023–25 → 56% hit (n=9). The rebound is entirely Adams ×2, Diggs,
Allen, Hopkins in the last three seasons.

## Verdict, honestly

- **Survives:** 29–30 mid-rounders underperform ≤28 in 6 of 7
  specifications, in both eras independently, and on the avg-vs-cost
  metric everywhere. Direction is probably real; magnitude uncertain
  (base-cell bust CI ≈ [41%, 81%] vs 41% for everyone else — the
  intervals touch).
- **Does not survive:** the 31+ rebound. n=16, flips sign across eras.
  No claim should rest on it.
- **The kill shot for tidiness:** the narrow band (48–108) erases the
  valley. Either the effect concentrates at the band edges or n=14 is
  too small to see it — both readings mean "fragile."

Practical translation for the Jackels: Amari Cooper '24 (age 30) sat
in the worst cell of every specification that shows an effect —
legitimately flag-worthy. Tyreek '25 (age 31) sat in the bucket we
now decline to characterize — "he was just unlucky" is as supported
as any other reading. The stronger, more robust filters remain
finding 08 (buy team-narrative discounts) and finding 09 (don't buy
production collapses).

## Methodology

Same cohort machinery as 08–09 (`scripts/wr_archetypes.py`, including
the `robustness of the 29-30 cell` section). Ages from nflverse
birthdates, computed at Sept 1 of each season. Buckets chosen after
one exploratory pass — which is exactly why the robustness section
exists and why confidence caps at Low-Medium until 2026+ seasons
provide out-of-sample evidence.

## Caveats

All of the above — this file *is* the caveat. If one heuristic must
survive: prefer your mid-round WRs under 27 or over 30 only as a
tiebreak between otherwise-equal targets, and let findings 08/09
drive the actual decision.
