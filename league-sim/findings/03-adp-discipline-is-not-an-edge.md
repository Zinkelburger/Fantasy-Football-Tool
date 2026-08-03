# 03 — CORRECTED: draft discipline IS the edge — ~90% of it

**Confidence: High** (simulation-verified; headline numbers are
environment v5, n=432 seat-rotated leagues per strategy, seed-paired.
*Filename is legacy: this finding originally claimed the opposite, an
artifact of the v1 opponent model — the correction is the finding.*)

## TL;DR

A bot that drafts the consensus board *perfectly* (BPA by ADP, sane
need-filling, zero opinions) scores **.598 all-play against the family
— a +9.7-point edge** — while the best strategies tested reach .610.
Translation: simply following a list without human noise captures
roughly **90% of the available edge**; positional allocation (RB
early, QB timing, TE punting) competes for the last point. The
league's biggest inefficiency is not what anyone drafts — it's the
17–30-pick spread with which they draft it.

## The data (environment v5)

| Strategy | All-play | Playoffs | Titles |
|---|---|---|---|
| robust_rb (RB-RB-RB) | **.610** | 78% | 21% |
| RB×3 then wait-cost math (rb3_pv) | .611 | 79% | 24% |
| pick_value (wait-cost) | .602 | 76% | 19% |
| BPA (ADP order, zero opinions) | **.598** | 75% | 20% |
| Family (calibrated real noise + biases) | .501 | 52% | 8% |

Decomposition: **discipline +9.7 points, allocation +1.2 more.** The
top three are statistical ties (robust_rb − pick_value = +0.010 ±
0.012 paired; rb3_pv − robust_rb = −0.000 ± 0.008), and pick_value's
whole gap is its 18%-of-early-picks QB habit, which is fairly priced
(banning QB before r6 moves it to .608, still within noise —
finding 06 again).

## The sharp-room test: whose edge survives good opponents?

v5 adds a theoretical room of 11 BPA villains (no draft noise,
hero-grade waivers; `hero_experiment(..., villain="bpa")`,
`analysis/sharp_room.py`). Paired against the in-room BPA control:

| Hero in sharp room | All-play | vs control |
|---|---|---|
| pick_value | .521 | **+0.023 ± 0.010** |
| rb3_pv | .516 | +0.019 ± 0.013 |
| robust_rb | .503 | +0.005 ± 0.010 |
| pv_late_qb | .490 | −0.008 ± 0.010 |
| family bot | .425 | **−0.073 ± 0.013** |

Three lessons. (1) The family's pick noise costs them 7.3 all-play
points against a disciplined room — the +9.7 above is that same number
seen from the other side. (2) robust_rb's edge is a *harvest of this
room's habits* (the family takes RBs ~5 picks late); against sharp
opponents the dogma adds nothing. (3) The wait-cost math is the only
strategy that keeps a real edge when the room sharpens — and its
early-QB option, useless against the family (who let QBs slip ~7
picks), becomes genuinely valuable against opponents who don't.

## Why the original finding said the opposite

v1 of this file reported BPA at .491 — *no better than the family*.
That number was real but the opponent model wasn't: v1 family bots
drafted with 1× the FFC market stdev (≈2–6 picks of noise) plus a
0.88 RB-reach bias. The league's actual six drafts show a reach
spread of **17–34 picks per round-bucket and no RB reach at all**
(`analysis/draft_tendencies.py`, `analysis/calibrate.py`). Against
opponents that sharp, list-following gains nothing — but those
opponents don't exist in this league. Calibrating the bots to the
measured noise flipped the conclusion, and the sharp-room table above
now shows both regimes in one experiment.

## Why this matters for the presentation

The league narrative "we'd win if we just followed the rankings" is
**correct** — that's the finding. Any credible list, followed with
discipline, is worth ~10 points of all-play and roughly 2.5× the
baseline title rate. Which list, and which clever deviations, are
worth about one more point combined. Slide version: *the sheet beats
your gut by ten points; the best strategy ever tested beats the sheet
by one.*

## Methodology

`BPA` in `simfl/strategies.py`: highest-ADP available player each
pick, with the same universal legality/need layer every bot has.
Family noise model calibrated to the league's six real ESPN drafts
(realized reach spread matches 6 of 8 round-buckets,
`analysis/calibrate.py`). Environment v5: seasons 2020–25, n=72 per
year per hero, seat-rotated, common random numbers across heroes
(seed=3). Family-room table: `analysis/hybrid_strats.py` +
`analysis/sharp_room.py`. v1 numbers preserved in
`results_v1_precalibration/`.

## Caveats

- The +9.7 measures the *family's* noise, not the list's quality; the
  sharp-room column is the honest bound on how fast it shrinks as the
  room improves.
- BPA uses FFC/FantasyPros standard ADP; the family drafts off ESPN's
  list. List-vs-list quality is unmeasured, but BPA landing within
  ~1 point of the best strategy bounds how much any list can matter.
- Title percentages at n=432 carry ±2% noise; rb3_pv's 24% vs
  robust_rb's 21% is not a real separation.
