# Receiver analysis feasibility audit

September 24, 2026. **We can reproduce much of the Flowers analysis with
existing data. Exact route-tree analysis requires an additional charted data
source.** The missing ingredient is measurement of every receiver's routes,
including untargeted routes, rather than statistical software.

Read both supplied Reddit posts through ff-reddit, including the full Flowers
body and its discussion. Also read the [original Flowers newsletter](https://www.movesfantasy.com/p/flowers),
Fantasy Points' [public summary of Dhanani's route-depth study](https://newsletter.fantasypoints.com/p/gurus-guys-roundup),
and his subsequent [Receiver Score methodology](https://www.fantasylife.com/articles/fantasy/introduction-to-receiver-score-how-the-model-was-built-4-key-202).
The [full original route-depth article](https://www.fantasypoints.com/nfl/articles/2026/fantasy-factors-understanding-route-depth)
returned HTTP 402; its exact sample, filters, and validation could not be inspected.
The Reddit route-type grouping is not necessarily the same as Dhanani's
route-depth buckets. This is a feasibility audit and descriptive reproduction,
not a new predictive backtest or a current Flowers recommendation.

## What is reusable

The [route-tree post](https://www.reddit.com/r/fantasyfootball/comments/1v3aw3s/route_tree_matters_for_fantasy_mildly_interesting/)
groups slants/outs/digs and corners/posts/go routes. It reports target rates of
23% versus 14%, with yards per route of 1.85 versus 1.75, using Fantasy Points
Data. The useful question is whether deployment explains opportunity before a
target occurs. The difference in target frequency is much larger than the
difference in yardage; receptions and touchdowns are needed to establish the
fantasy-point difference in each scoring format. Route names are not precise
depth measurements: an out or dig can be run at different depths.

The [Flowers post](https://www.reddit.com/r/fantasyfootball/comments/1u485bo/youre_too_low_on_zay_flowers/)
combines usage, efficiency, scheme, quarterback splits and a coaching-change
thesis. Its most transferable decomposition is an identity:

`yards / route = (targets / route) × (yards / target)`

With consistent populations, receiving yards per game can be decomposed into
team dropbacks × route participation × targets per route × yards per target.
This separates more passing, more playing opportunity, target earning, and
conversion efficiency. It is not itself a forecast; each factor still needs
to be predicted, with uncertainty and dependencies retained.

Dhanani's later Receiver Score article extends this to estimating target
probability and fantasy value for every route, combining environment,
red-zone opportunity, volume and execution. It claims improved backtests, but
does not supply code, a full evaluation table, or enough split details to
independently validate that claim. Its role persistence statistic is not a
forecast-accuracy statistic. This is also a different score from the ESPN
tracking-based Receiver Score cited in the Flowers post.

## Data and implementation inventory

| Analysis | What we have | Feasibility |
|---|---|---|
| Target share, air-yard share, WOPR | Cached weekly player stats and PBP; `advanced_usage.py` already exports target share | Available now; pool counts over matching games rather than average weekly shares |
| Yards per target, target depth, YAC/reception, explosive receptions | Cached player stats/PBP | Available now; provider definitions can differ |
| Team dropback rate, pass rate over expected, first-down tendencies | PBP; `team_context.py` already computes passing context | Available now; explicit play filters matter |
| Pace | PBP clocks and play timestamps | Implementable; choose a clock-running/neutral-situation definition before comparing published ranks |
| Play action, motion-on-play, screens, targeted-read labels | FTN caches for 2022–2026 | Available, but richer than the two FTN fields currently surfaced by `advanced_usage.py` |
| QB game splits | Weekly QB participation and PBP passer IDs | Available; a game in which Lamar appeared is not necessarily a healthy-Lamar game or a Lamar-only target sample |
| Routes run, route participation, TPRR, YPRR | Not in the inspected caches or existing advanced-usage export | Need a charted routes source; offensive snaps are not routes |
| Route type/depth, receiver-specific motion, alignment and coverage on every route | Not in current public FTN subset | Need richer charting; aDOT measures targets, not all routes |
| PFF grades, ESPN Receiver Score, proprietary separation grades | No verified local ingestion | Can cite published results as context; cannot independently rebuild the proprietary measures |
| Expected YAC and target-level separation aggregates | Public NGS loader/dictionary | Candidate free addition; not fetched or coverage-verified in this audit; does not supply all-route separation |

The [FTN dictionary](https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html)
defines motion at the play level. It cannot tell us which receiver moved.
There is also a read-label interpretation issue: the current dictionary maps
numeric codes starting at 0, while our Flowers target sample contains `1`, `2`,
`CHK`, `DES`, `SD` and no `0`. Preserve raw labels and verify the applicable
provider version before publishing a first-read statistic. This audit does not
assign first/second-read meanings to the numeric codes.

[NGS's public fields](https://nflreadr.nflverse.com/articles/dictionary_nextgen_stats.html)
include expected YAC and YAC above expectation. These offer a way to investigate
whether apparent YAC skill reflects situation, but do not reconstruct the
ESPN or Fantasy Points measures.

## Actual reproduction with our existing caches

`audit.py` reads only three 2025 parquet files and writes `results.json`, with
source hashes, definitions and coverage. It checks unique joins, 17 Flowers
games, and reconciliation of all his targets and receiving yards to the weekly
totals. The complete 2025 regular season is used unless stated otherwise.

| Flowers statistic | Published post | Our reproduction |
|---|---:|---:|
| Yards per target | 10.3 | 10.263 |
| Target share | 29.0% | 28.993% |
| Air-yard share | 35.7% | 35.664% |
| WOPR | 0.69 | 0.6845 |
| PPR/game with Lamar, 13 games | 15.03 | 15.031 |
| PPR/game without Lamar, 4 games | 11.98 | 11.975 |
| Average target depth | 10.1 | 10.203 |
| YAC/reception | 5.5, PFF | 5.326, nflverse |

Thus several central numbers reproduce closely without new subscriptions.
Provider ranks among 250-route qualifiers cannot be reproduced without the
route counts and the original player population. The article's opening 13.7
PPR/game does not reconcile with its own 13/4-game splits, whose weighted mean
is about 14.31. Our full-season mean is 14.312; excluding Week 18 gives 13.344.
That discrepancy needs a scoring/sample explanation, not an assumed correction.

The free FTN join also yields a useful new split: Flowers gained **475 yards on
28 play-action targets (16.96 yards/target)** versus **736 on 90 other targets
(8.18 yards/target)**. All 118 targets have a play-action label and totals
reconcile to 1,211 receiving yards. This is not the article's play-action YPRR:
we do not know his route counts. It is a descriptive association with a small
play-action sample, not evidence that doubling play action doubles his output.

Our explicit dropback denominator gives Chicago a 31.4% play-action rate and
Baltimore 22.4%; the article uses 33% and 26% from another provider. This supports
the direction of the comparison, not exact equivalence. Provider labeling,
sacks/scrambles and play filters must be aligned before calling a discrepancy
an error. Complete charting coverage is recorded for these denominators.

## Best next research

1. **Generalize the free receiver profile.** Produce the same decomposition and
   scheme splits for every WR/TE, with target counts and coverage, and detect
   changes in usage. Keep individual-player motion and routes unavailable.
2. **Test incremental prediction.** First predict next-game or next-four-game
   targets; then fantasy points. Compare lagged target share/WOPR and scheme
   features with lagged targets, existing xFP, and the current weekly baseline.
   Fit earlier seasons, validate later ones, and keep a final holdout. Our
   prior advanced-feature audit already inspected 2025, so further selection
   using that season is exploratory; freeze a specification for future 2026
   predictions. Use player-cluster uncertainty and consistent player samples.
3. **Test the article's YAC claim directly.** Measure YAC and deep-target
   efficiency persistence, then whether either adds forecast value after usage
   and prior scoring. Our existing regression-to-expected study found no clear
   incremental WR YAC/reception signal conditional on PPG; it is not a direct
   test of YAC versus deep-ball repeatability. Separate standard, half-PPR and
   PPR, since the posts' reception-heavy arguments need not transfer unchanged.
4. **Acquire routes only for the question they uniquely answer.** First test
   route participation, TPRR and short/deep share. If those improve prediction,
   test a route-level expected-target model and then expected points, with
   player/QB/team effects and shrinkage for sparse route/coverage combinations.
   Do not multiply marginal motion, route and play-action uplifts: those
   features overlap. Model teammates competing for one target coherently.

For forecast evaluation, distinguish active player games from DNPs, include
zero-target participants, use the same eligible population for baseline and
candidate, and separately evaluate return/absence uncertainty. Report MAE/RMSE
and calibration; for start/sit utility use decision-time rosters and availability.
Timestamp future source snapshots. A good retrospective Flowers case study
does not establish an edge across all recommendations.

The coaching-change claim belongs in a scenario until independently tested:
the prior offense's pace or pass rate need not transfer to a new roster, and
the article itself says Doyle was not Chicago's playcaller. A prior career-best
finish also does not establish a future floor.

## Practical route-data path

[Fantasy Points Data Suite](https://fantasypointsdata.com/) advertises every-route
detail and CSV table exports; its [official launch announcement](https://newsletter.fantasypoints.com/p/fantasy-points-data-suite-2)
confirms that domain. An authorized export is a practical starting point for
the route-tree replication. Verify historical seasons, weekly granularity,
untargeted-route denominators and permitted reuse before relying on it for a
full model. A table export is not proof of access to raw per-route records.
[TruMedia](https://www.trumedianetworks.com/football) also offers football
platform/API access, but no such access is configured in the inspected engine.
Neither service needs to be purchased to run the free experiments above.

```bash
.venv-league-sim/bin/python research/receiver-role-audit/audit.py
```

Only the audit script, report and output are added. Production rankings and
published editions are unchanged. Raw Reddit text is not included. Numerical
outputs derived from FTN are attributed to FTN Data via nflverse, CC-BY-SA 4.0.
