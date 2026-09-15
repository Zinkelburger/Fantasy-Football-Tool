# Expected points publication

Public home: https://andrewbernal.com/football/expected-points/
Methodology: https://andrewbernal.com/football/expected-points/methodology/
Website source: `../Andrew-Bernal-Website` (Astro, Cloudflare Pages).
Model: finding 39 (`engine/league-sim/findings/39-opportunity-scores.md`),
code in `engine/weekly/ep_model.py` and `engine/weekly/opportunity.py`.

## What is published

Per player: expected and actual points for every week played (with that
week's usage counts), season averages and totals, the average expected
points over the last four games, the actual-minus-expected gap, and role
value (EWMA of expected points, α = 0.35, seeded from the prior season).
All QB, RB, WR and TE with recorded usage are included, in standard, half
and full PPR, with 4- or 6-point passing touchdowns. The private advisor's
capped `skill` list must not control public coverage. Weekly, last-four,
season and recent averages come from the same full-precision
`opportunity_<season>_weekly.csv`; round only for display. The page offers
a weekly view and season average, with player details for weekly charts,
usage and the calculation. Next-week opponent and implied
team totals are deliberately not shown: they are not part of the number.

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
   mobile, commit, push, and verify the live URLs. For same-week corrections,
   leave that original route pinned and use the automatically generated dated
   edition route. Do not change prior snapshot bytes or their rendering.

For a scoring-only rebuild from saved data, use
`build_week.py --opportunity-only --season YEAR --week DECISION_WEEK`.
This never requests odds, injury news or ESPN rosters. It updates the usage
timestamp independently of saved market inputs. Commit the resulting bundle.

## Rules

- Never edit a published edition. Corrections are a new dated edition.
- Expected points are usage only. Do not blend ESPN projections, matchup
  multipliers or injury news into the published number; those belong in the
  private advisor.
- Methodology numbers on the site (held-out R², season r, next-week r,
  ffverse comparison) are finding 39's, re-verified 2026-09-15 from the cached
  2021–2025 play-by-play. Refitting the model (`ep_model.py fit`) means
  re-running that check and updating both the finding and the page.
- The current comparison is `research/opportunity-score/audit_public_scores.py`
  and its dated JSON/report, superseding the original comparison's exclusion
  of all zero scores and its in-sample next-week model. Credit the author,
  F4NT4SYF00TB4LLF4N, hosted by Subvertadown. High correlation does not mean
  identical values. Separate same-game description from next-week evaluation;
  fit our evaluation model only on earlier seasons. Include matched real zeros,
  record exclusions, show error in points and uncertainty. The author's own
  explanation confirms completed yards before catch for receivers. Do not
  infer feature usage, impossibility bounds or superiority from correlations.
- Six-point passing TDs use a separate OLS fit to actual points plus two per
  passing touchdown. Never multiply the total score by 1.5 or add observed TDs
  to expected points. Keep the original three advisor formats unchanged.
- Keep public pages about all players, never a private roster or league.
