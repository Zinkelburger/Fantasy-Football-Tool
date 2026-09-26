# 40 — Short-route roles draw more targets: external results worth testing

**Status: External research note, recorded 2026-09-24. Not independently
replicated or adopted as a ranking rule.**

**Confidence: Low for a predictive edge.** The reported descriptive results
are useful hypotheses, but we do not have the route-level data or the original
study's complete methodology to reproduce them.

## Reported results

The July 22, 2026 [Reddit post, “Route Tree matters for Fantasy”](https://www.reddit.com/r/fantasyfootball/comments/1v3aw3s/route_tree_matters_for_fantasy_mildly_interesting/)
uses Fantasy Points Data to compare two groups of route types:

| Route group | Targets per route run | Yards per route run |
|---|---:|---:|
| Slant / out / dig | 0.23 | 1.85 |
| Corner / post / go | 0.14 | 1.75 |

The post identifies Coker, Doubs, McConkey and Collins among receivers with
high short-route shares; Higgins, Johnston, Brian Thomas and Jameson Williams
among those with high deep-route shares. These are the author's historical
examples, not our current recommendations. The retrieved post does not give
the full sample, season filters, qualifying minimum or weighting method.

The author builds on Zain Dhanani's route-depth research. Fantasy Points'
[public summary](https://newsletter.fantasypoints.com/p/gurus-guys-roundup)
reports **11.5 half-PPR points/game for shallow-route receivers versus 8.7 for
deep threats**, and **27% versus 12% targets per route** for short versus deep
routes. These are a separate comparison: do not combine them with the Reddit
table as though the route definitions or populations were identical. The
[full original article](https://www.fantasypoints.com/nfl/articles/2026/fantasy-factors-understanding-route-depth)
returned HTTP 402 when checked; its complete methods were not available.

## What the finding suggests

A receiver's assignment can affect his chances to earn a target before the
ball is thrown. Two players with similar field time can have very different
opportunities if one repeatedly runs underneath and the other clears space
downfield. Measuring every route could expose that distinction even in a
zero-target game.

The target-frequency difference in the Reddit table is much larger than the
yardage difference. More targets alone do not establish the fantasy value:
receptions, touchdowns, scoring format, route volume and player ability also
matter. The half-PPR finding cannot be applied unchanged to our standard
league. An out or dig is also not a fixed depth; route type and route depth
should remain separate fields.

## Data limitation: our free data does not contain this route mix

Inspected `engine/weekly/cache/pbp_*.parquet`, player stats, the public FTN
charting subset, and `engine/weekly/advanced_usage.py`:

- We have targets, target air yards, offensive snap counts, and play-level
  flags for play action, motion and screens.
- We do **not** have receiver route counts, short/deep route shares, route
  types or average depth across all routes in those sources.
- **Average depth of target is not average route depth.** It observes only
  the routes that drew a target. **Offensive snaps are not routes run.** A
  player can block or be on the field for a running play.
- The free FTN motion flag describes a play, not which receiver moved. It
  cannot supply receiver-specific motion-at-snap route counts.

Thus the short/deep route result is preserved as **externally reported**, not
re-created with a mislabeled free proxy. [Fantasy Points Data Suite](https://fantasypointsdata.com/)
advertises route detail and CSV exports. Authorized exports with matching
denominators could support replication; raw per-route export access and
historical coverage still need verification.

## Technique to borrow when the data is available

Dhanani's later [Receiver Score methodology](https://www.fantasylife.com/articles/fantasy/introduction-to-receiver-score-how-the-model-was-built-4-key-202)
describes estimating target probability and fantasy value on every route,
then combining environment, red-zone opportunity, volume and execution. It
reports 0.89 year-to-year correlation for its environment component and
claims predictive improvement over prior fantasy PPG. The article does not
provide enough evaluation detail or code to independently verify the latter.
Persistence of a role score is not itself evidence of forecast accuracy.
This score is distinct from ESPN's Receiver Score.

First reproduce the descriptive tables with explicit route definitions,
counts, seasons and player minimums. Then test whether **lagged** route mix
adds to prior targets, target share and our expected-points baseline when
predicting future targets and fantasy points. Train on earlier seasons;
evaluate later ones and a frozen prospective sample. Separate scoring formats
and account for player/team/QB effects and sparse samples. Do not multiply
marginal route, motion and play-action bonuses, which overlap.

No route-based adjustment is justified yet. Related:
[17 — targets and efficiency](17-buy-targets-not-efficiency.md),
[41 — Flowers reproduction](41-receiver-opportunity-and-scheme.md), and the
[full feasibility audit](../../../research/receiver-role-audit/README.md).
