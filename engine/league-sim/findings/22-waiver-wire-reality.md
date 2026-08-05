# 22 — The waiver wire is worth ~30 points a season, and it is all hole-patching

**Confidence: High.** Clean paired counterfactual — identical draft,
field, schedule and seeds, the only difference being whether the hero
may claim. Three drafters agree on sign and size (+30/+31/+33, all
±5–6). Four waiver policies decompose it. Six seasons of underlying
football, 2,160 paired seasons plus 1,440 for the decomposition.

> **CORRECTED 2026-08-05.** The previous version of this finding said
> the wire was worth **+5 to +12** points a season under sim v4. That
> was an artifact of two measured bugs in the v4 waiver code, both of
> which crippled the *with-wire* arm: managers spent 25% of their
> claims on players already knowably out for the year, and a sniped
> hole claim left the starting slot **empty** instead of falling
> through to a midweek free-agency grab (~2.3 empty slots a season).
> Under v5 the same experiment returns **+30 to +33**. The old
> headline understated the wire by roughly 3×.

## TL;DR

Run the same team through the same season twice — once allowed to use
the waiver wire, once forbidden. The wire is worth **+30 to +33 points
a season**, about **+0.031 all-play** (~2.6% of a team's total). Nearly
all of it is **patching starting slots that would otherwise sit empty**:
QB +8, K +9, WR +9, TE +7. It is still **negative at RB** (−3).

The important new result is the decomposition: a policy that *only*
fills empty slots captures **+35.4**, while the aggressive policy that
also churns the bench weekly for projected upgrades captures only
**+30.3**. **The churn is worth less than nothing.** Everything the
wire gives you comes from not fielding a zero.

## What the wire is worth (v5)

Paired: identical drafter, identical field, identical schedule, same
seeds. The only difference is permission to claim.

| drafter | with wire | no wire | gain | ±95% | all-play | Δ | claims/yr |
|---|---|---|---|---|---|---|---|
| pick_value | 1197 | 1167 | **+30** | 5 | 0.609 | **+0.031** | 14.0 |
| robust_rb | 1204 | 1172 | **+31** | 5 | 0.616 | **+0.030** | 14.0 |
| bpa | 1195 | 1162 | **+33** | 6 | 0.602 | **+0.033** | 14.2 |

For scale, in all-play points (1 point = 0.01): the wire is worth
**~3.1**. The entire QB-timing sweep spans ~3–4 points from best round
to worst ([finding 14](14-qb-round-sweep.md): .578 at r2 vs .549 at
r12), and ADP discipline is worth ~6–8. So **using the wire properly
is worth about as much as getting QB timing exactly right, and about
half of drafting with discipline at all.** Under the old +0.01 number
it looked like a rounding error. It is not.

## Where the points land

Season points by lineup slot, with-wire minus without:

| drafter | QB | RB | WR | TE | FLEX | K |
|---|---|---|---|---|---|---|
| pick_value | +7 | −3 | +9 | +8 | +2 | +8 |
| robust_rb | +8 | −5 | +12 | +5 | +2 | +9 |
| bpa | +8 | −0 | +5 | +7 | +3 | +10 |

**Every position gains except RB.** The v4 version of this table showed
gains only at QB and K, which is what produced the old "it's just
roster maintenance at the singleton slots" story. With the empty-slot
bug fixed, WR and TE gain as much as QB does — because those slots
*were* going empty in the with-wire arm and getting scored as zeros.

## The decomposition — this is the actual finding

Same drafter (`pick_value`), same seeds, four waiver policies:

| arm | what it does | vs no-wire | ±95% | all-play Δ | adds/yr |
|---|---|---|---|---|---|
| `nowire` | never touches the wire | — | — | — | 0.0 |
| `holes_only` | **only** fills a slot that would be empty | **+35.4** | 3.9 | +0.034 | 4.3 |
| `naive_wk6` | holes + shop worst bench every 3rd wk from wk 6 | **+35.9** | 4.3 | +0.034 | 7.4 |
| `full_policy` | holes + any 3-ppg upgrade, checked weekly | +30.3 | 5.0 | +0.031 | 14.2 |

Season points by slot, arm minus no-wire:

| arm | QB | RB | WR | TE | FLEX | K |
|---|---|---|---|---|---|---|
| `holes_only` | +7.3 | +1.6 | +10.3 | +7.5 | +1.2 | +7.4 |
| `naive_wk6` | +7.4 | +0.2 | +10.4 | +7.9 | +2.9 | +7.1 |
| `full_policy` | +7.3 | −3.5 | +9.3 | +6.8 | +2.9 | +7.4 |

Three things fall out:

1. **Hole-patching is the whole wire.** 4.3 claims a season buys
   +35.4 points. That is ~8 points per claim, and it is the only
   mechanism that pays.
2. **Bench churn is negative.** Going from 4.3 to 14.2 adds a season
   *costs* 5 points. The extra ten claims drop useful depth for wire
   mirages — visible as RB going +1.6 → −3.5.
3. **The patient human loop is optimal.** `naive_wk6` — the way people
   actually play, shopping the worst bench spots every few weeks and
   keeping what works — captures +35.9, statistically identical to
   pure hole-patching and better than weekly churn. Being casual about
   upgrades is not a leak. Being *aggressive* about them is.

## Why the holes exist: they are more common than they feel

How often a full 15-man drafted roster has **no active body** for a
starting slot in a given week (10,080 team-weeks, no waivers):

| slot | % of team-weeks | per team-season |
|---|---|---|
| K | 17.8% | **2.50** |
| TE | 10.8% | **1.51** |
| QB | 8.2% | **1.15** |
| RB | 7.5% | 1.06 |
| WR | 3.6% | 0.51 |

A 15-man roster goes to the wire out of genuine necessity about **7
times a season**. That matches the 4.3 claims `holes_only` actually
makes (some holes get patched by a body already rostered). The K and
TE numbers are byes; the QB number is byes plus the fact that a
one-QB roster has no fallback at all.

## What ONE patched hole is worth

The per-event version, which is what a manager actually experiences.
For every team-week where the **no-wire** roster had an empty slot at
position P, what the paired **holes-only** roster scored at that same
slot that same week (`analysis/wire_hole_value.py`, 30 sims × 6
seasons):

| slot | hole-weeks | pts gained | median | p90 |
|---|---|---|---|---|
| **QB** | 90 | **+14.3** | 13.0 | 25.0 |
| **K** | 251 | **+8.4** | 9.0 | 15.0 |
| WR | 223 | +6.4 | 5.0 | 14.0 |
| TE | 297 | +4.8 | 3.0 | 11.0 |
| RB | 52 | +4.1 | 2.0 | 14.0 |

**Patching a QB hole is worth ~14 points in that single week** — more
than the entire season-long edge of most draft strategies in this
project, for one Wednesday click. This is the number the old
"the wire is worth ~1 point per claim" framing buried: claims are not
fungible. A hole claim is worth 4 to 14 points; a bench-churn claim is
worth zero.

The asymmetry is pure roster structure. You roster one QB and one K,
so their holes are total (you score 0 there). You roster five to eight
RB/WR, so a "hole" at RB is rare (52 events vs 251 at K) and shallow —
the replacement is competing with your own bench, not with a zero.

## What a claim actually looks like

The players we really added — how long we kept them, what they scored
while we held them:

| pos | adds | wks held | pts/wk held | median | p90 | cut within 2 wks |
|---|---|---|---|---|---|---|
| **QB** | 146 | 5.9 | **11.4** | 11.7 | 17.3 | **12%** |
| RB | 1,421 | 3.8 | 4.7 | 4.2 | 8.7 | **40%** |
| WR | 1,255 | 4.6 | 4.7 | 4.2 | 8.5 | 30% |
| TE | 545 | 4.1 | 4.4 | 3.7 | 8.0 | 36% |

**A waiver QB is a real player** — 11.4 points a week against a
top-12 starter's 19.1 (mean and median over 72 QB-seasons), held
nearly six weeks, cut quickly only 12% of the time. **Everything else is a body**: ~4.5 points a week, cut inside two
weeks a third of the time. That is fine when the alternative is a
zero, and pointless when the alternative is your own bench player.

## Practical rules

1. **Never field an empty slot.** That is the whole edge, it is worth
   ~30 points a season, and it is free. If your QB is on bye and you
   have no QB2, go get one — that single move is worth more than any
   ADP-discipline edge in this project.
2. **Check the wire when a bye or injury creates a hole, not weekly
   out of anxiety.** Shopping the bench every few weeks and keeping
   what works (`naive_wk6`) matches the best policy tested. Weekly
   churn measurably loses points.
3. **Don't chase RB upgrades off the wire.** RB is the one slot where
   claiming is negative in every specification — you are dropping
   drafted depth for 4.7 points a week.
4. **Do not plan a draft around the wire, but don't ignore it either.**
   ~2.6% of a season is real; it just isn't a substitute for depth
   you drafted. See [finding 34](34-roster-shape.md) for what shape
   that depth should take.

## Methodology

`analysis/wire_worth.py`: 60 sims × 6 seasons × 3 drafters, each season
run twice (with and without the wire) off the same seed — 2,160 paired
seasons. `NoClaims` policy (`simfl/waivers.py`) blocks all claims
including hole-fixing; everything else is identical.

`analysis/wire_decompose.py`: same construction, one drafter
(`pick_value`), four waiver policies × 360 seasons = 1,440 seasons,
all paired on the `nowire` arm per (year, sim).

Every mechanism live: emergent FA pool, adds *and* drops, season-ending
injuries clearing roster spots (`done_for_season`), `keep_value`
cutting underperformers, real Friday injury-report status driving
start/sit ([finding 21](21-injury-model.md)), rivals claiming for their
own reasons at per-seat rates calibrated to real ESPN transaction
counts, reverse-standings priority rebuilt weekly (a winning hero sits
at queue slot ~8.4 of 12).

Claims are chosen on **leak-free projection** (`fa_proj` — production
so far, no pedigree, no future). Nothing in this finding uses a
hindsight label.

Reproduce:
```bash
venv/bin/python analysis/wire_worth.py       # the headline pairing
venv/bin/python analysis/wire_decompose.py   # holes vs churn vs naive
venv/bin/python analysis/wire_hole_value.py  # value of one patched hole
```

`wire_hole_value.py` needs `run_season(..., track_weekly=True)`, which
records per-week slot points and per-week empty slots. It is off by
default and changes no other result.

## Caveats

- **This prices the wire on top of a full 15-man roster.** It is not
  the value of the wire to a team with an empty bench.
- `NoClaims` also forbids hole-fixing, so the no-wire arm fields an
  empty slot when a singleton position is out. That is deliberate —
  it is exactly the quantity being priced — but it means the number
  answers "what if I never touched the wire all year", not "what if I
  were slightly lazier about it". The `holes_only` vs `full_policy`
  contrast is the better guide to marginal effort.
- The no-wire arm cannot shed a player who is out for the year, so it
  carries dead weight; that inflates the gap somewhat.
- Six seasons of underlying football; the paired seasons resample it,
  they do not add new football.
- The rival bots claim by points-chasing at calibrated frequency. A
  sharper room would strip the wire faster and shrink this.
- K gains are bye-week patching, not kicker skill — see
  [finding 04](04-kickers-are-noise.md).
