# 30 — "Take the guy on the better offense" fails its test

**Confidence: High** (23 seasons of team results, 1,414 head-to-head
draft pairs over eight seasons — and the answer doesn't move under any
version of the test)

## TL;DR

Vegas really does know which offenses will score: its August team
lines have called the season's scoring order correctly in 23 straight
seasons, including 2025 (rank correlation +0.39 — the top-8 teams on
its list averaged 25.5 points a game, the bottom-8 just 18.0). But
using that to break a draft tie — two similar players, take the one on
the better offense — flat-out fails. Across eight years of draft
boards, when two same-position players went within 6 picks of each
other and one sat on a clearly better offense, the better-offense
player finished with more points only **46% of the time**. A coin flip
does better. Everyone in your draft can read the same Vegas lines, so
by draft day the good offense is already in the player's price.

## Vegas can pick offenses

We took the betting market's August win total for every team back to
2003 — the market's one-number opinion of a team before kickoff — and
checked it against the points that team actually scored. It has never
had a backwards year: 23 seasons, 23 positive correlations, averaging
+0.45. For 2025 specifically it went +0.39: real misses (Kansas City
was priced like a top-3 team and finished 21st in scoring; the Rams
were priced mid-pack and led the league), but the group call was
clearly right.

So the number on our [2026 board](#/board) — each offense's expected
points per game, built from the betting lines for all 272 games — is
real information about teams.

## But it can't pick between two players

Then we ran the tiebreak itself, the way you'd actually face it: two
players, same position, drafted within 6 spots of each other — a true
draft-room coin flip — where one team's August line sat at least 1.5
wins above the other's. Eight seasons, 1,414 such pairs:

| position | better offense won |
|---|---|
| QB | 48% |
| RB | 47% |
| WR | 44% |
| TE | 43% |
| **all** | **46%** |

Not one position cleared 50%. Only 2 of 8 seasons did. We re-ran it
with wider pick windows, bigger line gaps, only early-round picks, and
per-game scoring instead of totals: 44% to 51%, every time.

## Why both things are true

ADP is set by thousands of drafters who can all see the same Vegas
lines. "He's on a great offense" is priced in before you ever pick. If
anything the market pays slightly too much for it — good offenses
spread the ball around, while a bad team funnels everything to
[its one real receiver](#/blog/08-bad-team-wr1-edge). We're not
telling you to fade good offenses; we're telling you the tiebreak is
worth nothing, which is [the usual fate of easy edges](#/blog/03-adp-discipline-is-not-an-edge).

Where the team number still earns its keep: positions the draft market
*doesn't* price carefully — it's the main input to our
[kicker](#/blog/28-kicker-model) and [defense](#/blog/27-dst-model)
draft lists, and those backtests pass.
