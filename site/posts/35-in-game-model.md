# 35 — We built a live win probability, then measured how wrong it is

**Confidence: High** on how points arrive during a game (five seasons, 259,009 scoring plays); **Medium** on the win probability itself, which was tested on made-up matchups built out of real weeks

## TL;DR

Fantasy points arrive at a nearly steady drip across a game, so a live win probability works fine from the opening kickoff — you don't have to wait for the fourth quarter. The catch is that every version we built, including three clever ones, came out too confident. Matchups we called 85% actually won about 78% of the time. The fix that worked was not clever at all.

## Points arrive on a clock, not in a fourth-quarter avalanche

A common instinct is that games are decided late, so early numbers are meaningless. We checked. Splitting every game into twelve five-minute blocks and counting the fantasy points scored in each, ten of the twelve blocks land between 6.8% and 8.5% of the game's total. An even split would be 8.3%. Points really do just trickle in at a steady rate.

The two exceptions are the last five minutes of each half — 12.7% before halftime and 10.9% at the end of the game. That's the hurry-up offense: teams throw more, stop the clock more, and squeeze in extra plays. By quarter it comes out 21.6%, 28.6%, 22.6%, 27.1%. The second and fourth quarters are bigger, and it's the two-minute drills doing it.

Quarterbacks, running backs, receivers and tight ends all follow the same curve, within about a point of each other at every moment. One clock rule covers everybody.

So the model is close to the simplest thing imaginable: **a player's remaining points are his projection times the share of the game still to play**, knocked down about 8% because injuries, blowout benchings and garbage time all pull the same direction.

## Almost nothing improves on the clock

We tried the obvious upgrades and measured each one on a season the model had never seen. Adding the game's score — the idea that a team trailing badly throws more — helped by well under 1%. Adding what the player had already done that day helped about 1%, and only for running backs, where early carries genuinely reveal how much work he's getting. Adding the Vegas total for the game helped about 1% before kickoff and nothing after.

That's the whole list. Fitting the basic rate is worth roughly 4%; everything else together is worth 1 to 2%. If you were expecting a live projection to need a big machine behind it, it doesn't.

## Two teammates catching passes are not linked

We expected receivers on the same team to rise and fall together, since a good day for the offense should lift everyone. They don't: the correlation is 0.00. The shared benefit of a productive offense and the fact that they're competing for the same throws cancel each other almost exactly.

What is real is the quarterback's link to his own receivers — 0.28 with wideouts, 0.22 with tight ends — which makes sense, because his passing yards *are* their receiving yards. There's also a mild link between the two quarterbacks in a shootout, at 0.12. Everything else we measured sits at zero. So a live simulation needs exactly two connections, not a web of them.

## The honest part

Here is where most sites stop and ship the number. We simulated 4,000 matchups, printed a win probability for each, and then checked whether the ones we called 70% actually won 70% of the time.

They didn't. The number was too extreme in both directions — too close to 0%, too close to 100%. We tried three fixes, each motivated by something real we'd measured:

**Fix the shape of a player's day.** Individually, player scores look nothing like a bell curve — a tight end scores nothing in the second half a third of the time. We modelled that properly. It changed the result in the fourth decimal place, because a lineup is nine players added together and adding up nine lumpy things gives you something smooth.

**Add the quarterback correlation.** Real, measured, and worth nothing here, because a lineup has one quarterback in it.

**Let the uncertainty grow with the projection.** A 15-point running back swings about twice as widely as a 2-point one, which is true and which we'd measured. It improved things from 3.5% off to 3.2% off.

Three good ideas, no real progress. What actually worked was pulling every probability 13% back toward 50/50 — one number, no theory. That beat all three structural fixes put together, and it is the least satisfying finding we've published.

## What this means for the number on your screen

Our live win probability is good to about four percentage points, and it is least reliable exactly when it looks most certain. That's why the page says so underneath it.

The reason isn't the simulation — we've now established that the simulation barely matters. It's the projection going in. A better weekly projection would improve the win probability more than any amount of statistical machinery bolted on afterward, which is where our effort is going next. If you see a site quoting you a 93% win chance to the decimal point, they have not checked whether their 93% happens 93% of the time. We checked ours, and it doesn't quite.
