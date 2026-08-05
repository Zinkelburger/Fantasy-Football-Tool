# 34 — Roster shape barely matters, because the wire covers the holes it would have covered

**Confidence: Medium-High.** Paired sweep — identical field, schedule
and seeds, the only difference being a hard cap on how many of each
position the hero may draft. Eight shapes × 360 seasons in standard,
four shapes in half-PPR and PPR, plus a wire-off replication (eight
shapes × 240). The null is tight (±6 points) and the wire-off arm
reproduces finding 22's wire value to the point (−31) as a side
effect, which is a real cross-check. It is still a null within *one*
room and *one* set of six injury histories.

## TL;DR

Fixing the drafted roster shape — "1 QB, 3 WR, 1 TE, 1 K, rest RB",
"balanced 6/6", "two QBs", anything — is worth **nothing measurable**
against simply letting a value drafter take the board as it falls.
Every template tested lands within **9 points a season** of the
unconstrained drafter, most within 6, against ±6 confidence intervals.

The RB-heavy end is very mildly the better end of the range, which is
directionally consistent with RB scarcity, but no single shape
separates from the pack.

The mechanism matters more than the null: **a second QB is worth +0.1
points** even though an empty QB slot costs 14.3 points when it
happens ([finding 22](22-waiver-wire-reality.md)). Those two facts are
not in tension — the *wire* is already patching that hole for free.
Roster shape and the waiver wire are substitutes, and the wire is the
cheaper one because it costs a click instead of a draft pick.

Turn the wire off and the null collapses: every template drops to
−2.4 … −21.5, and **the RB-hoarding shape goes from best to worst**.
Lopsided rosters are wire-dependent rosters.

## Standard scoring — the sweep

`pick_value` drafter with a hard positional template; wire live for
everyone. Paired on `pv_free` (the same drafter, unconstrained).

| shape | QB-RB-WR-TE-K | PF | vs free | ±95% | all-play Δ |
|---|---|---|---|---|---|
| `pv_free` | (free) | 1197 | — | — | — |
| **`rb9_wr3`** | **1-9-3-1-1** | 1197 | **−0.2** | 6.3 | −0.002 |
| `qb2` | 2-6-5-1-1 | 1197 | **+0.1** | 4.6 | +0.001 |
| `rb8_wr4` | 1-8-4-1-1 | 1192 | −4.8 | 6.0 | −0.007 |
| `te2` | 1-6-5-2-1 | 1193 | −4.6 | 5.9 | −0.005 |
| `rb5_wr7` | 1-5-7-1-1 | 1192 | −5.7 | 5.9 | −0.009 |
| `rb7_wr5` | 1-7-5-1-1 | 1191 | −6.2 | 5.9 | −0.009 |
| `rb6_wr6` | 1-6-6-1-1 | 1189 | −8.6 | 5.8 | −0.014 |

**`rb9_wr3` — max RB depth, three WRs — ties the free drafter exactly
(−0.2 ± 6.3).** It is the best of the eight fixed templates. So the
"WRs are durable, RBs are scarce, hoard RBs" intuition is not wrong;
it just isn't worth anything, because a value drafter already ends up
RB-tilted in this room without being told to.

The mild gradient across the RB/WR sweep (−0.2, −4.8, −6.2, −8.6,
−5.7 going from 9 RBs down to 5) leans RB-heavy, but it is not
monotonic and every step sits inside a confidence interval. Read it as
"RB-heavy is the safe end", not as a curve.

## Half-PPR and full PPR

The draft board stays standard-market ADP (there is no PPR ADP in the
data), so these rows say how the *same market* prices a shape when
receptions score — not what a PPR-native room would do.

| shape | half Δ | ±95% | ppr Δ | ±95% |
|---|---|---|---|---|
| `pv_free` | — | — | — | — |
| `rb8_wr4` | −1.1 | 6.1 | −1.1 | 6.3 |
| `rb6_wr6` | −4.8 | 6.0 | −0.6 | 6.3 |
| `rb5_wr7` | −1.1 | 6.1 | **+0.5** | 6.6 |

The null holds in every format. The one directional hint: the WR-heavy
shape is the worst of the three in standard (−5.7), neutral in half
(−1.1), and the *best* of the three in full PPR (+0.5). That is the
expected direction and the expected size — reception scoring is worth
real points to WRs — but at ±6 it is a whisper, not a finding. It is
consistent with [finding 02](02-zero-rb-is-a-trap.md): WR-heavy plans
are PPR imports that cost you in a standard league.

## Why the null is the interesting part

An empty starting slot is expensive — 14.3 points at QB, 8.4 at K
([finding 22](22-waiver-wire-reality.md)). A full roster runs into one
about seven times a season. So why doesn't drafting insurance pay?

Because **the insurance is already free.** The wire patches those
holes for a waiver claim, and a claim costs nothing but attention. A
QB2 costs a draft pick that could have been a startable RB or WR. The
two plug the same hole; only one of them charges you for it.

This is the same result [finding 20](20-second-qb-te.md) found from
the other direction (a 2nd QB/TE is a free choice — all contrasts
null) and [finding 19](19-bench-composition.md) found from a third
(bench composition is a tiebreak, not an edge). Three independent
tests, one mechanism.

**The corollary, now measured.** Take the wire away and shape starts
to matter — a lot. Same templates, same seeds, hero forbidden from
claiming (40 sims × 6 seasons, standard):

| shape | vs free (wire ON) | vs free (wire OFF) | cost of losing the wire |
|---|---|---|---|
| `qb2` | +0.1 | **−2.4** | **−2.5** |
| `te2` | −4.6 | **−7.8** | **−3.2** |
| `rb7_wr5` | −6.2 | −14.8 | −8.6 |
| `rb6_wr6` | −8.6 | −17.7 | −9.1 |
| `rb8_wr4` | −4.8 | −15.8 | −11.0 |
| `rb5_wr7` | −5.7 | −20.1 | −14.4 |
| **`rb9_wr3`** | **−0.2** | **−21.5** | **−21.3** |

(±95% ≈ 6–8 in both columns. The two sweeps are each internally
paired against their own `pv_free`, but the *cross-sweep* difference
in the last column is not itself a paired statistic — read it as a
pattern, not a point estimate.)

Two things confirm the mechanism:

1. **Every template gets worse without the wire**, and the free
   drafter's own scoring falls 1197 → 1166 — a drop of 31 points,
   which is exactly the wire's measured value in
   [finding 22](22-waiver-wire-reality.md). Independent arithmetic,
   same answer.
2. **`qb2` and `te2` are the shapes that barely notice.** They lose
   2.5 and 3.2 points when the wire disappears, against 9–21 for
   every RB/WR template. That is what carrying your own insurance
   looks like: a QB2 is worth nothing while you can stream a QB, and
   becomes the most robust build the moment you cannot.

**And the RB-hoarding shape inverts completely.** `rb9_wr3` is the
*best* fixed template with the wire (−0.2) and the *worst* without it
(−21.5). Three WRs cannot cover WR byes and injuries on their own —
the shape only survives because the wire is quietly patching it every
few weeks. The same is true in mirror image of `rb5_wr7` (−20.1).
**Both extremes are wire-dependent builds.** If you are going to draft
lopsided, you are committing to working the waiver wire, whether or
not you realize it.

## Practical rules

1. **Don't draft to a template.** Take the value. Any shape you'd
   plausibly want is within a rounding error of free-drafting — *as
   long as you use the wire*.
2. **A lopsided roster is a promise to work the waiver wire.**
   `rb9_wr3` costs nothing with the wire and 21.5 points without it.
   If you know you're the manager who checks waivers twice a week,
   draft however you like. If you know you aren't, stay balanced —
   the flexible shapes lose the least when nobody is patching.
3. **Don't spend a pick on a QB2 or TE2 as insurance** in a league
   where you'll work the wire: it is worth +0.1. But note it is the
   *most robust* shape when the wire is off the table (−2.4), so it
   is the right call for a set-and-forget team, or in a room sharp
   enough that the QB wire is stripped bare.
4. **In PPR, stop hoarding RBs** — the WR-heavy shape flips from worst
   to best across the formats, even if the effect is small.

## Methodology

`analysis/roster_shape.py`. Templates are enforced as hard positional
caps on top of the `pick_value` drafter: within the template it still
takes the best value at the best time, it just cannot exceed the cap.
All templates sum to 15 (8 starters + 7 bench). 60 sims × 6 seasons
per shape, paired per (year, sim) on the unconstrained arm. The
wire-off arm (`--nowire`, which swaps the hero's policy to `NoClaims`
and changes nothing else) runs 40 sims × 6 seasons per shape, paired
on its *own* `pv_free` — so the two sweeps are each internally valid,
but differences *between* them are unpaired and should be read as a
pattern rather than a measured effect size.

Half/PPR arms rescore every player-week (`ScoringConfig(reception=…)`)
and rebuild the projection table, but keep the standard-market ADP
board — see the caveat above.

`POS_CAPS["RB"]` is raised from 8 to 9 so the `rb9_wr3` template is
legal.

Reproduce:
```bash
venv/bin/python analysis/roster_shape.py --formats std,half,ppr
venv/bin/python analysis/roster_shape.py --formats std --nowire --nsims 40
```

## Caveats

- **Injuries are the real historical record, not resampled draws.** A
  player who really missed eight games misses eight games in every
  sim. Variation across runs comes from draft and schedule, not from
  re-rolling injury luck. This sweep therefore measures depth against
  *six seasons of the injury luck that happened* — it cannot tell you
  what depth is worth in the tail where your three best RBs all tear
  an ACL. That tail is exactly where roster shape would pay, and this
  design is blind to it.
- One room (the calibrated family bots). A sharper room strips the
  wire faster, which would raise the value of drafted depth.
- Templates are caps, not scripts: `rb9_wr3` reaches 9 RBs only if the
  board offers them at value, so the realized shapes are close to but
  not exactly the template.
- Standard-market ADP in all three formats (see Methodology).
- The FLEX is RB/WR only in this league, which structurally favors
  RB/WR depth over TE/QB depth. A superflex or TE-premium league would
  not inherit this null.
