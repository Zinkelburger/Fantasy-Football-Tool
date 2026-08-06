# 25 — Our projection model does NOT beat the ADP board (corrected)

**Confidence: High** on the correction — apples-to-apples fix, and the
sign flips at every position. **Low** on the one thing that still wins:
the ADP+model stack is +0.006 ± 0.005, about 1σ.

> **Corrected 2026-08-05.** This finding used to claim the model
> out-ranked ADP at QB (+.09), WR (+.11) and TE (+.15). That was an
> artifact of scoring the two boards on **different sets of players**.
> Fixed in `analysis/player_model.py`; the corrected result is below.
> The old headline table is wrong and should not be quoted.

## Attribution

This line of work **starts from Kapania (2012), "Predicting Fantasy
Football Performance with Machine Learning Techniques," Stanford CS229
final project**
(cs229.stanford.edu/proj2012/Kapania-FantasyFootballAndMachineLearning.pdf)
— linear regression predicting next-season RB fantasy points from
prior-season yards/game and TDs/game (m=34 RBs, 2007–2010), plus a
k-means-then-regress variant that didn't improve it. His error (~40
pts/season, human expert ~34) and his stated limitations — no age, no
playing-time context, no injuries, one prior season, RBs only — are
the to-do list this model works through. The idea is his; the
extensions, data, and league-specific evaluation are ours.

## What the bug was

The evaluation loop scored the ADP benchmark only on test players who
actually had an FFC ADP, but scored the model and the naive baseline on
**every** player in the panel:

```python
m = ~te.adp_next.isna()
naive = spearman(te.ppg.values, te.y.values)              # all 2,232
model = spearman(pred, te.y.values)                        # all 2,232
adp   = spearman(-te.adp_next.values[m], te.y.values[m])   # only the 1,217
```

The 1,015 extra rows are a different population, and a much wider one:

| pos | with ADP (n, next-yr PPG) | no ADP (n, next-yr PPG) |
|---|---|---|
| QB | 184 · 16.1 | 159 · 8.0 |
| RB | 399 · 8.2 | 202 · 3.0 |
| WR | 477 · 7.4 | 426 · 2.9 |
| TE | 157 · 5.7 | 228 · 2.5 |

Rank-ordering a field that runs from stars to scrubs is far easier than
ordering only draftable players. The model was being credited for the
free call *"the undrafted guys finish worse"* — a call ADP was never
graded on. The naive baseline drops by almost exactly the same amount
under the fix (.603 → .480). It is the population, not the model.

## Corrected results

Leave-one-year-out, target years 2018–2025, **every board scored on the
same 1,217 ADP-covered player-seasons**. Spearman vs actual next-season
PPG.

| pos | naive | **ADP board** | model | ADP+½·model |
|---|---|---|---|---|
| QB | .369 | **.553** | .428 | .545 |
| RB | .546 | .694 | .640 | **.700** |
| WR | .541 | .643 | .614 | **.659** |
| TE | .465 | .502 | .492 | **.514** |
| pooled | .480 | .598 | .544 | **.604** |

Paired against ADP, one pair per position-year (n=32):

| board | mean diff | se | years won |
|---|---|---|---|
| naive − ADP | −0.118 | 0.023 | 5/32 |
| **model − ADP** | **−0.055** | 0.019 | 9/32 |
| **stack − ADP** | **+0.006** | 0.005 | 18/32 |

**The model loses to ADP at all four positions.** The only board that
edges the market on rank accuracy is the stack, and +0.006 ± 0.005 is
about one standard error. Suggestive, not established.

**Do not act on that stack number.** [Finding 32](32-draft-sim.md)
took the same boards into 9,000 simulated leagues and measured what
they are actually for: pure ADP won titles at 20.7%, a 25% model tilt
at 18.7%, a 50/50 blend at 14.8%, the pure model at 10.8%. Every step
toward the model made drafting worse. Rank correlation over the whole
ADP pool is not the objective — most of that pool is picked in rounds
you can rebuild off the wire, so ordering it better buys little, while
the stack's disagreements near the top cost real picks.

The practical rule, from finding 32 rather than from this table:
*draft off ADP in order; the model is context for choosing between
players the board already prices the same, and it moves nobody up or
down.*

The market wins for a substantive reason, not just a methodological
one. ADP is priced in August with camp reports, depth charts,
coordinator changes, holdouts, and the rookies competing for the same
touches. The model sees last season's box score, contracts, and age.

## What didn't rescue it

All on the matched population, LOYO, paired over 32 position-years:

| variant | pooled | vs ADP |
|---|---|---|
| retrain on the draftable population only | .550 | −0.048 ± 0.017 |
| ... plus ADP itself as an extra feature | .594 | −0.004 ± 0.013 |
| ADP + ¼·model | .605 | +0.007 ± 0.003 |
| ADP + ½·model | .610 | +0.012 ± 0.005 |

Giving the model ADP as a feature pulls it up to a tie and no further.
The model carries essentially no information the board lacks. (These
four rows predate the `yrs` and `tm_rook_pick` features; the shipped
model's stack number is the +0.006 in the table above.)

## The position room (depth chart) — real signal, no edge

Tested at the user's suggestion: for a WR, where does he sit in his own
team's WR room on the draft board, and how far back is the next one?
Features built from season-Y preseason ADP + season-Y roster: rank in
the room, whether he is the room's #1, ADP gap to the man ahead and the
man behind, how many teammates are drafted inside pick 200, and the
earliest pick his team spent at his position that year.

**It is a genuine predictor.** Standardized coefficients:

| feature | QB | RB | WR | TE |
|---|---|---|---|---|
| ADP gap back to the next man in his room | **+1.33** | **+0.57** | +0.29 | +0.30 |
| he is the room's #1 | −0.28 | **+0.94** | +0.36 | −0.01 |
| his rank in the room | **−0.69** | −0.36 | −0.16 | −0.43 |

Being the unambiguous lead back is worth +0.94σ at RB — an independent
confirmation of the bell-cow logic in finding 01. Adding these features
lifted the standalone model from .550 to .577 pooled and cut its
deficit to ADP from −0.048 to −0.021, almost all of it at QB
(.499 → .576).

**It adds nothing on top of ADP.** Stacked: +0.011 ± 0.006 with the
room features vs +0.012 ± 0.005 without; paired head-to-head
**−0.001 ± 0.005**. The reason is structural — five of the six features
are *computed from the ADP board*, so the model was re-deriving what
the board already knew. That also kills the "self-sufficiency"
argument for shipping them: features read off ADP do not survive the
loss of the ADP feed either.

**Decision: the room ordering is NOT a model feature.** It is carried
to the site's per-player note as plain context ("he's the Bengals WR1,
31 picks ahead of their WR2 (Tee Higgins)"), which is useful to a
drafter without pretending to be a disagreement with the market.

## Rookie draft capital — shipped, direction is clean, size unproven

`tm_rook_pick` (ln of the earliest pick a team spent at the player's
position that year, ln 300 = none) is the one depth-chart input **not**
read off ADP, so it is in the model. Its coefficient is positive at all
four positions — QB +0.25, RB +0.41, WR +0.32, TE +0.21 — meaning a
later pick (or none) at your position is good for you, i.e. **an early
rookie at your position costs the incumbent.** Consistent and
mechanistically sensible.

Its effect on rank accuracy is not established: stacked on ADP it
moved +0.0024 ± 0.0025 (t = 0.96), positive at QB (+0.011, 6/8 years)
and WR (+0.007, 6/8), negative at TE (−0.008, 2/8). Kept because the
mechanism is real and ridge shrinks it if it is noise. Flagged here as
unproven.

## What the coefficients say (standardized, λ=30, full panel)

Unaffected by the correction. These are descriptive fits, not the
head-to-head.

| feature | QB | RB | WR | TE |
|---|---|---|---|---|
| TD luck (actual−expected TDs/g) | **−0.55** | +0.07 | −0.26 | **−0.47** |
| age | +0.06 | **−0.46** | **−0.41** | +0.06 |
| seasons in the league | −0.12 | −0.11 | −0.15 | **−0.38** |
| new team next season | **−0.80** | −0.41 | −0.32 | −0.12 |
| position-room cap share | **+2.22** | +0.51 | +0.19 | +0.28 |
| league cap rank at position | −0.22 | +0.49 | +0.49 | +0.03 |
| draft capital (ln pick, higher=later) | −0.35 | **−0.46** | −0.09 | −0.17 |
| rookie drafted at his position | +0.25 | +0.41 | +0.32 | +0.21 |
| rushing yds/g | +0.19 | **+0.74** | −0.08 | +0.08 |

- **TD luck regresses**, formalizing finding 16 inside a multivariate
  model — except at RB, where TDs are goal-line *role* and it persists.
- **Age decay is real at RB and WR.** At TE it is mileage (seasons
  played), not birthdays.
- **The salary hypothesis (league-mate's idea) works.** Share of the
  team's position-room cap is by far the strongest QB feature.
- **Changing teams costs**, most at QB.
- Caveat: PPG, expected-PPG and the efficiency gap are linearly
  dependent (gap = actual − expected), so only their joint effect is
  interpretable; the table quotes the well-identified features.

## Methodology

`analysis/player_model.py`. Panel: player-seasons with ≥4 games and
≥2 PPG in season t who appear on a t+1 roster; target = t+1 PPG (≥1
game). Ridge per position, features standardized within training
folds, λ by nested leave-one-year-out; evaluation LOYO on the target
year, **restricted to players the ADP board covers**. Spearman is the
metric because a draft list is a ranking. Salary and roster features
use the upcoming season's numbers — knowable at draft time.

## Caveats / not done

- Rookies are out of scope here; they have their own model
  (`analysis/rookie_model.py`, finding 31). **Finding 31 should be
  checked for the same class of bug** — its ADP benchmark assigns a
  tied 999 to every rookie without a fantasy ADP while the model gets
  a distinct prediction for each, which handicaps the benchmark the
  same way this one was handicapped.
- Survivorship: players who wash out of the league entirely leave the
  panel. The model doesn't price roster-cut risk.
- The PPG target sidesteps availability. Total-points drafting should
  multiply by an expected-games model (finding 21's machinery).
- The PPR/half-PPR boards are separate fits but are **not** separately
  evaluated. The LOYO table above is standard scoring only, and the
  free ADP feeds don't archive per-format history to benchmark
  against.
- One model per position, ~20 features, n≈300–560. Year-to-year spread
  is wide (see the per-year table in the script output); 2019 was hard
  for everything.
