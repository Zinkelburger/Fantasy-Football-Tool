# Defense publication and accuracy

Public home: https://andrewbernal.com/football/defense/
Accuracy: https://andrewbernal.com/football/defense/accuracy/
Website source: `../Andrew-Bernal-Website` (Astro, Cloudflare Pages).
The website repository's `AGENTS.md` owns its publishing instructions.

## Weekly decisions

1. Follow `engine/weekly/RESEARCH.md`; verify league scoring and actual available
   defenses. Explicitly request the upcoming week when planning Monday waivers.
2. Refresh stale weekly data. Our model sorts opponent implied NFL points
   ascending; these are not projected fantasy points. Equal totals are ties.
3. Follow finding 27 (`engine/league-sim/findings/27-dst-model.md`), not ESPN
   fantasy projections. Never use ESPN projections to rank or break a tie.
   ESPN is a source for league availability, scoring rules, and actual results;
   ESPN-distributed market spreads/totals are also valid market inputs.
   Equal opponent totals mean no meaningful model preference. Use verified
   next-week matchup value or acquisition cost to choose between tied options;
   without that evidence, report the tie. Alphabetical order is display only.
   Review next-week matchups before recommending a second defense on the bench.
4. Do not use an injured player's old usage value as an immediate pickup case.
   Verify current role and availability; flag unsupported or missing evidence.

## Publication

- Odds API key is local in ignored `engine/league-sim/.env`; never put it in
  URLs in reports, public website files, browser code, or tracked configuration.
- Use existing `engine/league-sim/analysis/market_implied.py snapshot` to preserve
  US spreads + totals (2 credits per refresh). Monthly budget is 500 credits;
  record returned quota headers and reuse snapshots for analysis/builds.
  Extra regions, moneylines, historical requests, and player props are separate
  costs, not part of a routine defense refresh. Never fetch on page visits.
- Pair spread and total within each bookmaker and retain their update times;
  derive opponent points per book before taking the median. Verify week and
  kickoff, show source time, and leave unposted future lines unknown. Existing
  market/model sources come before developing a new scoring model. nfelo's
  model spread alone is insufficient to recover a team score.

- In the website repo use `python3 scripts/refresh-defenses.py --season YEAR
  --week WEEK --odds-snapshot /ABSOLUTE/PATH/TO/SAVED-nfl-odds.json`. Reuse a
  snapshot less than 24 hours old. The explicit snapshot path prevents silent
  source changes: incomplete requested-week coverage stops publication.
  Omitting the flag is the legacy ESPN/nfelo/nflverse fallback, not the preferred
  Odds API workflow. It must be identified as a different source in the edition.
- Dated `/football/defense/editions/SLUG/` routes are generated from the preserved
  JSON files. The current board links its own `editionUrl`. Keep earlier
  `/YEAR/week-WEEK/` routes pinned; never silently move them to a later revision.
- Never refresh a pregame forecast after its games begin. Preserve published
  `src/data/editions/` and `public/data/defense/` snapshots. Corrections get a new
  timestamp, explanation, and edition. Never backdate a forecast.
- Add a preserved `/football/defense/YEAR/week-WEEK/` route for each new week;
  verify current/outlook links, attribution, missing lines, and editorial text.
- Public rankings describe all defenses, not private league rosters or managers.
- Build/test the website, inspect it at mobile and desktop sizes, then publish
  through its existing Git/Cloudflare deployment when authorized. Verify the
  live URL; a local build or Git push alone is not a verified deployment.

## Accuracy

- Run the website's `scripts/grade-defenses.py --snapshot PATH` against its
  preserved primary-week edition. It uses this repo's ESPN read client and
  public scoreboard status; exports contain only D/ST results and scoring.
- Label the scoring as custom ESPN league scoring, not default ESPN scoring.
  Retain scoring weights, forecast hash, retrieval time, and source links.
- Include every forecast. Exclude pending games/missing scores, preserve true
  zero and negative scores, and state the denominator and provisional status.
- Report tie-aware Spearman, top-five mean, and all-completed-defense mean.
  These are not accuracy percentages. Do not claim superiority to ECR or ESPN
  without a separately timestamped pregame benchmark on matched coverage.
- Rerun after the final game/stat corrections. Keep dated downloads and previous
  weeks; update only the current summary for the graded week.
- Week 1 baseline is the September 6, 2026 edition. Raiders were #3; their
  successful outcome is one observation, not proof of model quality.

## MCP maintenance

Both servers use `engine/mcp_launch.sh weekly|reddit`. Test a fresh stdio MCP
initialization and tool listing after server edits. This does not restart the
app's existing connections. Reconnect those in the app's MCP settings when
needed; do not kill all Python processes or claim a restart from a health check.
