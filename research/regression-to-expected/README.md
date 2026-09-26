# Does scoring above or below expected points persist?

September 24, 2026. A from-scratch redo of findings 16, 17 and 39, written
without reusing their scripts or numbers. Code: `analyze.py`; every number
below is in `results.json`.

**Question.** A player's *gap* is actual fantasy points minus the points his
usage was worth (expected points, xFP). When a player runs above or below
his usage, what happens next? There are three possibilities:

- **Regress:** the gap vanishes and he scores at his usage.
- **Persist:** the gap is real skill and continues.
- **"Due":** he over-corrects the other way.

## Answer

1. **Nobody is "due."** At no position, sample size or model is a past
   shortfall followed by scoring *above* expectation. Every coefficient for
   the next game's gap is zero or positive. A player who underperforms his
   usage is not owed the points back.
2. **Within a season, the gap mostly regresses, and more so early on.** After
   2–3 games only about **0–7% of a WR's gap** shows up again in his next
   game's efficiency. A single game is almost pure noise: the per-game
   standard deviation of the gap is about 4 points, against 0.4–0.8 points
   of real player-to-player difference.
3. **It is not all luck, and it is not zero.** Over a full season the gap
   carries real skill:
   - For a player's efficiency within a season, the share worth keeping is
     about **10–25% after 8 games** and **17–37% after 17 games**, depending
     on position and model.
   - **Last season's gap predicts this season.** Early in a season it is worth
     about **a third** of its size (WR 0.33–0.35), several times more than a
     2-game sample from the current season.
4. **Beating your usage earns more usage.** Much of the carryover arrives as
   *more opportunity* in the following games, not as continued efficiency.
   For example, a WR with 8+ games whose points ran above his usage gets
   about 0.34 extra expected points next game for each point of gap.
5. **Usage is the better single predictor, but ignoring points entirely
   leaves accuracy on the table.** A usage-only average beats a points-only
   average at every position, by 0.13–0.17 points MAE (intervals clear of
   zero). A **70–80% usage / 20–30% points blend** beats both. Production
   uses 100% usage.

## Data and method

- **Two independent expected-points models, standard scoring:**
  - **nflverse `ff_opportunity`**, 2017–2025, 52k player-games. It is
    play-level and not fitted by us. Standard points = PPR total minus
    receptions, which matches box-score standard within 0.5 points in 98%
    of 2024 games. The mean gap is −0.27 to 0.00 every season, so the model
    is close to calibrated.
  - **Ours** (`engine/weekly/ep_model.py`), 2021–2025, refit
    **leave-one-season-out**, so no game is scored by coefficients fitted on
    its own season. It is floored at zero as in production.
- **Regular season only.** Weeks 1–17 through 2020, 1–18 after.
- **Intervals:** 95% player-cluster bootstrap with 400 resamples. A player's
  games or seasons are resampled together, because repeated observations of
  one player are not independent.
- **Within-season tests:** the next game's actual points are regressed on
  season-to-date expected points and season-to-date gap. The next game is
  then split into its **usage** (xFP) and its **efficiency** (gap) to see
  where the carryover goes.
- **Reliability:** the per-game intraclass correlation ρ of the gap. After n
  games, the share of the observed average gap worth keeping is
  nρ/(1+(n−1)ρ).

## Within a season, game to game

Coefficient on the season-to-date gap (95% CI), WR, nflverse:

| Games already played | Next game points | ...via next game usage | ...via next game efficiency |
|---|---|---|---|
| 1 | +0.06 [−0.01, +0.12] | +0.05 | +0.01 [−0.05, +0.06] |
| 2–3 | +0.12 [+0.05, +0.19] | +0.14 | −0.02 [−0.07, +0.03] |
| 4–7 | +0.21 [+0.12, +0.29] | +0.16 | +0.05 [−0.01, +0.11] |
| 8–17 | +0.48 [+0.35, +0.59] | +0.34 | +0.14 [+0.04, +0.23] |

The other positions and our own model show the same shape, as listed in
`results.json`. With our model the efficiency coefficient is larger, e.g. WR
8–17 games +0.28, because a simpler usage model leaves more real skill in the
gap. The efficiency coefficient is never significantly negative anywhere.

Per-game reliability ρ of the gap, and the share worth keeping:

| | nflverse ρ | kept after 8 games | kept after 17 | ours ρ | kept after 8 | kept after 17 |
|---|---|---|---|---|---|---|
| QB | .007 | 5% | 10% | .046 | 28% | 45% |
| RB | .020 | 14% | 26% | .032 | 21% | 36% |
| WR | .012 | 9% | 17% | .034 | 22% | 37% |
| TE | .017 | 12% | 23% | .034 | 22% | 37% |

## Early season: this season vs last

This covers players 1–3 games into a season with 8+ games the previous
season. The table shows the weight on each gap when predicting the next
game:

| | nflverse, this season | nflverse, last season | ours, this season | ours, last season |
|---|---|---|---|---|
| QB | +0.17 | +0.35 | +0.12 | +0.66 |
| RB | +0.13 | +0.36 | +0.20 | +0.23 |
| WR | +0.05 | +0.35 | +0.10 | +0.33 |
| TE | −0.01 | +0.25 | +0.04 | +0.23 |

A player's track record matters more than his first few games.

## Season to season (redo of findings 16 and 17), nflverse

Players with 8+ games in consecutive seasons at the same position.
**Persistence** is the slope of next season's per-game gap on this
season's gap:

| | pairs | total gap | TD part | non-TD (yardage) part |
|---|---|---|---|---|
| QB | 207 | +0.24 | +0.17 | +0.17 |
| RB | 480 | +0.22 | +0.10 (ns) | +0.22 |
| WR | 755 | +0.11 | +0.04 (ns) | +0.16 |
| TE | 374 | +0.29 | +0.13 | +0.33 |

When predicting next season's points per game from expected points plus
both parts of the gap, the yardage part carries a weight of **0.6–0.97**,
significant at every position. It carries far more than the gap-to-gap
slope suggests, because efficient players get more usage the next year. The
TD part carries 0.15–0.58, significant only for RBs.

**Finding 16** said TD luck regresses hard at every position: −1.6 PPG,
8/8 seasons, high confidence. The redo, with TD gap holding PPG fixed, per
TD point per game:

| | estimate | 95% CI | negative seasons |
|---|---|---|---|
| WR | −0.69 | [−0.94, −0.48] | 8/8 |
| TE | −0.48 | [−0.77, −0.15] | 6/8 |
| RB | −0.08 | [−0.50, +0.28] | 5/8 |
| QB | −0.01 | [−0.37, +0.32] | 3/8 |

**Verdict: holds for WRs and TEs, fails for RBs and QBs.** Pooling positions
overstated it. RB touchdowns above expectation partly persist, likely
because of goal-line roles that play-level xTD does not fully see.

**Finding 17** said WR targets predict next year beyond PPG, while
efficiency does not. The redo, next-season PPG per 1 SD of the stat, holding
PPG fixed:

| | estimate | 95% CI | verdict |
|---|---|---|---|
| WR targets/game | +0.84 | [+0.57, +1.16] | **holds** |
| WR catch rate over expected | −0.12 | [−0.33, +0.09] | holds (no signal) |
| WR YAC/reception | +0.04 | [−0.13, +0.23] | holds (no signal) |
| TE targets/game | +0.50 | [+0.11, +0.92] | old finding said ns; **real** |
| TE YAC/reception | +0.40 | [+0.13, +0.68] | new: real for TEs |
| RB carries/game | +0.65 | [+0.01, +1.31] | borderline |
| RB targets/game | −0.01 | [−0.46, +0.43] | no signal |

## Next-week prediction (redo of finding 39)

This compares a season-to-date EWMA (α = 0.35) of expected points (usage),
of actual points, and blends of the two. The table shows next-game MAE in
standard scoring:

| | model | usage only | points only | usage − points (CI) | best blend (share of points) |
|---|---|---|---|---|---|
| QB | nflverse | 6.32 | 6.47 | −0.15 [−0.22, −0.07] | 6.26 (30%) |
| RB | nflverse | 4.34 | 4.49 | −0.15 [−0.20, −0.11] | 4.33 (20%) |
| WR | nflverse | 3.92 | 4.10 | −0.17 [−0.21, −0.13] | 3.91 (20%) |
| TE | nflverse | 2.93 | 3.10 | −0.17 [−0.21, −0.13] | 2.93 (10%) |
| QB | ours | 6.39 | 6.52 | −0.13 [−0.24, −0.01] | 6.29 (40%) |
| RB | ours | 4.42 | 4.56 | −0.14 [−0.20, −0.07] | 4.40 (30%) |
| WR | ours | 3.85 | 4.01 | −0.16 [−0.21, −0.11] | 3.83 (30%) |
| TE | ours | 2.87 | 3.03 | −0.16 [−0.20, −0.12] | 2.87 (20%) |

**Verdict:** the core claim holds, since usage beats points everywhere. The
blend gain is small (0.00–0.10 MAE) but consistent, largest for QBs. Adding
a 20–30% points term to the production EWMA is a candidate change; it has
not been validated forward in time or adopted.

## Limits

- **Survivorship:** the next-game tests only include players who played the
  next game. A player benched for inefficiency is not counted.
- **What the gap contains:** skill, luck, and whatever each xFP model omits.
  A simpler model leaves more skill in the gap, which is why ours shows
  higher persistence than nflverse's.
- **Early seasons:** nflverse's xFP may have been trained on seasons that
  overlap 2017–2020. The mean gap is near zero throughout, and the results
  have the same shape on 2021–2025.
- **Leave-one-season-out:** fits for our model use future seasons as well as
  past ones. That is fine for describing the gap, but it is not a strict
  forward test of a production change.
- **Regressions:** linear and pooled across players. Individual skill
  (deep threats, goal-line backs) varies around these averages.
