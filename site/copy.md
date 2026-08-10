Every sentence the site says to a reader lives in this file.

HOW TO EDIT
  Find the `# key` heading for the text you want to change, edit the
  words under it, then run:

      python3 site/build_site.py

  That writes site/data/copy.json, which the pages read. Nothing in
  index.html or the .js files needs touching.

RULES
  - A line starting with `# ` and nothing but a key (letters, digits,
    dots, dashes) starts a new block. Everything until the next one is
    that block's text.
  - Markdown works: **bold**, *italic*, `code`, [links](#/blog/27-dst-model),
    lists, tables.
  - Some blocks are used as hover tooltips or plain labels. Those get
    their formatting stripped, so write them as plain sentences.
  - `{{posts}}` is replaced with the real number of research write-ups
    at build time. `{word}` placeholders are filled in by the page.
  - Text NOT in this file: the <title> and search-engine description in
    index.html's <head>, the column headers inside the data tables, and
    the research posts (site/posts/*.md) and cheat sheet
    (site/cheatsheet.md), which are already their own markdown files.


# site.name
FOSS Football

# link.github
Source on GitHub

# draft.frame
Draft assistant


# nav.guide
Rankings & research

# nav.live
My league

# nav.draft
Draft tool


# tab.plan
Draft plan

# tab.board
Kickers & defenses

# tab.weekly
This week

# tab.blog
Findings

# tab.models
How the models work


# home.title
Fantasy football advice you can check

# home.lede
Most fantasy advice is somebody's opinion, and you have no way to tell
a good one from a confident one. This site is the other thing: we
tested the popular advice, wrote down what happened, and published the
code and the data so you can check us.

Some of it confirmed what everyone says. Some of it didn't. And when we
built our own player rankings and they turned out to be worse than
simply following the draft order, we published that too — and the
advice below tells you to follow the draft order.

The rules change depending on whether your league gives points for
catches, so the draft plan asks you which one you play before it says
anything.

# home.whats-here
What's on here

# home.f.plan.title
The draft plan

# home.f.plan.body
Everything worth doing on draft night, in the order the rounds come at
you: who to take early, when to take a quarterback, what to do about
tight end, and which popular ideas to ignore. Pick standard, half PPR
or full PPR at the top and the plan changes with it — about a third of
the rules do.

Every rule links to the write-up behind it, so you can check any of it
rather than taking our word.

# home.f.kdst.title
Kicker and defense rankings

# home.f.kdst.body
These are the only two positions where a model clearly beats the draft
order, because their points come from the schedule rather than from the
player. A kicker's own past statistics tell you almost nothing about
his next season; how many points his offense is expected to score tells
you most of it.

So there are two lists: one for the last two picks of your draft, and a
fresh one every week for who to start. These are the same in every
scoring format — catches don't score for kickers or defenses.

# home.f.research.title
The findings

# home.f.research.body
{{posts}} write-ups, each one a question we could answer with data and
did. Does Zero RB work? Do hot streaks carry over? Are some players
actually injury-prone? Is a tight end worth an early pick?

Each one says how sure we are in plain words, shows the numbers behind
it, and says what would have to be true for it to be wrong.

# home.f.league.title
My league

# home.f.league.body
Connect an ESPN or Sleeper league and see your live matchup odds during
the games, whether the lineup you set is the best one your roster
allows, which free agents would actually improve it, and how much of
your record has been luck.

It reads your league and nothing else. There is no account and no
server — the league you pick stays in your browser.

# home.f.tool.title
Draft tool

# home.f.tool.body
Open this during a live draft. It follows your ESPN or Sleeper draft
pick by pick, keeps track of who is gone, and tells you who is worth
taking next given what your roster still needs and how long the players
you want are likely to last.

# home.how.title
How to read anything on this site

# home.how.body
- **Every claim links to its write-up.** If a rule doesn't say where it
  came from, we shouldn't have written it.
- **Every write-up says how sure we are**, in words rather than
  jargon, and says plainly which part of it is the shakiest.
- **We say when we were wrong.** Several write-ups correct earlier
  versions of themselves; those corrections are left in.
- **All of it is public** — the code, the data and the dead ends.


# plan.title
The draft plan

# plan.intro
Everything we have tested, reduced to what you actually do on draft
night. Every rule links to the write-up behind it, where you can read
the data and how sure we are.

Pick your league's scoring first. Whether a catch is worth nothing,
half a point or a full point changes what the good advice is — not for
every rule, but for enough of them to matter.

# plan.scoring.label
Scoring

# fmt.std
Standard

# fmt.half
Half PPR

# fmt.ppr
Full PPR

# plan.note.std
Standard scoring: no points for catches. This is the format all of our
simulations were run in, so these are the numbers we know best.

# plan.note.half
Half PPR: half a point per catch. The most common setting on ESPN and
Sleeper, and usually your app's default even when your league isn't
set that way.

# plan.note.ppr
Full PPR: one point per catch. Receivers and pass-catching running
backs are worth more here than anywhere else, and tight end is the
position that moves the most.

# plan.changed-only
Show only the {n} rules that change with scoring

# plan.changes
changes with scoring

# plan.changes.tip
This rule says something different depending on whether your league
pays for catches.

# plan.why.tip
The write-up this rule comes from.

# plan.none-changed
Nothing on this page changes in this format.


# weekly.title
Weekly rankings

# weekly.tab.dst
D/ST

# weekly.tab.k
K

# weekly.tab.skill
QB / RB / WR / TE

# weekly.search
Search…

# weekly.search.label
Search teams

# weekly.hide-taken
Hide taken

# weekly.hide-taken.tip
Hide every row you have marked as taken.

# weekly.clear
Clear

# weekly.clear.tip
Clear every mark on this list.

# weekly.dst.blurb
Defenses ranked by how many points Vegas expects their opponent to
score this week. Lower is better.
[Finding 27](#/blog/27-dst-model)

# weekly.dst.note.title
Why ESPN and Yahoo get the same list

# weekly.dst.note.body
ESPN and Yahoo score defenses differently. Yahoo pays more at the
extremes: a shutout is worth 10 points on Yahoo and 5 on ESPN, and
getting blown out costs 10 on Yahoo and 6 on ESPN. But both reward the
same thing, which is playing a bad offense. When we re-ran the model
under each scoring system, the order barely moved. Your point totals
will differ between the two sites. The ranking won't.

# weekly.k.blurb
Kickers ranked by how many points Vegas expects their own offense to
score this week, plus a small bonus for indoor games. Higher is better.
Pick the offense and the stadium, not the kicker.
[Finding 28](#/blog/28-kicker-model)

# weekly.skill.title
Starts in September

# weekly.skill.body
Weekly rankings for quarterbacks, running backs, receivers and tight
ends need a few weeks of real games before they mean anything.

The model is already built. It uses four things: how a player has
scored recently, his expected points (what his targets and carries are
normally worth), how many points the opposing defense gives up to his
position, and the Vegas line for the game. Expected points is the most
useful of the four.

It also drives the waiver advice. A player whose expected points rise
before his actual scoring does is the one to claim early.

We will publish all of it once we have graded it against real results
from this season, and not before.


# board.title
2026 draft: kickers and defenses

# board.subtitle
The only two positions worth ranking.
[See the models](#/models)

# board.blurb
Draft everyone else in the order your app already lists them, and
don't reach. In 9,000 practice drafts that won 2.5 times as many
titles as an average drafter, and it beat every ranking we built,
including our own.

Kickers and defenses are the exception. Their points come from their
team's offense and their schedule, not from the player, and a model
predicts those better than the draft order does.
[Finding 32](#/blog/32-draft-sim)

# board.k.title
Kickers

# board.dst.title
Defenses

# board.k.blurb
Take a kicker with one of your last two picks, off this list. A
kicker's own past stats predict almost nothing about his future ones.
His points come from his offense, so draft the offense.
[Kicker model](#/blog/28-kicker-model)

# board.dst.blurb
Take a defense with your other last pick, off this list. A defense's
points come mostly from the offenses it has to play, so the list is
sorted by how much its 2026 opponents are expected to score.
[Defense model](#/blog/27-dst-model)


# models.title
The models

# models.subtitle
What each model predicts, what it reads, and how we tested it.

# models.body
## Why we don't rank quarterbacks, running backs, receivers or tight ends

We built one, and it lost to the draft market.

The model used 20 inputs for returning players: how much they were
used, their expected points, touchdown luck, age, seasons played, where
they were drafted, their contract and share of the cap, and whether
they changed teams. We graded it against the draft market on the same
set of players. The market ranked them better at every position, .598
to .544. [Finding 25](#/blog/25-player-model)

Then we tested it in 9,000 simulated leagues with full drafts and full
seasons. Drafting by the model instead of by ADP cut the odds of
winning a title roughly in half, from 20.7% down to 10.8%. Every blend
of the two finished behind plain ADP.
[Finding 32](#/blog/32-draft-sim)

We built a rookie model too, from draft position, combine numbers and
landing spot, deliberately leaving fantasy ADP out of it. It came out
almost identical to the NFL draft order. Its projections are honest:
rookies it put at 8 or more points a game averaged 10.0 and were worth
starting 86% of the time, against 1% for its bottom group. But that
information is just what round a player was drafted in, which anyone
can look up and which is already priced into every draft board.
[Finding 31](#/blog/31-rookie-model)

So our advice for these four positions is the boring one: take your
platform's ADP in order and don't reach. Three pieces of that work are
still useful, and all three describe last season rather than predicting
the next one: expected points, touchdown-luck regression, and the
position-room note in the draft tool. The code and the dead ends are
kept in `archive/season-projection-model/`.

## Expected points, the "2025 expected" column

This is not a prediction. It is a review of last season.

For every play in 2025 it asks what an average player would have scored
from the same situation: who got the ball, where on the field, and on
what down and distance. Then it adds those up. A player who scored well
above his expected points usually got there on touchdown luck, which
does not repeat. The opportunities themselves do repeat.

The gap between the two is the strongest buy-or-avoid signal in our
research at receiver and tight end.
[Finding 16](#/blog/16-td-luck-regresses)
[Finding 17](#/blog/17-buy-targets-not-efficiency)

## Kicker model

**Predicts:** kicker points, for a week and for a season.

**Reads:** how many points Vegas expects his own offense to score. That
one number is nearly the whole model. On top of it, an indoor game is
worth about 0.7 points and a windy one costs about 0.5. A kicker's own
past stats predict almost nothing.
[Finding 28](#/blog/28-kicker-model)

## Defense model

**Predicts:** defense points, for a week and for a season.

**Reads:** how many points Vegas expects the opposing offense to score.
That does about 97% of the work. Every point off the opponent's
expected total is worth about 0.38 more defense points. The season list
adds this up across all 17 games of the 2026 schedule.
[Finding 27](#/blog/27-dst-model)

## Weekly player model, starting in September

**Predicts:** this week's points for quarterbacks, running backs,
receivers and tight ends.

**Reads:** how a player has scored recently, his expected points from
recent usage (the most useful of the four), how many points the
opposing defense gives up to his position, and the Vegas line for the
game.

## Injury model

**Predicts:** whether a player will actually play.

**Reads:** the injury reports from 2018 through 2025. It gives the
chance that a player listed on Friday plays on Sunday, how much playing
hurt costs him, how long each type of injury keeps a player out, and
how much he is slowed in his first game back.
[Finding 21](#/blog/21-injury-model)

## Vegas offense table

This one is not ours. It is the betting market's.

Add up the lines for all 272 games on the 2026 schedule and you get the
points per game expected from every offense. The kicker and defense
models both read it.

It is not a tiebreaker between two skill players. Everyone can see the
same lines, so it is already priced into what those players cost in a
draft. [Finding 30](#/blog/30-good-offense-tiebreak)

# models.source
Every model's code and data are public:
[github.com/Zinkelburger/Fantasy-Football-Tool](https://github.com/Zinkelburger/Fantasy-Football-Tool)


# blog.title
Research

# blog.subtitle
Newest first. Every write-up shows its work.

# blog.glossary.title
What the stats mean, in plain English

# blog.glossary.body
- **Spearman, or rank correlation.** How well two rankings agree, on a
  scale from −1 to 1. 1 means identical order, 0 means no relationship
  at all. This is our usual measure, because fantasy is about who
  finishes ahead of whom.
- **Pearson correlation.** How closely two sets of numbers move
  together, also −1 to 1. Like Spearman, except it also cares how big
  the gaps are, not just the order.
- **Implied total.** How many points Vegas expects a team to score,
  worked out from that game's point spread and over/under.
- **ADP, or average draft position.** Where real drafters are actually
  taking a player. The market's opinion of him.
- **All-play.** The record you would have if you played every team in
  the league every week. It measures how good a team is with schedule
  luck taken out.
- **Backtest, or leave-one-year-out.** Testing a model on past seasons
  it never saw while it was being built, so it can't grade its own
  homework.
- **MAE, or mean absolute error.** How many points a prediction missed
  by, on average.
- **95% confidence interval.** The margin of error: the range the true
  number sits inside, 19 times out of 20.

# blog.back
← All research

# blog.notfound
We couldn't find that write-up.


# live.title
My league

# live.field.label
Your Sleeper username, or an ESPN league id

# live.field.placeholder
username, league id, or a league URL

# live.connect
Connect

# live.connecting
Connecting…

# live.switch
Change league

# live.via
via

# live.tab.matchup
Matchup

# live.tab.startsit
Start/sit

# live.tab.waivers
Waivers

# live.tab.teams
Teams

# live.tab.review
Week in review

# live.tab.moves
Moves

# live.help.title
What this needs

# live.help.body
Everything here is read-only, and the league you pick stays in this
browser. There is no server to send it to.

**Sleeper** needs your username and nothing else.

**ESPN** needs the league id, which is the number after `leagueId=` in
the league's web address. Public leagues work straight away. A private
ESPN league needs our
[browser extension](https://github.com/Zinkelburger/Fantasy-Football-Tool/tree/main/chrome-extension),
which reads the league using the ESPN login you already have and passes
back only the answer. With the extension installed, your leagues show
up here on their own and you don't have to type anything.

**Yahoo** needs a login server that we don't run, so it isn't
supported.

# live.found.one
Your ESPN league, found in this browser.

# live.found.many
Your ESPN leagues, found in this browser.

# live.pick.team
{league} — which team is yours?

# live.pick.league.one
We found one league.

# live.pick.league.many
We found {n} leagues. Pick one.

# live.pick.team.prompt
Pick your team

# live.err.noleagues
That account has no leagues this season.

# live.err.noteams
That league has no teams in it.

# live.err.noid
Enter your ESPN league id, or paste the league's web address.

# live.hint.espn
ESPN league {id}.

# live.hint.sleeper
Sleeper user {name}.

# live.hint.is-sleeper
It's a Sleeper username

# live.hint.is-espn
It's an ESPN league id


# matchup.prob.label
chance to win

# matchup.prob.caveat
Accurate to about 4 percentage points, and least reliable when it is
most confident.

# matchup.note
Week {week}. {n} of your starters {have} not kicked off yet. We
simulated the rest of the week {sims} times. In 80% of those runs your
final margin landed between {lo} and {hi} points.

# matchup.dead
Counted as zero from here: {names}.

# matchup.no-team
We couldn't work out which team is yours.

# matchup.no-opponent
No opponent is set for week {week} yet.

# matchup.error
We couldn't load your matchup: {error}

# matchup.tip.remaining
Points we expect him to score in the rest of his game.

# matchup.tip.no-remaining
No points expected from here, because he is {why}.


# league.loading
Loading your league…

# league.no-team
We couldn't work out which team is yours.

# league.startsit.no-projection
Nobody on your roster has a projection for week {week} yet, so there is
nothing to compare. Projections usually appear a few days before the
games.

# league.startsit.blurb
Your best legal lineup this week, next to the one you have actually
set, using this week's projections. A projection is not a promise, but
over a season, starting the higher number wins more weeks than it
loses.

# league.startsit.gain
projected points sitting on your bench

# league.startsit.nogain
Your lineup is already the best one available.

# league.startsit.nothing
Nothing to change this week.

# league.startsit.empty-slot
an empty slot in your lineup

# league.startsit.lineup-title
The lineup

# league.startsit.nobody
— nobody eligible —

# league.startsit.missing
We have no projection for {names}. They count as zero here. That is
usually right, because it normally means a bye week or an inactive
player, but occasionally it just means the data is missing.

# league.waivers.search
search players

# league.waivers.only-available
only show available

# league.waivers.nomatch
Nobody matches that.

# league.waivers.truncated
Showing the top 120 of {n}.

# league.waivers.note
"Proj" is how many points we expect him to score this week under your
league's scoring rules.

"Adds" is how many points he would add to your best legal lineup if you
picked him up. A dash means he would not crack your lineup this week,
which is the real answer to whether he is worth a waiver claim. It is a
one-week number, so a player on a bye reads as a dash even when he is
worth stashing.

# league.waivers.tip.adds
What he would add to your best lineup this week.

# league.waivers.tip.no-adds
He wouldn't crack your lineup this week.

# league.waivers.tip.owned
Rostered in {pct}% of ESPN leagues.

# league.teams.blurb
Teams ranked by how many points their best legal lineup is projected to
score this week. This is not the standings. A good team in a bad bye
week will sit lower than its record suggests, and that is the point:
this ranks who is dangerous on Sunday, not who has been lucky.

# league.review.loading
Loading every week…

# league.review.no-weeks
No week has finished yet this season, so there is nothing to compare.

# league.review.no-games
No finished games to read yet.

# league.review.blurb
All-play is the record you would have if you played every team in the
league every week. It ignores who you happened to be scheduled
against, so it is a fairer measure of how you are doing than your real
record is.

"Luck" is your real win rate minus your all-play win rate. A positive
number means the schedule has been kind to you.

# league.review.through
Through {n} finished {weeks}. The week in progress is not counted.

# league.review.tip.lucky
Winning more than the scores deserve.

# league.review.tip.unlucky
Losing more than the scores deserve.

# league.moves.loading
Loading recent moves…

# league.moves.none
No completed moves in the last four weeks.

# league.moves.blurb
Every completed add, drop and trade from the last four weeks, newest
first.

# league.moves.error
ESPN wouldn't give us the list of moves: {error}


# tip.mark-row
Click to mark: taken, then mine, then clear.

# tip.opp-implied
How many points Vegas expects the opponent to score. Lower is better.
This one number does about 97% of the work: every point off the
opponent's total is worth about 0.38 more defense points (finding 27).

# tip.stream
One of the three best matchups this week. Picking defenses by the
opponent's total ranks them more than twice as well as picking by how
good the defense itself is, .30 against .13. Play the matchup, don't
hold a name (finding 27).

# tip.own-implied
How many points Vegas expects this kicker's own offense to score.
Higher is better. Kickers score when their team moves the ball and
wins. The kicker's own past stats predict almost nothing (finding 28).

# tip.dome
Indoors, so no wind and no weather. Worth about 0.7 points to a kicker
in our model. That is small, but it is the second-biggest effect we can
see, after how much his offense is expected to score. Wind costs about
0.5 (finding 28).

# tip.own-season
How many points Vegas expects this offense to score per game, averaged
over the whole 2026 season. A kicker's points follow his offense, not
his own past stats.

# tip.dome-schedule
How many indoor games this team plays in 2026, home and away. Each one
is worth about 0.7 kicker points, so a 10-dome schedule beats a 0-dome
schedule by roughly 0.4 points a game (finding 28). Use it to break a
tie, not as a reason to reach.

# tip.dome-count
{dome} of {games} games are indoors, worth about {edge} extra kicker
points a game over the season.

# tip.opp-season
How many points this defense's opponents are expected to score,
averaged over the whole 2026 season. Every point lower is worth about
0.38 more defense points a week (finding 27). Preseason win totals are
the best season-long signal we have, better than any signal built from
past stats (finding 26).


# error.load
This page didn't load. Check your connection, then try again.

# error.generic
We couldn't load that: {error}
