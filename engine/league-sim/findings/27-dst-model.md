# 27 — D/ST weekly model: Vegas is ~97% of everything anyone knows

**Confidence: High** (4,089 defense-weeks, 8 seasons, LOYO)

## TL;DR

A weekly D/ST projection built subvertadown-style (his published
predictability analysis guided the design — see Attribution): opponent
implied total from Vegas + opponent giveaways + opponent sacks-allowed
(the O-line angle) + own-defense traits + home/wind + opponent QB-Elo.
Leave-one-season-out, within-week Spearman vs actual D/ST points:

| model | Spearman | Pearson | MAE |
|---|---|---|---|
| naive (own D/ST ppg) | .127 | .123 | 4.51 |
| **Vegas only (opp implied total)** | **.304** | .299 | 4.31 |
| + opp O-line / giveaways | .307 | .302 | 4.31 |
| + own defense traits | .309 | .301 | 4.31 |
| + home/wind | .308 | .299 | 4.31 |
| + opponent QB-Elo | .308 | .299 | 4.31 |

**One number carries the position.** Everything else — O-line quality,
giveaway-proneness, the defense's own yards-allowed skill, even
whether a backup QB starts — adds ≤ .005, because the closing line
already prices all of it (the QB-Elo null is the cleanest proof: the
spread moves when the starter sits, before our feature ever sees it).

## Practical rules (site products 3/6, family-league streaming)

- Rank D/ST by **opponent implied total**, full stop. Each Vegas point
  off the opponent's total ≈ +0.38 D/ST pts.
- Tiebreakers that are real but tiny: giveaway-prone opponent (+0.36
  per giveaway/g), sack-prone O-line (+0.50 per sack-allowed/g), wind
  ≥15mph (+0.4).
- **Don't pay for a "good defense"** — own-defense trait adds ~nothing
  to weekly ranking (coefficient ≈ 0 once the market is in). Stream
  freely; the naive .127 → model .304 gap is the streaming edge.
- D/ST is the noisiest slot in fantasy: mean 5.1, sd 5.8 — the model
  ceiling is a ranking tilt, not a prediction.

## Attribution & the 0.42 question

Design follows what subvertadown has published
(subvertadown.com/article/attempting-to-find-a-more-predictable-d-st-scoring-scheme):
points-allowed is mostly the opponent, sacks/turnovers regress hard,
yards-allowed is the one semi-stable defensive trait (self-corr
0.175). He reports his full model reaching ~0.42 correlation vs our
0.30-0.31; his exact metric (pooled vs within-week, scoring scheme) is
unstated, so the numbers aren't directly comparable. The fair test:
he publishes free weekly D/ST ranks — **log them alongside ours from
September and score both against actuals** (goes into the accuracy
harness, SITE_PLAN item 2).

## Head-to-head vs subvertadown (2026-08-04)

Three comparison angles, since his exact projections are paywalled and
his accuracy-report leaderboards are chart images:

1. **Metric-matched self-comparison.** His reports display Yahoo
   scoring; his methodology article implies full models reach ~0.37
   pooled correlation under standard schemes. Ours, recomputed both
   ways (`scratchpad dst_yahoo` variant): 2024 pooled Pearson
   **0.378** (ESPN) / 0.371 (Yahoo); 2025: 0.312 / 0.310. Within-week
   Spearman 0.34-0.35 both years. We are at or near his published
   ballpark in 2024 and a shade under in 2025 — with a 7-feature OLS.
2. **Live agreement.** His free page shows only his top-2 for 2026
   week 1: Jaguars 9.0, Chargers 8.7. Our board (opponent implied
   totals from the Aug-2026 odds snapshot): **#1 Jaguars vs Browns
   (16.5 implied), #2 Chargers vs Cardinals (17.8)** — identical
   picks. At the top of the board the two engines are the same
   signal wearing different clothes.
3. **The real test starts in September**: log his free weekly ranks +
   FantasyPros D/ST ECR alongside ours, score all three against
   actuals (accuracy harness, SITE_PLAN item 2). Historical
   head-to-head would need his past lists (wayback is unreachable
   from this environment; hand-pasted tables would work, as with the
   WR/CB test).

## Methodology

`analysis/dst_model.py`. D/ST points computed from play-by-play
2018–2025 (sacks, INTs, fumble recoveries, safeties, defensive TDs) +
final scores for points-allowed tiers (ESPN-default-ish; tiers in
`PA_TIERS`). Features are season-to-date rates with a 4-game
prior-season blend (leak-free early weeks). Opponent QB value from
nfelo's continued QB-Elo (`qb_elos.csv`). OLS per ladder step, LOYO by
season.

## Caveats

- Special-teams return TDs are not credited (defensive TDs only) —
  D/ST points slightly undercounted; irrelevant for ranking.
- PA tiers are ESPN-default approximations; the site will need
  per-platform scoring configs (Yahoo scorer already exists in
  `defense_prediction/`).
- Uses closing lines; Tuesday-waiver decisions see softer numbers, so
  live edge is a bit smaller than backtest edge.
