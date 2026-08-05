# 03 — Just sticking to the rankings is 90% of the edge

**Confidence: High** (the corrected result survived a rebuilt,
tougher simulation — and the correction is the story)

## TL;DR

The biggest edge in our family league is not a clever strategy — it's
simply sticking to a list. A bot that drafts straight off consensus
rankings, with zero opinions, beat the simulated family by almost 10
points of all-play. The best strategy we ever tested added about one
more point. Discipline is roughly 90% of the available edge.

## We got this one wrong first

The original version of this finding claimed the opposite: that
list-following added nothing. The number was real, but our simulated
opponents were too sharp — early versions of the family bots only
wandered a few picks off the rankings. Then we measured our league's
six real drafts and found the actual wander is 17 to 30 picks per
round. Once the bots drafted like the real room, the conclusion
flipped. We're publishing the correction because that's the whole
point of doing this in public.

## The numbers

All-play is the record you'd have if you played every team every week,
so .500 is average.

| Drafter | All-play | Titles |
|---|---|---|
| RB-RB-RB opening | .610 | 21% |
| Rankings only, no opinions | .598 | 20% |
| Simulated family | .501 | 8% |

Read it in two steps: showing up with any credible list and following
it is worth almost 10 points and roughly two and a half times the
normal title rate. Everything after that — which positions to favor,
when to take a quarterback — is a fight over the last point.

## What happens when everyone else sharpens up

We also ran the test in a room of eleven disciplined opponents. There,
the family-style drafter loses by about 7 points — the same edge seen
from the other side. And the [RB-RB-RB plan](#/blog/01-robust-rb-wins)
loses its advantage entirely, because that plan works by harvesting
our room's habit of waiting on running backs. The only strategy that
kept a real edge against sharp opponents was the one doing cold math
about what each pick costs to wait on.

The slide version for draft night: the sheet beats your gut by ten
points; the best strategy we've ever tested beats the sheet by one.

