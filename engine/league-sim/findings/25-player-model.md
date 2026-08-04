# 25 — A ridge projection model beats the ADP board everywhere but RB

**Confidence: Medium-High** (leave-one-year-out over 7–8 target years,
consistent sign pattern; single-model, not yet stress-tested)

## Attribution

This line of work **starts from Kapania (2012), "Predicting Fantasy
Football Performance with Machine Learning Techniques," Stanford CS229
final project**
(cs229.stanford.edu/proj2012/Kapania-FantasyFootballAndMachineLearning.pdf)
— linear regression predicting next-season RB fantasy points from
prior-season yards/game and TDs/game (m=34 RBs, 2007–2010), plus a
k-means-then-regress variant that didn't improve it. His error (~40
pts/season, human expert ~34) and his stated limitations — no age, no
playing-time context, no injuries, one prior season, RBs only — are
the to-do list this model works through. The idea is his; the
extensions, data, and league-specific evaluation are ours.

## TL;DR

Our season projection model: for each position, a ridge regression
(line-fitting that resists over-trusting any one stat) predicts
**next season's fantasy points per game** from 16 features — usage,
TD luck, age, draft capital, salary — trained on 2,232
player-seasons. How well does each ranking match what actually
happened, tested only on seasons the model never saw (Spearman)?

| pos | naive (this yr PPG) | **ADP board** | **model** | ADP+model |
|---|---|---|---|---|
| QB | .572 | .553 | **.647** | .545 |
| RB | .607 | **.694** | .671 | **.700** |
| WR | .669 | .643 | **.753** | .656 |
| TE | .564 | .502 | **.647** | .536 |
| pooled | .603 | .598 | **.679** | — |

The model out-ranks the FFC ADP board at QB (+.09), WR (+.11), and TE
(+.15). **RB is the market's stronghold** (.694 vs .671) — RB value is
depth-chart/situation knowledge the market prices well — and there a
simple rank-average stack (ADP + ½·model) is best (.700). Practical
rule: *trust the model's WR/TE/QB ranks; at RB, average with ADP.*

## What the coefficients say (standardized, λ=30)

| feature | QB | RB | WR | TE |
|---|---|---|---|---|
| TD luck (actual−expected TDs/g) | **−0.55** | +0.01 | **−0.30** | **−0.49** |
| age | −0.10 | **−0.59** | **−0.54** | −0.25 |
| new team next season | **−0.78** | −0.41 | −0.32 | −0.18 |
| position-room cap share | **+2.31** | +0.47 | +0.20 | +0.28 |
| league cap rank at position | −0.24 | +0.46 | +0.49 | +0.02 |
| draft capital (ln pick, higher=later) | −0.38 | **−0.48** | −0.10 | −0.15 |
| rushing yds/g | +0.22 | **+0.73** | −0.09 | +0.06 |

- **TD-luck regresses**, formalizing finding 16 inside a
  multivariate model — except at RB, where TDs are goal-line *role*
  and the role persists.
- **Age decay is real at RB and WR** (−0.6σ), mild at QB/TE —
  finding 10's age story, now conditioned on everything else.
- **The salary hypothesis (league-mate's idea) works**: share of your
  team's position-room cap is the strongest QB feature by far (the
  paid QB1 plays), and paid-lead-back signals carry real weight at RB.
- **Changing teams costs**, most at QB.
- **Draft capital keeps predicting after two seasons of production**,
  strongest at RB — teams give carries to their sunk costs.
- Production features (PPG, prior-year PPG, expected PPG, targets)
  all load positive as expected. Caveat: PPG, expected-PPG, and the
  efficiency gap are linearly dependent (gap = actual − expected), so
  their *individual* coefficients share credit and only their joint
  effect is interpretable; the table above quotes only the
  well-identified features.

## The 2026 board

`data/market/model_board_2026.csv` (returning players; run
`analysis/player_model.py --list` to regenerate). The same run also
writes `_half.csv` and `_ppr.csv`: the whole panel is re-scored and the
model refit at 0.5 and 1.0 points per reception, so a PPR board is a
separate fit rather than the standard board re-sorted (McCaffrey passes
Taylor, Wan'Dale Robinson gains 12 WR spots, deep-only Alec Pierce loses
7). Every number quoted below and above is standard scoring, the
league this study is written for. Top of board: Allen;
Bijan/Taylor/Gibbs; JSN/Nacua/Chase/ARSB; Bowers-tier TE per model.
Sanity behaviors: buys the Justin Jefferson bounce-back (pred 9.2 vs
injured 6.5), fades TD-fueled outliers (Skattebo 12.1 → 8.1).

## Data (all public, fetched by `scripts/fetch_market_data.py`)

nflverse weekly stats (league-exact scoring, per-category floors),
`ff_opportunity` expected stats (usage-based expected PPG + expected
TDs), `adv_weekly` (targets, target share, carries), OverTheCap
contracts via nflverse (exact per-season cap hits → cap %, team
position-room share, league positional cap rank), draft picks (draft
capital), seasonal rosters 2017–2026 (age, team changes). FFC ADP via
the sim pool for the benchmark.

## Methodology

`analysis/player_model.py`. Panel: player-seasons with ≥4 games and
≥2 PPG in season t who appear on a t+1 roster; target = t+1 PPG (≥1
game). Ridge per position, features standardized within training
folds, λ by nested leave-one-year-out; evaluation LOYO on the target
year. Spearman is the metric because a draft list is a *ranking*.
Salary features use the upcoming season's cap numbers — knowable at
draft time (contracts sign in spring).

## Caveats / not done

- **Rookies are out of scope** (no season-t features): the board
  covers returning players only. Rookie plan: draft capital + combine
  + landing spot as a separate model (backlog).
- **No scheme/coordinator features** — no clean free source found;
  the one input we couldn't get. Team-level pace/pass-rate features
  from pbp are the feasible proxy (backlog).
- Survivorship: players who wash out of the league entirely leave the
  panel (no t+1 games); the model doesn't price roster-cut risk.
- PPG target sidesteps availability; total-points drafting should
  multiply by an expected-games model (finding 21's machinery).
- One model per position with 16 features and n≈300–560 — ridge keeps
  it honest, but the year-to-year spread (see per-year table in the
  script output) is wide; 2019 was hard for everything.
