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

**B10. Second-QB insurance** (extended to TE) — *graduated to
[finding 20](20-second-qb-te.md)*: null on every forced-vs-banned
contrast, on two independent base drafters (|Δ| ≤ 0.25 ± 0.35 all-play).
The backup does play (QB2 starts ~27% of weeks on a frozen roster), but
waivers sell the same coverage. Real effects found instead: QB2 forced
at r12–14 costs 0.4–0.6, and punting TE1 to r10 without streaming costs
1.4. Also documents a `pick_value` wart — a global `BENCH_WEIGHT` over
raw (non-replacement-adjusted) points makes it take a QB2 ~100% of the
time; worth ≈0.1–0.3 to fix, i.e. nothing.

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

**B15. QB-Elo streaming/downgrade features.** nfelo's continued QB-Elo
(`data/market/qb_elos.csv`) tracks per-QB value live (same-season corr
with fantasy PPG 0.78) and its `qb_adj` columns price starter→backup
downgrades per game. Tests: (a) does adding own-QB value to the weekly
QB model beat M4's .434? (b) can the sim's `Streamer("QB")` policy
rank wire QBs by QB-Elo instead of trailing points, and does that
close any of late-QB's −2.9 gap (finding 06)? (c) opponent-QB-out
context for weekly projections. See finding 26's nfelo section.

**B14. Knowable-information oracle.** Finding 24 measured the
*foresight* ceiling: +685 pts/season over disciplined drafting. Rerun
the same beam search but restrict the oracle's evaluation to
information available at draft time (previous-season points, ADP,
age/rookie status, the finding 15–18 signals) and score the resulting
rosters on the *actual* season. The gap splits into "knowable at the
draft" (a real skill ceiling a better bot could chase) vs "pure luck."
Machinery exists (`analysis/oracle_draft.py` — swap `board.tot`/
`hero_eval`'s objective for a draft-time projection, keep hindsight
scoring); the design question is which projection defines "knowable."

**B16. Player props as the live projection.** Finding 35 showed the
in-game win probability is capped by projection quality, and the
headroom test put the gap between a crude and a decent projection at
6 points of matchup-winner accuracy *at kickoff* (68.3% → 74.3%),
shrinking to 0.3 points by the start of Q4. Props are the market's own
per-player projection, and findings 26/27/28 all landed on "the
closing line already prices what our features see" — so props are the
obvious next rung. Test: pull Sunday-morning props (rec yds, rush yds,
pass yds, receptions, anytime TD) from the Odds API, de-vig each pair,
convert to expected fantasy points, and score them against Sleeper's
free weekly projection and against actuals. Questions: (a) do props
beat Sleeper's projection on the ~150–200 starters they cover?
(b) does the win probability's Brier improve at kickoff, where the
headroom actually is? (c) is a props/projection blend better than
either — finding 25's ADP+½·model pattern suggests it might be.
Cheapest version is paper-trading it live from week 1; a real backtest
needs the $59 one-month historical plan. Ships as
`site/data/props_<week>.json` behind the `projOf()` fallback chain in
`site/live.js` (see docs/SITE_PLAN.md).
