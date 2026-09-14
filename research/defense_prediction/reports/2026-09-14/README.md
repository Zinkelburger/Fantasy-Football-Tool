# Full-season defense outlook: source and feasibility audit

Checked September 14, 2026. Open `season-outlook.html` for the 32-team × 18-week
matchup table. Each cell distinguishes fresh market totals, archived lookahead
lines, missing forecasts, and byes. Nothing here replaces a preserved pregame
edition on andrewbernal.com.

## Where the implied totals come from

For a defense with sportsbook spread S and game over/under T:
**opponent implied points = (T + S) / 2**. A defense favored by 8 in a 40-point
game faces an opponent implied to score 16. This is arithmetic on betting lines,
not an ESPN fantasy projection. nflverse's `spread_line` uses the opposite sign
for the home team; convert before applying this formula.

Our current production inputs are ESPN-distributed market odds, nfelo-distributed
market odds, and nflverse schedule lines. The distribution source is not the
prediction author: nfelo's `home_line_close` is the market spread, whereas
`nfelo_home_line_close` is nfelo's market-adjusted model spread. `total_line_close`
is a market game total, not an nfelo-generated total.

## Actual coverage

| Source | Coverage found |
|---|---|
| Fresh nflverse schedule | 272 games; spread + total for all 16 Week 1 and 16 Week 2 games; none Week 3–18 |
| nfelo `nfelo_games.csv` | 16 games in 2026, all Week 1; model spreads and market totals |
| nfelo `elo_snapshot.csv` | 32 teams, tagged 2026 Week 1 |
| Older repo schedule, committed August 4 | Adds archived lines for all 16 Week 3 games and 3 Week 4 games; not current odds |
| Older Odds API research | Finding 26 says an August 3 fetch covered all 272 games; derived 17-game team averages remain, but raw event snapshot was not found |
| Current Odds API check, 16:52–16:53 UTC | Key verified. US, US2, EU, UK and AU all return the same 17 games: tonight's Week 1 finale and all 16 Week 2 games. No Week 3–18 lines. The free events endpoint also lists only these 17 games. |

The old season averages cannot recover the individual 272 game lines. The Odds
API is now connected locally; its current endpoint exposes upcoming games
with whatever lines bookmakers offer. It does not guarantee every future game
has a spread and total on every retrieval. Today's observation does not disprove
the August notes, but those notes are not evidence of current full-season coverage.

## Authenticated check and operating budget

The key is saved in ignored `engine/league-sim/.env`, mode 0600. Both the existing
market tool and weekly environment loader can read it. No key is stored in this
report, HTML, snapshots, or source control.

| Request | Credits | Remaining |
|---|---:|---:|
| Sports / key verification | 0 | 500 |
| NFL spreads + totals, US | 2 | 498 |
| NFL event list | 0 | 498 |
| NFL spreads + totals, US2/EU/UK/AU | 8 | 490 |

The US response has nine bookmaker IDs, with eight or nine complete pairs per
game. We calculate each bookmaker's implied team score from its own spread and
total, then take the median. Both market update timestamps remain in the audit;
they need not be identical. These are conventional market-implied points, not
exact statistical expectations or fantasy-point forecasts. Bookmaker observations
are correlated; nine books do not mean nine independent models.

US consensus at retrieval: SF vs MIA **16.0**, PHI at TEN **16.25**, TB vs CLE
**16.25** opponent points. This is a new source/time comparison, not a rewrite of
the already published Week 2 edition. SF now narrowly leads; a quarter-point
difference is small and can move. Equal numbers retain tied ranks.

For routine updates, the existing tool now supports:

```bash
.venv-league-sim/bin/python engine/league-sim/analysis/market_implied.py snapshot
```

This explicitly spends 2 credits and preserves a dated US spreads/totals response
in `engine/weekly/cache/odds-api-audit/`. Replaying/auditing saved data costs zero:

```bash
python3 research/defense_prediction/audit_odds_api.py
python3 research/defense_prediction/audit_nfelo_outlook.py
```

One refresh daily is 60–62 credits/month; three per week is about 26/month.
Do not fetch per team/game for these markets, add unused moneylines, or fetch
all regions routinely. Website builds should consume saved data, never make an
API request per visitor. No recurring job was created during this audit.

The documentation says historical odds require a paid plan and cost 10 credits
per market per region (20 for a spreads/totals snapshot). No historical request
or subscription upgrade was made. Date filters restrict posted events; they do
not generate lines for an arbitrary future week. There is no NFL-week parameter;
join event teams and kickoff dates to the nflverse schedule, as this audit does.

`odds-api-audit.json` contains request parameters without credentials, quota
receipts, source hashes, all same-book pairs, game IDs, and tied defense ranks.
The original API envelopes remain in the ignored cache for exact replay.

## Existing scoring-model alternatives

[DRatings](https://www.dratings.com/predictor/nfl-football-predictions/) does
publish separate team scores and game totals: its September 17 page, checked
today, projects Detroit 23.8 and Buffalo 26.9 (50.7 total). This is a real existing
score forecast, unlike interpreting nfelo's margin as a total. However, the
public results table reports winner/log-loss performance, which does not
validate team-score or fantasy-defense accuracy. Its
[methodology](https://www.dratings.com/methodology/) describes ratings and win
probabilities but does not supply a reproducible full-season scoring model.
No supported public full-season score API or full-season game-score export was
verified. Treat it as a possible comparison source, not a proven drop-in fallback.

Recommendation: use Odds API market consensus for available games, retain
nfelo/nflverse as public comparison sources, and keep future cells unknown until
we obtain actual lookahead lines or validate an existing score forecast. There
is no need to build a new scoring model to operate the weekly defense workflow.

## Is nfelo the same as market lines?

No. Its raw model uses Elo strength and game adjustments, translates that into
a spread, and then regresses toward opening/closing market lines. Current
upstream code deliberately suppresses small disagreements. It is not an
independent future-bookmaker-line model trained to predict the eventual close;
it predicts game outcomes with market information included.

Matched 4,431 regular-season games, 2009–2025, using normalized game IDs and
identical coverage for every calculation:

| Measure | Market | nfelo spread + same market total |
|---|---:|---:|
| Mean absolute game-margin error | 10.130 | 10.117 |
| Mean absolute team-score error | 7.374 | 7.365 |

The final model spread equals the market in 59.99% of games; mean absolute
spread difference is 0.550 points. Tiny numerical gains do not demonstrate
meaningful superiority. These are retrospective, mutable historical files,
not an independently archived live test and not fantasy D/ST scores.
`historical-pairs.json` provides every matched row; `audit.json` has exact metrics
and source hashes. Reproduce with `python3 research/defense_prediction/audit_nfelo_outlook.py`
using the downloaded files in `engine/weekly/cache/nfelo-audit/`.

## Can we project defenses for the whole season?

Yes, with explicit provenance for each game:

1. **Current market:** paired spread and total, preferably from the same bookmaker
   and update time; derive each bookmaker's opponent total, then take the median.
2. **Archived market:** keep the old date visible; do not silently promote an
   August estimate to today's price. Prefer refreshed market data when available.
3. **Model estimate:** if no market exists, project opponent points from a
   separately tested offense/defense scoring model. nfelo's team ratings can
   contribute to the expected margin, but they do not determine the game total.
   A fixed league-average total would conflate good offenses and good defenses.
4. **Unknown:** show matchup without a number when evidence is insufficient.

The table can then support next-3/4-week averages, fantasy-playoff weeks 15–17,
byes and complementary two-defense schedules. Exclude byes from game averages;
show coverage counts so teams with missing hard matchups don't look superior.
Use actual market opponent totals for this week's selection, consistent with
finding 27. Label long-range estimates experimental until tested.

Validation must freeze each team's inputs at the historical decision date.
Compare errors versus the eventual market line AND actual fantasy D/ST results
at each forecast horizon (1, 2, 4, 8+ weeks). Never use the season's final ratings
or eventual closing total to generate an earlier forecast. Assess nfelo-based
alternatives on the same games/scoring; use confidence intervals clustered by
week/season. Our historical finding 27 using closing lines does not validate
this new long-range extension automatically.

## Primary sources

- [nfelo output data](https://github.com/greerreNFL/nfelo/tree/main/output_data)
- [nfelo model source](https://github.com/greerreNFL/nfelo/blob/main/nfelo/Model/Nfelo.py): `project_spreads` selects the next unplayed week, not all future weeks.
- [nfelo output formatter](https://github.com/greerreNFL/nfelo/blob/main/nfelo/Formatting/NfeloFormatter.py): distinguishes model output from market spread/total columns.
- [Current market-regression implementation](https://github.com/greerreNFL/nfelo/blob/main/nfelo/Utilities/MarketRegression/README.md)
- [nfelo power-rating explanation](https://www.nfeloapp.com/nfl-power-ratings/)
- [nflverse schedule data](https://github.com/nflverse/nfldata/blob/master/data/games.csv)
- [The Odds API NFL coverage](https://the-odds-api.com/sports-odds-data/nfl-odds.html)
- [The Odds API endpoint documentation](https://the-odds-api.com/liveapi/guides/v4/)
