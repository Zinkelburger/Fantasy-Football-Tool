# 31 — Our rookie model is a draft-order list. That's the honest version.

**Confidence: High** (this corrects an earlier mistake of ours; the main result is a tie, measured across nine draft classes)

## TL;DR

We built a rookie projection model that never looks at fantasy ADP: draft capital, draft age, combine numbers, and the landing spot — how much salary his team already pays at his position, and how early the incumbent ahead of him gets drafted. We used to claim it out-ranked the fantasy market's rookie ADP at QB, WR, and TE. **That was wrong**, for a reason worth explaining. Graded properly, the model lands exactly level with simply ranking rookies by where the NFL drafted them, and there is no evidence it beats the fantasy market anywhere.

## The mistake we made

Three-quarters of drafted rookies are never priced by fantasy drafters at all — only 185 of the 721 rookies in our study ever appeared on a rookie ADP list. We scored those 536 unpriced players as a tie for last place, then measured how well each list ranked the class.

That quietly rigged the test. A tie isn't a ranking. Our model gave every one of those 536 players a distinct number, so it got credit for sorting a group the market was never asked to sort. The market was being graded on a question it hadn't answered.

It's worse at some positions than others. Fantasy drafters price maybe one to five rookie quarterbacks a year, and in most years zero to two rookie tight ends. So our old "wins" at QB and TE were rank correlations against a column that was a handful of real numbers and a wall of ties. Those positions cannot be tested against rookie ADP at all — not "we tested and it was close," but *there is no test to run.*

Embarrassingly, the earlier write-up specifically argued this wasn't the same bug we'd just fixed [in the veteran model](#/blog/25-player-model), because every rookie appeared on every list. Same players, yes — but a crippled opponent.

## What's actually true

**Against NFL draft order**, which really is a complete ranking of the class, the comparison is sound and covers all nine classes:

| | draft order | our model |
|---|---|---|
| QB | .58 | **.64** |
| RB | .59 | .53 |
| WR | .62 | .60 |
| TE | .59 | .60 |

Across all 36 position-classes, the model beat draft order by −0.001, with a margin of error of 0.023, winning 15 of 36. That is a tie to three decimal places. Thirteen inputs — a whole combine, salary data, landing spot — and the result is the same as writing down the draft order. (QB looks better, but on nine classes of nine to fourteen players that's one standard error of noise, not a real position-level edge.)

**Against the fantasy market**, only running back and receiver have enough priced rookies to test:

| | classes we could test | draft order | rookie ADP | our model |
|---|---|---|---|---|
| RB | 7 | .37 | **.60** | .42 |
| WR | 3 | .38 | .24 | **.40** |
| QB | 0 | — | — | — |
| TE | 0 | — | — | — |

Pooled over those ten testable class-positions, our model came in 0.078 *behind* rookie ADP with a margin of error of 0.099, winning 3 of 10. Raw draft order did worse still. Nothing here clears its own error bar, so the honest reading is: no evidence of an edge, and the point estimate is against us. The one thing that does survive from the earlier version is the running back story — fantasy drafters are genuinely good at rookie backfields.

## What the model actually learned

Draft capital is nearly the whole model — the coefficient on draft pick is three to six times any other input. That explains the tie: the model is mostly a smoothed restatement of where players were drafted. That's not a scandal; NFL teams watched every college snap and the pick number is their summary of it. But it does mean the extra inputs are earning very little.

The landing-spot reads are the part that adds something real: a rookie QB behind a well-paid veteran scores less (teams don't bench the guy they pay), and a rookie RB scores more when the back ahead of him goes late in fantasy drafts — the one ADP-flavored input we allow, because it prices his path to the field, not the player. Draft age leans the way you'd expect at WR and TE: older rookie, worse.

The combine was a disappointment. Forty times, bench, cone — coefficients near zero almost everywhere, and the few that aren't are small. Two years of hype about a 4.3 forty is worth less than one round of draft position.

## So how accurate is it, in actual points?

Ranking is one question; whether the numbers on the board mean anything is another, and it's the one you'd actually ask. Across the 473 rookies drafted from 2020 to 2025, the model's projection missed a player's real rookie-year average by **1.8 points a game**. Guessing the class average instead misses by 2.5. Fitting a simple curve through NFL draft position misses by 1.7 — very slightly *better* than our model. Same verdict as the ranking test, now in points.

But there's one thing it genuinely does well, and it's worth separating out: **the numbers are honest.** Group every rookie by what the board promised and check what they actually scored:

| Board said | How many | They actually averaged | Became startable |
|---|---|---|---|
| under 2 | 245 | 0.9 | 1% |
| 2 to 4 | 139 | 2.8 | 12% |
| 4 to 6 | 49 | 5.2 | 31% |
| 6 to 8 | 26 | 7.6 | 58% |
| 8 or more | 14 | 10.0 | 86% |

Every tier lands on its promise, and the tiers separate hard — from a 1% hit rate at the bottom to 86% at the top. So the board is trustworthy about *how good* a rookie is likely to be, even though it isn't better than draft order at *sorting* them. Those are different claims and we'd been running them together.

Where it goes wrong is availability, not evaluation. Its worst misses are Travis Etienne, J.J. McCarthy and Travis Hunter — all projected as useful, all of whom missed the season. And its biggest under-calls are the quarterbacks who won leagues: it saw Justin Herbert as a 7.9 (he averaged 20.0), Jayden Daniels as 8.6 (20.2), C.J. Stroud as 10.3 (15.4).

## Trustworthy tiers still aren't an edge

The obvious next thought is to publish the tiers on their own — forget the ordering, just tell people which rookies we're confident in. We checked whether that would be worth anything, by measuring how well each list separates the rookies who became startable from the ones who didn't. Our model scores 0.893 on that test, where 0.5 is a coin flip. Simply fitting a curve through NFL draft position scores 0.895.

And you don't even need the curve. Draft round by itself gives you the same tiers: first-rounders were startable 54% of the time, second-rounders 25%, third-rounders 5%, and everyone after that between 2% and 4%.

So the tiers are real, but the information in them belongs to the NFL draft, not to us — and it's already inside every fantasy draft board, because fantasy drafters watch the draft too. Publishing it as our own confidence tiers would be dressing up a fact you can read for free.

One near-miss worth admitting, since it nearly became a headline here. Looking at just the rookies fantasy drafters actually priced, NFL draft position appeared to separate hits from busts clearly better than the fantasy market did — enough to survive a bootstrap. The tempting claim was "for rookies, trust the NFL draft over rookie ADP." It doesn't hold up: split by position, running back flips the other way and receiver shrinks to almost nothing, and the pooled gap turns out to be carried by sixteen quarterbacks plus the fact that rookie QBs are startable far more often than rookie tight ends. Pooling positions made a fact out of an artifact.

## What the rookie board is good for

It is not a more accurate list than the market. What it *is* is a **complete** one: it prices all 80 drafted rookies, where fantasy ADP prices about 20 — with tiers you can trust even if the order within them is just draft position. Checked head to head, the startable rookies inside our top 10 and inside the NFL's top 10 picks came out at exactly 33 apiece over six classes. At running back, let rookie ADP lead.

## What this is not

No college production — target share, breakout age, yards per route. The free college data mirrors publish play-by-play only, and the good season-stat APIs need keys. That's the v2 upgrade, and given the model currently only ties draft order, it's the only thing likely to move it.
