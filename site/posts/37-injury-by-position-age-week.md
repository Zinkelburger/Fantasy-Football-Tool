# 37 — Running backs aren't made of glass. December is.

**Confidence: High** (the week-of-season result and the position
finding rest on 1,488 player-seasons; the age results are Medium, and
one tight end number is unresolved)

## TL;DR

Drafted players miss between 2.1 and 2.7 games a season depending on
position, and the gaps between positions are too small to measure —
running backs are not meaningfully more fragile than receivers. What
does change, a lot, is the calendar: a player is about twice as likely
to go down in your fantasy playoffs as in September. Age raises injury
risk at wide receiver and nowhere else we could prove.

## What we measured

We took the draftable player pool for each of the last eight seasons —
the roughly 179 players with a draft price — and followed every one of
them week by week. That's 1,488 player-seasons and 24,690 player-weeks,
and the pool is fixed before the season starts, so nobody gets dropped
for having a bad year.

One thing had to be fixed first, and it's the reason this study
exists. When a player goes on injured reserve, **he disappears from
the NFL injury report completely**. Nick Chubb's 2023 has no injury
report rows at all after the knee that ended his season. Neither does
Kirk Cousins' 2023. So counting "weeks listed Out" — which is how our
earlier work measured this — quietly erases the worst injuries, the
exact ones you care about. We used snap counts to ask whether a player
actually took the field, and roster paperwork to ask whether the
reason was health.

## Running back is not the injury position

| Position | Games missed per season | Never missed a game | Lost the season |
|---|---|---|---|
| Quarterback | 2.06 | 59% | 14.5% |
| Running back | 2.57 | 45% | 11.0% |
| Wide receiver | 2.28 | 44% | 9.5% |
| Tight end | 2.73 | 40% | 15.0% |

Running backs do miss a bit more than receivers — 0.29 games a year.
But when we resample the data to ask how precisely we know that
number, the honest range runs from −0.15 to +0.71. It includes zero.
Every other pairing does too. And notice who's at the top of both
columns: tight ends, not running backs.

There is one real running back tax, and it isn't how often. It's
**when**. Among players whose seasons ended early, the typical running
back played his last game in week 7. For receivers and quarterbacks
it's week 9, for tight ends week 11. The odds are the same; the
running back just takes more of your season with him.

## The calendar is the thing nobody prices

Here's the chance a healthy player goes down in a given week, by where
you are in the season:

| Position | Weeks 1–6 | Weeks 7–12 | Weeks 13–16 |
|---|---|---|---|
| Quarterback | 7.0% | 12.0% | 16.0% |
| Running back | 10.0% | 16.6% | 18.5% |
| Wide receiver | 10.0% | 14.7% | 15.6% |
| Tight end | 10.2% | 16.4% | 22.1% |

Weeks 13–16 are your fantasy playoffs. Risk there runs somewhere
between 1.6 and 2.2 times what it was in September, and we cut weeks
17 and 18 out of this table entirely so that teams resting starters
for the playoffs can't be the explanation.

If anything this understates it. By December the fragile players are
already hurt and no longer in the pool, so the group still standing is
the healthy one — and it's *still* going down twice as fast.

This is far and away the largest effect in the study. It dwarfs every
difference between positions.

## Age: receivers, and only receivers

Each extra year of age costs a wide receiver about 0.13 games of
availability, and that result holds up when we test it. At running
back, tight end and quarterback, we could not tell the age effect
apart from zero.

That is worth being careful about, because the raw numbers look like a
much better story. Running backs aged 29 and over miss 3.35 games a
season, well above every younger group. Two things eat most of it.

The first is price. Old running backs who still get drafted get
drafted **cheap** — an average draft slot of 106, against 77 to 88 for
backs in their prime. And cheap players miss more games for reasons
that have nothing to do with age: they're committee backs and backups,
nobody hurries them back, and a team will happily park one on injured
reserve rather than carry him. When you compare old and young backs at
*the same draft price*, the gap shrinks.

The second is sample size. There are only 57 old-running-back seasons
in eight years of drafts. What's left after the price correction is
about +0.88 games, and the honest range around it runs from −0.29 to
+2.17.

So this is not "we proved old running backs are fine." It's "we
can't tell yet." The leftover effect is the same size as the receiver
one we *did* confirm, and it shows up as a tail rather than a shift —
the median old back and the median young back both miss exactly one
game; it's the unlucky quarter that separates, at 5 games against 3.
Treat it as an open question, not a settled null.

## Playing hurt

Receivers get listed Questionable more than anyone — 8.7% of their
weeks, against 7.4% for running backs. Another piece of folk wisdom
pointing the wrong way. But quarterbacks and running backs are the
least likely to actually play once tagged (57% and 63%, against 71%
for receivers and 78% for tight ends).

When a Questionable player does suit up, we compared him to his own
healthy average that same season — so this is the player against
himself, not against better players. Quarterbacks give you 85% of
normal, receivers 90%, running backs 91%. Tight ends showed no drop at
all, which contradicts our own earlier finding that a Questionable
tight end costs you 25%. The two studies used different methods and
we haven't resolved it, so for now treat the tight end discount as
unknown rather than trusting either number.

## What to do with it on draft day

Stop docking running backs for injury. The fragility gap between
positions isn't there at any size we can measure. There are good
reasons to think hard about running backs — the position's value drops
off faster than receiver, which is finding 23 — but "he'll get hurt"
isn't one of them.

Do dock old receivers. That's now two independent reasons: they score
less per game *and* they're available less often.

And price the calendar. A player tagged Questionable in week 14 is a
worse bet than the same player with the same tag in week 3, and points
you bank in September come from the safest stretch of the season.

## The honest limits

The draftable pool is only about 179 players a year, so tight end and
quarterback are thin — 180 and 214 seasons. When we say a position gap
isn't there, we mean we can't find it in this much data, not that it's
zero. We also tested four positions for an age effect and one came
back significant, so the receiver result deserves a fresh season
before anyone treats it as settled. And weeks 17 and 18 mix real
injuries with teams shutting players down, which is why the weeks
13–16 comparison is the one we quote.
