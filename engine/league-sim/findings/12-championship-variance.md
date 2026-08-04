# 12 — Back-to-back runner-up finishes are variance, not process failure

**Confidence: High** (simulation math + the league's own history)

## TL;DR

The Jackels went a combined **24-4** with the #1 seed and #1 points-for
in both 2024 and 2025 — and lost the championship game both times.
Meanwhile the champions had the **#3** (2024) and **#7** (2025) draft
hauls. This is exactly what playoff structure does to the best team:
titles are decided by 2–3 single-week coin flips that even a dominant
roster only tilts, never controls.

## The data

From the ESPN league history:

| Year | Jackels record | PF (league rank) | Seed | Final rank | Champion (their draft-haul rank) |
|---|---|---|---|---|---|
| 2024 | 13-1 | 1493 (#1, +160 over 2nd) | 1 | **2nd** | Yarmouth Bernal Bombers (#3) |
| 2025 | 11-3 | 1320 (#1) | 1 | **2nd** | Buckhead Bullies (#7, 7-6 season) |

From the simulator (environment v3, METHODS.md): the backtest's best
title-rate strategy — Robust RB at .598 all-play, a *dominant* weekly
edge — still converts it into only a 20.3% title rate: four seasons
in five, the best plan tested does not win the ring. Weekly dominance compounds weakly
through a 3-round bracket. A rough illustration: a team that beats an
average playoff opponent 65% of the time (a *huge* weekly edge) wins
two straight playoff games only ~42% of the time — and the Jackels
had byes, so two wins was the requirement. Losing consecutive finals
with a coin weighted your way is unremarkable: even at 65-65, you
lose at least one of two successive finals ~58% of the time.

## Why this belongs in the presentation

Two audiences need it:

1. **The Jackels**, so two silver medals don't trigger process
   changes. The process produced the league's best regular-season
   team twice; the sim says that's the controllable part, fully
   achieved.
2. **The league**, because "X won the title, copy X" is the natural
   fallacy — and in both years the champion drafted worse than the
   runner-up. Titles identify the luckiest good-enough team, not the
   best process.

The right scoreboard for *process* is all-play win% and points-for.
By those, the Jackels have been the best team in the league two years
running.

## Methodology

- League facts: `data/espn/league_2024.json`, `league_2025.json`
  (records, seeds, final ranks from ESPN's own fields).
- Draft-haul ranks: perfect-lineup points from drafted rosters only,
  all 12 teams (`scripts/jackels_review.py`; see finding 11 for the
  definition).
- Title-vs-strength relationship: the strategy grid
  (`results/*.json`) — compare the all-play and title columns.
- The 65% illustration is arithmetic, not simulation: 0.65² ≈ 0.42.

## Caveats

- We don't have the league's weekly matchup data in these exports, so
  the two finals losses can't be dissected shot-by-shot here. If the
  full matchup history gets exported later, a "how unlucky exactly?"
  addendum is computable.
- None of this means playoffs are pure luck — a .598 team wins 2.4×
  the baseline title rate (20.3% vs 8.3%) over time. It means two
  specific finals are far too small a sample to indict a process.
