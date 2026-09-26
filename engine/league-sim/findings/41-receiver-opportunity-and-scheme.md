# 41 — Receiver opportunity and scheme: the Flowers case partly reproduces for free

**Status: Descriptive reproduction and external research note, recorded
2026-09-24. No new forecast model or player recommendation.**

**Confidence: High for the reproduced totals under our stated definitions;
Low for an incremental predictive edge.** One player's retrospective splits
do not validate a strategy across receivers.

## Source and reusable idea

Stephen Krupka's June 12, 2026 [Flowers post](https://www.reddit.com/r/fantasyfootball/comments/1u485bo/youre_too_low_on_zay_flowers/)
and [original newsletter](https://www.movesfantasy.com/p/flowers) combine
target earning, efficiency, opportunity share, team passing tendencies,
play action, quarterback splits and a coaching-change thesis. Sources include
TruMedia, PFF and other named providers.

The central decomposition is useful with consistent data populations:

`yards per route = targets per route × yards per target`

It separates earning opportunities from converting them. Expanded to a game,
receiving yards equal team dropbacks × route participation × targets per route
× yards per target, when all four terms use matching definitions. Each term
needs its own estimate to turn that identity into a forecast.

## What we reproduced

Cache-only calculation from 2025 nflverse weekly player stats and play-by-play,
plus FTN charting. Regular season, all 17 Flowers games, unless noted.

| Statistic | Source post | Our calculation |
|---|---:|---:|
| Yards per target | 10.3 | 10.263 |
| Target share | 29.0% | 28.993% |
| Air-yard share | 35.7% | 35.664% |
| Weighted opportunity rating (WOPR) | 0.69 | 0.6845 |
| PPR/game with Lamar, 13 games | 15.03 | 15.031 |
| PPR/game without Lamar, 4 games | 11.98 | 11.975 |
| Average target depth | 10.1 | 10.203 |
| YAC/reception | 5.5, PFF | 5.326, nflverse |

Flowers had 118 targets, 86 catches and 1,211 receiving yards. Share
denominators are all identified team targets/air yards in his games: 407
targets and 3,376 air yards. WOPR is `1.5 × target share + 0.7 × air-yard
share`, using ratios of season totals rather than averages of weekly ratios.
Lamar's presence means at least one recorded pass attempt in the game; it is
not a health assessment or a play-level on/off comparison.

The article's opening 13.7 PPR/game does not match its own 13/4-game splits:
those imply about 14.31. Our all-season mean is 14.312; excluding Week 18
gives 13.344. Record this as an unresolved scoring/sample discrepancy. Small
YAC and air-yard differences can reflect provider measurements; they do not
by themselves invalidate the analysis.

## An additional result from our free FTN data

| Flowers' 2025 targets | Targets | Receiving yards | Yards per target |
|---|---:|---:|---:|
| Play action | 28 | 475 | 16.96 |
| Other plays | 90 | 736 | 8.18 |

All 118 targets have a play-action label, and the split reconciles to his
season receiving yards. This is **yards per target, not yards per route**.
It supports the descriptive observation that his play-action targets were
productive. It does not establish that extra play-action usage would preserve
that efficiency: target depth, opponents, selection and a 28-target sample
can all matter.

Using our retained-dropback denominator, Chicago's play-action rate was
31.4% versus Baltimore's 22.4%. The post reports 33% and 26% from another
provider. The ordering agrees; the definitions are not aligned sufficiently
to claim an exact replication. Sacks, scrambles and charting decisions affect
the denominator. The output records full label coverage for our populations.

## What remains unavailable or unproven

- **Route counts and route mix are absent from our inspected free data.** We
  cannot reproduce YPRR, TPRR, play-action YPRR or rankings among receivers
  qualifying on 250 routes. See [finding 40](40-receiver-route-mix.md).
- Free FTN provides play-level motion/screens/read labels. It does not
  identify a particular receiver's motion or every receiver's assigned read.
  The live dictionary's numeric read-code mapping needs reconciliation with
  our cache before a first-read metric is published; raw labels are retained.
- Claims that YAC is more repeatable than deep-ball efficiency need a direct
  longitudinal comparison. [Finding 17](17-buy-targets-not-efficiency.md) and
  its [2026-09-24 recheck](../../../research/regression-to-expected/README.md)
  found no clear incremental WR YAC/reception signal conditional on prior
  PPG; that is not the same test as comparing the two types of efficiency.
- The new coordinator's prior team's pace and passing rate do not
  automatically transfer. The article acknowledges that Doyle did not call
  Chicago's plays. Treat that transfer as a scenario, not a measured boost.
- A previous career-best finish does not establish a future floor. These
  June preseason arguments are not a current injury or lineup assessment.

## Implication for our research

We can build receiver profiles now from target/air-yard shares, WOPR,
target depth, efficiency, and FTN scheme splits. The fields exist even though
our current advanced-usage export exposes only part of them. Generalize
across all receivers and test future target volume before fantasy points.

Compare only information available before each game against lagged targets
and the existing expected-points baseline. Keep the same player population,
retain active zero-target games, distinguish DNPs, report player-cluster
uncertainty, and score standard/half/PPR separately. Further selection on
already-inspected 2025 outcomes is exploratory; freeze a specification for
prospective evaluation. A good descriptive split alone does not warrant
changing the production model.

## Reproduce and inspect

```bash
.venv-league-sim/bin/python research/receiver-role-audit/audit.py
```

[Script](../../../research/receiver-role-audit/audit.py),
[results and source hashes](../../../research/receiver-role-audit/results.json),
[full audit](../../../research/receiver-role-audit/README.md).
The script validates unique joins, the 17-game sample, and reconciliation of
targets and receiving yards. It writes only the audit JSON. No predictive
backtest was run. Sources: nflverse player stats/PBP; FTN Data via nflverse
(CC-BY-SA 4.0). Numerical projections and narrative remain separate.
