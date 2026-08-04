# 01 — RB-RB-RB is the best title-rate plan: it converts the RB cliff into championships

**Confidence: High** (simulation-verified, n=1,440 seasons, null-validated;
numbers are environment v3 — see finding 13's version table)

## TL;DR

Opening the draft with three straight running backs produced **.598
all-play** and a **20.3% championship rate** — 2.4× the 8.3% seat
baseline and 3+ points of title rate clear of every other plan tested.
On all-play it ties the wait-cost drafter (`pick_value`, finding 13's
sibling); on titles nothing touches it. RB-early remains the best way
to convert a weekly edge into rings.

## The data

1,440 simulated seasons per strategy (240 × 6 years, every draft seat),
hero vs eleven family bots calibrated to the league's six real drafts.
See METHODS.md for the harness.

| Strategy | All-play | ±95% CI | Playoffs | Titles | Avg finish |
|---|---|---|---|---|---|
| Pick value (wait-cost) | .599 | .006 | 76.0% | 17.0% | 4.27 |
| Pick value + handcuffs | .598 | .006 | 76.2% | 16.9% | 4.25 |
| **Robust RB (RB-RB-RB)** | **.598** | .006 | 74.2% | **20.3%** | 4.33 |
| Early QB | .592 | .006 | 74.3% | 15.8% | 4.49 |
| BPA (ADP order) | .591 | .006 | 74.2% | 15.3% | 4.48 |
| WR heavy | .585 | .006 | 72.8% | 15.8% | 4.54 |
| Punt TE + stream | .584 | .005 | 74.4% | 15.8% | 4.49 |
| Hero RB | .568 | .006 | 69.1% | 13.4% | 4.95 |
| Late-round QB | .563 | .006 | 68.6% | 12.6% | 5.01 |
| Zero RB | .548 | .006 | 62.5% | 9.7% | 5.44 |
| Family baseline | .500 | .006 | 50.2% | 7.6% | 6.46 |

Per-year all-play for Robust RB:

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| .584 | .601 | **.580** | .589 | .577 | .656 |

Steady against this field — but note 2022, the RB-bust year, where it
was nearly the *worst* disciplined plan (Zero RB hit .618 that year).
The plan's edge is an average, not a guarantee.

## Why it works here

Two format facts multiply (see 07-what-a-starter-is-worth):

1. RB is the steepest value curve: RB1 ≈ 19 PPG falling to ≈ 12 by
   RB10. WR falls only 16 → 10.6 over the same ranks.
2. The FLEX takes only RB/WR, and scoring is non-PPR — so there is no
   way to recover RB scarcity later, and WR volume is cheap all draft.

Grabbing three top-15 RBs corners the scarce asset while the room
spreads across positions. The reason it leads *titles* specifically
while tying on all-play: three early RBs is a concentrated,
higher-variance roster shape, and championship equity pays for
variance at the top (compare `pick_value`'s balanced .599/17.0%).

## Methodology

- Strategy implementation: `simfl/strategies.py` (`RobustRB` — first
  three picks restricted to RB, then identical need-aware
  board-following logic every bot shares).
- Backtest harness and validation: METHODS.md. Raw per-cell results:
  `results/robust_rb_*.json`.
- Environment: v3 (calibrated family noise, reverse-standings waivers,
  news-aware projections). Earlier drafts of this finding cited v1
  numbers (.518/11.2%) from `results_v1_precalibration/`; the ordering
  was the same, the levels were not — see finding 13's version table.
- Reproduce: `venv/bin/python -m simfl.grid --heroes robust_rb -n 240`
  then `venv/bin/python -m simfl.plots`.

## Robustness: does the simulated room compete for RBs like the real one?

Challenged (2026-07-30): "my leaguemates take RBs early — is the sim
field soft on RBs?" Checked against the six real ESPN drafts — RBs
taken in rounds 1–3 (36 picks), real vs sim (30 v3 family drafts/yr):

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| Real room | 16 | 20 | 17 | 14 | 15 | 14 |
| Sim field | 19.8 | 19.4 | 18.1 | 15.3 | 14.9 | 15.2 |

Five of six years match within ~1 pick; the exception (2020) has the
sim *over*-draining RBs, which biases against Robust RB — the finding
is conservative there. The mechanism is also clarified by this table:
the room does draft RBs (~5 in round 1) but *spreads* them across
teams; RB-RB-RB wins by concentration on one roster, not by
exploiting neglect. (Validation script inline in the 2026-07-30
session; reproduce by counting positions in
`data/espn/league_*.json` picks vs `run_draft` output.)

## Update 2026-08-02 (environment v5 spot-check)

A seat-rotated v5 run (n=432/strategy, `analysis/hybrid_strats.py`)
confirms the levels ahead of the full grid rerun: robust_rb **.610
all-play / 21% titles**, still atop the family-room board. Three new
results sharpen the interpretation:

- **The opening *is* the plan.** Welding the wait-cost drafter onto a
  forced RB×3 opening (`rb3_pv`) reproduces robust_rb exactly
  (paired diff −0.000 ± 0.008) — after three RBs, the mid-round engine
  doesn't matter. Conversely, pick_value left alone spends 57% of its
  first three picks on RB anyway; the two plans are a statistical tie
  (+0.010 ± 0.012).
- **The edge is room-specific.** In the sharp room (METHODS,
  `villain="bpa"`), robust_rb keeps only +0.005 ± 0.010 over the
  in-room control while the wait-cost drafter keeps +0.023 ± 0.010.
  RB-RB-RB's margin over other disciplined plans is a harvest of this
  family's measured RB-lateness (+5.1 picks), not a law of nature.
- **The mechanism now has equations.** Finding 23: RB value = 191 −
  31·ln(rank) vs WR 156 − 21·ln(rank) — a 45%-steeper decay, premium
  already priced into ADP, so the edge is taking the fast-depreciating
  position first (forced-swap test: +0.017 all-play in round 1,
  +0.015 round 2, noise by round 3).
- **Hindsight agrees on round 1.** 58% of hindsight-optimal drafts
  open RB (median buy: the season's actual RB1) even with perfect
  knowledge of every alternative — the RB-first skeleton survives the
  strongest test available (finding 24).

## Caveats

- Roughly 9 of the ~10 points of all-play edge here is shared by
  every disciplined plan (see finding 03, corrected): discipline is
  the tide, RB-RB-RB is the extra half-knot plus the title-variance
  shape.
- 2022 shows the plan can trail its rivals in an RB-bust year even
  while beating the field. Never present the average without that row.
- Tested against this family model; a room full of RB-hungry sharks
  would erode the edge (the RBs would be gone). *Now measured*: see
  the 2026-08-02 update — the erosion is nearly total in a
  fully-disciplined room.
- The result is format-local: in PPR or TE-flex leagues this exact
  claim is known to flip (which is finding 02's point in reverse).
