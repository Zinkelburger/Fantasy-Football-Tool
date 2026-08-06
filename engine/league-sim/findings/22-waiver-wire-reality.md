# 22 — The wire is worth 30 points a season, and it's all hole-patching

**Confidence: High.** 2,160 paired seasons, three drafters, same seeds.

> **Corrected 2026-08-05.** This used to say +5 to +12. That was wrong.
> Two bugs in the old waiver code sabotaged the team that was *allowed*
> to claim: it spent a quarter of its claims on players already known
> to be out for the year, and a sniped claim left the starting slot
> empty instead of grabbing the next body. Fixed, the answer tripled.

## The number

Same team, same league, same schedule, same seeds. Once with the wire,
once without.

| drafter | with wire | no wire | gain | ±95% | all-play Δ |
|---|---|---|---|---|---|
| pick_value | 1197 | 1167 | **+30** | 5 | +0.031 |
| robust_rb | 1204 | 1172 | **+31** | 5 | +0.030 |
| bpa | 1195 | 1162 | **+33** | 6 | +0.033 |

Three points of all-play. Getting QB draft timing exactly right is
worth about the same. Drafting with ADP discipline is worth twice it.

## All of it is patching empty slots

Four policies, same drafter, same seeds:

| policy | vs no wire | ±95% | claims/yr |
|---|---|---|---|
| fill empty slots only | **+35.4** | 3.9 | 4.3 |
| shop the bench every 3rd week from wk 6 | **+35.9** | 4.3 | 7.4 |
| hunt upgrades every week | +30.3 | 5.0 | 14.2 |

Filling holes is the entire edge. The extra ten claims a week-by-week
churner makes *cost* five points — you drop real depth for wire
mirages. RB goes from +1.6 to −3.5 as churn rises.

Checking waivers casually beats checking them obsessively.

## What one patched hole is worth

Team-weeks where the no-wire roster had nobody to start at a position,
and what the same team scored there once allowed to fix it:

| slot | hole-weeks | points gained | median | p90 |
|---|---|---|---|---|
| **QB** | 90 | **+14.3** | 13.0 | 25.0 |
| K | 251 | +8.4 | 9.0 | 15.0 |
| WR | 223 | +6.4 | 5.0 | 14.0 |
| TE | 297 | +4.8 | 3.0 | 11.0 |
| RB | 52 | +4.1 | 2.0 | 14.0 |

Fourteen points for one Wednesday click. Claims are not
interchangeable: a hole claim is worth 4 to 14 points, a bench-swap
claim is worth zero.

You start one QB and one K, so those holes are total — you score zero.
You roster six RB/WR for five slots, so RB holes are rare (52 events
vs 251 at K) and shallow.

## Holes are more common than they feel

A full 15-man roster with no waivers, by week:

| slot | % of team-weeks | per season |
|---|---|---|
| K | 17.8% | 2.50 |
| TE | 10.8% | 1.51 |
| QB | 8.2% | 1.15 |
| RB | 7.5% | 1.06 |
| WR | 3.6% | 0.51 |

Seven times a season you genuinely need the wire.

## What you actually add

| pos | adds | wks held | pts/wk | cut within 2 wks |
|---|---|---|---|---|
| **QB** | 146 | 5.9 | **11.4** | 12% |
| RB | 1,421 | 3.8 | 4.7 | 40% |
| WR | 1,255 | 4.6 | 4.7 | 30% |
| TE | 545 | 4.1 | 4.4 | 36% |

A waiver QB is a real player — 11.4 a week against a top-12 starter's
19.1, held six weeks, rarely cut. Everything else is a body worth about
4.5 a week. Fine when the alternative is zero. Pointless when the
alternative is your own bench.

## Rules

1. **Never field an empty slot.** Worth 30 points a season, costs
   nothing.
2. **Go to the wire when a bye or injury opens a hole, not weekly.**
   Weekly churn loses points.
3. **Don't chase RB upgrades.** It's negative in every test.
4. **A waiver QB covers a bye fine.** It does not fix drafting your
   QB1 in round 10 — see [finding 36](36-draft-order.md).

## Methodology

`analysis/wire_worth.py` — 60 sims × 6 seasons × 3 drafters, each run
twice off the same seed. `NoClaims` blocks every claim including
hole-fixing.

`analysis/wire_decompose.py` — one drafter, four policies, 1,440
seasons, paired per (year, sim).

`analysis/wire_hole_value.py` — needs `run_season(track_weekly=True)`,
which records per-week slot points and empty slots. Off by default,
changes nothing else.

Everything live: emergent FA pool, adds and drops, season-ending
injuries clearing spots, real Friday injury reports driving start/sit
([finding 21](21-injury-model.md)), rivals claiming at rates calibrated
to real ESPN transaction counts, reverse-standings priority rebuilt
weekly. Claims are chosen on production-to-date only — no pedigree, no
hindsight.

```bash
venv/bin/python analysis/wire_worth.py
venv/bin/python analysis/wire_decompose.py
venv/bin/python analysis/wire_hole_value.py
```

## Caveats

- Prices the wire on top of a full roster, not an empty one.
- The no-wire arm can't drop a player who's out for the year, so it
  carries dead weight. Inflates the gap somewhat.
- Six seasons of real football. The paired seasons resample it; they
  don't add new football.
- The rival bots aren't sharp. A better room strips the wire faster.
- K gains are bye-week patching, not kicker skill
  ([finding 04](04-kickers-are-noise.md)).
