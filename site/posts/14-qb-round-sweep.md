# 14 — Take your first quarterback in rounds 4 to 6

**Confidence: Medium-High** (clean apples-to-apples design; trust the shape of the curve more than any single number)

## TL;DR

We ran eight computer drafters that were identical except for one
thing: the earliest round they'd take a quarterback. Rounds 4–6 came
out on top, anywhere from round 2 to 8 was nearly as good, and the
real mistake was waiting past round 10. Our family's actual habit —
first QB around round 5 — turns out to be exactly right.

## The experiment

Comparing quarterback strategies across different leagues and seasons
muddies everything, so we changed exactly one dial. Eight copies of
the same disciplined drafter, each banned from taking a QB before a
target round — round 2, 3, 4, 5, 6, 8, 10, or 12 — and otherwise
identical, each drafted through 720 simulated seasons in a room
modeled on our family's real drafts.

## The curve

| Earliest QB round | All-play record |
|---|---|
| 2 | .578 |
| 3 | .579 |
| 4 | .582 |
| 5 | .588 |
| 6 | .587 |
| 8 | .575 |
| 10 | .564 |
| 12 | .549 |

All-play is your record if you had played every team every week — the
least lucky way to score a season. The whole spread is about 4 points
of all-play, roughly half a win a year, with one clear peak at rounds
5–6. Reaching up to round 2 costs about 1 point; waiting until round
12 costs about 4. The penalty for too early is mild; the penalty for
too late is the real one.

## Why the middle wins

The top quarterbacks are genuinely better, but the worst starting QB
in a 12-team league still scores around 16 points a game — the
position has a high floor. Spend a round-2 pick on one and you've
skipped a running back or receiver, positions with no such floor
([finding 01](#/blog/01-robust-rb-wins)). Wait past round 10 and
you're choosing from the bottom of the startable barrel, and the
waiver wire can't rescue you at quarterback
([finding 06](#/blog/06-qb-timing)). Rounds 4–6 is where a
top-ten quarterback naturally drifts to in our league's draft rooms.

## Fine print

"Round 5" means the drafter *opens its window* there; the actual pick
usually lands somewhere in rounds 5–7 depending on the room. And all
eight of these drafters beat the family-modeled bots by a wide margin
regardless of QB plan — but that gap is about disciplined drafting in
general ([finding 03](#/blog/03-adp-discipline-is-not-an-edge)), not
about quarterbacks. Don't read it as a QB effect.

