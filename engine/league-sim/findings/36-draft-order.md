# 36 — Draft order: QB timing is the only lever that matters

**Confidence: High** for QB timing (monotone across four arms, 27-point
spread). **High** for the QB2/TE2/bench nulls (tight CIs, 1,200+ paired
seasons each). **Medium** for the early-RB count, which is
observational.

Almost nothing about draft order matters. One thing does.

- **QB by round 5.** Every round you wait costs points. Round 4 is
  +10, round 10 is −17.
- **Open RB.** Two or three in rounds 1–4.
- **Everything else is free.** TE timing, a backup QB, the RB/WR split
  on your bench — all inside the noise. Stop agonising.
- **A backup TE is the one thing that's actively worse than nothing.**

## QB timing is the lever

Timing windows only. No caps on RB/WR counts, so no arm is ever forced
to take a player it doesn't want.

| rule | vs baseline | ±95% | all-play |
|---|---|---|---|
| QB1 from round 4 | **+10.1** | 10.4 | .611 |
| QB1 from round 6 | +2.0 | 11.5 | .604 |
| QB1 from round 8 | −9.7 | 12.8 | .592 |
| QB1 from round 10 | **−17.0** | 11.7 | .586 |

27 points from best to worst. Each interval is wide, but four arms
land in order — that's the signal.

There's no cliff to time. Each round of delay costs a few points, so
"grab the best QB once the RB rounds are done" is the whole rule.

**Waiting is not rescued by streaming.** A waiver QB scores 11.4 a
week; a top-12 starter scores 19.1. Over 14 weeks that gap *is* the
late-QB penalty ([finding 22](22-waiver-wire-reality.md)).

**Conditional rules don't help.** "If I opened RB-heavy take the QB at
5, else wait to 8" scored +5.4 — between the fixed round-4 and round-6
rules, beating neither. Take the QB early regardless of how the RB
rounds went.

## The backup QB does get used, and still wins nothing

2,893 teams that drafted a QB2:

| | |
|---|---|
| weeks he actually started | 3.3 of 14 (median 2) |
| never started at all | 17% |
| started 3+ weeks | 47% |
| **became the primary starter** | **18%** |
| ppg in weeks he started | 14.8 |

So "maybe one of them becomes good" is real — it happens about one year
in five. It still doesn't pay:

| arm | PF | all-play | playoffs | titles | ±95% |
|---|---|---|---|---|---|
| QB2 allowed | 1191 | .602 | 76.9% | 21.8% | 2.3% |
| QB2 banned | 1192 | .601 | 78.0% | 21.4% | 2.3% |

Paired title difference **+0.4% ± 2.9%** over 1,200 paired seasons.
Nothing.

He's not useless, he's *redundant*. The weeks he starts are the weeks
you'd have streamed a QB anyway, and the streamer scores 11.4 to his
14.8. You're buying three points a week, six times a year, with a
draft pick.

Draft one if you like. Don't plan around it.

## A backup TE is worse than nothing

Banning the TE2 scored **+2.9** against +2.0 for keeping it. The
observational data agrees in every early-round build: teams that took
zero late TEs beat teams that took two, .531 vs .507.

Use the pick on anything else.

## TE timing barely registers

QB fixed at round 5, only the TE rule moves:

| rule | vs baseline | ±95% | TE slot pts |
|---|---|---|---|
| TE from round 4 | +0.7 | 8.9 | 91 |
| TE from round 6 | −5.2 | 9.0 | 85 |
| TE from round 8 | −5.4 | 9.7 | 79 |
| TE from round 10 | −6.8 | 10.0 | 75 |
| TE from round 12 | −5.2 | 10.2 | 75 |
| TE from round 14 (punt, stream) | −4.4 | 10.2 | 73 |

Waiting costs you 18 points **in the TE slot** (91 → 73) and costs the
team nothing, because the pick buys a better player somewhere else.
That's what a fungible position looks like.

Every arm sits inside its own interval. Take the TE whenever — but see
[finding 33](33-te-same-pick.md), which has the sharper same-pick
result: rounds 1–4 or round 10+, never the 5–9 middle.

**Streaming TE is worse than it was.** Undrafted TEs cracking the
year's top 8 went 3, 2, 3 in 2020–22 then 0, 1, 0 in 2023–25
([finding 05](05-never-pay-up-for-te.md)), and a TE hole patched off
the wire is worth only 4.8 points. Don't plan on it.

## The bench doesn't care what position you fill it with

Rounds 9–15 forced to one position, starters already covered:

| arm | vs free | ±95% | all-play | titles |
|---|---|---|---|---|
| RBs only | +0.9 | 1.4 | .604 | 23.8% |
| WRs only | −0.7 | 1.9 | .602 | 22.8% |

**Late RB minus late WR: +1.6 ± 2.3 points.** Nothing.

This overturns the observational read. Watching ordinary drafts, teams
that took four late RBs beat teams that took none by five points of
all-play in every early-round stratum — a huge gap. It's endogenous.
Those teams took four late RBs *because* good RBs kept falling to
them, and that's what the outcome measures. Force the rule and the gap
vanishes.

Consistent with [finding 19](19-bench-composition.md), which found the
same null under the old simulator.

Late RBs *are* the boom-or-bust asset — that part of the folklore is
true (ADP 96–180, 2020–25):

| pos | 3+ startable weeks in a row | dud (≤1 week) | ppg |
|---|---|---|---|
| RB | **15%** | 42% | 4.5 |
| WR | 10% | 36% | 5.3 |
| **TE** | 23% | 20% | 4.9 |
| **QB** | **31%** | **16%** | 13.9 |

An RB ascends more often than a WR. He also busts more often, and the
two cancel. Note the real story in that table: **late QBs and TEs hit
far more often than late RBs or WRs.** That's why drafters naturally
end up with two QBs (81%) and two TEs (67%) — the bodies are simply
better. It just doesn't win, for the redundancy reasons above.

## Open RB

Observational — 18,000 team-seasons, nobody told what to draft:

| RBs in rounds 1–4 | teams | all-play |
|---|---|---|
| 0 | 1,516 | .450 |
| 1 | 5,446 | .490 |
| 2 | 6,852 | .510 |
| **3** | **3,581** | **.517** |
| 4 | 605 | .506 |

Peak at three, two close behind, four slightly worse.

Treat this as the weakest claim here — teams end up with three early
RBs partly because RBs fell to them. But it points the same way as the
hindsight-optimal search (58% of *perfect* drafts open RB, and the
median round-1 RB bought is the season's actual RB1,
[finding 24](24-hindsight-optimal-drafts.md)), the same-rank talent
premium ([finding 23](23-early-rb-vs-wr.md)), and the strategy
backtest ([finding 01](01-robust-rb-wins.md)). Four independent looks,
same direction.

## The flowchart

1. **Rounds 1–4:** RBs. Take two or three. Don't force a fourth.
2. **Round 5–6:** best QB available. Don't let it slide past 6.
3. **TE:** elite in rounds 1–4 or wait until round 10+. Never 5–9.
4. **Everything else:** WRs, wherever they fall.
5. **Rounds 9–15:** genuinely doesn't matter. No TE2.
6. **In season:** fix empty starting slots off the wire. Ignore the
   rest of the wire.

## Methodology

- `analysis/flowchart.py` — QB timing + QB2/TE2 arms. Timing windows
  only, never count caps. 40 sims × 6 seasons × 10 arms, paired.
- `analysis/qb2_usefulness.py` — QB2 start rate via
  `run_season(track_weekly=True)`, which records the pids actually in
  each week's lineup. Titles arm: 200 sims × 6 seasons.
- `analysis/te_timing.py` — TE window sweep, QB pinned at 5.
- `analysis/bench_tilt_v5.py` — rounds 9–15 forced to one position.
  Both arms reach equally hard, so the head-to-head is clean.
- `analysis/draft_shape_bands.py` — observational, 18,000 team-seasons,
  split into rounds 1–4 and 9–15.

## Caveats

- **The forced-template trap.** An earlier version of this work capped
  positional counts, which made the drafter reach past better players
  — worth about 10 points of preseason talent. Worse, the RB/WR
  templates pinned QB=1 and TE=1, so they were secretly testing "no
  backup QB/TE". Every arm here constrains *when*, not *how many*.
- One room, the calibrated family bots. A sharper room changes the
  QB timing result most (early QB gains value against sharp rooms —
  [finding 03](03-adp-discipline-is-not-an-edge.md)).
- Injuries are the real historical record, not resampled. A player who
  missed eight games misses eight in every sim, so none of this sees
  the tail where your top three RBs all go down at once.
- The early-RB table is observational. Everything else here is a
  forced A/B.
- Standard scoring, 1 QB / 2 RB / 2 WR / 1 TE / 1 FLEX (RB-WR) / 1 K.
  Superflex or TE-premium would break the QB and TE results.
