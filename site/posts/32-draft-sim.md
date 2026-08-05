# 32 — We simulated 23,000 leagues to test our model against ADP. Draft off the board.

**Confidence: High** (1,800 simulated leagues per strategy across six real seasons, thirteen strategies, with a control that landed exactly where it should)

## TL;DR

We ran full simulated fantasy leagues — draft, lineups, waivers, playoffs — over the 2020–2025 seasons, with one seat drafting from our projection model and eleven bots drafting like a real family league. Drafting by the model instead of ADP cut title odds roughly in half. Then we tried nine narrower versions — tilt only at tight end, only in the late rounds, only for rookies, or act only on our own tested buy/fade calls — and every one of them was a dead heat with simply taking the ADP board in order. The winner, by a lot, is the boring strategy: take the board in order, fill your starters sanely, never reach.

## The test

Each simulated league is 12 teams, 15 rounds, standard scoring — our family league's exact shape. Eleven seats draft the way real leagues do: ADP with real reach behavior, measured from our league's own drafts. The twelfth seat is the test seat, and it rotates through every draft slot, 300 leagues per season, with the same random luck replayed for every strategy so the comparison is fair. After the draft, every team plays the season identically — same lineup rules, same waivers, using only information available before each week. The only thing that differs is the draft list.

The model's lists were rebuilt honestly for each season: to draft 2023, the model was retrained without any knowledge of 2023 — the same rule as all our backtests.

## The result

| Draft list | Season win rate | Playoffs | Title |
|---|---|---|---|
| Pure ADP, drafted with discipline | **.595** | 74.5% | **20.7%** |
| ADP tilted 25% toward our model | .594 | 74.9% | 18.7% |
| ADP and model averaged 50/50 | .580 | 71.2% | 14.8% |
| Our model instead of ADP | .522 | 57.3% | 10.8% |
| A 12th family-style drafter | .500 | 49.3% | 9.3% |

(Season win rate is your record if you played every team every week; 8.3% is the title rate of a random team.)

The control row is the reason to trust the rest: a twelfth family-style drafter in a family room wins exactly as often as chance says it should.

## "But ADP isn't even that good" — right, so we tried nine more ways

That table only rules out swapping the whole board. And the objection is fair: ADP is genuinely mediocre, matching what actually happens about as well as a 0.60 out of 1.00, and a perfect-hindsight draft would beat every real strategy by hundreds of points a season. There's plenty of room above ADP. So we tried every narrow way we could think of to claim some of it — tilt only at tight end, where the market is worst; tilt only outside the top twelve; tilt only in the late rounds; use our rookie model to re-rank rookies; spend the last picks on rookies the market never priced; and apply only our *tested* buy/fade calls as small nudges.

**All nine landed in a dead heat with plain ADP.** The best of them, tilting only outside the top twelve, was worth 1.6 points across an entire season — we tested it head-to-head, league by league, and the difference was smaller than its own margin of error. The harder any version pushed, the worse it did.

## Where our numbers *do* disagree with the market usefully

One test did find something. Instead of asking "is our list better," we asked "when we disagree with the market about one player, does the disagreement point the right way?"

Inside the top twelve at a position, our disagreements are worth nothing at all — the correlation is flat zero. Past position rank 30, they're clearly informative, and that holds in five of six seasons. On the players where we disagreed hardest, the ones we liked more than the market beat their draft price by about 0.8 points a game, and the ones we liked less missed by about 0.65.

So our numbers do know something — but only about players cheap enough that the market has stopped paying attention. And that turns out not to be worth much on draft day: those are bench and flex bodies, and only a couple of your picks even land there. A real edge on cheap players is still a small edge.

It's a strong hint about where to look next, though. The waiver wire is made entirely of those players, and there's no draft market there at all to be right ahead of us. That's the next thing we'll test.

## What it means

**Our model is not a draft list, in any dose or any corner of the board.** This was already the verdict of [finding 25](#/blog/25-player-model) on ranking accuracy; the sims confirm it where it counts. The model seat lost to the ADP seat in all six seasons, and no narrow version — by position, by round, by rookie status, or by our own tested findings — ever beat the board.

That last one is worth dwelling on, because it's the closest thing here to a disappointment. Our buy/fade research ([finding 16](#/blog/16-td-luck-regresses), [finding 17](#/blog/17-buy-targets-not-efficiency)) is real: a receiver who scored well above what his targets were worth really does give it back the next year. But acting on it at the draft table didn't win more leagues — and we gave that test every advantage, including letting it use a rule tuned on the same seasons it was being graded on. The finding is true about football. It just isn't news to the draft market, which has already moved the player before you get there.

**The real edge in the table is discipline, not cleverness.** The pure-ADP seat won titles at 2.5× the base rate — against realistic opponents — by doing nothing but refusing to reach. That's the edge our draft tool actually delivers on draft day, and it's bigger than anything a projection model has earned in our testing.

The model keeps the job the data supports: when you click a player on the board, it shows his usage, his touchdown luck, his position room, and the findings that name him — context for choosing between two players the market prices the same. It doesn't move anyone up or down your list, because we measured what happens when it does.
