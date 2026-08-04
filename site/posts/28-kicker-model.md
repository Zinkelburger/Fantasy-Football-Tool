# 28 — Kickers: stream the situation, not the leg

**Confidence: High** (eight seasons, 4,200 kicker-weeks, always scored on a held-out season)

## TL;DR

Kickers are the least predictable position in fantasy, and the kicker himself is the least important part of the prediction. Ranking kickers by their own scoring history barely beats guessing; what actually predicts kicker points is the situation — is his team favored, is the game in a dome, does his coach settle for field goals.

## What actually predicts kicker points

We built a weekly kicker model the same way as [the defense model](#/blog/27-dst-model): add ingredients one at a time, test each version only on seasons it never saw. The ingredients that carry weight are all about circumstance. Win probability matters most — winning teams kick. A dome adds most of a point; wind of 15+ mph takes about half a point away. And coaching identity is real: teams whose drives habitually stall into field-goal attempts feed their kicker, while great offenses actually starve theirs, because touchdowns mean one-point extra points instead of three-point field goals.

The kicker's own recent scoring, added on top of all that? Nothing. His history is nearly irrelevant once you know his situation.

## The ceiling is low everywhere

The honest numbers, in rank correlation (how well the model's weekly ordering matched reality; 0 is random, 1 is perfect): ranking kickers by their own points per game scores .08 — barely above a coin flip. The full model reaches .19. That's a real improvement, and it's still only about half the defense model's .30. This is [kickers are noise](#/blog/04-kickers-are-noise) with the measurement attached: the position is streamable, but even the best streaming signal is a gentle tilt.

## What to do with it

Draft your kicker with your last pick — every finding on this site agrees on that. In season, don't agonize between two comparable kickers; there is no analysis that resolves that choice. When you do switch, take the kicker whose team is favored, indoors if possible, with a coach who kicks. That's the whole edge, and pretending there's more would be fake precision. The weekly kicker board on this site is built from exactly these inputs.

---

*The full write-up, with every table and how to reproduce it: [findings/28-kicker-model.md](https://github.com/Zinkelburger/Fantasy-Football-Tool/blob/main/engine/league-sim/findings/28-kicker-model.md)*
