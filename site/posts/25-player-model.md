# 25 — We graded our projections against the draft board. The board won.

**Confidence: High** (this corrects an earlier mistake of ours, and the answer comes out the same at all four positions)

## TL;DR

We built a projection model that predicts each returning player's fantasy points per game for next season from his usage, age, touchdown luck, draft pedigree, and salary. We used to say it ranked players better than the market's draft board at QB, WR, and TE. **That was wrong.** We were grading the two lists on different sets of players, which flattered ours. Graded on the same players, the draft board beats our model at every position. What still helps — a little — is using the model as a tiebreaker on top of the board instead of in place of it.

## Where the idea came from

The starting point is a 2012 Stanford class project that predicted running back seasons with a simple line fit on the previous year's yards and touchdowns. Its author listed everything the approach lacked — age, playing-time context, injuries, positions besides RB. That list became our to-do list. The result is one model per position, 20 inputs each, trained on 2,232 player-seasons, using ridge regression — a line-fitting method that resists over-trusting any single stat.

## The mistake we made

To score a ranking you ask how well it matches what actually happened. We ran that check on every returning player for our model, but only on players who had a draft price for the market's list — because players nobody drafts don't have one.

That sounds harmless. It isn't. The players with no draft price are the deep, undrafted end of the league: receivers who went on to average 2.9 points a game, against 7.4 for the drafted ones. Sorting a list that runs from stars to scrubs is easy. Sorting only the players you'd actually consider drafting is hard. We were handing our model the easy part and never asking the market to do it.

The giveaway: a dumb baseline — rank everyone by last season's points per game — gains just as much from the same mistake. It was the player list, not the model.

## What's actually true

Every list graded on the same players, always on a season the model was never trained on. Rank correlation, where 0 is a coin flip and 1 is a perfect match:

| | last year's PPG | draft board | our model | board + model |
|---|---|---|---|---|
| QB | .37 | **.55** | .43 | .55 |
| RB | .55 | .69 | .64 | **.70** |
| WR | .54 | .64 | .61 | **.66** |
| TE | .47 | .50 | .49 | **.51** |
| all | .48 | **.60** | .54 | **.60** |

The board beats our model at all four positions. Averaging the two edges the board alone, but barely: across 32 position-seasons it won by 0.006 with a margin of error of 0.005, ahead in 18 of them. That's a hint, not a finding — and we since tested that hint properly. [Simulating 9,000 leagues](#/blog/32-draft-sim) showed the blend is actually *worse* to draft with: pure ADP won titles 20.7% of the time, a quarter-model tilt 18.7%, a half-and-half blend 14.8%. Every step toward the model made drafting worse, so don't use the blend either.

**So the honest advice is to draft off the board.** Use our projections to pick between players you already rate about the same, not to move a player up or down a round.

There's a real reason the market wins. A draft price in August already contains training-camp reports, depth charts, new coordinators, holdouts, and the rookies drafted to take somebody's job. Our model sees last season's stat line, contracts, and age. It is playing with fewer cards.

## We tried to fix it

Retraining the model on only draftable players didn't close the gap. Handing the model the draft price itself as an input pulled it level and no further — which tells you the model knows almost nothing the board doesn't.

Then we tried the idea that seemed most likely to work: **the depth chart.** For a receiver, where does he sit in his own team's receiver room, and how far back is the next guy?

It turned out to be a real predictor. Being the clear lead back on your team is worth a lot, and a big gap back to the next man at your position is the strongest version of that signal at every position. Adding it made our standalone model meaningfully better.

But it added nothing on top of the draft board — for a reason we should have seen coming. We were reading the depth chart *off the draft board* in the first place. Asking "is he his team's WR1?" means checking which teammate is drafted earlier. The model was rediscovering what the board had already told it.

One piece of that idea is genuinely independent: **the rookie a team just drafted at your position.** That comes from the NFL draft, not from fantasy prices. It's in the model now, and it points the way you'd expect at all four positions — a rookie taken early at your position costs the incumbent. Whether it actually improves the rankings is still too close to call, and we'd rather say so than dress it up.

## What you'll see on the board

Click a player and you'll now get a plain line about his position room: *"He's the Bengals WR1 on the draft board — 31 picks ahead of their WR2 (Tee Higgins)"*, plus a note if his team spent a real pick at his position this year. It's there to show you who he has to beat out. It is deliberately not a buy or fade mark, because — as above — it isn't a disagreement with the market.

## What the model learned

None of the correction touches what the model *learned*; those are descriptions of how players age and score, and they hold up. [Touchdown luck regresses](#/blog/16-td-luck-regresses) — except at RB, where goal-line work is a job that persists. [Age costs backs and receivers the most](#/blog/10-wr-age-effects). And when the model can see both a player's age and his seasons in the league, they split: the tight-end decline loads almost entirely on mileage, not birthdays — an old TE in his first starting years is fine — while backs and receivers decline on age no matter how fresh the legs. Changing teams costs everyone, most of all QBs. A league-mate's salary idea works: a player's share of his team's payroll at his position is the single strongest QB signal — the paid guy plays. And draft pedigree keeps predicting even two seasons into a career, because teams keep feeding their sunk costs.

## What it can't do

No rookies — they have no NFL season to learn from; [the rookie model](#/blog/31-rookie-model) covers them separately. No coach or scheme inputs, because no clean free data source exists. And it predicts points per game, not games played; availability is [the injury model's](#/blog/21-injury-model) job. The half-PPR and PPR boards are separate fits — the model is retrained on points scored that way, not the standard board re-sorted — but the head-to-head above is standard scoring only, because the free ADP feeds don't archive per-format history to grade against.
