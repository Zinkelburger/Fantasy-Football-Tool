# 20 — The 2nd QB / 2nd TE is a free choice; only the *timing* can hurt

**Confidence: High** for the null (paired design, 1,440 seasons per
arm, two independent base drafters agree). **Medium** for the
"take QB2 by round 10, not 12–14" ordering.

## TL;DR

Spending a late pick on a backup QB or TE — the dart throw you can
start on byes, in matchups, or if he breaks out — is worth
**nothing, and costs nothing**. Every forced-vs-banned contrast lands
inside ±0.35 points of all-play. The bench spot is yours to do what
you like with. Two things *are* real: forcing a QB2 late (rounds
12–14) is mildly bad, and delaying your TE1 to round 10 without a
streaming plan is genuinely expensive.

## The data

Engine v3, n=240 × 6 seasons = **1,440 seasons per arm**, hero rotating
all 12 seats. Arms are *paired on seed*: sim `i` of every arm faced the
same field from the same seat, so differences are within-pair and the
CIs are far tighter than unpaired all-play CIs at this n.

**On the base disciplined drafter** (control .589):

| Arm | All-play | vs ctrl | ±95% | Titles |
|---|---|---|---|---|
| control | .589 | — | — | 16.6% |
| never a 2nd TE | .587 | −0.14 | 0.28 | 16.2% |
| 2nd TE @ r10 | .586 | −0.26 | 0.34 | 15.4% |
| 2nd TE @ r12 | .590 | +0.10 | 0.30 | 16.2% |
| 2nd TE @ r14 | .588 | −0.11 | 0.32 | 15.8% |
| never a 2nd QB | .586 | −0.33 | 0.36 | 16.2% |
| **2nd QB @ r10** | .590 | +0.10 | 0.26 | **17.9%** |
| 2nd QB @ r12 | .585 | **−0.41** | 0.33 | 16.7% |
| 2nd QB @ r14 | .583 | **−0.60** | 0.35 | 16.7% |
| 2nd TE r12 + 2nd QB r13 | .582 | **−0.67** | 0.37 | 16.7% |
| punt TE to r10, single TE | .575 | **−1.42** | 0.46 | 15.2% |
| punt TE to r10, two darts | .577 | **−1.17** | 0.47 | 15.0% |

**On top of `pick_value`** (control .596) — same arms, same conclusion:

| Arm | All-play | vs ctrl | ±95% |
|---|---|---|---|
| control | .596 | — | — |
| never a 2nd TE | .596 | −0.03 | 0.27 |
| 2nd TE @ r12 | .595 | −0.13 | 0.31 |
| never a 2nd QB | .595 | −0.13 | 0.36 |
| 2nd QB @ r12 | .593 | −0.31 | 0.35 |
| both | .593 | −0.33 | 0.37 |

**The clean A/B — force the second vs ban it outright** (paired):

| Contrast | Δ all-play | ±95% | |
|---|---|---|---|
| TE2 @ r12 − no TE2 [base] | +0.24 | 0.31 | noise |
| QB2 @ r12 − no QB2 [base] | −0.07 | 0.35 | noise |
| TE2 @ r12 − no TE2 [pick_value] | −0.10 | 0.32 | noise |
| QB2 @ r12 − no QB2 [pick_value] | −0.18 | 0.34 | noise |
| 2nd dart − single TE (both punting to r10) | +0.25 | 0.33 | noise |
| punt TE1 to r10 − normal TE1 timing | **−1.42** | 0.46 | **real** |

Four independent tests of "backup or not," two base drafters, all
null. The only real number in the table is about *when you take your
first TE*, not whether you take a second.

## Why the dart throw doesn't pay

**Not because the backup never plays.** On frozen post-draft rosters
(no waivers), the backup is used more than folklore suggests:

| pair | weeks the backup started | season pts added | slot empty 1-deep | 2-deep |
|---|---|---|---|---|
| QB2 @ r12 | 27.5% | +23.4 | 17.1% | 4.6% |
| TE2 @ r12 | 32.4% | +10.7 | 20.9% | 4.7% |

A QB1 misses ~2.4 weeks to bye and injury and gets out-projected in
another ~1.4, so the QB2 starts ~3.9 weeks a season.

**It doesn't pay because the wire sells the same ticket.** Those
numbers are the value of a backup *when you cannot replace him* — an
upper bound. Switch waivers on and the "empty slot" weeks, which are
the bulk of the backup's job, get filled by a Tuesday claim instead of
a draft pick. The slot decomposition of full seasons shows the money
moving, then cancelling:

```
vs control (reg-season pts by slot)   QB     RB     WR     TE   FLEX   total
never a 2nd TE                      +0.3   +1.6   +1.0   -3.2   +2.0    +1.6
never a 2nd QB                      -6.4   +1.4   +2.2   -1.2   +0.5    -5.4
```

Banning the TE2 costs TE-slot points and gets them back at RB/WR/FLEX.
Banning the QB2 costs more than it recovers — but ~5 points on a
~1,150-point season is 0.5%, which is exactly why all-play can't see
it. This is [finding 19](19-bench-composition.md)'s mechanism again:
rounds 10–15 are worth so little that no reshuffling of them registers.

## A note on `pick_value`'s reasoning

`pick_value` drafts a QB2 in **100.0%** of drafts (median round 10) and
a TE2 in 69.2% (median round 12), measured over 240 drafts across the
six seasons; the base drafter is 97.1% / 65.4%. The QB2 habit looks
wrong and is *reasoned* wrong — but the error turns out not to cost
anything. At a round-10 pick it scores:

```
Tua Tagovailoa    QB  adp= 96.7   raw wait_cost= 24.0   <- takes this
Courtland Sutton  WR  adp= 96.6   raw wait_cost=  9.1
Damien Harris     RB  adp=100.5   raw wait_cost=  8.4
```

The fitted QB curve is ~2× as steep *in raw points* (slope −76.7 per
ln-pick vs −39.3 RB, −32.7 WR) purely because QBs score ~370 points a
season to an RB's ~160. So waiting always looks costlier at QB.

The wait-cost differential itself is sound, and genuinely
replacement-like: at a round-5 pick the best available kicker scores
`wait_cost = 0.0`, because no one will take a K before your next turn,
so the same kicker is still there — exactly the property the docstring
claims. The error is narrower than "it isn't VORP." It is that **for a
bench player the formula uses the wrong baseline**. It asks *how much
worse is the QB I could draft next round*, when the real question is
*how much better is this QB than the one I would stream the week I
actually need him*. The flat `BENCH_WEIGHT = 0.45`
(`simfl/strategies.py:270`) is the stand-in for that, and it is most
wrong at QB — where the streaming alternative is nearly as good and the
raw-points scale is double everyone else's.

The arms above say fixing it would buy ≈0.1–0.3 points of all-play,
i.e. nothing — so it is a wart, not a leak.

## Practical rules

1. **Backup QB/TE: do what you feel like.** It is not a strategy, and
   nobody at the table is gaining or losing a game over it.
2. **If you do take a QB2, take it around round 10** — not 12–14. By
   then the startable backups are gone and you are just burning a pick
   (−0.41 at r12, −0.60 at r14).
3. **Don't stack both** — TE2 r12 + QB2 r13 is the worst non-punt arm
   tested (−0.67).
4. **Don't punt your TE1 to round 10 unless you actually intend to
   stream** (−1.42). A second dart does not rescue it (+0.25, noise).

## Methodology

`SecondArm` mixin (`simfl/strategies.py`): forces the best available
player at a position at a fixed round, or bans the second one outright.
It overrides `pick`/`banned` and never touches `score`, so the identical
intervention sits on both base drafters. Both controls were rerun in
the same batch — no cross-engine-version comparisons (see
[finding 13](13-handcuffs-are-free-insurance.md)). Reproduce:

```bash
venv/bin/python scripts/stash_sweep.py       # results_stash/
venv/bin/python scripts/stash_report.py      # paired tables
venv/bin/python scripts/stash_mechanism.py   # slot + frozen-roster views
```

## Caveats

- The `never` arms are **draft-only bans**; the waiver policy may still
  add a QB/TE in-season. That is realistic but softens the contrast, so
  the true forced-vs-banned gap is if anything smaller than shown.
- `punt TE to r10, single TE` bans the TE2 *and* carries no streaming
  policy, so its −1.42 is not a clean test of TE1 timing and does **not**
  overturn [finding 05](05-never-pay-up-for-te.md), whose round-10+ advice
  is explicitly conditional on streaming the position afterward.
- Title-rate columns move ±1.5% on noise at this n (SE ≈ 1.0%); the
  17.9% for QB2 @ r10 is not a real title edge.
- The QB2 ordering (r10 > r12 > r14) is three cells with overlapping
  CIs; the *sign* is consistent but the shape is soft.
- All of this is against the calibrated family field. A room that
  hoards QBs early would make the last startable QB scarcer and could
  move the QB2 result.
