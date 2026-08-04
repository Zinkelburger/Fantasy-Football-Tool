# 25 — Our projections out-rank the draft board, except at RB

**Confidence: Medium-High** (consistent on seasons the model never saw, but it's one model, not yet stress-tested)

## TL;DR

We built a projection model that predicts each returning player's fantasy points per game for next season from his usage, age, touchdown luck, draft pedigree, and salary. Tested only on seasons it never saw, it ranks players better than the market's draft board at QB, WR, and TE. At RB the market still wins, so there we average the two.

## Where the idea came from

The starting point is a 2012 Stanford class project that predicted running back seasons with a simple line fit on the previous year's yards and touchdowns. Its author listed everything the approach lacked — age, playing-time context, injuries, positions besides RB. That list became our to-do list. The result is one model per position, 16 inputs each, trained on 2,232 player-seasons, using ridge regression — a line-fitting method that resists over-trusting any single stat.

## How well it ranks

We score a board by rank correlation: how well two rankings agree, where 0 is a coin flip and 1 is identical, always measured on a season the model was never trained on. Our model beats the ADP board by about +.09 at QB, +.11 at WR, and +.15 at TE. At RB the market wins — running back value is depth-chart and situation knowledge that drafters genuinely price well — and there, averaging the model's rank with ADP beats either one alone. So the practical rule is simple: trust the model at QB, WR, and TE; at RB, split the difference with the board.

## What the model learned

Its habits are sensible. [Touchdown luck regresses](#/blog/16-td-luck-regresses) — except at RB, where goal-line work is a job that persists. [Age costs backs and receivers the most](#/blog/10-wr-age-effects). Changing teams costs everyone, most of all QBs. A league-mate's salary idea works: a player's share of his team's payroll at his position is the single strongest QB signal — the paid guy plays. And draft pedigree keeps predicting even two seasons into a career, because teams keep feeding their sunk costs.

## What it can't do

No rookies — they have no NFL season to learn from, and need a separate model. No coach or scheme inputs, because no clean free data source exists. And it predicts points per game, not games played; availability is [the injury model's](#/blog/21-injury-model) job. This model powers the season-long board on this site.

---

*The full write-up, with every table and how to reproduce it: [findings/25-player-model.md](https://github.com/Zinkelburger/Fantasy-Football-Tool/blob/main/engine/league-sim/findings/25-player-model.md)*
