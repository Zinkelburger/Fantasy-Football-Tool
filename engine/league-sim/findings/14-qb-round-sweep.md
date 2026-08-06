# 14 — QB timing sweep: rounds 4–6 is the sweet spot

**Confidence: Medium-High** for the shape. The levels vs the family
field are inflated by an unrelated discipline gap — do not quote them
as QB effects.

Eight identical draft strategies that differ in one thing: the
earliest round they'd take a QB. Rounds 4–6 wins. Anywhere from 2 to
8 is nearly as good. Waiting past round 10 is where it gets expensive
— about 4 points of all-play, against ~1 point for reaching in rounds
2–3. Annoyingly for the presentation, the family's real-life habit —
first QB in round 5 — is exactly right.

## The number

n=120 sims × 6 seasons per cell (720 each), engine v3 (calibrated
family + news-aware projections), fresh family baseline in the same
run (`scripts/qb_sweep.py`, `results_qb/`):

| Strategy | All-play | ±95% | Playoffs | Titles |
|---|---|---|---|---|
| family (null check) | .496 | .008 | 50.1% | 7.9% |
| QB round 2 | .578 | .008 | 71.0% | 14.3% |
| QB round 3 | .579 | .008 | 72.2% | 14.2% |
| QB round 4 | .582 | .008 | 72.1% | 14.9% |
| **QB round 5** | **.588** | .008 | **76.5%** | 13.3% |
| **QB round 6** | **.587** | .008 | 74.2% | **16.8%** |
| QB round 8 | .575 | .008 | 71.0% | 15.4% |
| QB round 10 | .564 | .008 | 68.2% | 16.2% |
| QB round 12 | .549 | .008 | 63.5% | 12.5% |

## Two separate effects

1. **Every cell sits at .55–.59 because of discipline, not QBs.** All
   qb_rN bots inherit the base disciplined drafter, and the family
   model was recalibrated to the league's real drafts — much noisier
   than the earlier stylized field (reach sd ~15+ picks). Against that
   field, plain discipline is worth ~+6-8 points of all-play whatever
   the QB plan. That's a statement about the league.
2. **The QB-timing effect is the spread within the sweep,** because
   the cells share every non-QB behavior. Peak .588 at r5, .549 at
   r12, .578 at r2. Spread ≈ 4 points of all-play with ±0.8 CIs —
   real, modest, single-peaked.

## Why rounds 4–6 wins

The QB value curve is steep at the top, but the last starter still
scores ~16 PPG (findings 06/07). Rounds 2–3 spend a premium pick that
RB/WR value needs (finding 01). Rounds 10+ eat the bottom of the
startable barrel, and finding 06 showed the wire can't rescue you.
Rounds 4–6 is where a top-6-to-10 QB drifts to at this league's
actual QB timing — median QB1 round 5, eight round-1 QBs in 2021's
panic year notwithstanding.

## Methodology

`QBAtRound` strategies (`simfl/strategies.py`): QB banned before the
target round, strong pull (×0.40) for the best QB once open, all else
identical to base. Same engine, same seeds, family baseline rerun in
the same batch.

```bash
venv/bin/python scripts/qb_sweep.py
```

## Caveats

- Title-rate ordering (r6 16.8% > r5 13.3%) is noise (SE ~1.3%).
  Trust all-play and playoff ordering; treat titles as directional.
- "Round 5" means the strategy *opens its QB window* there. The
  actual purchase lands rounds 5–7 depending on the room.
- The .55+ levels vs the calibrated family field measure the league's
  drafting noise — finding 03's story amplified under v3 calibration.
  Worth its own slide. Not a QB finding.
