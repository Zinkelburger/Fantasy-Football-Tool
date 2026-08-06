# 31 — The rookie model ties NFL draft order and does not beat rookie ADP (corrected)

**Confidence: High** on the correction. **High** that the model ≈ draft
order (−0.001 ± 0.023 over 36 position-classes). **Low** on anything
about rookie ADP — the fantasy market prices too few rookies to test it
at three of four positions.

> **Corrected 2026-08-05.** This used to claim the model "beats rookie
> ADP at QB/WR/TE, loses at RB." That was an artifact of giving every
> rookie the fantasy market never priced a **tied** worst-rank of 999
> — 74% of the panel. The old version explicitly argued the finding-25
> bug did not apply here because the player set was the same. That
> reasoning was wrong: the set was the same, but the benchmark was
> crippled. A tied block is not a ranking, and the model was being
> scored on its ability to sort a group ADP was never asked to sort.
> Fixed in `analysis/rookie_model.py` (`market_adp_rank` now returns
> NaN and callers mask). Corrected results below.

## Question

Can we rank a rookie class without touching absolute fantasy ADP —
draft capital + combine + landing spot only? Constraint set by the
user: one relative-ADP feature is allowed (the incumbent ahead of the
rookie), because it prices his path to the field, not the player.

## Setup (`analysis/rookie_model.py`)

- **Panel**: all drafted QB/RB/WR/TE, classes 2017–2025 (n=721),
  from nflverse `draft_picks.parquet`; 2026 class (n=80) scored out.
- **Target**: rookie-year fantasy points per **scheduled** game
  (16 pre-2021, 17 after), league-exact scoring, refit per format
  (std / half / full PPR). Per-scheduled, not per-played, so early
  busts and never-played count as the zeros they were.
- **Features (13)**: ln(overall pick); draft age; combine ht/wt/40/
  vertical/broad/cone/shuttle/bench (`combine.parquet`, pfr_id join
  86%, NaN→mean-impute); position-room cap % already committed on the
  drafting team (OTC contracts × rookie-year roster); prior-season
  team offense rating (`team_ratings`); ln(best incumbent ADP at his
  team+position, class-of-year excluded).
- **Model**: per-position ridge, standardized, lambda by nested
  leave-one-class-out (mirrors player_model.py).
- **Eval**: leave-one-class-out Spearman, run separately against each
  benchmark **on the rows where that benchmark is defined**.

## Why rookie ADP can barely be tested

Only **185 of 721** drafted rookies (26%) were ever priced by the
fantasy market. Priced rookies per class, by position:

| class | QB | RB | WR | TE |
|---|---|---|---|---|
| 2018 | 1 | 9 | 6 | 1 |
| 2019 | 1 | 10 | 5 | 1 |
| 2020 | 2 | 12 | 9 | 0 |
| 2021 | 5 | 6 | 7 | 2 |
| 2022 | 0 | 11 | 9 | 0 |
| 2023 | 1 | 8 | 5 | 2 |
| 2024 | 3 | 9 | 7 | 1 |
| 2025 | 5 | 22 | 18 | 7 |

At a floor of 8 players per cell, **RB is testable in 7 classes and WR
in 3. QB and TE are not testable at all.** The old finding's QB (+.14)
and TE (+.14) "wins over rookie ADP" were rank correlations against a
column that was 1–5 real values and the rest ties.

## A) Every drafted rookie — draft order vs the model

Draft order *is* a complete ranking of the class, so this comparison is
sound and covers all 9 classes.

| pos | draft order | **model** |
|---|---|---|
| QB | .579 | **.644** |
| RB | .587 | .532 |
| WR | .619 | .599 |
| TE | .594 | .599 |

**Paired over 36 position-classes: model − draft order = −0.001 ±
0.023, wins 15/36.** Dead level. Thirteen features, a combine, landing
spot and cap data, and the whole thing lands exactly on "rank them by
where the NFL drafted them."

The coefficients say why: `ln_pick` is −2.75 (QB), −2.02 (RB), −1.38
(WR), −0.85 (TE) — 3–6× any other input. The model is mostly a
smoothed restatement of draft capital. QB looks better than draft
order (+.065 mean), but on 9 classes of n≈9–14 that is one standard
error of noise.

## B) Rookies the fantasy market priced — the ADP head-to-head

| pos | classes | draft order | **rookie ADP** | model |
|---|---|---|---|---|
| RB | 7 | .372 | **.599** | .420 |
| WR | 3 | .375 | .240 | **.398** |
| QB | 0 | — | — | — |
| TE | 0 | — | — | — |

Paired over the 10 testable cells:

| comparison | mean diff | se | wins |
|---|---|---|---|
| model − ADP | −0.078 | 0.099 | 3/10 |
| draft order − ADP | −0.118 | 0.095 | 2/10 |

The model does not beat rookie ADP. Neither does raw draft order.
Neither gap clears its own standard error on 10 cells. **On the
rookies the market bothers to price, we have no evidence of an edge,
and the point estimate is against us.** The RB story replicates from
the old version: the fantasy crowd is good at rookie backfields (ADP
.599 vs model .420 over 7 classes).

## C) Accuracy in POINTS, not ranks (`analysis/rookie_accuracy.py`)

Blocks A and B grade ordering. They say nothing about whether the PPG
numbers printed on the board mean anything, which is what a reader
actually sees. n=473 drafted rookies with a gsis id and a pick,
classes 2020-25, LOYO predictions, target = PPG per SCHEDULED game.

| predictor | MAE | bias | RMSE |
|---|---|---|---|
| our model | 1.80 | +0.01 | 2.55 |
| draft order (LOYO log fit on ln pick) | **1.73** | −0.01 | **2.49** |
| class-position mean | 2.50 | −0.00 | 3.26 |

Same verdict as block A, now in points. The model cuts error 28% vs
predicting the average, and is a hair WORSE than a curve through draft
position. Per class it beats draft order in 3 of 6 (2021, 2022, 2025).
Per position it is level at RB/WR/TE (within 0.05 MAE) and clearly
worse at QB (2.93 vs 2.55) — and QB is where block A's rank
correlation looked *best* (.644 vs .579). It orders quarterbacks fine
and prices them badly, because rookie QB outcomes have the widest
spread: a hit averages 20, a bust 4.

**Calibration is the one genuine strength.** Bucketed by projection:

| projected | n | mean proj | mean actual | % >= 7 PPG |
|---|---|---|---|---|
| < 2 | 245 | 1.1 | 0.9 | 1% |
| 2-4 | 139 | 2.9 | 2.8 | 12% |
| 4-6 | 49 | 4.7 | 5.2 | 31% |
| 6-8 | 26 | 6.7 | 7.6 | 58% |
| 8+ | 14 | 10.3 | 10.0 | 86% |

Every bucket's mean projection lands on its mean outcome, and the
tiers separate hard (1% -> 86% startable). The board's *numbers* are
honest and its *tiers* are informative even though its *ordering* adds
nothing over draft position. Those are separable claims.

Usefulness check — startable (>=7 PPG) rookies inside each list's top
10, summed over the six classes: **model 33, NFL's top 10 picks 33.**
An exact tie, again.

### Are the tiers an EDGE? No — the information is the NFL draft's

Calibration says our numbers are honest. It does not say anyone needed
us to produce them. AUC for separating startable rookies (0.5 = coin
flip), n=473:

| score | AUC |
|---|---|
| our model projection | 0.893 |
| draft-order log fit | **0.895** |
| raw draft pick | 0.872 |

Identical. And draft round alone reproduces the tier table:

| round | n | mean actual | % startable |
|---|---|---|---|
| 1 | 65 | 7.4 | 54% |
| 2 | 61 | 4.2 | 25% |
| 3 | 62 | 2.1 | 5% |
| 4-5 | 142 | 1.6 | 4% |
| 6-7 | 143 | 0.8 | 2% |

So "tiers of rookies we're confident in" would be repackaging what
round a player went in — free, public, and already inside rookie ADP
because fantasy drafters read the NFL draft too. **Do not ship it as
an edge.**

### A near-miss worth recording (caught before publication)

On the 151 rookies the fantasy market priced, pooled AUC looked like a
real market inefficiency: draft order 0.808 vs rookie ADP 0.700,
paired bootstrap +0.108, 95% CI [+0.018, +0.198], excluding zero. The
tempting headline was "for rookies, trust the NFL draft over rookie
ADP."

It dissolves within position:

| pos | n | draft order | rookie ADP | diff |
|---|---|---|---|---|
| QB | 16 | 0.727 | 0.509 | +0.218 |
| RB | 68 | 0.805 | **0.844** | −0.040 |
| WR | 55 | 0.768 | 0.720 | +0.048 |
| TE | 12 | — | — | (too few) |

RB reverses and WR is small. The pooled gap was carried by 16
quarterbacks plus the composition effect of pooling positions with
very different startable rates — rookie QBs clear 7 PPG far more often
than rookie TEs. Pooled AUC across positions is not a safe statistic
here. No edge over rookie ADP survives.

Receipts (model top-5 per class) show the failure mode is
availability, not evaluation. The worst misses are Travis Etienne
(proj 7.1, actual 0.0), J.J. McCarthy (7.0, 0.0) and Travis Hunter
(8.6, 0.0) — all missed the season. Per-SCHEDULED-game charges those
to the model in full, which is the right call for a draft board but
means ~a third of its error is an injury model's job, not a
projection's. Biggest under-calls are the QB league-winners it saw as
ordinary: Herbert (7.9 -> 20.0), Daniels (8.6 -> 20.2), Stroud
(10.3 -> 15.4).

## Coefficients (lam=30, full panel, standardized)

`ln_pick` dominates everywhere (above). Landing spot adds real signal:
`room_cap` −0.65 at QB (a paid veteran blocks the rookie),
`ln_vet_adp` +0.46 at RB (weak incumbent → rookie points),
`team_off` −0.65 at QB. `draft_age` negative at WR/TE (−0.20/−0.29).
Combine ≈ noise: |β| mostly < 0.2; the QB `shuttle` +0.75 on n≈105 is
overfit, not signal.

## Product rule (changed)

The rookie board is, in effect, **a draft-order list with a
landing-spot tilt** — present it that way. Do not claim it beats the
fantasy market. At RB the market is measurably better and rookie ADP
should lead. The board remains useful as a *coverage* tool: it prices
all 80 drafted rookies where ADP prices ~20. That is a different and
honest claim from being more accurate.

Board CSV: `data/market/rookie_board_2026.csv` (rebuild via
`analysis/rookie_model.py`, then `build_deploy.py`).
Site rewrite: `site/posts/31-rookie-model.md`.

## Caveats / v2

- No college production (target share, breakout age): cfbfastR free
  mirrors are pbp-only (~100MB/season, ESPN ids that don't join our
  sports-reference slugs); CFBD API needs a key. Draft capital proxies
  much of it. This is the clear v2 upgrade — and given the model
  currently only ties draft order, it is the *only* thing likely to
  move it.
- ADP benchmark uses FFC standard lists; the 2017 class has no ADP file
  (draft-order benchmark covers all 9 classes).
- Only 7 of 80 2026 rookies are in `roster_2026.parquet` yet, so 2026
  landing-spot features come from the draft-team code (PFR→nflverse
  canon map) + the ADP snapshot; refresh rosters before draft week.
- The B-block model is the same fit as the A-block, scored on a subset —
  not refit on priced rookies. Finding 25 tested that refit and it did
  not help there; not retested here (10 cells is too few to learn from).
