# Hypothesis backlog

Testable theories queued or proposed, with test designs and a data
feasibility check. Findings graduate from here into numbered files.

## Running / queued

**B1. QB draft-round sweep** — *graduated to
[finding 14](14-qb-round-sweep.md)*: rounds 4–6 peak (.588 all-play),
near-flat 2–8, real decay past 10. Levels vs family are discipline-
gap-inflated under v3 calibration; only within-sweep differences are
QB effects.

**B2. Bench composition: hoard RBs vs WRs** — *graduated to
[finding 19](19-bench-composition.md)*: the lottery-ticket asymmetry
is real (21% vs 13% sustained-run rate) but converts to only
+0.5 all-play / +1.1 titles, within noise. RB as bench tiebreak,
nothing more.

**B3. Handcuff strategy at scale** — *graduated to
[finding 13](13-handcuffs-are-free-insurance.md)*: ran the full grid
twice (with and without news-aware projections, which shipped
alongside). Dead tie with plain pick_value (.598 vs .599) — insurance
is fairly priced at zero; handcuff on ties only. NOTE for other
findings: the engine environment changed (v2 calibration, v3 news
promotion) — see the version table in finding 13 before quoting
levels from `results/`.

## Proposed — data confirmed available

**B4. Waiver EV upgrade.** Current sim FA valuation = EWMA of points
+ skeptical prior (`lineup.py`), which is points-chasing with shrinkage.
Upgrade path: nflverse `load_ff_opportunity` provides *expected*
fantasy points from usage (targets, carries, air yards) — claim
players whose expected points exceed actual (usage precedes scoring).
Test: does an expected-points waiver bot beat the EWMA bot?

**B5. Runner skill vs situation (the Jeanty question).** NGS rushing
(2016+) has `rush_yards_over_expected` — expected yards conditions on
blocking/defenders at handoff, so RYOE isolates the runner. PFR
advstats add yards-before-contact vs after. Test: low-volume RBs with
high RYOE/att — do they outperform when volume arrives (next 4 weeks
after a starter injury, or next season)? If yes, it's a waiver/stash
screen the league can't see.

**B6. O-line health index + visualization.** Weekly OL starters from
`load_snap_counts` (positions T/G/C) + `load_injuries`: continuity =
how many of the week-1 starting five are playing. Test: team RB
fantasy PPG vs OL continuity, within-team across weeks. Deliverable:
team × week heatmap; use as a context layer for waiver decisions.

**B7. Rookie RB paths to relevance.** All rookie RBs 2020-2025: week
they first cracked positional top-24, and whether the incumbent ahead
of them (by preseason depth) played that week — separates "earned the
job" from "injury opened the door," by draft capital. Informs how to
value rookie RB stashes and when to buy.

**B8. Draft-seat advantage.** Family-vs-family title/finish rates by
seat — computable from existing grid JSONs (hero=family cells rotate
seats). Settles whether the snake position matters enough to argue
about draft-order lotteries.

**B9. Rookie reach EV.** The league reaches ~7 picks on rookies
(calibration data). Cohort: rookies vs veterans at equal ADP, hit and
bust rates by position. Is the family's rookie thing a leak or a lean?

**B10. Second-QB insurance.** The league drafts a 2nd QB in 58% of
team-drafts (QB2 median round 13). Sim: baseline family vs family
forced to skip QB2 (extra bench RB/WR instead — connects to B2). The
QB availability numbers (91% early-QB availability, best of any
position) suggest QB2 is mostly wasted, but bye-week friction is real.

**B11. WR archetypes out-of-sample.** Findings 08-10 predictions
frozen before the 2026 season: bad-team-WR1s should hit ≥40%,
fallen studs should bust ≥50%. Score them next January.

## Proposed — feasibility limited, proxies only

**B12. RB pass protection.** No free pass-block grades exist. Proxies:
(a) pass-down snap share — RB on field on 3rd-and-long/two-minute
(from `load_participation`, complete through ~2023, or situational
target/carry splits from pbp after); (b) year-over-year growth in
pass-down usage as the "earned trust" signal. Tests: do rookies with
higher pass-down usage outscore same-capital rookies? Does pass-down
share predict snap share the following season? (The quote is the
hypothesis: backs who can't protect don't see the field.)

**B13. Trades.** Not modeled, no historical league trade data in the
exports. Out of scope unless the league exports activity logs.
