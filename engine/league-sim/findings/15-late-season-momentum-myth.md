# 15 — Late-season momentum is a myth

**Confidence: High** (well-powered null: n≈1,000 player-season pairs,
tight confidence intervals around zero, and a clean placebo test)

## TL;DR

"He finished the season hot" tells you **nothing** about next year.
A player's last few weeks predict next season *worse* than his full
season does, and add zero information once you know his full-season
average (partial r = +0.04, indistinguishable from nothing). The
kill shot: the last 5 weeks are no more predictive than the *first*
5 weeks of the same season. A hot finish is a small sample wearing
a story.

## The data

2017→2025, eight season transitions, family scoring (ESPN std, 4pt
pass TD, floored yardage). Sample: rosterable players (top QB24 /
RB50 / WR60 / TE24 by season points), ≥8 games this year, ≥6 next.

Pearson r with next-season PPG:

| Predictor | QB | RB | WR | TE |
|---|---|---|---|---|
| Full-season PPG | **.500** | **.594** | **.577** | **.532** |
| Last 5 weeks | .377 | .511 | .391 | .453 |
| Last 3 weeks | .285 | .481 | .314 | .374 |
| Last 1 week | .126 | .425 | .147 | .195 |

Every shorter window is worse, at every position. Three significance
results (permutation p-values; CIs are player-clustered bootstraps
since the same player contributes multiple pairs):

- **Last-3 adds nothing beyond full-season PPG**: partial r = +0.044,
  p = 0.16, CI [−0.03, +0.11], n = 1,009. A powered null — the CI
  rules out anything but a trivial effect.
- **Recency placebo**: r(last-5, next) − r(first-5, next) = +0.014,
  CI [−0.03, +0.06] on identical rows. September and December weeks
  are interchangeable; more weeks helps only because it's more sample.
- **Full season keeps its signal after controlling for the last 3
  weeks** (partial r = 0.64) — the information flows one way.

## The RB whisper (don't build a slide on it)

RB is the one position where the last week hints at extra signal —
late-season backfield takeovers are sometimes real jobs:

- RB last-1 partial beyond PPG: +0.153, perm p = 0.012, **but** the
  player-clustered CI is [−0.01, +0.30] — not robust. Last-3: +0.102,
  p = 0.08. Suggestive, not proven (Low confidence).
- Fader asymmetry: RB/TEs who *collapsed* over the final 3 weeks
  decline next year by ~0.7–0.8 PPG more than the rest, but only the
  TE version reaches p = 0.04 (CI still grazes zero). Low confidence.

## Draft rule

Draft off full-season (or multi-season) rates. When a August ranking
or a family member cites "how he finished," that information is
already priced into season PPG — or it's noise. The only defensible
exception: an RB whose *role* visibly changed late (starter traded or
benched, not just a hot stretch), and even that is a tiebreaker.

## Methodology

`scripts/next_season_signal.py` (full stats suite ≈4 min; `--quick`
skips it). Weekly points from cached nflverse weeklies scored by
`simfl.scoring`; windows use each season's real length (17 weeks
pre-2021, 18 after); "last-K PPG" requires ≥⌈K/2⌉ games in the
window. p-values: two-sided permutation (5,000 perms, Freedman-Lane
for partials). CIs: 95% bootstrap resampling players (2,000 draws).

## Caveats

- Sample is *rosterable* players; deep-waiver breakouts aren't tested.
- Requires ≥6 games the next year, so career-enders are excluded —
  this biases every predictor equally, not the comparison.
- Week 18 (17 pre-2021) includes playoff-locked teams resting
  starters, adding noise to the shortest windows; the first-K
  placebo shows the conclusion doesn't depend on it.
