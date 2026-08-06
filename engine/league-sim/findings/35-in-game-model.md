# 35 — Live win probability: the clock is the whole model, and everyone's number is too confident

**Confidence: High** for the scoring-curve and correlation measurements
(5 seasons, 259,009 player-plays, 242,177 player-game-checkpoints).
**Medium** for the calibration result — it rests on synthetic matchups
built from real weeks, not on real league rosters.

## TL;DR

- Fantasy points accrue **almost exactly linearly with the game clock**.
  Quarter shares are 21.6 / 28.6 / 22.6 / 27.1 percent, and the entire
  deviation from flat is the two two-minute drills.
- So `remaining = 0.92 x projection x fraction of game left` is a
  genuinely good live model. Fitting anything on top of it —
  game script, live production, Vegas totals — buys **1–2%**.
- Same-team receivers are **uncorrelated** (r = 0.00). The only real
  in-game link is QB to his own pass-catchers (r = 0.28).
- Every published win-probability number, ours included, is
  **overconfident at the extremes**: matchups called 85% win about 78%
  of the time. Three separate fixes failed to remove it. A flat 0.87
  shrink toward 50% does.

## Question

We want live in-game matchup tracking. Two things have to be true for
that to be worth building: you have to be able to predict remaining
points from partway through a game, and the win probability you print
has to be honest. So: how do fantasy points actually accumulate across
a game, what predicts the rest of them, and is the resulting
probability calibrated?

## Setup

- nflverse play-by-play, 2021–2025 regular season, fantasy points
  attributed per play to passer / rusher / receiver / fumbler at
  half-PPR decimal scoring (`analysis/ingame_model.py`).
- Attribution spot-checked against known games: J.Allen's 2024 week 14
  scores 51.9 and J.Chase's week 10 scores 49.9 — both exact.
- Panel of 242,177 (player, game, checkpoint) rows, checkpoints every
  300 game-seconds.
- The stand-in for "the projection a manager had" is a **leak-free
  trailing EWMA** (alpha 0.35) of that player's prior games this
  season, requiring 3 prior games. It is deliberately not a season
  average — that would be hindsight.
- Fit on 2021–2024, scored out-of-sample on 2025.

## Result 1 — the clock curve

Share of all fantasy points scored in each 5-minute block:

| block | share | | block | share |
|---|---|---|---|---|
| Q1 15–10 | 6.80% | | Q3 15–10 | 7.21% |
| Q1 10–5 | 7.49% | | Q3 10–5 | 7.43% |
| Q1 5–0 | 7.21% | | Q3 5–0 | 7.81% |
| Q2 15–10 | 8.12% | | Q4 15–10 | 8.51% |
| Q2 10–5 | 7.57% | | Q4 10–5 | 8.19% |
| **Q2 5–0** | **12.74%** | | **Q4 5–0** | **10.93%** |

An even split would be 8.33%. Ten of the twelve blocks sit between 6.8
and 8.5 percent. The two exceptions are the two-minute drills.

By quarter: **Q1 21.6%, Q2 28.6%, Q3 22.6%, Q4 27.1%.**

The curves are the same for every position — QB, RB, WR and TE are
within 1.5 percentage points of each other at every checkpoint. One
universal clock curve serves all four.

**This kills the "you can't predict until the fourth quarter" intuition.**
Q4 holds 27% of the scoring, barely above a flat 25%. Half the points
are gone by halftime, and the model is usable from kickoff.

## Result 2 — nothing beats the clock

Out-of-sample RMSE on 2025, predicting a player's remaining points:

| moment | pos | clock only | + fitted rate | + game script | + live production | + Vegas total |
|---|---|---|---|---|---|---|
| kickoff | QB | 8.661 | 8.245 | 8.245 | 8.246 | **8.144** |
| | RB | 7.165 | 6.956 | 6.956 | 6.961 | **6.939** |
| | WR | 5.961 | 5.754 | 5.754 | 5.753 | **5.752** |
| | TE | 5.260 | 5.073 | 5.073 | 5.073 | **5.062** |
| halftime | QB | 6.084 | 5.917 | 5.879 | 5.878 | **5.856** |
| | RB | 4.822 | 4.739 | 4.732 | **4.626** | **4.617** |
| | WR | 4.010 | 3.910 | 3.905 | 3.905 | **3.905** |
| | TE | 3.767 | 3.692 | 3.684 | 3.677 | **3.672** |
| start of Q4 | QB | 4.536 | 4.461 | 4.445 | 4.445 | **4.443** |
| | RB | 3.412 | 3.363 | 3.361 | **3.316** | **3.315** |

Fitting the rate coefficient is worth ~4%. Everything after it is
worth ~1% combined. The one exception with any life in it is **live
production for running backs** (halftime 4.739 → 4.626, 2.4%) — an RB
who is getting carries is revealing his workload, which the pregame
number didn't know.

The fitted rate is **below 1.0 at every position** — QB 0.966, RB
0.914, WR 0.916, TE 0.921 — so a player's rest-of-game is slightly
*worse* than a flat clock split of his projection. Blowout benchings,
in-game injuries and garbage time all push the same way.

## Result 3 — the correlation structure is nearly empty

Residual correlation between players in the same game, at kickoff:

| pair | r | n |
|---|---|---|
| QB ↔ own WR | **+0.277** | 7,650 |
| QB ↔ own TE | **+0.219** | 3,752 |
| QB ↔ own RB | +0.054 | 4,832 |
| WR ↔ own WR | **+0.002** | 21,034 |
| RB ↔ own RB | +0.003 | 6,802 |
| WR ↔ own TE | −0.007 | 13,235 |
| QB ↔ opposing QB | +0.123 | 2,160 |
| WR ↔ opposing WR | +0.035 | 27,034 |

Two teammates catching passes from the same quarterback are
**uncorrelated**. The shared lift from a good offensive day and the
competition for the same targets cancel almost perfectly.

That rules out the obvious implementation. A shared team factor would
force WR↔WR to equal QB↔WR, and it doesn't. The structure the data
implies is causal: a quarterback's day is *built out of* his receivers'
days. Draw the pass-catchers independently, then build the QB from
them. Two correlation terms, not a covariance matrix.

## Result 4 — the honest part: it's overconfident, and the obvious fixes don't work

Building 4,000 synthetic 9-player matchups per checkpoint out of real
2025 weeks and simulating each 2,000 times:

| simulation | Brier (halftime) | mean calibration error |
|---|---|---|
| normal draw, constant sigma | 0.1330 | 3.5% |
| zero-inflated skewed marginals | 0.1333 | — |
| + QB-stack correlation | 0.1406 | — |
| + sigma scaled to projection | 0.1412 | 3.2% |

**All four land in the same place.** Three plausible fixes, each
motivated by a real measured feature of the data, and none of them
moves the needle:

1. **Zero-inflation doesn't survive aggregation.** Individually the
   marginals are badly non-normal — a TE scores nothing in the second
   half 33% of the time, skew runs +0.76 to +2.15, kurtosis up to 9.9.
   But a lineup is nine of them added together, and the central limit
   theorem eats the shape. Fixing the marginals changed the Brier score
   in the fourth decimal.
2. **Correlation is real but too small to matter.** Only the QB link
   is non-zero, and a lineup holds one quarterback.
3. **Heteroskedasticity is real** — RB residual sd runs 3.96 at a
   1.7-point projection and 8.08 at 15.6 — and modelling it improved
   calibration error from 3.5% to 3.2%. Real, and nearly worthless.

What survives is a clean, monotone bias in one direction:

| predicted | actual | gap |
|---|---|---|
| 3.1% | 6.8% | +3.7 |
| 14.8% | 19.1% | +4.3 |
| 44.9% | 49.5% | +4.6 |
| 65.0% | 63.7% | −1.4 |
| 74.9% | 68.2% | −6.6 |
| 85.1% | 81.2% | −3.9 |
| 96.6% | 93.0% | −3.6 |

The middle of the range is close to honest; the tails are pushed out.
Because the bias is monotone, the fix is a one-parameter shrink:

    p_reported = 0.5 + 0.87 x (p_simulated − 0.5)

The 0.87 is the mean of the per-decile ratios above. **That single
constant is worth more than all three structural fixes combined**,
which is the least satisfying and most useful sentence in this finding.

## What to build

```
remaining_i   = decay[pos] x projection_i x (seconds_left / 3600)
sigma_i       = sqrt(c0 + c1*pred_i + c2*pred_i^2)   evaluated at the
                KICKOFF projection, then scaled down the measured
                sigma-by-clock table for that position
draw          = normal; pass-catchers independent of each other, the QB
                built out of his own pass-catchers (0.277 WR / 0.219 TE
                / 0.054 RB) plus 0.123 on a factor shared with the
                opposing QB
win prob      = P(my total > their total) over 10k draws, then shrunk 0.87
```

Parameters exported to `data/market/ingame_params.json` by
`analysis/ingame_model.py`. It is a few hundred lines of arithmetic and
runs in the browser in well under a second.

### Three ways the first implementation got this wrong

Worth recording, because each one was a plausible reading of the
paragraph above and each one moved the printed number.

1. **Scaling sigma by the clock twice.** `sigma_var_fn` is fit at
   `sec_left == 3600` only — it maps a full game's projection to a full
   game's spread. Feeding it the already-clock-scaled mean *and then*
   multiplying by `sqrt(fraction left)` made a halftime matchup about
   17% too narrow, and the start of Q4 about 40% too narrow. The clock
   scaling belongs to the measured `sigma[pos][sec]` table, not to a
   square root: for a running back at halftime the table says 0.665
   where `sqrt(0.5)` says 0.707.
2. **Putting the receivers on a shared team factor.** It is the obvious
   way to write the draw, and result 3 above is the reason it's wrong —
   it forces WR↔WR to equal QB↔WR, and WR↔WR is 0.00. Loading the *QB*
   with weight r on each of his own pass-catchers' independent shocks
   reproduces every measured pair exactly (verified by simulation:
   0.265 / 0.210 / −0.002 / 0.118 against measured 0.277 / 0.219 /
   0.002 / 0.123).
3. **Giving unscorable players a stand-in projection.** A starter on a
   bye had no projection and no game on the scoreboard, and a fallback
   of "a typical week at his position" plus "assume the game hasn't
   kicked off" handed him about nine points that could never arrive.
   This is the caveat at the bottom of this page, met in the least
   useful way possible. The rule that works: no projection means no
   points, and say so on the screen.

### K and D/ST

The four positions above are the four this study covers, and the live
page starts nine players. `analysis/kdst_sigma.py` fills the other two
rather than leaving the browser on an invented flat sigma of 6:

| | decay | sigma at kickoff | how |
|---|---|---|---|
| K | 0.960 | 4.99 | play-by-play, same method as above (n=21,554) |
| D/ST | 0.799 | 5.86 | full-game fit on weekly D/ST points (n=1,790) |

D/ST **borrows its clock shape** from the offensive positions, and that
is an assumption rather than a measurement: a defense's biggest scoring
component is the points-allowed tier, which is only knowable when the
game ends, so "remaining D/ST points at halftime" isn't well defined the
way "remaining rushing points" is. The borrowing is recorded in the
`_meta.kdst` block of the params file so it can't be mistaken for a fit.

That D/ST decay of 0.799 is much the lowest of the six, which is
finding 27's premise showing up from a different direction: defensive
scoring regresses hard, so a defense's recent form buys you less than
any other position's does.

The honest headline for the UI: **this number is good to about ±4
percentage points, and it is at its worst when it is most confident.**
Nobody else says that, and saying it is the differentiator.

## Caveats

- The projection stand-in is a trailing EWMA, not a real projection
  list. A better projection would lower every RMSE in result 2 and
  probably shrink the overconfidence, since some of that bias is the
  projection being worse in the tails than its own residual implies.
  **The ceiling here is set by projection quality, not by simulation
  machinery** — which is where the engineering effort should go.
- Matchups are synthetic: 18 players drawn at random from a week, so
  the lineups aren't position-legal and can be unrealistically shaped.
  The direction of every result is robust across all arms, but the
  absolute Brier scores would move on real rosters.
- Half-PPR decimal scoring throughout. The clock curve is a share and
  is close to format-invariant; the sigma table is not, and should be
  refit per format before it's used for a standard or full-PPR league.
  **The site currently ships the half-PPR table to every league,
  including standard ones**, which is a known and unmeasured
  approximation — the reception term is the only difference and it is
  the low-variance part of a receiver's day, so the error should be
  small and in the direction of slightly too wide for standard. Refit
  per format when there's a reason to.
- 2025 is a single out-of-sample season.
- In-game injuries are invisible here. A player who leaves in the first
  quarter looks like a catastrophic projection miss. Real live tracking
  should read the injury feed and zero those players out rather than
  asking the model to absorb them.
