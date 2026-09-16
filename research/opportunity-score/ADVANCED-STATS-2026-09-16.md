# Advanced stats review — September 16, 2026

We can obtain all the requested categories without buying a new data feed.
Add them as descriptive context first. There is no new evidence here that
changing our expected-points coefficients would improve future predictions.

## What the author is showing

The [matching WR post](https://www.reddit.com/r/fantasyfootball/comments/1whgkui/week_1_wr_stats_target_leaders/)
is F4NT4SYF00TB4LLF4N's 2026 Week 1 table. Its definitions and the JSN 46%
and Metcalf 204-air-yard discussion match the supplied screenshot. The post
does not identify a data supplier in the retrieved body/comments. The exact
source and collection method remain unverified. No message was sent to him.

His RB Opportunity is carries plus targets. His WR/TE lists are ordered by
targets. These are descriptive volume rankings, not the expected-fantasy-point
scores we publish. A target and a carry receive different values in our model,
and field position and target depth also matter.

## Sources we actually accessed

| Statistic | Source and implementation | Status |
|---|---|---|
| Carries, targets, catches, yards | Cached nflverse PBP / weekly player stats | Already held |
| Air yards, red-zone and end-zone targets | PBP; already in `ep_model.usage()` | Already used in expected points |
| Target share | Already present in cached player stats; export computes player targets / all identified team targets per game | Added to descriptive export |
| Catchable targets, drops | [FTN charting via nflverse](https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html), joined on game + play IDs | Downloaded 2,675 rows across all 16 Week 1 games; all 251 targeted skill players have complete labels |
| Rushing yards before contact | [PFR weekly advanced rushing via nflverse](https://nflreadr.nflverse.com/reference/load_pfr_advstats.html), joined through PFR/GSIS IDs + game/team | Downloaded 117 rows across 15 games; 101 skill players have a matched measurement |

`nflreadpy.load_ftn_charting([2026])` and
`nflreadpy.load_pfr_advstats(seasons=[2026], stat_type="rush", summary_level="week")`
both succeeded without credentials. PFR's season-level 2026 rushing table was
empty, so choosing weekly data is essential. PFR contact numbers for Gibbs
(112), Bijan (33), Jeanty (45), Henry (49) and Hall (58) match the screenshots.
That suggests a shared upstream source; it does not prove his download path.

[FTN's public subset](https://nflreadr.nflverse.com/reference/load_ftn_charting.html)
is manually charted, carries CC-BY-SA 4.0 and requires attribution to FTN Data
via nflverse. It contains catchability and drops, not yards before contact.
PFR and FTN are separate providers and their values must remain identifiable.
The FantasyPros advanced-stat pages were accessible, but returned no populated
HTML tables in this check. They were not verified as an automated data source.
No paid feed, scraping workaround or new account is required for this export.

## Screenshot comparison

This is a transparent spot check of the first six rows in each screenshot,
18 of 120 displayed players. The manually transcribed sample and reproduction
script live beside this report. Sample column names select our comparison
fields; they do not establish the screenshot's provider.

| Field | Exact agreement |
|---|---:|
| Targets and receptions | 18/18 each |
| RB opportunities, carries and rushing yards | 6/6 each |
| Receiving yards, rounded target share, strict <20 red-zone targets | 12/12 each |
| Air yards | 10/12 |
| Contact yards | 5/5 available; Walker unavailable |
| Catchable targets and drops vs FTN | 7/12 each |

Specific differences: JSN air yards 75 in screenshot vs 76 in our cached
nflverse; McBride 88 vs 89. McBride catchable targets 10 vs FTN 11; Metcalf
drops 1 vs FTN 2. These differences alone do not establish which observation
is correct; provider judgment, definitions and revision timing need checking.

All 12 sampled receivers' screenshot catchable counts equal receptions plus
drops. FTN's `is_catchable_ball` is a separate charted definition and does not
necessarily equal that sum. Never relabel receptions + drops as FTN catchable
targets or treat every incomplete pass as a drop.

Walker has 0 contact yards in the screenshot but no matching PFR row in our
download. We export null. The screenshot's Monday caveat explains why that
zero must not be interpreted as measured blocking performance.

Our model defines red zone as <=20 yards from goal; his note says <20.
The export retains both definitions, `tgt_rz` and `tgt_rz_lt20`. A target
thrown into the end zone from outside the red zone is an end-zone target
without being a red-zone snap. Air yards retain negative values and include
incomplete targets; they are different from yards before catch on receptions.

## Do our scores align?

The screenshots contain no new expected-points scores to compare. The saved
[September 15 audit](REVIEW-2026-09-15.md) compared his hosted 2024/2025 scores
against ours: descriptive Pearson correlation ranges from 0.900 to 0.990 by
position/year. That is broad agreement, with meaningful individual differences.

In that audit's temporal holdout, our preceding-four-game average had next-week
MAE lower by about 0.03–0.13 half-PPR points in all six comparisons; three of six
player-bootstrap intervals included zero. This is a small, uncertain advantage,
not proof of universal superiority. It evaluates trailing averages, not the
production EWMA, and excludes absent usage rows. No new forecasting backtest
was run for catchability/contact features in this task.

## Improvements to the process

1. Expose opportunity counts, target share and provider-labelled charted stats
   beside expected points. The engine export now provides these fields; the
   public website has not been changed or deployed.
2. Preserve unavailable/partial measurements as null. Record known-target
   counts, coverage, source hashes, cache timestamps and ID/carry mismatches.
   A source download covering a game does not by itself mean every field is ready.
3. Refresh descriptive context after games and recheck corrections Thursday.
   [nflverse's schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
   recommends the Wednesday-night/Thursday PBP refresh for corrections; FTN
   ingestion runs four times daily, while PFR advanced ingestion runs daily.
   Actual availability still depends on the providers. Refreshing these files
   does not update a previously published immutable edition.
4. Test lagged target share first for role forecasting; then catchability,
   drops and contact efficiency in separate ablations. Train on earlier years,
   evaluate future weeks/seasons and compare MAE, RMSE, calibration, lineup
   decisions and coverage using the same player-week population. Include
   DNP/zero-usage cases when evaluating start/sit outcomes and preserve the
   scoring format. Historical final charting alone cannot establish Tuesday
   availability; archive retrieval timestamps now for future evaluation.
5. Keep realized context separate from usage value. Catchability reflects QB
   accuracy, target difficulty and charting judgments; contact yards reflect
   blocking, defensive fronts and runner decisions. They are not automatic
   bonuses or penalties. Adding them to a same-game fit can explain outcomes
   without improving next week's forecast, and raw volume is already priced
   in the current expected-points model.

## Reproduce

```bash
.venv-league-sim/bin/python engine/weekly/advanced_usage.py --season 2026
.venv-league-sim/bin/python research/opportunity-score/compare_screenshot_sample.py
.venv-league-sim/bin/python -m unittest discover -s engine/weekly -p 'test_advanced_usage.py' -v
```

The first command is strictly cache-only. Add `--refresh` to fetch PBP, weekly
stats, FTN, PFR and the ID crosswalk. It writes
`data/weekly/advanced_usage_2026_weekly.csv` and a `.sources.json` manifest.
Optional feed failures are recorded; a retained cache is explicitly marked.
The export is a separate command, not yet part of the Tuesday/Saturday build.
Existing expected-points data, model coefficients and published editions remain
unchanged. Four focused tests cover denominator scope, red-zone boundaries,
negative air yards, missing/partial labels, duplicate plays and PFR carry checks.
