# 10 — WR age effects: what survives scrutiny and what was overfit

**Confidence: Medium-High** for "29 and older underperform their
price", after the board-wide re-test below. **Low** for the 29–30
"death zone" specifically — that framing was the overfit part.

> **Extended 2026-08-06.** This page tested ages inside ADP 36–120
> only, and hedged to "use age as a tiebreaker, not a rule". Re-run at
> every price over ten drafts (2016–2025,
> `scripts/wr_archetypes.py --full`), scoring each WR against unflagged
> WRs at the same price and standardizing to the peers' price mix, the
> broad cut is the one that holds:
>
> | Cut | Price-standardized top-24 gap |
> |---|---|
> | **29 and older** | **−8 points [−15, −1]** |
> | 29–30 only | −3 points [−13, +9] |
>
> So it is age, not a two-year death zone. The 29+ result survives
> everything we threw at it: hit thresholds of top-12 (−7), top-24
> (−8) and top-36 (−12), all significant; 2-, 4- and 6-band price
> schemes (−8 in each); both eras (−2.7 early, −7.4 late); and every
> leave-one-year-out refit (−6% to −11%, never flipping). No single
> season drives it.
>
> This is the only one of findings 08/09/10 that came through the
> board-wide re-test, so it is the only one the draft tool still
> states as a verdict — and it now fires at any price, not just the
> middle rounds.
>
> **What kind of penalty it is (2026-08-06).** Splitting the outcome by
> how good a season we ask for, price-standardized, the damage is
> concentrated in the tail:
>
> | Outcome | WR 29+ | Peers | Price-matched gap |
> |---|---|---|---|
> | top-5 | 8/136 | 7.4% | −2.1 [−6.2, +2.0] |
> | top-12 | 17/136 | 17.3% | **−6.9 [−12.1, −1.8]** |
> | top-24 | 37/136 | 32.6% | **−8.0 [−15.1, −0.9]** |
> | beat his price by 40+ ranks | 5/136 | 9.6% | **−5.2 [−9.4, −0.8]** |
>
> His 90th-percentile price-adjusted finish is +31.0 against +39.7 for
> same-priced peers. So the old receiver is not especially likely to be
> *bad* — he is about half as likely to give you the season that wins a
> league. That is a ceiling penalty, and it should weigh most when you
> are shopping for upside and least when you need a floor. The draft
> tool's mark says "lower ceiling at this price" for this reason.

The first pass found a tidy story: mid-round WRs aged 29–30 are a
death zone (17% hit, 61% bust) while 31+ veterans bounce back. Only
half of it survived. **WRs 29 and older do underperform younger ones
as a group**, and 29–30 is the worst age band in most versions of the
test. The 31+ rebound is noise. One reasonable way of slicing the data
softens even the 29–30 dip. Use age as a tiebreaker, not a rule.

## The first-pass data

Mid-round WRs (ADP 36–120), 2020–2025, age at Sept 1:

| Age | n | Top-24 | Bust (>45) | Avg vs cost |
|---|---|---|---|---|
| ≤24 | 85 | 34% | 45% | −14.5 |
| 25–26 | 42 | 38% | 33% | −5.3 |
| 27–28 | 38 | 32% | 34% | −15.6 |
| **29–30** | 23 | **17%** | **61%** | −23.8 |
| 31+ | 16 | 38% | 44% | −17.7 |

A valley at 29–30 with a rebound at 31+, plus a neat mechanism ("the
market reprices at 31, not 29"). Too neat, so we stress-tested it.

## The robustness checks

Slice ~200 player-seasons into 5 age buckets × several outcome
definitions and *some* cell will look extreme by chance. Then you
invent a story for it. The cure is changing things that shouldn't
matter — the era, the ADP band, the bust threshold — and seeing
whether the pattern holds.

| Specification | 29–30 bust | ≤28 bust | 29–30 n |
|---|---|---|---|
| Base (2020–25, ADP 36–120, bust >45) | 61% | 39% | 23 |
| Era 2020–2022 only | 62% | 34% | 8 |
| Era 2023–2025 only | 60% | 45% | 15 |
| Wider band (ADP 30–130) | 58% | 40% | 26 |
| **Narrow band (ADP 48–108)** | **36%** | 37% | 14 |
| Bust >40 | 61% | 45% | 23 |
| Bust >50 | 48% | 33% | 23 |

The 31+ "rebound" under an era split: 2020–22 → 14% hit (n=7);
2023–25 → 56% hit (n=9). The rebound is entirely Adams ×2, Diggs,
Allen, Hopkins in the last three seasons.

## Verdict

- **Survives:** 29–30 mid-rounders underperform ≤28 in 6 of 7
  specifications, in both eras independently, and on avg-vs-cost
  everywhere. The direction is probably real, the magnitude uncertain
  — base-cell bust CI ≈ [41%, 81%] against 41% for everyone else, so
  the intervals touch.
- **Does not survive:** the 31+ rebound. n=16, flips sign across eras.
  No claim should rest on it.
- **The kill shot for tidiness:** the narrow band (48–108) erases the
  valley. Either the effect concentrates at the band edges or n=14 is
  too small to see it. Both readings mean fragile.

For the Jackels: Amari Cooper '24 (age 30) sat in the worst cell of
every specification that shows an effect, so he was flag-worthy.
Tyreek '25 (age 31) sat in the bucket we now decline to characterize —
"he was just unlucky" reads as well as anything else. The robust
filters are finding 08 (buy team-narrative discounts) and finding 09
(don't buy production collapses).

## Methodology

Same cohort machinery as 08–09 (`scripts/wr_archetypes.py`, including
the `robustness of the 29-30 cell` section). Ages from nflverse
birthdates, computed at Sept 1 of each season. Buckets were chosen
after one exploratory pass, which is why the robustness section exists
and why confidence caps at Low-Medium until 2026+ seasons provide
out-of-sample evidence.

## Caveats

- The robustness section above is the caveat.
- If one heuristic must survive: prefer mid-round WRs under 27 or over
  30, and only as a tiebreak between otherwise-equal targets.
- Let findings 08 and 09 drive the actual decision.
