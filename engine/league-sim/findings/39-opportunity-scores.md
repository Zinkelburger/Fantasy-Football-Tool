# 39 — Opportunity scores: a per-position price on every touch

> **Re-checked 2026-09-24** in `research/regression-to-expected/`. Usage beats points for next-week MAE at every position, confirmed with both our model (leave-one-season-out) and nflverse. But a 20–30% blend of actual points beats usage alone, and the gap between actual and expected points partly persists (about a third of last season's gap carries forward). It is not pure luck.

## September 15, 2026 correction and scoring extension

The current audit is [REVIEW-2026-09-15.md](../../../research/opportunity-score/REVIEW-2026-09-15.md)
with machine-readable results in `research/opportunity-score/audit-2026-09-15.json`.
It supersedes the historical comparison and predictive claims below. The
original text remains as research history, not current publication guidance.

- Six-point passing TD scoring is fitted separately to fantasy points plus
  two per actual passing touchdown. Expected points never use the current
  game's touchdowns as inputs. The original 4-point fit remains unchanged.
- All public QB/RB/WR/TE rows now come from recorded weekly usage, independent
  of the private advisor's capped player list. Weekly values retain precision
  so season and weekly views agree. The QB detail exposes passing air yards.
- Temporal holdout uses only earlier seasons to fit our test model. The
  previous next-week calculation reused production coefficients fitted on the
  season being evaluated and must not be presented as fully held out.
- Match verified name variants, retain true zero scores with observed usage,
  report excluded records and compare the same player-weeks. Current scores
  are highly correlated, not literally identical. The author is
  F4NT4SYF00TB4LLF4N; Subvertadown hosts his tables.
- Our up-to-four-game average has 0.03–0.13 points lower next-calendar-week
  mean absolute error in all six comparisons. Three exploratory 95% intervals
  include zero. Selection, publication timing and DNP coverage remain limits.
  This is a trailing-average comparison, not validation of EWMA or a claim of
  universal superiority. Keep the usage model; the tested alternatives do
  not consistently improve next-week error.
- The author's explanation confirms yards before catch for receivers. Do
  not infer information leakage or an upper bound on accuracy from a
  correlation. Our inputs also contain information observed during plays
  (target depth, scrambles). Residuals contain skill, randomness and model
  omissions, not just luck.

Recomputed 2025 holdout (fit 2021–2024), half PPR: QB 4pt MAE 4.765,
RMSE 6.192, R² .544; QB 6pt MAE 6.055, RMSE 7.850, R² .505 (640 games).
RB/WR/TE holdout results remain in the linked JSON. All numerical claims on
the revised page are generated from this audit rather than the older tables.

## Original finding (historical)

**Confidence: High.** 26,301 player-games, 2021–2025 regular season, held-out 2025.

Opportunity score = expected fantasy points given usage. One linear
model per position and scoring format, ordinary least squares on
nflverse play-by-play, no tuning, no seed. Refit with
`python engine/weekly/ep_model.py fit`; coefficients live in
`engine/weekly/model/ep_coefficients.json`.

## The model

For each player-game, count:

| feature | meaning |
|---|---|
| rush_att | carries (designed runs and QB scrambles) |
| rush_rz / rush_i10 / rush_i5 | carries from the 20 / 10 / 5 or closer |
| tgt | targets |
| tgt_rz / tgt_i10 | targets from the 20 / 10 or closer |
| tgt_ez | end-zone targets (air yards reach the goal line) |
| tgt_deep | targets thrown 20+ yards downfield |
| air_yds | total air yards on targets |
| pass_att / pass_rz / pass_i10 | pass attempts, and from the 20 / 10 (QB) |
| pass_air_yds | total air yards thrown (QB) |

Response: the player's actual fantasy points that game (nflverse
`fantasy_points` for standard, `fantasy_points_ppr` for PPR, the mean
for half). Regular season only; a player-game exists if he had any
opportunity. The fit is `numpy.linalg.lstsq` with an intercept.

Half-PPR coefficients (points per unit):

| feature | QB | RB | WR | TE |
|---|---|---|---|---|
| intercept | +0.96 | -0.36 | -0.12 | +0.08 |
| pass attempt | +0.13 | – | – | – |
| pass attempt, inside 20 | +0.47 | – | – | – |
| pass attempt, inside 10 | +0.66 | – | – | – |
| air yard thrown | +0.02 | – | – | – |
| carry | +0.60 | +0.55 | +0.89 | +1.15 |
| carry, inside 20 | +0.59 | +0.30 | +0.54 | – |
| carry, inside 10 | +0.77 | +0.37 | +1.24 | – |
| carry, inside 5 | +1.16 | +0.84 | – | – |
| target | – | +0.91 | +0.98 | +0.93 |
| target, inside 20 | – | +0.24 | +0.25 | +0.65 |
| target, inside 10 | – | +1.43 | +0.86 | +0.87 |
| end-zone target | – | +0.77 | +0.76 | +0.97 |
| target 20+ yds downfield | – | +1.06 | +0.03 | -0.12 |
| air yard targeted | – | +0.02 | +0.03 | +0.03 |

Zone features stack: an RB carry from the 3 is worth
0.55 + 0.30 + 0.37 + 0.84 = 2.06 expected half-PPR points; the same
carry from the 40 is 0.55. An RB target inside the 10 is
0.91 + 0.24 + 1.43 = 2.58 before air yards. The prices are readable,
which is the reason for a linear model over a boosted one.

## Held-out accuracy (fit 2021–2024, scored on 2025)

Per-game R² and RMSE, half-PPR:

| pos | R² | RMSE | n test |
|---|---|---|---|
| QB | .544 | 6.19 | 640 |
| RB | .622 | 4.77 | 1,358 |
| WR | .568 | 4.16 | 2,134 |
| TE | .609 | 3.29 | 1,129 |

Standard scoring is a little lower (RB .59, WR .50), PPR a little
higher (RB .66, WR .62, TE .67): the reception point is the most
predictable point in the game.

Season level, players with 8+ games in 2025, Pearson r between mean
expected points and mean actual points: QB .920, RB .972, WR .944,
TE .933. This is the range subvertadown reports for his opportunity
score (.93–.97); the metric behaves the same way.

## vs ffverse `ff_opportunity`

ffverse's expected-points model prices each play with a separate
model per outcome (completion, yards, touchdown, interception). On
the same 2025 player-games:

| pos | ours vs actual | ffverse vs actual | ours vs ffverse |
|---|---|---|---|
| QB | .743 | .780 | .952 |
| RB | .790 | .794 | .981 |
| WR | .755 | .771 | .981 |
| TE | .790 | .797 | .968 |

Game-level Pearson r. ffverse is 0.5–4 points of correlation better;
the two numbers are the same number. We use ours because it runs the
morning after the games from a 15-line feature spec, while ffverse
publishes a season file on its own schedule (the 2026 file did not
exist on September 10, 2026).

## The prediction that matters

`ewma_ep` is an exponentially weighted average of expected points,
α = 0.35 on the newest game, seeded with the prior season's per-game
expected points shrunk toward replacement level by min(1, games/4).
`ewma_ep_pre` is the value going into a week — only earlier weeks.

For every player's second game onward in 2025, correlation with that
game's actual half-PPR points:

| pos | n | EWMA of expected pts | EWMA of actual pts |
|---|---|---|---|
| QB | 563 | **.395** | .377 |
| RB | 1,217 | **.571** | .535 |
| WR | 1,909 | **.487** | .451 |
| TE | 1,003 | **.475** | .435 |

Usage beats the box score for predicting next week at every position.
This is the number the weekly table sorts by, and the number the
waiver tool means by "value".

## What it does not know

- Nothing about the opponent. The site shows the Vegas team total
  beside the score; the advisor multiplies by
  clip(sqrt(implied / 22.5), 0.8, 1.2), a mild tilt per finding 26.
- Nothing about a role change until it shows in the touches. A
  starter's injury moves the backup's opportunity score one game
  late; that is exactly what the Reddit/news layer is for.
- Nothing after the play starts. Broken tackles, drops, and
  interceptions are the luck half by construction.

## Data

nflverse play-by-play and weekly player stats via `nflreadpy`,
fetched by `engine/weekly/nfl_data.py`. Outputs:
`data/weekly/opportunity_<season>.csv` (season to date, one row per
player) and `opportunity_<season>_weekly.csv` (one row per
player-week). Rebuilt Tuesday and Saturday by
`.github/workflows/weekly.yml`.

## vs Subvertadown's published scores (2024, 2025)

Checked 2026-09-15 against his exported weekly tables (RB, WR, TE; he
does not publish QB), matched by player name and week, byes and zero
weeks dropped. Script: `research/opportunity-score/compare_subvertadown.py`.
His score is on the half-PPR scale (regression slope on ours 0.97–1.04,
means within 0.3 points).

Pearson r, per player-game and per player season mean (8+ games), half-PPR:

| season | pos | games | his vs ours | his vs actual | ours vs actual | season: his vs ours | his vs actual | ours vs actual |
|---|---|---|---|---|---|---|---|---|
| 2024 | RB | 1,216 | .991 | .824 | .827 | .998 | .952 | .953 |
| 2024 | WR | 1,864 | .976 | .734 | .752 | .990 | .924 | .928 |
| 2024 | TE | 759 | .979 | .763 | .778 | .991 | .893 | .912 |
| 2025 | RB | 992 | .984 | .776 | .793 | .998 | .959 | .958 |
| 2025 | WR | 1,500 | .922 | .859 | .752 | .976 | .964 | .935 |
| 2025 | TE | 852 | .948 | .827 | .781 | .981 | .932 | .903 |

2024: the two scores are the same number (r .98–.99 per game, .99+ per
season) and predict actual points equally well. 2025 RB likewise.

2025 WR and TE: his score agrees with ours less (.92–.95) and tracks
actual points *better* than ours (.86 vs .75 per game for WR). A pure
pre-snap usage model tops out around .75–.79 per game at WR (ours .752,
ffverse .771 on the same season), so a .86 means his 2025 receiver
score carries information from after the snap; his method page lists
yards before catch, which needs a completion. That makes it a better
descriptor of the week that happened and no longer a strictly
opportunity-only number. Ours stays usage-only by design.
