# 27 — D/ST weekly model: Vegas is ~97% of everything anyone knows

**Confidence: High.** 4,089 defense-weeks, 8 seasons, leave-one-year-out
testing — train on 7 seasons, score on the held-out 8th, rotate.

Pick your defense with one number: the **opponent implied total** — how
many points Vegas expects the offense your defense is facing to score
(derived from the game's point spread and over/under). Fewer expected
opponent points, better defense start.

In eight seasons of backtesting that single stat predicted weekly
defense scoring better than everything else we tried combined. O-line
quality, turnovers, home field, wind, even whether a backup QB starts:
each moved accuracy by ≤.005. The betting line already knows all of
it. (The design follows subvertadown's published work — see
Attribution.)

The model ladder, scored by how well each version ranked defenses
within a week. Spearman is rank correlation: 1.0 means the model's
weekly ordering matched reality perfectly, 0 means it was random. MAE
is the average miss in fantasy points.

| model | Spearman | Pearson | MAE |
|---|---|---|---|
| naive (own D/ST points per game) | .127 | .123 | 4.51 |
| **Vegas only (opp implied total)** | **.304** | .299 | 4.31 |
| + opp O-line / giveaways | .307 | .302 | 4.31 |
| + own defense traits | .309 | .301 | 4.31 |
| + home/wind | .308 | .299 | 4.31 |
| + opponent QB-Elo | .308 | .299 | 4.31 |

**One number carries the position.** O-line quality,
giveaway-proneness, the defense's own yards-allowed skill, a backup QB
starting — each adds ≤ .005, because the closing line already prices
it. The QB-Elo null is the cleanest proof: the spread moves when the
starter sits, before our feature ever sees it.

## Yes, the model counts sacks and pick-6s

The obvious objection: "surely some defenses score way more pick-6s,
interceptions, and sacks than others — are we even counting those
points?" Two answers.

**1. Every scoring category is counted.** The model's target — the
thing it predicts — is full D/ST fantasy scoring, computed from
play-by-play data: 1 point per sack, 2 per interception, 2 per fumble
recovery, 2 per safety, 6 per defensive touchdown (pick-6s and
scoop-and-scores included), plus the points-allowed tier bonus. Sacks
and turnovers are most of what we're predicting.

**2. Better defenses exist, and Vegas already prices them.** The
Ravens really do get more sacks and interceptions than the Panthers.
When a great defense takes the field, the opponent's implied total
drops *because* the market knows the defense is good. "Opp implied
total" is not an alternative to measuring defense quality. It is a
measure that already contains defense quality, priced by people
betting real money.

The "+ own defense traits" row tests this directly: add the defense's
own sack rate, yards allowed and takeaway rate on top of the Vegas
number and weekly ranking accuracy moves .304 → .309. Nearly nothing.
Sacks and turnovers regress violently week to week — a defense's own
interception rate barely predicts its next-game interceptions — and
the one semi-stable trait, yards allowed, is already in the line.

## Rules (site products 3/6, family-league streaming)

- Rank D/ST by **opponent implied total**, full stop. Each Vegas point
  off the opponent's total ≈ +0.38 D/ST pts.
- Tiebreakers that are real but tiny: giveaway-prone opponent (+0.36
  per giveaway/g), sack-prone O-line (+0.50 per sack-allowed/g), wind
  ≥15mph (+0.4).
- **Don't pay for a "good defense."** Own-defense traits add ~nothing
  to weekly ranking once the market is in. Stream freely; the naive
  .127 → model .304 gap is the streaming edge.
- D/ST is the noisiest slot in fantasy: mean 5.1 points, standard
  deviation 5.8. The model ceiling is a ranking tilt, not a
  prediction.

## What the site product still needs

Head-to-head, subvertadown's D/ST page wins on presentation and
horizon, not signal — at the top of the board our picks are identical
(see below). Four additions would close the gap:

1. **Confidence scores.** The model's typical miss is a residual
   spread of ~4.3 points, so each projection can ship with an honest
   probability: "72% chance this defense outscores the median start
   this week." That is ranking confidence, not point-prediction
   confidence. With a position this noisy, a score-to-the-point
   prediction would be fake precision.
2. **Multi-week outlook: this week / next 4 weeks / rest of season.**
   Answers "is this defense good for the season, or just one week?"
   Future weeks have no betting lines yet, so future opponent implied
   totals must be synthesized from a team strength rating (nfelo-style
   Elo, or our own from game scores) plus the schedule. This is where
   defense quality legitimately re-enters the model: over a stretch of
   weeks, schedule softness plus own strength decide whether a defense
   is a hold or a one-week rental. nfelo can't beat this week's
   closing line — nothing in our ladder could — but it's the right
   ingredient for weeks that don't have lines yet.
3. **Season-to-date history strip.** We already compute every
   defense's weekly fantasy points from play-by-play. Show the
   week-by-week strip next to each defense. It predicts nothing, but
   it answers "has this D actually been producing?" and builds trust
   in the ranks.
4. **Per-platform scoring toggle (ESPN / Yahoo).** ESPN-default tiers
   are implemented; a Yahoo scorer already exists in
   `defense_prediction/`. The backtest holds under both (2024 pooled
   Pearson 0.378 ESPN / 0.371 Yahoo), so this is a display/config
   task, not a research task.

## Attribution & the 0.42 question

Design follows what subvertadown has published
(subvertadown.com/article/attempting-to-find-a-more-predictable-d-st-scoring-scheme):
points-allowed is mostly the opponent, sacks/turnovers regress hard,
yards-allowed is the one semi-stable defensive trait (year-over-year
self-correlation 0.175). He reports his full model reaching ~0.42
correlation vs our 0.30–0.31. His exact metric (pooled vs within-week,
scoring scheme) is unstated, so the numbers aren't directly
comparable. The fair test: he publishes free weekly D/ST ranks — **log
them alongside ours from September and score both against actuals**
(goes into the accuracy harness, SITE_PLAN item 2).

## Head-to-head vs subvertadown (2026-08-04)

Three comparison angles, since his exact projections are paywalled and
his accuracy-report leaderboards are chart images:

1. **Metric-matched self-comparison.** His reports display Yahoo
   scoring; his methodology article implies full models reach ~0.37
   pooled correlation under standard schemes. Ours, recomputed both
   ways (`scratchpad dst_yahoo` variant): 2024 pooled Pearson
   **0.378** (ESPN) / 0.371 (Yahoo); 2025: 0.312 / 0.310. Within-week
   Spearman 0.34–0.35 both years. We match his published ballpark in
   2024 and land a shade under in 2025 — with a 7-feature linear
   model.
2. **Live agreement.** His free page shows only his top-2 for 2026
   week 1: Jaguars 9.0, Chargers 8.7. Our board (opponent implied
   totals from the Aug-2026 odds snapshot): **#1 Jaguars vs Browns
   (16.5 implied), #2 Chargers vs Cardinals (17.8)** — identical
   picks. At the top of the board the two engines are the same signal.
3. **The real test starts in September**: log his free weekly ranks +
   FantasyPros D/ST expert-consensus ranks alongside ours, score all
   three against actuals (accuracy harness, SITE_PLAN item 2).
   Historical head-to-head would need his past lists (wayback is
   unreachable from this environment; hand-pasted tables would work,
   as with the WR/CB test).

## Methodology

`analysis/dst_model.py`. D/ST points computed from play-by-play
2018–2025 (sacks, INTs, fumble recoveries, safeties, defensive TDs) +
final scores for points-allowed tiers (ESPN-default-ish; tiers in
`PA_TIERS`). Features are season-to-date rates with a 4-game
prior-season blend (leak-free early weeks). Opponent QB value from
nfelo's continued QB-Elo (`qb_elos.csv`). Ordinary least-squares
regression per ladder step, leave-one-year-out by season.

## Caveats

- Special-teams return TDs are not credited (defensive TDs only), so
  D/ST points are slightly undercounted. Irrelevant for ranking.
- PA tiers are ESPN-default approximations; the site will need
  per-platform scoring configs (Yahoo scorer already exists in
  `defense_prediction/`).
- Uses closing lines. Tuesday-waiver decisions see softer numbers, so
  live edge is a bit smaller than backtest edge.
