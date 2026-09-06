The draft plan, in three scoring formats.

HOW TO EDIT
  Run `python3 site/build_site.py` after any change here; it writes
  site/data/plan.json, which the page reads.

RULES
  `## id | Section heading` starts a round band.
  `### id | The rule, as a sentence` starts a rule. That headline is
      the rule — it is emphasised by the page, so never wrap it in
      asterisks. This is on purpose: hand-bolded lead sentences drifted
      out of sync with each other, and half of them were bolded across
      a line break, where the markdown never fired at all.
  `@all`  body shown in every format.
  `@std` / `@half` / `@ppr`  body shown only in that format, after @all.
  `@why slug, slug`  the findings behind the rule.
  A rule carrying any of @std/@half/@ppr is flagged "changes with your
  scoring" and can be filtered down to on the page.

  Formats: @std is no points for catches. @half is half a point per
  catch. @ppr is one point per catch.


  The page's own intro text is `plan.intro` in site/copy.md, with the
  rest of the site's prose.


## before | Before you pick

### ranked-list | Bring a ranked list and follow it
@all
Drafting off a credible ranked list instead of going by feel is worth
about ten points of team strength over a season. That is the biggest
single effect on this page, and it costs you nothing but the discipline
to use the list you brought.
@why 03-adp-discipline-is-not-an-edge

### know-players | Spend your prep on players, not on draft strategy
@all
We compared the two directly. Knowing which players are going to be
good is worth roughly 40 times as much as picking them in a clever
order. If you have one evening to prepare, spend all of it reading
about players.
@why 24-hindsight-optimal-drafts

### take-the-board | Take the board in order, and don't reach
@all
"The board" means your app's average draft position list — where real
drafters are actually taking each player. Simply taking the best player
left on it, without reaching for anyone, beat every custom ranking we
built, including our own.

Reaching is the specific mistake. Every rule below that says "take a
position" means take him when he is roughly the best player left, not
five picks before that.
@why 32-draft-sim, 03-adp-discipline-is-not-an-edge

### scoring-matters | Check which scoring your league uses before you take anyone
@all
A catch is worth zero points, half a point, or a full point depending
on the league, and that one setting moves whole positions. Receivers
who catch 90 balls for short gains are ordinary in standard scoring and
excellent in full PPR. Your app's default board is usually half PPR
even when your league is not, so check.
@why 33-te-same-pick, 29-round-profile


## rounds-1-3 | Rounds 1 to 3

### rb-early | Start with running backs
@all
Running backs run out first. Their value drops off almost twice as fast
as receiver value does as you go down the list, and the waiver wire
never restocks them — in a 12-team league the other eleven rosters are
already holding around 66 backs.
@why 01-robust-rb-wins, 23-early-rb-vs-wr, 07-what-a-starter-is-worth

### zero-rb | Don't let anyone talk you into Zero RB
@all
Zero RB means deliberately taking no running back in the early rounds
and patching the position later.
@why 02-zero-rb-is-a-trap


## rounds-4-8 | Rounds 4 to 8

### qb-timing | Take your first quarterback in the middle rounds
@all
Anywhere from round 4 to round 6 is comfortable, and round 2 to round 8
is fine. The real mistake is waiting past round 10 planning to stream
one — that is where the results fall off.
@why 14-qb-round-sweep, 06-qb-timing, 36-draft-order

### bad-team-wr1 | The best receiver on a bad team is not the edge we thought
@all
Bad teams trail, trailing teams throw, and one receiver eats most of
it — so a losing team's number one receiver should be a bargain. In
the middle rounds he looked like one: top 24 at his position 43% of
the time against 25% for others.

Re-checking that at every price killed it. Those receivers are
expensive, and almost any expensive receiver hits; once you compare
them only against receivers who cost the same pick, the edge is
indistinguishable from zero. The draft tool no longer marks them at
all — we would rather show you nothing than a note that hands you a
number and then tells you not to use it.
@why 08-bad-team-wr1-edge

### buy-targets | Buy targets, not efficiency
@all
A target is a pass thrown in a player's direction. A receiver who gets
a lot of them but scored modestly is worth buying — the targets come
back next year. A receiver who scored a lot on very few targets is not:
that is a hot streak, and it does not come back.

The rule holds in all three formats, but it is worth the most in
standard scoring, which is the opposite of what we expected.
@std
This is where the edge is biggest. Standard scoring hides catch
volume: a receiver with 110 catches for short gains looks ordinary on
the scoreboard, so his target count is telling you something his
points are not.
@half
The edge is real but smaller than in standard, because half a point per
catch has already put some of the target information into his visible
points.
@ppr
The edge is smallest here, and the reason is not that targets stopped
mattering — it is that they stopped being a secret. In full PPR, a
high-target receiver's points already show you his volume, so counting
his targets adds less on top of what the scoreboard said.
@why 17-buy-targets-not-efficiency

### td-luck | Fade last year's touchdown luck, buy last year's bad luck
@all
Touchdowns bounce around far more than the yards and catches
underneath them. A player who scored many more touchdowns than his
usage justified will usually score fewer next year, and the reverse is
just as true. The draft tool marks both.
@std
This correction is strongest in standard scoring, where touchdowns are
the largest share of a player's points and a lucky season inflates him
the most.
@half
Slightly weaker than in standard: catches make up part of the total, so
a touchdown-lucky season is a smaller distortion.
@ppr
Weakest of the three, though still clearly there. With a point per
catch, touchdowns are a smaller slice of the total, so there is less
luck in the number to begin with.
@why 16-td-luck-regresses

### decline-trap | The receiver who is cheap after a bad year is priced about right
@all
The profile is specific: top 20 at his position two years ago, bad last
year, and priced like a bargain now. We used to call him a trap on the
strength of 17 players. Widened to ten drafts and 44 of them, the trap
is gone — he does about as well as his price, no better and no worse.

Neither the bounce-back story nor the trap story is worth acting on.
Buy him if the price is right for other reasons.
@why 09-decline-discount-trap

### injury-prone | Ignore the "injury-prone" label at quarterback and receiver
@all
We checked whether missing games one year predicts missing games the
next. At quarterback and receiver it does not, so the discount other
drafters give you on those players is free money. Tight end is the one
place to be mildly careful, and even that rests on only 24 repeat
cases.
@why 18-injury-prone-is-mostly-myth

### wr-age | Be careful with receivers aged 29 and 30 at middle-round prices
@all
That age band busted more than any other in our data. Read this one as
a nudge rather than a rule: half of the original age story died when we
stress-tested it, and this is what survived.
@why 10-wr-age-effects


## rounds-9-12 | Rounds 9 to 12

### tight-end | Take an elite tight end only if he falls to you
@all
Both halves of this matter, and they pull in opposite directions.

The good half: early tight ends really are worth their pick. Since
2018, 26 tight ends went in the first four rounds. For each one we
looked at the receivers and backs drafted within six picks of him, and
in 18 of those 26 cases the tight end turned out to be the better pick.
They almost never collapse — 8% of them busted, against 20 to 24% for
the receivers and backs going at the same picks.

The bad half: in our simulated seasons, every drafter who decided in
advance to take a tight end won fewer titles than one who just took the
best player available, and the more he had to overpay, the worse he
did. Planning to get one is what costs you, not owning one.

So: take him if he is there, never move up for him, and if he is gone,
wait until round 10. Rounds 5 to 9 are the worst place to shop for the
position — the odds of getting a useful tight end fall off a cliff
after round 4, so a middle-round tight end costs you a real pick for
round-12 results.
@std
Standard scoring is where an elite tight end is worth the least. Those
26 early tight ends were worth 19 points more across a season than the
receivers and backs at the same picks — real, but a luxury rather than
a priority. Let him come to you and don't feel bad if he doesn't.
@half
Worth a little more than in standard: 25 points across a season over
the receivers and backs at the same picks.
@ppr
This is where elite tight ends are worth the most, and it is not close:
34 points across a season over the receivers and backs at the same
picks, nearly double the standard-scoring figure. The reason is catch
volume — an elite tight end catches around 90 balls while the twelfth-
best catches about 50, and in full PPR that gap is 40 extra points by
itself.

In a full-PPR league, move the elite tight ends up about half a round
to a round from where you would take them in standard. That is still
not permission to reach past that.
@why 33-te-same-pick, 05-never-pay-up-for-te

### second-qb-te | A second quarterback or tight end is optional, but late or not at all
@all
Whether you carry one barely matters. When you take him matters: late
is free, early costs you a useful pick.
@why 20-second-qb-te

### roster-shape | Don't draft to a roster template
@all
Any roster shape you would plausibly want — more backs, more receivers,
balanced — is worth about the same, but only if you work the waiver
wire during the season.

If you know you are a set-your-lineup-and-forget-it manager, that
changes: stay balanced and take a backup quarterback. That pick is
worthless to an active manager and the most protective thing an
inactive one can do.
@why 34-roster-shape

### bench-rbs | Don't fill your bench with backup running backs
@all
Stashing them wins about one percent of championships. They are lottery
tickets, and the bench is where you should be holding players who might
actually start for you.
@why 19-bench-composition

### handcuffs | Your star running back's backup is insurance, not profit
@all
Owning him pays off in exactly the seasons your starter gets hurt, and
loses in the rest, and those two cancel almost perfectly. Take him if
he is free. Never reach for him.
@why 13-handcuffs-are-free-insurance


## rounds-13-15 | Rounds 13 to 15

### kdst-last | Spend your last two picks on a kicker and a defense, and don't think hard
@all
This is the one part of the plan that does not change with your
scoring at all — catches don't score for kickers or defenses in any
format, so these two lists are the same in every league.

Take them last. A kicker's own past statistics predict almost nothing
about his next season.
@why 04-kickers-are-noise, 27-dst-model, 28-kicker-model

### defense-one-number | For a defense, the only number that matters is how bad the opponent's offense is
@all
Draft whoever plays the worst offenses in the first few weeks, then
change your defense every week all season. Picking defenses by their
opponent works more than twice as well as picking by how good the
defense itself is.

Our ranked lists for both positions are on the
[kickers and defenses](#/board) tab.
@why 27-dst-model

### kicker-offense | For a kicker, pick the offense and the stadium, not the leg
@all
Kickers score when their team moves the ball. Take the kicker on a good
offense, and break ties with a dome — an indoor game is worth about 0.7
points, which is small, but it is the second-largest thing we can
measure after the offense itself.
@why 28-kicker-model

### offense-not-tiebreak | "He's on a better offense" is not a tiebreaker between two skill players
@all
Vegas does know which offenses will score the most, and it is right.
But everyone can see the same betting lines, so that knowledge is
already inside the price you are paying in the draft. It helps you at
kicker and defense, where almost nobody prices it in. It does not help
you choose between two receivers.
@why 30-good-offense-tiebreak


## season | During the season

### waivers | The waiver wire is maintenance, not strategy
@all
Working it all season is worth 5 to 12 points over the whole year,
mostly from patching holes at quarterback and kicker. That is real, and
it is much smaller than people think.

The one thing worth claiming quickly is a player whose usage has
jumped — more targets or more carries — because usage arrives before
the points do.
@why 22-waiver-wire-reality

### momentum | Hot and cold streaks mean nothing for next season
@all
How a player did over his last three weeks tells you nothing about how
he does next year. This is not a small effect we are rounding down; it
is a firm, well-measured zero. Price players on the whole season.
@why 15-late-season-momentum-myth

### injury-tags | Read the injury tags like this
@all
Out and Doubtful mean zero points; don't start them. A player listed as
Questionable on Friday plays about 69% of the time, and when he does
play he scores about 83% of what he normally would. So a Questionable
player is worth roughly half his usual line before you know anything
else.
@why 21-injury-model

### matchups | Don't overthink weekly matchups
@all
Who a player faces, and the weather, are worth about a point a week at
most — and the betting lines have already accounted for both. Start
your best players.
@why 26-team-environment


## expectations | What to expect from your picks

### round-profile | Early picks buy reliability, late picks buy lottery tickets
@all
A first-round pick gives you a player worth starting most weeks 81% of
the time. A fifteenth-round pick does it 5% of the time. Spend them
accordingly: don't expect a late pick to solve a starting job, and
don't burn an early one on a player you are unsure about.

This table barely moves between formats. Only 3.8% of drafted running
back and receiver seasons change whether they finished in the top 24 of
their position when you rescore them from standard to full PPR — the
same players are good in both, they just score differently.

One myth to drop in every format: late-round running backs do not hit
more often than late-round receivers. In rounds 9 to 15 backs returned
a startable season 8.9% of the time and receivers 11.2%, and receivers
led in six of the eight seasons. In full PPR the gap is wider still,
8.4% against 12.0%. Neither gap is big enough to be sure of, so the
honest version is that there is no late-round running back edge in any
format — the one you remember was that season's luck.
@why 29-round-profile

### variance | Losing two finals in a row is normal bad luck, not a broken plan
@all
Even the best plan on this page wins the title something like one year
in five. Over a handful of seasons that produces long dry spells purely
by chance. Judge your draft by whether you followed a tested plan, not
by whether it won.
@why 12-championship-variance
