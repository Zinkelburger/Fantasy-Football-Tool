# Advanced-feature model evaluation — September 16, 2026

Keep the existing expected-points coefficients. None of the tested additions established a reliable next-week improvement on confirmation data. Display the new stats as context.

## Protocol

Five feature sets were specified before evaluating results: target share; catchable target count and rate; drop count and rate; rushing yards before contact and per-carry rate (RB only); and their combination. Each extends the existing position-specific OLS usage model. All candidates and the baseline use identical training years and populations. Training-only means plus missingness indicators handle unavailable fields. Scores are floored at zero, as in production.

Training: 2022–2023 to validate on 2024; 2022–2024 to confirm on 2025. FTN starts in 2022, so these comparison fits use a shorter history than the current production fit (2021–2025). Coefficients never use outcomes from their evaluated season. The production model file was not refit. Three scoring formats: standard, half PPR and PPR; QB models were not candidates.

Primary outcome: mean absolute error (MAE) for the next calendar week, using the production 35% EWMA and prior-season seed, recomputed from each candidate’s scores. Future game usage is never an input to the forecast. The report also includes same-game fit, RMSE, bias and trailing-four-game forecasts. The next-week primary comparison requires a recorded usage row in both weeks and the same team. Byes, season boundaries and known next-week team changes are excluded.

A separate sensitivity population adds zero for missing next-week usage when the player’s previously observed team plays. This is an inferred zero-usage scenario, not a verified active-roster/DNP model. It cannot identify injury, retirement or transaction status and is not a complete start/sit accuracy evaluation. Historical final charting cannot establish that those labels were available at Tuesday decision time.

Selection: lowest 2024 half-PPR next-week EWMA MAE per position. Adoption requires at least 0.05-point improvement in validation AND confirmation, a confirmation player-bootstrap 95% interval wholly below zero for candidate-minus-baseline MAE, at most 0.02-point RMSE regression, and no >0.02 MAE regression in other formats or the zero-usage sensitivity. Only the validation-selected candidate is eligible; the other 2025 results are diagnostic. The 0.05-point threshold is a small practical floor, not a claim of statistical significance. Bootstrap uses 2,000 resamples of players with all their cases together, seed 916.

## Confirmation results for validation-selected candidates

Half PPR, 2025. Lower error is better. Positive gain means improvement.

| Position | Selected on 2024 | Cases | Baseline MAE | Candidate MAE | Gain | Candidate − baseline 95% interval |
|---|---|---:|---:|---:|---:|---|
| RB | contact | 1035 | 4.873 | 4.869 | +0.003 | -0.049 to +0.048 |
| WR | catchability | 1553 | 4.435 | 4.403 | +0.032 | -0.093 to +0.021 |
| TE | target_share | 767 | 3.630 | 3.631 | -0.001 | -0.015 to +0.017 |

All three confirmation intervals include zero. None passes the adoption gate, even if we disregard the practical 0.05-point floor.

## Every candidate: 2025 next-week MAE

Half PPR. This diagnostic table does not reselect a winner on the confirmation year.

| Position | Baseline | Target share | Catchability | Drops | Contact | Combined |
|---|---:|---:|---:|---:|---:|---:|
| RB | 4.873 | 4.877 | 4.880 | 4.871 | 4.869 | 4.872 |
| WR | 4.435 | 4.424 | 4.403 | 4.437 | — | 4.398 |
| TE | 3.630 | 3.631 | 3.644 | 3.632 | — | 3.650 |

## Why a better same-game fit is insufficient

For WRs, catchability lowers 2025 same-game half-PPR MAE from 2.955 to 2.337 points, but its next-week gain is only 0.032 with an interval spanning no improvement. The combined model improves the same-game fit further, but was not the validation-selected WR candidate and its confirmation interval also crosses zero. For RBs, contact yards lower same-game MAE from 3.085 to 2.718, while the next-week gain is only 0.003. These fields explain what happened after a play began; that alone does not establish a better measure of future role value.

This experiment tests these feature sets in our existing interpretable scoring architecture. It does not show that the information can never help a different model, nor validate an injury-aware lineup optimizer. Direct lagged nonlinear models, route participation and other providers were not tested. Avoid tuning repeatedly against the 2025 confirmation outcomes. Retain 2026 as prospective evidence, with source availability snapshots.

## Sources, reproducibility and implementation

Public nflverse PBP/player stats, FTN charting, PFR weekly advanced rushing and the PFR/GSIS crosswalk. Downloaded 2022–2025 FTN/PFR files successfully without credentials. Exact source hashes, missing-field coverage, training/test counts, every scoring-format result and uncertainty are saved in `advanced-model-audit-2026-09-16.json`. Current descriptive export contains 309 skill player rows, including 251 targeted players with complete FTN labels and 101 matched contact-yard records.

```bash
.venv-league-sim/bin/python research/opportunity-score/test_advanced_models.py
.venv-league-sim/bin/python research/opportunity-score/test_advanced_evaluation.py
```

Historical PBP/player stats, FTN and PFR must be cached before the audit; the audit itself makes no network calls. The current export refresh is `engine/weekly/advanced_usage.py --season 2026 --refresh`. The normal weekly build now refreshes optional charting and writes the export after expected points, reusing the same PBP/stat cache. Website publication validates counts and the export hash, creates a new dated edition and preserves previous editions. Target share is player targets divided by all identified team targets; season display uses ratio of totals in games with recorded player usage. Missing/partial charted totals remain null, rather than becoming zeros or a biased average of only covered games.
