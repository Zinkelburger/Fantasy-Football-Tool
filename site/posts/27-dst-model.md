# 27 — Pick your defense with one number: the opponent's total

**Confidence: High** (eight seasons of defense-weeks, always scored on a held-out season)

## TL;DR

The best way to pick a defense each week is the opponent implied total — the score Vegas expects the offense your defense is facing to put up, worked out from the point spread and the over/under. Lower is better. In eight seasons of backtesting, that single number predicted weekly defense scoring better than everything else we tried combined.

## What we tested

We built the model in steps and scored each step by rank correlation — how well its weekly ordering of defenses matched reality, where 0 is random and 1 is perfect. Ranking defenses by their own scoring average manages .13. The opponent implied total alone jumps to .30. Then everything else — opposing O-line quality, giveaway-prone opponents, the defense's own sack rate, home field, wind, even a backup QB starting — adds almost nothing, because the betting line already knows all of it. When a starting QB sits, the spread moves before our data ever sees the news. That gap from .13 to .30 is the whole streaming edge.

## Yes, it counts sacks and pick-6s

A fair objection: surely some defenses just make more plays than others. Two answers. First, the model predicts full defense scoring — sacks, interceptions, fumble recoveries, defensive touchdowns, and the points-allowed bonus. Those plays aren't ignored; they're most of what we're predicting. Second, better defenses do exist, and Vegas already prices them: when a great defense takes the field, the opponent's total drops *because* the market knows it's good. The implied total isn't an alternative to measuring defense quality — it contains it, priced by people betting real money. Meanwhile a defense's own sack and interception rates swing so hard week to week that they barely predict their own next game.

## How to use it

Rank defenses by opponent implied total, full stop — each Vegas point off the opponent's total is worth roughly +0.4 defense points. Don't pay for a name-brand defense on draft day; stream the slot all season. And keep expectations honest: defenses average about 5 points with a weekly swing of about 6, the noisiest slot in fantasy, so the model is a tilt, not a prophecy. The design follows subvertadown's published work, and for 2026 week 1 his two free picks and ours were identical. This model powers the weekly defense board on this site; [the kicker model](#/blog/28-kicker-model) is its noisier sibling.

---

*The full write-up, with every table and how to reproduce it: [findings/27-dst-model.md](https://github.com/Zinkelburger/Fantasy-Football-Tool/blob/main/engine/league-sim/findings/27-dst-model.md)*
