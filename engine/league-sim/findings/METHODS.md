# Shared methodology

Everything in this directory rests on the same data and, where noted,
the same simulator. This file is the one place that explains both.

## The league being modeled

Sumfun League (ESPN id 112618), verified from the exported league
settings, not assumed: 12 teams, snake draft, **standard non-PPR
scoring** (1 pt/25 pass yds, 1 pt/10 rush/rec yds with whole-point
floors, 4-pt pass TD, 6-pt rush/rec TD, −2 INT and fumble lost, FG
3/4/5 by distance, −1 missed FG), lineup QB / 2 RB / 2 WR / TE /
FLEX (RB/WR only) / K / D-ST, 7 bench. Waiver priority resets to
reverse standings weekly. D/ST is excluded from all analysis (drafted
last, mechanically unlike every other position).

## Data sources

| What | Source | Notes |
|---|---|---|
| ADP 2020–2024 | FantasyFootballCalculator API, 12-team standard | includes per-player draft-position stdev from ~700–2,700 real drafts/yr |
| ADP 2025 | FantasyPros standard consensus | recovered from a Wayback Machine snapshot dated 2025-09-03 (FFC purged its 2025 data); stdev imputed from a linear fit on the FFC years |
| Weekly stats 2018–2025 | nflverse via `nflreadpy` | regular season only; fantasy points recomputed from raw stat lines under the league's exact scoring |
| Rookie years, birthdates, schedules | nflverse | |
| League history 2020–2025 | ESPN league export (`data/espn/league_*.json`) | drafts, teams, standings, settings |

ADP names are joined to nflverse stats by normalized name + position
(4 alias corrections, e.g. Hollywood/Marquise Brown). Across 2020–2025,
every unmatched ADP player was manually verified to be a genuine
zero-stat season (holdout, season-ending injury, retirement) — those
players **stay in the pool** with zero points, because drafting a bust
is part of history.

## The simulator (used by findings 01–03, 06)

A full week-by-week season, not best-ball: snake draft → 14-week
head-to-head regular season with waivers after every week → 6-team
playoff, weeks 15–17, top-2 byes.

Honesty rules:
- Every in-season decision uses only information available at the
  time: trailing weekly points (EWMA, α=0.35) blended with a preseason
  prior, plus knowledge of who is inactive/on bye (mirrors real injury
  reports). Nobody sees future points.
- The preseason prior is the *previous* season's realized PPG curve by
  positional rank — no hindsight leaks into expectations.
- The free-agent pool is emergent: it is whatever the other eleven
  simulated managers didn't roster, so streaming claims compete.

The field: eleven "family" bots that draft near ADP with noise
calibrated to this league's six real drafts (`analysis/calibrate.py`),
prefer rookies slightly, fill needs sanely, take K/D-ST at the end,
and chase last week's points on waivers. One "hero" bot plays a named
strategy. The hero rotates through all 12 draft seats; 240 simulations
per (strategy, season); seasons 2020–2025 → **1,440 seasons per
strategy**, ~13,000 total.

**Validation (the null test):** a family bot dropped into the family
field scores all-play 0.500 ± 0.006 and wins titles at ≈ 1/12 in every
season. Any deviation a strategy shows is therefore signal, not
harness bias.

**The sharp room (added 2026-08-02):** `hero_experiment(...,
villain="bpa")` swaps the eleven family bots for eleven disciplined
ADP drafters with hero-grade waivers — a theoretical room with no
measured family habits. Any strategy's edge splits into a
room-exploiting part (family room minus sharp room) and a
room-independent part (what survives sharp villains). The null test
holds there too: bpa-in-bpa-room = 0.497. Used by finding 03's
sharp-room table (`analysis/sharp_room.py`).

Metrics:
- **All-play win %** — each week, your score vs all 11 others; the
  schedule-luck-free measure of team strength. Baseline 0.500.
- **Title rate** — championship frequency including the playoff
  coin flips. Baseline 1/12 ≈ 8.3%.

## General caveats

- Six seasons (2020–2025) is the window; football changes.
- Strategies are tested against *this* family model. A different field
  (e.g. sharks) could shift results.
- Waiver behavior is stylized; trades are not modeled.
- The family bots reproduce the league's *total* positional appetite
  and early-round drain (validated against all six real drafts in
  findings 01 and 19) but not year-specific herd timing — the real
  rounds-10-12 RB run and 2021's round-1 QB panic are fads the model
  smooths over.
- Historical cohort studies (findings 08–10) slice ~200 player-seasons
  and inherit all the usual multiple-comparisons risks; each file
  carries its own robustness section, and confidence ratings reflect it.
