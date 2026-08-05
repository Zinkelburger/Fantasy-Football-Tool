# 32 — Full-league sims: drafting by the model loses to ADP; no narrow version of it helps either

**Confidence: High** (300 leagues × 6 seasons per arm, paired seeds,
sanity control lands exactly at baseline; monotone dose-response;
13 arms tested including every narrow variant we could think of)

## Question

Finding 25 (corrected) says the ADP board out-ranks the player model on
every position. Rank correlation is a list metric, not a league
outcome — so: in full simulated seasons, what does drafting from the
model actually cost or earn? And since the model is *independent* of
ADP, does blending it into the board (user's suggestion) buy anything?

## Setup

- Env v5 sim (12-team ESPN std, 15 rounds, calibrated family room).
- Hero vs 11 `Family` bots (noisy-ADP, league-calibrated), hero
  rotated through all 12 seats, 300 sims/season, seasons 2020–2025,
  identical seed sequence per arm (common random numbers).
- Identical in-season play for everyone: leak-free EWMA lineups,
  same waiver rules. The ONLY difference between arms is the draft
  list.
- **Model lists are leakage-free**: `analysis/export_model_history.py`
  refits the player model per season with that (Y−1 → Y) pair held
  out — the hero drafts 2023 from a list printable in August 2023.
  Exported after the finding-25 correction landed, so `yrs` and
  `tm_rook_pick` are inside.
- **ModelBoard hero** (`simfl/strategies.py`): within each position,
  the ADP board's veteran slots re-ordered by model prediction;
  rookies/K and cross-position timing stay ADP; candidate window is
  the model's own board order. **ModelBlend** heroes: veteran slot =
  (1−w)·ADP rank + w·model slot, w = 0.25 / 0.5. **BPA** = w=0
  control, same competence layer. **Family hero** = 12th family bot,
  harness sanity check.

## Result (pooled 2020–2025, 1800 leagues per arm)

| hero | all-play | PF/season | playoffs | title | avg finish |
|---|---|---|---|---|---|
| BPA (pure ADP) | **.595** | **1189** | 74.5% | **20.7%** | **4.37** |
| blend w=0.25 | .594 | 1187 | 74.9% | 18.7% | 4.41 |
| blend w=0.50 | .580 | 1175 | 71.2% | 14.8% | 4.75 |
| model (w=1) | .522 | 1126 | 57.3% | 10.8% | 5.98 |
| family control | .500 | 1102 | 49.3% | 9.3% | 6.49 |

Baselines: all-play .500, playoffs 50%, title 8.33%. Title se ≈ 0.9pp
at n=1800.

- **Sanity holds**: the family control is .500 / 9.3% — a 12th family
  bot is average in a family room.
- **Pure model is costly**: −.073 all-play vs BPA, title odds roughly
  halved (10.8% vs 20.7%), lost all 6 seasons; 2020 was below the
  random-room baseline (.446).
- **Monotone dose-response**: every increment of model weight hurts
  (w=0 .595 → w=.25 .594 → w=.5 .580 → w=1 .522). The 25% tilt is a
  statistical tie with BPA on all-play/PF/playoffs (Δall-play −.001);
  its −2.0pp title gap is ~2se — no evidence of gain anywhere, so the
  honest read is "no benefit, possible small cost."
- Finding 25's +0.006±0.005 rank-correlation hint for board+model
  stacking does **not** cash into league outcomes.
- Side-product: **BPA vs the family room is the real edge** — pure
  ADP discipline (no reaching, sane roster fills, K last) is worth
  2.5× baseline title odds against calibrated family behavior. The
  draft tool's job is delivering that discipline, not out-thinking
  the market.

## Round 2: the narrow versions (user challenge — "ADP isn't even good, is there really no way to tilt it?")

A whole-board tilt is a blunt instrument. Round 1 only rules out
*uniform* interventions. These arms each apply the model (or our
findings) in one narrow place, everything else BPA, same seeds:

| arm | what it changes | all-play | title |
|---|---|---|---|
| BPA (control) | — | .595 | 20.7% |
| `blend_notop` | tilt outside top 12 at each position | .598 | 20.0% |
| `blend_te` | tilt TE only (ADP's worst position) | .596 | 19.4% |
| `rookie_flier` | last 12 picks = model-picked unpriced rookies | .596 | 20.3% |
| `rookie_flier25` | last 25 picks likewise | .596 | 19.2% |
| `rookie_board` | re-rank the ~20 PRICED rookies by rookie model | .595 | 20.1% |
| `blend_late` | tilt only past position rank 30 | .592 | 19.7% |
| `marks` | our tested buy/fade marks as ±15% rank nudges | .592 | 19.7% |
| `blend_qbte` | tilt QB+TE only | .591 | 19.8% |
| `marks_hard` | same marks at ±30% | .578 | 19.3% |

**Every narrow arm is a tie with BPA; none beats it.** The only arms
that clearly lose are the aggressive ones, same monotone pattern as
round 1.

`blend_notop` is the only arm whose pooled means all sit on the good
side of BPA, so it got a proper paired test
(`analysis/paired_arm_test.py`, differencing sim-for-sim on the shared
seed sequence — arms face the same room, seat and injury draws, which
removes most of the variance the pooled means carry):

| metric | blend_notop | bpa | paired diff | verdict |
|---|---|---|---|---|
| all-play | .5981 | .5962 | +0.0019 ± 0.0022 (t=+0.85) | within noise |
| points-for | 1191.2 | 1189.6 | +1.6 ± 1.9 (t=+0.85) | within noise |
| title rate | .2000 | .2033 | −0.0033 ± 0.0122 (t=−0.27) | within noise |

A season's worth of model tilt outside the top 12 is worth about 1.6
points-for, i.e. nothing. (`HeroStats` now records per-sim
`title_flags` so title rate can be paired too.)

The `marks` result deserves emphasis: it is a **friendly-test
negative**. The hot/cold threshold and the WR/TE-only restriction were
both chosen on 2017-25 data, which includes these six target seasons,
so that arm drafted with mild hindsight about which rule works — and
still did not beat taking the board in order. Findings 16/17 remain
true about *player scoring*; what fails is the leap from "true" to
"therefore move him on your draft board," because ADP already moved
him.

## Why: where our disagreements with ADP actually carry information

`analysis/disagreement_check.py` — for each leakage-free model board,
d = (ADP position rank − model position rank), resid = actual PPG −
E[PPG | ADP rank] (log-linear, the pick_value shape). If our
disagreements are informative, corr(d, resid) > 0. n=932
player-seasons, 2020-25:

| slice | corr(d, resid) |
|---|---|
| all | +0.060 ± 0.033 |
| top 12 at position | **−0.022 ± 0.059** (nothing) |
| position rank 13-30 | +0.069 ± 0.055 |
| position rank > 30 | **+0.164 ± 0.057** (2.9se) |
| WR, rank > 30 | **+0.189 ± 0.076** |
| QB / RB / WR / TE pooled | −.01 / +.09 / +.06 / +.10 |

Biggest disagreements (|d| ≥ 15): the 45 players we liked MORE beat
their price by +0.80 PPG; the 36 we liked LESS missed by −0.65 PPG.
Late-board effect is positive in 5 of 6 seasons (2021 the exception,
−0.13; 2022 +0.40 and 2025 +0.34 carry it).

So the information is real but lives **only past the point where the
market stops paying attention** — which is exactly why round 1's
uniform tilt lost: it spent model error across the top of the board,
where we are worthless, to buy a small edge at the bottom.

And yet `blend_late` (tilt only past rank 30) did NOT convert that
into wins. Two reasons, both mundane: by rank 30+ the per-player
stakes are small (these are bench and flex bodies whose season swings
a point or two a game), and in a 12x15 draft only a handful of picks
land in that zone for any one team. A real edge on cheap players is
still a small edge.

## A structural limit worth recording

The "coverage" claim for the rookie model (finding 31 — we price all
80 drafted rookies, ADP prices ~20) **cannot be tested in a draft at
all**: the ADP board is 179 deep and a 12x15 draft is 180 picks, so
the unpriced tail is never reached. `rookie_fill`, the arm originally
written for it, was provably identical to BPA and was replaced by
`rookie_flier` (promote unpriced rookies INTO the last rounds), which
is a tie. Whatever coverage is worth lives on the **waiver wire**, not
draft day — that is where an in-season test would have to happen.

Caveat on the rookie arms: drafted rookies who never recorded a stat
are absent from the sim pool (~8 of ~78 a year), so rookie-reaching
arms cannot draw the very worst outcomes and are mildly flattered.
They still only tied.

## Per-year (all-play, hero vs BPA same year)

| year | BPA | w=.25 | w=.5 | model |
|---|---|---|---|---|
| 2020 | .598 | .575 | .555 | .446 |
| 2021 | .618 | .612 | .575 | .527 |
| 2022 | .609 | .625 | .631 | .567 |
| 2023 | .586 | .569 | .538 | .525 |
| 2024 | .566 | .569 | .577 | .541 |
| 2025 | .596 | .612 | .606 | .529 |

2022/2025 tilts beat BPA; 2020/2023 they lose bigger. Year-level noise,
no exploitable pattern.

## Product rule

Draft off the ADP board. The model stays what the corrected finding 25
made it: a click-note (his numbers, his position room, the findings
that name him) and at most a tiebreak between similarly priced players
— never a re-ranking, not even a partial one, not even at TE, not even
late, not even for rookies. The board page and cheat sheet should sell
the *discipline* edge, which is real and measured.

## Open door (the one thing round 2 did NOT close)

The late-board disagreement signal is real (+0.164, 2.9se, 5 of 6
seasons) and simply has no room to pay off in a draft. Two places it
could still matter, both untested:

1. **Waiver wire.** Season-long, the wire is where deep players
   actually change hands, and there is no ADP there at all — the
   market's information advantage evaporates. `analysis/
   disagreement_check.py`'s late-board slice is exactly the population
   the wire draws from. A `WaiverPolicy` that ranks free agents by the
   model instead of by recent points is the natural next arm.
2. **2026 out-of-sample.** The rank-30 cut was chosen on these same
   seasons. Whatever it is worth, this year is the first honest test.

## Repro

```
venv/bin/python analysis/export_model_history.py
venv/bin/python analysis/export_rookie_history.py
venv/bin/python analysis/export_marks_history.py
venv/bin/python analysis/disagreement_check.py
venv/bin/python -m simfl compare --years 2020-2025 \
    --heroes bpa,model,blend25,blend50,family -n 300 --seed 0 --by-year
venv/bin/python -m simfl compare --years 2020-2025 \
    --heroes blend_notop,blend_late,blend_te,blend_qbte,marks,marks_hard,\
rookie_board,rookie_flier,rookie_flier25 -n 300 --seed 0
venv/bin/python analysis/paired_arm_test.py blend_notop
```

Site rewrite: `site/posts/32-draft-sim.md`.
