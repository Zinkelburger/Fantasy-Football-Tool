# 19 — Bench RBs are real lottery tickets, but hoarding them buys almost nothing

**Confidence: Medium-High** for the null. Same-engine paired design.
The descriptive split is solid.

## The number

The theory says bench RBs become starters overnight while bench WRs
sit dead. The first half is true. Late-round RBs turn into multi-week
starters more often than WRs — 21% vs 13%.

It buys nothing. A drafter that tilted its bench toward RBs gained
**+0.5 points of all-play and +1.1% titles**. Both inside the noise.

Let RB break ties for your last bench spots. Don't burn mid-round
picks on the theory.

## The tickets are real

`scripts/bench_lottery.py`, ADP 96–180, 2020–2025:

| | Bench RBs (n=151) | Bench WRs (n=154) |
|---|---|---|
| Startable weeks (pos top-24), avg | 3.1 | 3.0 |
| P(4+ startable weeks) | 38% | 33% |
| P(3+ *consecutive* startable weeks) | **21%** | **13%** |
| P(dud: ≤1 startable week) | 36% | 29% |

Same average, different shape. RB is the boom-or-bust asset (Mostert
'23: 13 startable weeks; Bucky '24: 11), WR the steadier one. The
overnight-starter path is real and RB-specific.

## The roster gain is not

Environment v3, n=120 × 6 seasons each, shared batch,
`scripts/bench_sweep.py`, `results_bench/`. Identical drafting until
all starting slots are covered, then bench picks tilted (×0.72 toward
/ ×1.18 against a position):

| Strategy | All-play | ±95% | Playoffs | Titles |
|---|---|---|---|---|
| Bench: hoard RBs | .587 | .008 | 76.2% | 17.5% |
| Bench: hoard WRs | .585 | .008 | 76.8% | 16.7% |
| Untilted (BPA) | .582 | .008 | 74.4% | 16.4% |

The ordering RB ≥ WR ≥ none holds across the summary metrics and
mildly across years. Every gap is inside the CI.

## Why it doesn't pay

1. **The wire sells the same tickets.** When a starter goes down the
   promoted backup is claimable that Tuesday. With news-aware claims
   in v3, and real leaguemates reading the same news, pre-stashing
   pre-pays for what waivers offer. Finding 13's handcuff result
   (fairly-priced insurance) generalized to all bench RBs.
2. **Bench spots have a day job**: bye-week coverage, where a WR body
   is exactly as useful as an RB body.
3. **The tilt only moves rounds ~9–15 picks**, where expected points
   are small whichever position you take (finding 07's flat tails).

## Methodology

Descriptive: startable week = that week's points in the positional
top-24 (12-team starters + flex share); cohort = drafted players with
ADP 96–180. Sim: `BenchTilt` strategies in `simfl/strategies.py`;
control is the same base drafter with no tilt, run in the same batch
with the same seeds. Reproduce: `venv/bin/python scripts/bench_lottery.py`
and `venv/bin/python scripts/bench_sweep.py`.

## Does the sim drain late RBs like the real room?

Challenged (2026-07-30): "by round 10 there are no RBs left in our
league." RBs taken per round bucket, six real drafts vs 30 v3 family
drafts a year:

| Rounds | Real (avg) | Sim (avg) |
|---|---|---|
| 1–3 | 16.0 | 17.5 |
| 4–6 | 10.7 | 12.3 |
| 7–9 | 11.0 | 12.9 |
| **10–12** | **14.5** | **10.9** |
| 13+ | 11.0 | 8.0 |
| Total | 63.2 | 61.4 |

The real room does run on RBs in rounds 10–12 (2025: 20 taken vs
sim's 10.3). The sim drains more RBs in rounds 1–9 instead, and the
cumulative boards converge by the end of round 12 — ~52–54 gone
either way. So the post-draft RB pool matches reality, which is what
the null result's waiver logic depends on. What the model misses is
the *timing fad* of the late run.

For this league: if you want bench lottery RBs, **take them by round
9**, ahead of the documented 10–12 frenzy. Rounds 10–12 are the worst
time to want an RB and the cheapest time to take TE/WR darts, because
the room is looking the other way.

## Caveats

- +0.5 all-play / +1.1 titles is the expected sign and could be a
  small real effect drowned by n=720. Doubling n would resolve it.
  Even the optimistic read is a half-point strategy.
- The tilt tested is moderate — 2–3 picks swung. All seven bench
  spots RB would also wreck bye coverage. Untested.
- In leagues without news-savvy waiver competition, pre-stashing
  gains more. This null depends on the modeled wire being competent.
