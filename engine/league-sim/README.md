# league-sim

A full-season simulator for a 12-team **ESPN standard (non-PPR)** family
league, built to backtest draft-day and waiver-wire strategies against
real NFL results, 2020–2025.

Not best-ball: every simulated season runs week by week — snake draft,
lineup decisions, rolling-priority waivers, head-to-head schedule,
six-team playoff. Free agents are whatever the other eleven simulated
managers left on the wire, so "can I stream a TE?" is answered by
competition, not assumption.

## League model

- 12 teams, snake draft, 15 rounds
- Starters: QB, 2 RB, 2 WR, TE, FLEX (RB/WR only), K — 7 bench, no D/ST
- ESPN standard scoring: 1 pt/25 pass yds, 1 pt/10 rush/rec yds
  (whole-point floors), 4 pt pass TD, 6 pt rush/rec TD, −2 INT/fumble,
  distance-scored FGs
- Weeks 1–14 regular season, playoffs weeks 15–17 (top-2 byes)
- ESPN rolling waiver priority: claim something, go to the back

## Honesty rules

- Every in-season decision uses **only information available at the
  time**: trailing points, preseason expectations, and who's inactive.
  Nobody peeks at the future.
- Preseason expectations come from the *previous* season's positional
  curves — no hindsight.
- Players drafted off real ADP who then missed the whole season
  (Deshaun Watson 2021, Joe Mixon 2025...) stay in the pool. Busts are
  part of history.

## Data

| What | Source |
|---|---|
| ADP 2020–2024 (12-team standard, with per-pick stdev) | FantasyFootballCalculator API |
| ADP 2025 | FantasyPros standard consensus, recovered via Wayback Machine (2025-09-03 snapshot) |
| Weekly stats, schedules, rookie years | nflreadpy (nflverse) |

Everything caches under `data/` after the first `fetch`.

## Usage

```bash
venv/bin/python -m simfl fetch                    # warm the data caches
venv/bin/python -m simfl draft  --year 2023 --hero zero_rb --seat 5
venv/bin/python -m simfl season --year 2023 --hero punt_te --seat 5
venv/bin/python -m simfl mc     --year 2024 --hero late_qb -n 200
venv/bin/python -m simfl compare --years 2020-2025 --heroes all -n 100
venv/bin/python -m simfl analyze kickers          # hot-kicker persistence
venv/bin/python -m simfl analyze streaming --pos TE
venv/bin/python -m simfl analyze scarcity
venv/bin/python -m simfl.grid --heroes all -n 240 # parallel backtest grid
venv/bin/python -m simfl.plots                    # presentation figures
```

## Strategies

| name | idea |
|---|---|
| `family` | The control field: drafts near ADP with realistic per-pick noise, a soft spot for RBs and rookies, chases last week's points on waivers |
| `bpa` | Takes the board in ADP order, no convictions |
| `robust_rb` | RB-RB-RB to open |
| `zero_rb` | No RB before round 6 |
| `hero_rb` | One RB in round 1, none again until round 7 |
| `early_qb` | Elite QB by ~round 3 |
| `late_qb` | No QB before round 10, streams a second off waivers |
| `punt_te` | No TE before round 12, streams the position all season |
| `wr_heavy` | WR lean in rounds 1–6 |

Add your own: subclass `DraftStrategy` in `simfl/strategies.py`,
override `banned()` / `score()`, register it in `STRATEGIES`. In-season
behavior is pluggable the same way via `WaiverPolicy`.

## Architecture

```
simfl/
  config.py      league + scoring settings (single source of truth)
  data.py        fetch & cache: ADP, weekly stats, byes, rookie years
  pool.py        joins ADP board to actual weekly results per season
  scoring.py     ESPN standard scoring from raw stat lines
  models.py      PlayerSeason, Team
  draft.py       snake engine + shared roster-legality rules
  strategies.py  draft personalities (the interesting file)
  lineup.py      leak-free projections + lineup setting
  waivers.py     waiver policies + rolling-priority claim processor
  season.py      week-by-week season: schedule, scoring, playoffs
  montecarlo.py  hero-vs-field experiments with seat rotation
  grid.py        parallel (strategy × season) backtest, JSON results
  analysis.py    descriptive studies (kickers, streaming supply, scarcity)
  plots.py       presentation figures
  cli.py         readable terminal frontend
```
