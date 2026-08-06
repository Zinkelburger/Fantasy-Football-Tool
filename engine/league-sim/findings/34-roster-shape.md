# 34 — Roster shape: mostly a retracted finding

**Confidence: Low** for the shape comparisons — the design was broken.
**High** for the one thing that survives: turning the wire off costs 31
points, which independently reproduces
[finding 22](22-waiver-wire-reality.md).

> **Retracted 2026-08-05, same day it was written.** This tried to
> price roster shape by forcing positional templates on the drafter.
> The design has two faults, and together they make the shape
> comparisons uninterpretable. The live version of this question is
> [finding 36](36-draft-order.md), which constrains *when* you may
> draft a position rather than *how many* you must end up with.

## What went wrong

**1. Templates make the drafter reach.** Forced to fill a quota, it
passes on better players. Measured at the draft table, no season
simulated:

| template | drafted talent vs free | realized QB-RB-WR-TE-K |
|---|---|---|
| free | — | 2.0-6.5-3.8-1.6-1.0 |
| 1-9-3-1-1 | **−11.1** | 1.0-9.0-3.0-1.0-1.0 |
| 1-8-4-1-1 | −10.4 | 1.0-8.0-4.0-1.0-1.0 |
| 1-6-6-1-1 | −10.3 | 1.0-6.0-6.0-1.0-1.0 |
| 1-5-7-1-1 | −10.2 | 1.0-5.0-7.0-1.0-1.0 |
| 2-6-5-1-1 | **−0.4** | 2.0-6.0-5.0-1.0-1.0 |

(talent = sum of the roster's leak-free preseason ppg expectation)

**2. The RB/WR templates weren't testing RB/WR.** Every one of them
pinned QB=1 and TE=1. The unconstrained drafter naturally takes 2.0 QBs
and 1.6 TEs. So those arms were mostly measuring "no backup QB or TE",
not the RB/WR split — which is exactly why the one template that
allowed a QB2 (`2-6-5-1-1`) was the only one that cost nothing.

The talent metric has its own flaw, for that matter: QBs score more per
game than RBs, so any roster with a QB2 scores higher on it regardless
of quality. Use it to detect reaching, not to rank rosters.

## What survives

Turn the wire off and the free drafter falls **1197 → 1166**. That −31
is the wire's value, arrived at from a completely different direction
than [finding 22](22-waiver-wire-reality.md)'s +30/+31/+33. Two
independent measurements, same answer.

Templates also hurt more without the wire (−2.4 to −21.5, against −0.2
to −8.6 with it). Directionally that says drafted depth and the wire
substitute for each other, which is the right mechanism. But the
per-shape numbers inherit the reach confound, so treat the ordering as
unusable.

## Where the question actually got answered

[Finding 36](36-draft-order.md), with forced A/B tests that never cap
positional counts:

- late RB vs late WR: **+1.6 ± 2.3 points**. Nothing.
- QB2: **+0.4% ± 2.9% titles**. Nothing.
- TE2: slightly worse than nothing.
- QB timing: 27-point spread. The only lever.

## Methodology

`analysis/roster_shape.py` (templates, kept for the record) and
`analysis/shape_reach_cost.py` (the draft-table talent measurement that
exposed the problem).

```bash
venv/bin/python analysis/shape_reach_cost.py
venv/bin/python analysis/roster_shape.py --formats std --nowire --nsims 40
```

## Lesson

If an experiment forces a roster to look a certain way, check what it
had to give up to get there before reading the outcome. A constraint
that costs 10 points of talent will show up as the shape being bad.
