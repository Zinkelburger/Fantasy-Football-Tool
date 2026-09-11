# 39 — Opportunity scores: a per-position price on every touch

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
