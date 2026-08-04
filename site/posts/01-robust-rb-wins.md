# 01 — Open your draft with three straight running backs

**Confidence: High** (1,440 simulated seasons, and the result survived every attack we threw at it)

## TL;DR

In our league, starting RB-RB-RB won the championship about 20% of the
time in simulation. A team's fair share in a 12-team league is 8.3%, so
that's close to two and a half times the expected rate — and no other
plan we tested came close.

## What we tested

We rebuilt our family league inside a simulator: same 12 teams, same
standard scoring, and computer drafters trained on our last six real
drafts so the room behaves like the actual room. Then we replayed six
seasons 240 times each, from every draft slot, with one test team
following a fixed plan — "take running backs with your first three
picks, then draft normally" — against eleven bots drafting the way our
family actually drafts.

The RB-RB-RB team won 20.3% of the championships. A team that just
drafted for value at every pick won 17%. Zero RB — deliberately
skipping running backs early, a strategy you'll see recommended all
over the internet — won 9.7%, barely better than drafting on autopilot.

## Why it works

Standard scoring is brutal to running backs. The top RB scores around
19 points a game and the tenth-best around 12 — a seven-point cliff.
Wide receivers fall much more gently, from about 16 to 11 over the same
stretch, and decent ones keep showing up on the waiver wire all season.
Good running backs are the one thing you cannot get later.

Our league also waits slightly longer on running backs than the math
says it should. Three top picks spent on RBs corners the scarce
position while everyone else spreads out. And a roster built on three
stud RBs is a boom-or-bust shape: it wins some weeks huge, and in
fantasy, championships pay for booms.

## Where this could go wrong

Two honest warnings. In 2022 — the year the big running backs all got
hurt or flopped — this plan was nearly the worst of the disciplined
strategies, and Zero RB had its one great year. The 20% is an average,
not a promise. And the edge exists *because* our room waits on RBs; in
a league full of RB-hungry drafters the advantage mostly disappears,
because the backs are gone before you can corner them. That second
point is measured, not a guess — see [how we test drafting skill
itself](#/blog/03-adp-discipline-is-not-an-edge).

---

*The full write-up, with every table and how to reproduce it:
[findings/01-robust-rb-wins.md](https://github.com/Zinkelburger/Fantasy-Football-Tool/blob/main/engine/league-sim/findings/01-robust-rb-wins.md)*
