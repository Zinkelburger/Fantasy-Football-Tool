# 23 — Early RB vs WR: the premium is real, already priced, and still worth taking first

**Confidence: High** (8 seasons of data with cluster-bootstrap CIs;
causal swap test in sim v5, n=432 paired leagues per cell)

## TL;DR

Why take a running back before a receiver? We fit the value curves —
how many points the market's #k-ranked RB or WR actually returns
over a season. Both decline smoothly as you move down the board, but
RB value falls **45% faster** than WR value:

```
RB: E[pts, wks 1-14] = 191 − 31·ln k      (b 95% CI [−36, −27])
WR: E[pts, wks 1-14] = 156 − 21·ln k      (b 95% CI [−27, −16])
```

Four principles fall out, each separately supported:

1. **Same rank, RB wins — until it doesn't.** RB_k − WR_k = +35 pts at
   k=1 [16, 60], +18 at k=6, +11 at k=12 [3, 20], and is
   indistinguishable from zero past k≈18. The crossover rank is 38
   (90% CI [20, 109]); P(crossover ≤ 18) = 3%.
2. **The market already prices the level.** At the same *overall* ADP
   (year-FE interaction model), the RB premium is +7 ± 24 pts at pick
   6 — statistically nothing — hits zero around pick 31–46, and turns
   *negative* by pick 100 (−5.0 [−10.0, +0.6]). You cannot beat this
   room by "buying the cheap position"; there isn't one.
3. **The actionable edge is the slope, not the level.** RB value
   decays 45% faster per ln-rank (−31 vs −21). Even at fair per-pick
   prices, order of operations matters: take the fast-depreciating
   asset first, because WR value is still on the shelf three rounds
   later and RB value is not. The sim confirms this causally: an
   otherwise-identical disciplined drafter forced to RB instead of WR
   at its round-1 pick gains **+0.017 ± 0.009 all-play** (round 2:
   +0.015 ± 0.009; round 3: +0.007 ± 0.009 — noise by round 3, where
   the forced choice is ~RB10 vs ~WR6).
4. **The floor flips at k≈12.** Kernel p25 curves cross there: beyond
   the top-12 RBs, the bad-RB outcome is worse than the bad-WR outcome
   (ADP 25–36 band: p25 = 64 vs 78). RB is the high-variance position
   everywhere (residual sd 54 vs 38 pts) — bad for safety, fine for
   titles in a 12-team H2H format.

## It is a talent premium, not an availability myth

Decomposing the same-ADP model (year FE) into per-game scoring and
games played:

| at pick | RB ppg premium | RB games effect |
|---|---|---|
| 12 | +1.01 ppg | −0.66 games |
| 48 | +0.23 ppg | −0.63 games |

Same-ADP RBs miss only ~0.65 more games than WRs — the "RBs get hurt"
tax is real but small and roughly flat in ADP. What decays is the
per-game talent premium (+1.0 ppg at pick 12 → +0.2 by pick 48), so
early RBs carry the injury tax easily and late RBs don't. **Early RB
is a good buy; late RB is a bad buy.** Bust *anatomy* differs too:
RB busts are injury busts; WR busts are performance busts (rounds 4–6:
28% of WRs play 10+ games and still finish below WR30, vs 19% of RBs).
The wire also restocks WR better: 26% of top-24 weekly WR scorers went
undrafted vs 18% at RB — a dead WR pick is easier to replace.

## What it buys in bands (raw means, 2020–25, busts included)

| ADP | RB pts (p25) | WR pts (p25) | RB missed | WR missed |
|---|---|---|---|---|
| 1–12 | 150 (120) | 126 (101) | 2.1 | 2.0 |
| 13–24 | 129 (98) | 113 (95) | 2.1 | 1.8 |
| 25–36 | 102 (64) | 97 (78) | 3.1 | 2.1 |
| 37–72 | 91 (56) | 92 (63) | 2.5 | 2.0 |

## Why this doesn't crown RB-RB-RB as "the answer"

Forced-RB is worth real points against *this* room partly because the
family drafts RBs ~5 picks late (finding 03). In a sharp room (11
ADP-disciplined villains, `analysis/sharp_room.py`), robust_rb's edge
over BPA evaporates (+0.005 ± 0.010) while the wait-cost drafter keeps
+0.023 ± 0.010 — the slope logic generalizes, the dogma doesn't.
(Hindsight-optimal drafts split the difference: 58% open RB, but only
38% of their first-three picks are RB — finding 24.) In
the family room the two are a statistical tie (robust_rb − pick_value
= +0.010 ± 0.012; RB×3-then-value = robust_rb −0.000 ± 0.008), because
pick_value's math already spends 57% of its first-three picks on RB.

## Methodology

`analysis/rb_wr_curves.py` (figure:
`figures/rb_wr_curves.png`). Player-seasons 2018–25 with FFC standard
ADP, k ≤ 40, y = weeks 1–14 points under league scoring. Mean curves
by OLS on ln k; all CIs from cluster bootstrap resampling *seasons*
(years are the correlated unit; player-level resampling would
understate error). Functional form checked by leave-one-year-out MAE
against a Nadaraya-Watson kernel and an isotonic (PAV) fit — all
within 0.4 pts, so the parametric curve is adequate (no band
artifacts). Same-ADP premium from y ~ ln(ADP) × position with year
fixed effects (within transformation). Quantiles are kernel-weighted
with bootstrap bands. Causal check: `analysis/rb_wr_swap.py` — same
drafter, same seeds, pick forced RB vs WR in exactly one round.
Bands/bust table: `analysis/rb_wr_bands.py`. R² of rank on outcome is
0.18–0.20 — rank explains a fifth of the season; these are curves
through a cloud, which is why the CIs are the finding.

## Caveats

- STD scoring only. PPR adds ~2–3 catches/game of WR value and is
  known to compress or flip the same-rank premium; do not export.
- ADP is FFC standard-format consensus, not the family's board; the
  family's RB-lateness makes the effective in-room premium slightly
  larger than the market numbers here.
- 2018 and 2025 have the steepest RB slopes (−40, −44); the premium
  breathes year to year (per-year slopes printed by the script).
- Crossover CI is wide [20, 109]: treat "RB through the top-18, agnostic
  after rank ~24" as the safe read, not a sharp threshold at 38.
