# 03 — CORRECTED: draft discipline IS the edge — ~90% of it

**Confidence: High** (simulation-verified, n=1,440 seasons; numbers are
environment v3. *Filename is legacy: this finding originally claimed
the opposite, an artifact of the v1 opponent model — the correction is
the finding.*)

## TL;DR

A bot that drafts the consensus board *perfectly* (BPA by ADP, sane
need-filling, zero opinions) scores **.591 all-play against the
family — a +9.1-point edge** — while the cleverest strategies tested
top out at .599. Translation: simply following a list without human
noise captures roughly **90% of all available edge**; positional
allocation (RB early, QB timing, TE punting) is competing for the
last point. The league's biggest inefficiency is not what anyone
drafts — it's the 17–30-pick spread with which they draft it.

## The data

| Strategy | All-play | Titles |
|---|---|---|
| Best tested (pick_value / robust_rb) | .599 / .598 | 17.0% / 20.3% |
| BPA (ADP order, zero opinions) | **.591** | 15.3% |
| Family (calibrated real noise + biases) | .500 | 7.6% |

Decomposition of the total edge: **discipline +9.1 points, allocation
+0.8 more.** Allocation still matters where it counts most — Robust
RB converts the same all-play into 20.3% titles vs BPA's 15.3% — but
it is a refinement on discipline, not a substitute.

BPA per-year: .586, .602, .612, .583, .554, .607 — never below .55
against this field.

## Why the original finding said the opposite

v1 of this file reported BPA at .491 — *no better than the family*.
That number was real but the opponent model wasn't: v1 family bots
drafted with 1× the FFC market stdev (≈2–6 picks of noise) plus a
0.88 RB-reach bias. The league's actual six drafts show a reach
spread of **17–34 picks per round-bucket and no RB reach at all**
(`analysis/draft_tendencies.py`, `analysis/calibrate.py`). Against
opponents that sharp, list-following gains nothing — but those
opponents don't exist in this league. Calibrating the bots to the
measured noise flipped the conclusion. The v1 narrative ("the
family's RB habit accidentally corrects the market") also dies with
it: the family has no RB habit (mean RB reach is +5.1, slightly
*late* vs market).

## Why this matters for the presentation

The league narrative "we'd win if we just followed the rankings" is
**correct** — that's the finding. Any credible list, followed with
discipline, is worth ~9 points of all-play and roughly double the
baseline title rate. Which list, and which clever deviations from it,
are worth about one more point combined. Slide version: *the sheet
beats your gut by nine points; the best strategy ever tested beats
the sheet by one.*

## Methodology

`BPA` in `simfl/strategies.py`: highest-ADP available player each
pick, with the same universal legality/need layer every bot has.
Family noise model calibrated to the league's six real ESPN drafts:
perceived pick ~ N(ADP · pos_delay, max(3×market_sd, 30)), rookie
bias 0.95 — realized reach spread matches the real drafts in 6 of 8
round-buckets (`analysis/calibrate.py`). Environment v3 throughout;
v1 numbers preserved in `results_v1_precalibration/`. Reproduce:
`venv/bin/python -m simfl.grid --heroes bpa -n 240`.

## Caveats

- The +9.1 is a measure of the *family's* noise, not of the list's
  quality: the edge exists because opponents are noisy, and it shrinks
  exactly as fast as the room sharpens (v1 is the limiting case).
- BPA uses FFC/FantasyPros standard-format ADP. The family drafts off
  ESPN's default list; list-vs-list quality is unmeasured here, but
  BPA landing within 0.8 points of the best strategy bounds how much
  any list choice can matter.
- 2024 (.554) was BPA's worst year against this field — even
  discipline has variance; present the range, not just the mean.
