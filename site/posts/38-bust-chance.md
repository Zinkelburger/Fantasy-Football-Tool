# 38 — We can tell you a player's bust chance. It's just his draft slot.

**Confidence: High** (1,489 drafted players over eight drafts, four
different definitions of "bust", and fourteen out of fourteen tests
came back empty)

## TL;DR

A bust probability is a real, buildable number — where a player is
drafted predicts whether he'll return a startable season well, and the
percentages we'd print land within a few points of what actually
happens. But everything we hoped would sharpen it — age, touchdown
luck, injury history, last year's usage — adds nothing. The market has
already priced all of it. A bust number tells you about your pick, not
about your player.

## The question

Every draft board shows a price. We wanted to know if anything we
learn in August moves a player's bust chance *after* that price has
had its say. If a 30-year-old receiver coming off a lucky touchdown
season is a worse bet than his draft slot suggests, we should be able
to find it.

## How we tested it

We took every drafted quarterback, running back, receiver and tight
end from the last eight drafts — 1,489 players. Then we built four
models, each one adding more to the last:

- the base rate alone, as a sanity check
- **the price**: where he was drafted, plus his position
- the price plus age
- the price plus age, rookie status, last year's touchdown luck, last
  year's points per game, last year's games missed, last year's targets
  and last year's carries

Every input is something you'd actually know in August — nothing peeks
at the season it's predicting. And we never let a model grade its own
homework: we trained on seven seasons and scored the eighth, rotating
through all eight.

We also used four different definitions of "bust", from "didn't return
a startable season" to "finished more than twice as low as where you
drafted him", so the answer couldn't depend on one arbitrary cutoff.

## The price knows everything

Scored on how well it sorts busts from non-busts, where 50% is a coin
flip:

| Model | "Never gave you a startable season" |
|---|---|
| Base rate only | 44% — no information, as expected |
| **The price** | **79%** |
| Price + age | 79% |
| Price + everything | 79% |

The price does real work. Nothing we add to it does any.

Because a big model can drown a good signal, we also tested each input
**on its own** against the price. Seven inputs, two definitions,
fourteen tests. All fourteen came back as noise, and four of the seven
actually made the prediction slightly worse. The best of them — last
year's games missed — is exactly the input our earlier work already
showed is nearly worthless.

Age doesn't even separate busts inside a single round. Among
fourth-to-eighth-round picks, older running backs busted 11% more than
younger ones — but older receivers busted 4% *less*, and in the late
rounds both signs flip again. That's what a pattern that isn't there
looks like.

## What the number does say

The price-based number is well behaved. When it says a group of
players has a 30% chance of busting, 32% of them bust. When it says
80%, 83% do. Written the way a drafter reads it:

| Round | 1 | 3 | 5 | 7 | 9 | 11 | 13 | 15 |
|---|---|---|---|---|---|---|---|---|
| Chance of a startable season | 81% | 63% | 44% | 32% | 27% | 24% | 21% | 5% |

That is honest and it's worth knowing. Your first-rounder is a 4-in-5
shot. Your tenth-rounder is 1-in-5. Most people's draft-day
disappointment is really a mispriced expectation about round 9.

What it can't do is break a tie. If two players sit in front of you at
the same pick, their bust numbers are identical, because the number is
built from the pick.

## Why this keeps happening to us

This is the fifth time this project has run into the same wall. Our
player model lost to the draft board. Our rookie model tied the NFL
draft order exactly. Our draft simulator found that any amount of
model weight made a strategy worse. And now this.

The mechanism is the same every time, and it's worth saying plainly:
age, touchdown regression and injury history are not secrets. They are
the most-discussed inputs in fantasy football. By the time a player
has a draft price, the market has already marked him down for all
three. The 30-year-old receiver coming off a lucky touchdown year
isn't mispriced — he's cheap **because** of it. We keep rediscovering
information that's already in the price and mistaking it for an edge.

## What to do with it

Use a bust number to set expectations, not to pick players. It's a
good answer to "how much should I count on this pick" and no answer at
all to "which of these two."

And be suspicious of anyone selling you a bust score built from age
and touchdown regression. We built exactly that and tested it
properly, and it doesn't beat reading the round number off the board.

## The honest limits

Eight drafts is not a lot. An edge of a percentage point or two would
need roughly three times this data to show up, so "we found nothing"
means "nothing detectable in 1,489 players", not "provably zero". Our
draft prices come from a standard-scoring board, and a PPR market
could in principle price these things differently. And this only rules
out the inputs we have — real beat-writer reporting, contract details
or training camp usage might do something. They just aren't in our
data.
