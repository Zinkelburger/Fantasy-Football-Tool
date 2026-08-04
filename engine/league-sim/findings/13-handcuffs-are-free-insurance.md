# 13 — Handcuffs are correctly-priced insurance: free to hold, but no edge

**Confidence: Medium-High** (simulation-verified in two environments,
n=1,440 seasons each; the effect is a precise ~zero, not an imprecise
maybe)

## TL;DR

The hypothesis (Andrew's): *rostering your own RB1's handcuff is the
right play in head-to-head — lower variance beats best-ball upside
when you expect to be the better team (e.g. Bucky Irving + Rachaad
White, 2025).*

Verdict: **half right, and the half that's right costs nothing.**
Handcuffs really do deliver starter-level production in exactly the
weeks your starter is out (9.5 PPG, 48% of them at RB1 level). But a
wait-cost drafter that pays a premium for its own handcuffs ties the
plain one — **.598 vs .599 all-play** — because the insurance payout
is offset point-for-point by the flex value of the best-available
pick it gave up. Handcuff on ties, never at a price.

## The descriptive data (2020–2025, `analysis/rules_tests.py`)

124 starter/handcuff pairs (starter = a team's best RB by ADP inside
the top 72; handcuff = same NFL team's next RB on the ADP board), 73
of which saw the starter miss at least one week the cuff played:

| Situation | Handcuff PPG |
|---|---|
| Starter OUT | **9.5** (≈ RB12-level; RB12 = 9.9) |
| Starter playing | **4.6** (below waiver replacement, 6.5) |
| Cuffs at RB1-level (≥9.9) when starter out | **35/73 (48%)** |

The case that motivated the question — Bucky Irving 2025 (missed 8
weeks): Rachaad White gave **7.7 PPG in the Bucky-out weeks** vs 3.6
otherwise. Functioned as designed, mediocre payout (front-loaded:
19 and 14 in weeks 5–6, ≤6 after).

ADP stdev is no tiebreak either way: high-disagreement players
(Croskey-Merritt types) show no systematic residual vs the value
curve (quartile residuals −7 / +2 / +7 / −3 — non-monotone noise).

## The simulation

Strategy `pick_value_hc` (`simfl/strategies.py`): identical to
`pick_value`, but from round 9 the handcuff of an already-rostered
top-72 RB is scored at full lineup weight plus a 10-season-point
insurance bonus. 240 sims × 6 seasons per cell, seat-rotated,
common random numbers vs the plain drafter.

**Environment v2** (calibrated family bots, reverse-standings
waivers, EWMA-only projections — cuffs sit unrecognized for a week
or two after an injury):

| | all-play | titles | note |
|---|---|---|---|
| pick_value | .606 | 17.6% | |
| pick_value_hc | .602 | 18.3% | worse in 5/6 years |

**Environment v3** (adds news-aware projections — see below — so
*everyone* starts and claims promoted backups immediately):

| | all-play | titles | playoffs |
|---|---|---|---|
| pick_value | .599 | 17.0% | 76.0% |
| pick_value_hc | .598 | 16.9% | 76.2% |

Per-year diff (hc − plain, v3): −.006, −.003, −.001, −.002, **+.008**,
−.002. A dead tie: the v2 penalty was partly an artifact of
projection lag; with realistic news-reading the premium is exactly
fairly priced.

## Why there's no edge

A bench spot is an option, and the two options pay the same:

- **Handcuff (narrow option):** pays only when *your* starter sits.
  Marginal payout ≈ 9.5 − ~7.0 (your next-best fill-in) ≈ +2.5 PPG
  across the handful of outage weeks, discounted by the chance the
  starter stays healthy.
- **Best available (broad option):** pays on any bye, any injury at
  the position, or by out-scoring your WR2/flex in any given week.

The variance argument (insurance → titles) showed up with the right
sign in v2 (+0.7pp titles) and vanished in v3 once opponents could
also claim promoted backups off waivers. Both effects are within
±1.1pp title CI.

## Engine change shipped with this finding

`simfl/lineup.py` now models news-reading (`NEWS_PROMOTE = 0.75`,
`STARTER_ADP_CUTOFF = 120`): any week a team's top preseason RB is
inactive, his best active backup projects at 75% of the starter's
projection, for lineup decisions **and** FA/waiver valuation.
Sanity case: Rachaad White's week-5–12 projection rises 4.0 → 10.3
while Bucky is out. This upgrade compressed every hero's edge by
~0.8pp (sharper field) without changing any strategy ordering.

## Environment versions (record-keeping)

| | family bots | waivers | projections | results dir |
|---|---|---|---|---|
| v1 | original (noise=1×ADP sd, rb_bias 0.88) | rolling priority | EWMA | `results_v1_precalibration/` |
| v2 | calibrated to real drafts (noise floor 30, rookie 0.95) | reverse-standings + per-seat activity | EWMA | `results_v2_pre_newsread/` |
| v3 | as v2 | as v2 | EWMA + news promotion | `results/` (pre-rerun) |
| v4 | as v2 | + `done_for_season` cuts | + real Friday injury reports (Q-discount by pos), promotion recalibrated 0.85/0.55/0.30 | (never gridded) |
| v5 (current) | as v2 | + free-agency pass fills post-waiver holes; no claims on knowably-done players; drops never empty a starting slot; 2 claims name distinct drops | as v4 + EWMA runs over 50/50 actual/expected-points blend (LOO-chosen, `analysis/ep_projections.py`) | `results/` after rerun |

Findings 01–12 cite v1 numbers; orderings replicate in v2/v3 but
levels differ (e.g. robust_rb .518 → .607 → .598). Rerun any of them
against `results/` before putting a level (not an ordering) on a slide.
v5's waiver fixes were driven by three measured artifacts of v3/v4: the
default policy spent 25% of its claims on players already out for the
year, a sniped hole claim had no fallback (≈2.6 empty hero starting
slots a season, mostly TE/K — a real manager just grabs the next name
in free agency Wednesday), and an upgrade could cut the team's only
active player at a position. Post-fix: 0% dead claims, 0.03 empty
slots/season.

## Reproduce

```bash
venv/bin/python analysis/rules_tests.py           # descriptive stats
venv/bin/python -m simfl.grid --heroes pick_value,pick_value_hc -n 240
```
