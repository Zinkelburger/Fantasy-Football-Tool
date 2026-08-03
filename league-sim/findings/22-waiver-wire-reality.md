# 22 — The waiver wire is worth about 10 points a season, and most of it is QB and K

**Confidence: Medium-High.** Clean paired counterfactual — identical
draft, field, schedule and seeds, the only difference being whether the
hero may claim. Three drafters agree on sign and rough size. Six
seasons of underlying football.

> **STALE (sim v4).** The v5 waiver audit found the hero's policy spent
> 25% of its claims on players already out for the year and fielded
> ~2.3 empty starting slots a season when its single hole claim got
> sniped — both understate the wire. Rerun `analysis/wire_worth.py`
> under v5 before citing numbers.

## TL;DR

Run the same team through the same season twice, once allowed to use
the waiver wire and once forbidden, and the wire is worth **+5 to +12
season points** — about **1% of a season, ~1 point of all-play**. Nearly
all of it comes from patching **QB and K**, the two slots where you
start one and roster one. It is **negative at RB**. And the players you
add reflect that: a waiver **QB scores 11.9 pts/wk while you hold him**,
a waiver RB/WR/TE scores **~4** and gets cut inside two weeks a third of
the time. The wire is roster maintenance, not a strategy.

## What the wire is worth

Paired: identical drafter, identical field, identical schedule, same
seeds. The only difference is permission to claim.

| drafter | with wire | no wire | gain | ±95% | all-play Δ | claims/yr |
|---|---|---|---|---|---|---|
| pick_value | 1176 | 1164 | **+12** | 4 | +0.013 | 10.3 |
| robust_rb | 1173 | 1168 | +5 | 5 | +0.005 | 10.3 |
| bpa | 1165 | 1158 | +7 | 5 | +0.008 | 10.5 |

Ten claims a season buy you roughly a **point and a bit each**. For
scale, the entire QB-timing sweep ([finding 14](14-qb-round-sweep.md))
spanned 4 points of all-play; the wire is worth about a quarter of that.

## Where the points land — and this is the whole mechanism

Season points by lineup slot, with-wire minus without:

| drafter | QB | RB | WR | TE | FLEX | K |
|---|---|---|---|---|---|---|
| pick_value | **+5** | −3 | +5 | −1 | +4 | +2 |
| robust_rb | **+7** | −6 | +2 | −2 | +1 | +4 |
| bpa | **+6** | −2 | −1 | −1 | +1 | +4 |

**QB and K gain in all three. RB and TE lose in all three.**

The reason is roster structure, not football. You start one QB and one
K and you roster one or two of each — so when yours is on bye or hurt,
you have an actual *hole*, and the wire fills it. At RB and WR you
roster five to eight bodies for five starting slots, so a hole
essentially never opens; claiming there just churns the back of your
bench, and sometimes churns off someone who would have been better.

This is the mechanism behind [finding 20](20-second-qb-te.md)'s null
from the other direction: a drafted QB2 and a waiver QB plug the *same
hole*, so buying one with a pick adds nothing.

## What a claim actually looks like

The players we really added — how long we kept them, what they scored
for us while we held them:

| pos | adds | wks held | pts/wk held | median | p90 | cut within 2 wks |
|---|---|---|---|---|---|---|
| **QB** | 106 | 5.8 | **11.9** | 11.7 | 18.0 | **10%** |
| WR | 971 | 4.9 | 4.2 | 3.7 | 8.5 | 28% |
| RB | 1,045 | 4.1 | 3.9 | 3.2 | 8.3 | **41%** |
| TE | 281 | 4.7 | 3.8 | 3.2 | 6.5 | 27% |

**A waiver QB is a real player** — 11.9 points a week against a
starter-tier 18.7, held nearly six weeks, cut quickly only 10% of the
time. You go to the wire for a quarterback rarely (106 adds vs 1,045 at
RB) and when you do, it works.

**Everything else is filler.** A waiver RB gives you 3.9 points in the
weeks you hold him and gets cut inside two weeks 41% of the time. That
is not a dart throw that hits; that is churning the bottom of a bench.

## Practical rules

1. **Don't plan a draft around the wire.** It is worth ~1% of a season.
   Depth you draft is not meaningfully replaceable by depth you claim.
2. **Do go to the wire for a QB or K hole.** That is where every point
   of the gain lives, and it is the one claim that reliably works.
3. **Late-round RB/WR "lottery tickets" off waivers are not tickets.**
   Median 3.2 pts/wk, cut 41% of the time. Consistent with
   [finding 19](19-bench-composition.md)'s null on bench composition.

## Methodology

`analysis/wire_worth.py`: 60 sims × 6 seasons × 3 drafters, each season
run twice (with and without the wire) off the same seed — 2,160 paired
seasons. `NoClaims` policy (`simfl/waivers.py`) blocks all claims
including hole-fixing; everything else is identical.

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

Reproduce: `venv/bin/python analysis/wire_worth.py`

## Caveats

- **This prices churn on top of a full 15-man roster**, which is why it
  is small. It is *not* the value of the wire to a team with an empty
  bench, and it does not say a drafted bench is worthless — it says
  marginal churn of an already-full bench is.
- `NoClaims` also forbids hole-fixing, so the no-wire arm fields an
  empty slot when a singleton position is out. That makes this an
  *upper* bound on the wire's value, and it is still only ~10 points.
- The no-wire arm cannot shed a player who is out for the year, so it
  carries dead weight. Same direction: upper bound.
- Six seasons of underlying football; 2,160 paired seasons resample it.
- The rival bots claim by points-chasing at calibrated frequency. A
  sharper room would strip the wire faster and shrink this further.
- K gains partly reflect bye-week patching, not kicker skill — see
  [finding 04](04-kickers-are-noise.md).
