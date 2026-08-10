# 37 — Injury risk: the position barely matters, the calendar matters a lot

**Confidence: High** for the week-of-season curve and the
position-gap null — 1,488 player-seasons, 24,690 player-weeks, and the
pipeline reproduces finding 21's play rates exactly. **Medium** for the
age results (the WR slope is one significant result out of four
positions tested). **Low** for the tight-end production cell, which
contradicts finding 21 and is unresolved.

- Drafted players miss **2.1 to 2.7 games a season** depending on
  position — and **every pairwise gap between positions is inside the
  noise**. RB minus WR is +0.29 games, 95% CI [−0.15, +0.71]. "Running
  back is the injury position" is not supported.
- Tight end is nominally the *worst* position on games missed (2.73)
  and on season-enders (15.0%), not running back.
- The real running-back tax is **timing, not frequency**: when an RB's
  season ends, the median last week played is **7**, versus 9 for
  WR/QB and 11 for TE. Same odds, more of your season gone.
- **Injury risk roughly doubles by the fantasy playoffs.** New
  absences per available player-week run ~10% in weeks 1–6 and 15.6–22.1%
  in weeks 13–16. Weeks 17–18 are excluded from that comparison so
  resting starters can't explain it.
- Age raises games missed at **wide receiver only** (+0.133 games per
  year, CI [+0.041, +0.226]). The RB age slope is +0.074, CI crossing
  zero — the "old running back breaks down" story does not appear in
  games missed at the sample sizes we have.

## Question

Findings 18 and 21 answered two narrow questions: does injury history
repeat (mostly no), and what is a Friday tag worth (Out means out,
Questionable means 69%). Neither answered what people actually argue
about at the draft table: what is the **baseline**? Does a drafted RB
miss more games than a drafted WR? Does risk climb through the season?
Does it climb with age?

## Setup

- **Population**: the ADP-draftable board for each season 2018–2025 at
  QB/RB/WR/TE — 1,508 player-seasons, 1,488 matched to rosters (99%).
  Defined **before** the season, so nothing is conditioned on how it
  turned out.
- **Panel**: every week the player's team had a game (byes drop out via
  the schedule; mid-season trades follow the roster team). 24,690
  player-weeks.
- `research/injury_predictor/position_age_injury.py`, outputs in
  `results_position_age.json`, panel cached as
  `panel_position_age.parquet`.

### The measurement trap that shapes the whole design

**Players placed on injured reserve fall off the NFL injury report
entirely.** Nick Chubb's 2023 and Kirk Cousins' 2023 have *zero*
injury-report rows after the injuries that ended their seasons. Aaron
Rodgers' 2023 shows up only in weeks 13–18, when he was practising to
return from the Achilles.

So counting "weeks listed Out" — the method behind finding 18 — erases
precisely the season-ending injuries this finding is about. Two
independent sources fix it:

- **did he play** = nflverse snap counts, `offense_snaps > 0`
- **was it injury** = weekly roster status in {RES, PUP, NFI} **or** a
  report status of Out/Doubtful

**Validation**: run finding 21's numbers through this pipeline and they
reproduce. Out players suited up 0.09% of the time (finding 21: 0.1%),
Doubtful 1.06% (finding 21: 1%). The Questionable play-rate ordering
also reproduces, QB lowest.

## Result 1 — position barely separates

Per player-season, players who were on a roster for 14+ team games:

| Pos | n | Games missed | 95% CI | Never missed | Missed 4+ | Missed 8+ | Season-ending |
|---|---|---|---|---|---|---|---|
| QB | 214 | 2.06 | [1.57, 2.58] | 58.9% | 21.0% | 9.8% | 14.5% |
| RB | 529 | 2.57 | [2.25, 2.91] | 45.0% | 24.4% | 11.9% | 11.0% |
| WR | 558 | 2.28 | [2.01, 2.56] | 44.4% | 23.7% | 9.3% | 9.5% |
| TE | 180 | 2.73 | [2.22, 3.29] | 40.0% | 30.0% | 11.7% | 15.0% |

Every pairwise difference, bootstrapped:

| Gap | Estimate | 95% CI | Verdict |
|---|---|---|---|
| RB − WR | +0.29 | [−0.15, +0.71] | noise |
| TE − WR | +0.45 | [−0.15, +1.07] | noise |
| RB − QB | +0.52 | [−0.09, +1.10] | noise |
| TE − RB | +0.16 | [−0.45, +0.82] | noise |

Not one gap clears zero. Note also the direction: **tight end is
nominally worst on games missed and on season-enders**, which is the
opposite of the folk ordering. Season-ending injuries (defined as
losing the final 4+ games after having played) are 170 cases total, and
the QB list is a clean sanity check — Burrow 2023, Rodgers 2023,
Cousins 2023, Prescott 2020 and 2024, Garoppolo 2018, Lance 2022,
Lamar 2022, Kyler 2022. Several of those have no injury-report rows at
all; only the IR-status source catches them.

The one place running back is genuinely worse is **when** the season
ends:

| Pos | Median last week played, among season-enders |
|---|---|
| RB | 7 |
| QB | 9 |
| WR | 9 |
| TE | 11 |

An RB's lost season costs you roughly two more weeks of your own
season than a receiver's does. That is a real cost and it is not
captured by counting games missed.

## Result 2 — the calendar is the big effect

New injury absences per **available** player-week (players already out
are removed from the denominator, so this is a hazard, not a
prevalence):

| Pos | Wk 1–6 | Wk 7–12 | Wk 13–16 | Wk 17–18 |
|---|---|---|---|---|
| QB | 7.02% | 11.98% | 15.96% | 24.28% |
| RB | 10.01% | 16.64% | 18.51% | 23.63% |
| WR | 10.04% | 14.69% | 15.61% | 19.65% |
| TE | 10.15% | 16.37% | 22.09% | 25.00% |

Two checks on the obvious objections:

- **Is it just teams resting starters in week 18?** No. Weeks 17–18 are
  broken out separately and the rise is already there by weeks 13–16 —
  the fantasy playoff weeks — at 1.6× to 2.2× the September rate.
- **Is it survivorship?** It works against us. By December the fragile
  players are already out and excluded from the at-risk pool, so the
  surviving population is the *healthier* one. The true rise is if
  anything steeper than this table.

This is the largest, cleanest effect in the study, and it is bigger
than any position difference by a wide margin.

## Result 3 — age

Extra games missed per year of age, controlling for log(ADP), bootstrap
CIs:

| Pos | Slope | 95% CI | Verdict |
|---|---|---|---|
| QB | −0.019 | [−0.109, +0.079] | noise |
| RB | +0.074 | [−0.045, +0.204] | noise |
| WR | **+0.133** | **[+0.041, +0.226]** | **real** |
| TE | +0.081 | [−0.087, +0.261] | noise |
| pooled | +0.058 | [+0.006, +0.116] | real, tiny |

Threshold form, in case the effect is a cliff rather than a slope:

| Test | Extra games | 95% CI | n old | Verdict |
|---|---|---|---|---|
| WR 29+ | +0.92 | [+0.17, +1.75] | 110 | real |
| WR 30+ | +0.75 | [−0.11, +1.64] | 80 | noise |
| RB 28+ | +0.88 | [−0.04, +1.92] | 90 | noise |
| RB 29+ | +0.88 | [−0.29, +2.17] | 57 | noise |
| TE 30+ | +0.56 | [−0.78, +2.11] | 34 | noise |
| QB 33+ | −0.35 | [−1.59, +1.01] | 48 | noise |

### Why the raw RB 29+ number misleads

The raw table looks alarming: RBs aged 29+ miss **3.35** games against
2.14–2.74 for younger buckets. Two things eat most of it.

**Price.** Old RBs who are still drafted are drafted cheap — mean ADP
106 for the 29+ group versus 77–88 in the prime-age buckets. Cheap
players miss more games for reasons that have nothing to do with age:
they are committee backs and backups, nobody rushes them back, and
they are likelier to be stashed on IR than carried. Putting log(ADP) in
the regression compares old and young RBs *at the same draft price* and
the gap falls from ~+1.0 raw to +0.88.

**Sample.** 57 old-RB seasons is not enough to separate +0.88 from
zero; the CI runs [−0.29, +2.17].

That is what "does not survive the control" means here — **not
disproven, unproven.** The point estimate is the same size as the
confirmed WR effect, and matching on ADP tier still shows old RBs
missing more inside every tier (+2.64, +0.57, +0.78 games in the
25–60, 61–120 and 121+ tiers). The distribution also says it is a tail
effect, not a broad shift: the median is 1 game missed for both old and
young RBs, and it is the 75th percentile that moves (5 games vs 3).
Read it as a real possibility we cannot yet measure, not as a null.

## Result 4 — tags and playing hurt

Per player-week, and conditional play rates:

| Pos | Listed Questionable | On the report at all | Plays if Questionable |
|---|---|---|---|
| QB | 4.6% | 8.9% | 56.9% |
| RB | 7.4% | 11.0% | 62.6% |
| WR | **8.7%** | **13.8%** | 71.1% |
| TE | 6.9% | 11.7% | 78.0% |

Receivers get tagged most often, not running backs — another folk
ordering that does not hold. But QBs and RBs are the least likely to
actually suit up once tagged.

Points as a percentage of **that player's own healthy-week average**
that season (own-baseline, so this is not a talent comparison):

| Pos | Questionable | Limited in practice | DNP in practice | First game back |
|---|---|---|---|---|
| QB | 85.2% (n=80) | 92.2% | — | 86.0% (n=46) |
| RB | 91.0% (n=326) | 93.4% | 86.4% (n=73) | 89.4% (n=166) |
| WR | 90.0% (n=447) | 92.9% | 85.3% (n=174) | 95.4% (n=217) |
| TE | 100.2% (n=113) | 98.7% | — | 103.1% (n=70) |

**Unresolved conflict with finding 21.** Finding 21 put a Questionable
TE at −25% and a Questionable WR at −20%; this measurement puts TE at
0% and WR at −10%. The methods differ (own-baseline here, cross-
sectional there) and the TE cell rests on 113 player-weeks. Until one
is shown wrong, the TE discount should be treated as **unknown**, and
the simulator's `set_lineup` TE multiplier of 0.75 (env v4, from
finding 21) should be flagged as resting on the disputed number.

## What to do with it

- **Stop docking running backs for injury at the draft table.** The
  position gaps do not exist at measurable size. Draft RBs for the
  reasons in finding 23 (the steeper positional curve), not against
  them for a fragility that is not there.
- **Do dock old receivers.** This is a second, independent reason on
  top of finding 10's production cliff: a 30-year-old WR is both worse
  per game and less available.
- **Price the calendar.** A week-13 injury tag is a materially worse
  signal than the same tag in week 3, and points banked in September
  are points banked in the healthiest part of the season.
- Treat the RB timing tax, not the RB injury rate, as the real reason
  handcuffs matter (finding 13).

## Honest limits

- The ADP pool is ~179 players a season, so TE (n=180 seasons) and QB
  (n=214) are thin. The position nulls are "no gap detectable at this
  sample", not "no gap".
- "Injury absence" needs a roster IR flag or an Out/Doubtful listing. A
  player who is quietly inactive with no designation is not counted —
  correct for fantasy purposes, but it means late-season shutdowns of
  players on eliminated teams are only counted when the team files
  paperwork.
- Weeks 17–18 mix injury with resting even after the split. The
  weeks 13–16 comparison is the one to quote.
- Four positions were tested for an age slope and one came back
  significant; the WR result deserves an out-of-sample season before it
  is treated as settled.
