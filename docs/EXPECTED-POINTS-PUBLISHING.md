# Expected points publication

Public home: https://andrewbernal.com/football/expected-points/
Methodology: https://andrewbernal.com/football/expected-points/methodology/
Website source: `../Andrew-Bernal-Website` (Astro, Cloudflare Pages).
Model: finding 39 (`engine/league-sim/findings/39-opportunity-scores.md`),
code in `engine/weekly/ep_model.py` and `engine/weekly/opportunity.py`.

## What is published

Per player: role value (EWMA of expected points, α = 0.35, seeded from the
prior season), expected and actual points per game, the gap, usage per game,
and the upcoming week's opponent and market-implied team total. Top 40 QB,
70 RB, 90 WR, 40 TE by half-PPR role value, in standard, half and full PPR.
The numbers are exactly the `skill` rows of `data/weekly/latest.json`; the
website script adds ranks and provenance, nothing else.

## Weekly steps

1. Wait for the Tuesday `weekly.yml` build (10:00 UTC) or run
   `.venv-league-sim/bin/python engine/weekly/build_week.py` yourself after the
   Monday night game is in nflverse. The Saturday build and a Monday run are
   pregame for the week in progress and miss Monday night: check that
   `opportunity_<season>_weekly.csv` has all 32 teams for the completed week.
2. Commit `data/weekly/` here first, so the edition records the commit.
3. In the website repo run
   `python3 scripts/refresh-expected-points.py --season YEAR --through-week N
   --source /ABSOLUTE/PATH/Fantasy-Football-Tool/data/weekly`. It refuses a
   bundle with a team missing from any week 1..N or with weeks after N, and
   never overwrites an existing edition.
4. Add `src/pages/football/expected-points/YEAR/week-N.astro` importing the new
   edition file, run the website tests and `npm run build`, inspect desktop and
   mobile, commit, push, and verify the live URLs.

## Rules

- Never edit a published edition. Corrections are a new dated edition.
- Expected points are usage only. Do not blend ESPN projections, matchup
  multipliers or injury news into the published number; those belong in the
  private advisor. The page shows the implied team total beside the number.
- Methodology numbers on the site (held-out R², season r, next-week r,
  ffverse comparison) are finding 39's, re-verified 2026-09-15 from the cached
  2021–2025 play-by-play. Refitting the model (`ep_model.py fit`) means
  re-running that check and updating both the finding and the page.
- Subvertadown comparison: his .93–.97 back-tested correlations are
  season-level; ours are held-out season-level .92–.97. Say "same range", not
  "better". No per-game benchmark on matched coverage exists.
- Keep public pages about all players, never a private roster or league.
