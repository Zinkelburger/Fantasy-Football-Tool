# 38 — Bust chance is real and knowable, and it is entirely the draft price

**Confidence: High.** 1,489 drafted player-seasons 2018–2025, four
independent bust definitions, leave-one-year-out scoring, and 14 of 14
single-feature tests came back noise. This is the fifth independent
confirmation of the same pattern in this project.

- A calibrated bust probability **is** buildable. Price alone scores
  AUC **0.79** at predicting "never gave you a startable season" and
  its predicted rates land on the actual rates within a few points
  across the whole range.
- **Nothing we know adds to it.** Age, prior-season TD luck, prior
  games missed, prior points per game, rookie status, prior targets and
  prior carries were each tested on their own against price. All 14
  tests (7 features × 2 definitions) returned noise.
- The kitchen-sink model beats price-only by **+0.002 to +0.023 AUC**
  depending on definition — every confidence interval crosses zero.
- So the honest product is a bust number **derived from draft slot and
  position**. It sets expectations correctly. It cannot help you choose
  between two players sitting at the same pick.

## Question

The board already shows a price. Does anything we know in August —
age, TD regression, injury history, last year's usage — move a
player's bust probability *after* the price has had its say?

Asked the other way: users want a per-player "bust chance" on the
board. Is such a number statistically real, and does it contain
anything beyond the round number?

## Setup

- `analysis/bust_model.py`, base panel from `round_profile.build()`:
  every ADP-drafted QB/RB/WR/TE 2018–2025, 1,489 player-seasons.
- **Every feature is preseason-knowable.** Prior-season features are
  keyed to the draft year they'd be read in — 2023's row carries 2022's
  numbers. Nothing peeks at the season being predicted.
- **Leave-one-year-out**: fit on seven seasons, predict the eighth,
  pool the out-of-sample predictions. No model ever grades its own
  training year.
- Logistic regression, ridge-penalised, IRLS. Nested comparison:

  | Model | Features |
  |---|---|
  | M0 | intercept only (the base rate) |
  | M1 | log(ADP) + position — "the price" |
  | M2 | M1 + age |
  | M3 | M1 + age, rookie, TD luck, prior PPG, prior games missed, prior targets, prior carries |

- Four bust definitions, so the answer can't hinge on one arbitrary
  cutoff. `pos_rank` is the player's positional draft rank (RB8 etc.),
  `fin` his positional finish by season total points. A player with no
  season at all is a bust in every definition.

  | Name | Definition | Base rate |
  |---|---|---|
  | `bust_2x` | `fin > 2 × pos_rank` | 24.6% |
  | `bust_1_5x` | `fin > 1.5 × pos_rank + 3` | 33.2% |
  | `bust_starter` | missed top-12 (QB/TE) / top-24 (RB/WR), among picks drafted inside that cut | 38.5% |
  | `not_startable` | missed that cut, all picks | — |

## Result 1 — price predicts, features don't

Out-of-sample AUC (higher is better), Brier and log-loss (lower is
better):

| Target | M0 | M1 (price) | M2 (+age) | M3 (+all) | M3 − M1 | 95% CI | Verdict |
|---|---|---|---|---|---|---|---|
| `not_startable` | 0.438 | **0.791** | 0.794 | 0.794 | +0.0027 | [−0.005, +0.011] | noise |
| `bust_2x` | 0.461 | **0.687** | 0.685 | 0.689 | +0.0022 | [−0.013, +0.017] | noise |
| `bust_starter` | 0.476 | **0.622** | 0.628 | 0.645 | +0.0230 | [−0.008, +0.054] | noise |
| `bust_1_5x` | 0.476 | **0.595** | 0.592 | 0.601 | +0.0061 | [−0.013, +0.026] | noise |

M0 sits at chance, confirming the scoring is honest. M1 jumps a long
way — the market genuinely knows who is risky. M2 and M3 do not move
it. Note that adding age alone (M2) makes two of the four definitions
*worse*.

`bust_starter` has the largest point estimate (+0.023) and 5 of 8
held-out seasons positive, which is exactly what noise looks like at
n=576. It is the one worth re-testing when more seasons accumulate.

## Result 2 — one feature at a time

A kitchen sink can drown a real signal, so each candidate was also run
alone against price:

| Feature | `bust_2x` Δ AUC | 95% CI | `not_startable` Δ AUC | 95% CI |
|---|---|---|---|---|
| prior games missed | +0.0085 | [−0.002, +0.019] | +0.0010 | [−0.004, +0.006] |
| TD luck | +0.0023 | [−0.008, +0.013] | −0.0018 | [−0.004, +0.000] |
| prior PPG | +0.0023 | [−0.008, +0.013] | −0.0020 | [−0.004, +0.001] |
| age | −0.0016 | [−0.006, +0.003] | +0.0027 | [−0.002, +0.008] |
| rookie | −0.0004 | [−0.002, +0.001] | −0.0003 | [−0.002, +0.002] |
| prior targets/g | −0.0011 | [−0.006, +0.004] | +0.0001 | [−0.002, +0.003] |
| prior carries/g | −0.0023 | [−0.009, +0.005] | −0.0009 | [−0.003, +0.001] |

**14 of 14 noise.** Four of seven features have a negative point
estimate. The best single result — prior games missed, +0.0085 — is
consistent with finding 18: injury history is nearly worthless as a
predictor.

Age also fails to separate busts *inside* a price band, and the signs
do not even agree:

| Band | RB | WR | TE | QB |
|---|---|---|---|---|
| R1–3 | −4% | +8% | — | — |
| R4–8 | +11% | −4% | −5% | −5% |
| R9–15 | −5% | +9% | +4% | +4% |

(old-minus-young bust rate, split at the within-band median age)

## Result 3 — the price-only number is well calibrated

`not_startable`, predicted vs actual, out of sample:

| Predicted bin | n | Mean predicted | Actual |
|---|---|---|---|
| 0–20% | 95 | 11.3% | 17.9% |
| 20–40% | 133 | 30.3% | 32.3% |
| 40–60% | 250 | 50.8% | 45.6% |
| 60–75% | 393 | 68.3% | 64.1% |
| 75–85% | 351 | 80.3% | 82.6% |
| 85–95% | 267 | 88.1% | 93.3% |

`bust_2x` is tighter still: 14.7 predicted / 14.5 actual, 24.6 / 23.8,
34.6 / 38.5, 44.5 / 46.1, 63.7 / 62.5.

Expressed the way a drafter would read it, chance of a startable
season by round (this reproduces finding 29's 81% → 5% curve
independently):

| Round | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Startable | 81% | 68% | 63% | 54% | 44% | 46% | 32% | 34% | 27% | 20% | 24% | 15% | 21% | 7% | 5% |

## Why this keeps happening

This is the fifth independent result in this project with the same
shape:

- **Finding 25** — the ADP board beats the player model at every
  position.
- **Finding 31** — the rookie model ties draft order exactly.
- **Finding 32** — any model weight in a draft strategy is neutral at
  best; pure ADP wins.
- **`disagreement_check`** — our disagreement with ADP only correlates
  with residual past positional rank 30, where the market stops
  looking.
- **This finding** — nothing we know moves bust probability after
  price.

The mechanism is the same each time. Age, TD regression and injury
history are not secrets; they are the most widely discussed inputs in
fantasy football, and the market has already docked the player for
them by the time an ADP exists. A 30-year-old receiver coming off a
TD-luck spike is not *unpriced* — he is cheap **because** of it. Our
features re-derive information the price already contains.

## What to do with it

- A bust/startable number **can** ship, and it is honest: it is
  calibrated and out-of-sample validated. Label it for what it is —
  a function of where the player is being drafted.
- It is genuine expectation-setting ("your 10th-rounder is a 1-in-5
  shot at a starter") and useless as a tiebreak between two players at
  the same pick. Any UI must not imply otherwise.
- Do **not** ship a bust number that claims to incorporate age or TD
  regression. We tested that directly and it does not survive.
- If it ever does move, the likeliest place is `bust_starter` on early
  picks, and the likeliest feature is prior games missed. Re-test when
  2026 and 2027 land.

## Honest limits

- Eight drafts. A +0.02 AUC edge would need roughly triple this sample
  to resolve, so "noise" here means "not detectable in 1,489
  player-seasons", not "provably zero".
- ADP is FantasyFootballCalculator standard-scoring; a PPR board could
  in principle price these features differently, untested.
- The features are the ones already in this repo. A genuinely new input
  — beat writer reporting, contract data, training-camp usage — is not
  ruled out by this result.
- `bust_2x` rises with pick quality (52% in round 1, 13% in round 15)
  because 2× positional rank is a much harder bar early. That is
  internally consistent but makes it the wrong number to display;
  `not_startable` is the display-friendly one.
