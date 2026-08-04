# Methodology

Question: the reddit-scraped draft notes (2024: 244 files of raw comment
pastes; 2025: 355 files of LLM-summarized outlooks) — do they carry any
information that improves draft picks beyond ADP, or are they redundant
hype? Two independent tests: a correlation study on outcomes, and a
mock-draft Monte Carlo that mimics exactly how the Go tool uses them.

## Pipeline

```
scripts/prep_data.py      note files + ADP boards + weekly stats -> data/joined_{year}.csv
scripts/scoring_prompt.md LLM tone scoring (done once, July 2026) -> data/sentiment_scores.csv
scripts/analyze.py        correlation study                       -> results/correlation_output.txt
scripts/mock_drafts.py    2,400-season mock-draft backtest        -> results/mock_draft_output.txt
```

All scripts run with `engine/league-sim/venv/bin/python`.

## Step 1 — ground truth (prep_data.py)

- **Actual results**: `engine/league-sim/data/weekly_{year}.parquet` (nflverse),
  weeks 1–17, ESPN standard scoring (0.04/pass yd, 4 pass TD, −2 INT,
  0.1/rush+rec yd, 6 TD, −2 fumble, distance-scored kickers, no PPR) —
  the family league's format. Season total points and positional finish
  rank per player.
- **Market rank**: 2024 = ADP column of `2024/ADR.csv`; 2025 = consensus
  rank of `2025/go/std_with_depth.csv` (ESPN+Sleeper). ~225 ranked
  players each year.
- **Name matching**: unicode-stripped, punctuation-stripped, suffix-
  stripped keys plus a 7-entry alias table (nflverse uses "Tank Dell",
  "Josh Palmer", ...). Match rate 236/244 (2024) and 311/355 (2025);
  the remainder are team-DST files, two meta files, and real players
  with zero stat lines all season.
- **Zero-stat players are kept as 0-point busts**, not dropped (Amari
  Cooper, Aiyuk, Mixon 2025; AJ Dillon 2024...). Dropping them would
  flatter the notes whenever a noted player completely busted.

## Step 2 — tone scoring (LLM)

Each of the 599 files scored −2..+2 by a Claude Sonnet subagent using
the fixed rubric in `scripts/scoring_prompt.md`, plus a `has_negative`
flag. Scores keyed by **(year, filename)** — 198 players have files in
both years, scored independently (149 of them differ across years).
The scorer never saw ADP or results. One pass, no ensemble; treat ±1
boundaries as noisy.

## Step 3 — correlation study (analyze.py)

Define `value = positional market rank − positional finish rank`
(value > 0 = beat draft cost). If the notes know something ADP doesn't,
corr(tone, value) must be > 0. Spearman correlations with two-sided
permutation p-values (5,000 shuffles, seeded). Views: full market
universe, top-120 only (rank-residuals are bounded and asymmetric deep
in the pool — deep players can only beat their rank, early players can
only miss it — so the draftable range is the honest view), per-game
scoring for players with ≥6 games (strips injury luck), and tone-bucket
means/beat-rates.

## Step 4 — mock drafts (mock_drafts.py)

Uses league-sim's `hero_experiment`: 12-team snake, 15 rounds, hero
rotates through all 12 seats, 11 opponents are the family-calibrated
noisy-ADP bots, full week-by-week season with lineups, waivers and
playoffs. 240 seasons per strategy per year, common random numbers so
per-sim paired deltas vs the control are exact.

Five heroes, identical except for how tone is used inside the "next 10
by ADP" window the Go tool displays: `bpa` (pure ADP control),
`notes_hard` (tone overrides: take the best-noted of the window),
`notes_soft` (tone nudges perceived rank by 8%/point ≈ a tiebreaker),
`notes_anti` (take the worst-noted; if notes carry signal this must be
bad), `rand_10` (random pick from the window; prices the cost of
deviating from ADP regardless of direction).

The anti/random pair is what separates "the notes flag real duds" from
"any reach down the board is costly."

## Honesty rules

- No draft-time input uses future information: tone comes from
  pre-season notes, market rank from pre-season boards; results only
  ever appear on the outcome side.
- The 2025 season was complete before scoring, but the scorer agents
  saw only note text. A scorer with background knowledge of 2025
  outcomes could in principle leak hindsight into tone — mitigated by
  the rubric forcing judgments from the text's own framing; residual
  risk acknowledged. Note the leak would *flatter* the notes, and they
  still showed no positive edge.
- Simulation opponents, waivers, and scoring are league-sim's family
  calibration, unmodified. Strategy code adds only the tone term.

## Known limitations

- Two seasons. Effects of ±10–20 season points are at the edge of what
  two years can resolve; single-cell significances (8 strategy-year
  cells) deserve skepticism.
- Tone is one number per player; the test says nothing about the value
  of specific *facts* in the files (depth-chart notes, injury news),
  only about directional hype.
- The simulator's bots approximate the family, not the real room; PF
  deltas transfer as rough magnitudes (baseline ≈ 1,130–1,155 PF, so
  20 PF ≈ 1.7%).
- LLM tone scoring is single-pass; rescoring would jitter ±1 cases.

## Bug found and fixed during the study

The first run collapsed same-named files across years (dropped
duplicates by filename), so the 198 dual-year players reused their 2024
tone in the 2025 analysis. Fixed by keying scores on (year, filename);
both experiments rerun. All committed results are from the corrected
pipeline.
