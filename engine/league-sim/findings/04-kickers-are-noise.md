# 04 — Early-season kicker scoring predicts nothing

**Confidence: High.** Descriptive, every kicker 2020–2025.

A hot start tells you nothing about a kicker. The top scorer after
week 1 finished the rest of the season around **#19 of ~34 kickers**,
the middle of the pack. Even the best kicker through four weeks
rarely stays on top. Draft any kicker with your last pick, swap for
bye weeks, and never spend waiver priority chasing last week's hero.

## The data

| Year | Wk-1 top kicker | ROS rank | Wks 1–4 top kicker | ROS rank |
|---|---|---|---|---|
| 2020 | Matt Prater | #27 | Stephen Gostkowski | #26 |
| 2021 | Robbie Gould | #19 | Justin Tucker | #10 |
| 2022 | Younghoe Koo | #18 | Younghoe Koo | #23 |
| 2023 | Jake Elliott | #10 | Jake Elliott | #19 |
| 2024 | Jake Moody | #27 | Brandon Aubrey | #8 |
| 2025 | Spencer Shrader | n/a* | Spencer Shrader | n/a* |

\* Shrader didn't play enough games after week 1 to qualify. The
week-1 "hot kicker" of 2025 didn't even keep the job.

The full scatter — every kicker's weeks-1–4 rank vs rest-of-season
rank, all six years pooled — is
`figures/fig2_kicker_persistence.png`. A shotgun blast with no
visible diagonal.

The stakes are tiny anyway. K1 to K16 is about **3 points per game**
(see finding 07), the smallest spread of any position.

## Methodology

- Population: all kickers with weekly stat lines, 2020–2025 (~34/yr).
- "Top after week 1" = highest single-game week-1 score. "Top through
  4" = best PPG among kickers with ≥3 games played in weeks 1–4.
- "ROS rank" = rank by PPG over the remaining weeks, minimum 6 games
  played. That removes injury/cut noise, which *helps* the
  hot-kicker case by excluding Shrader-type flameouts. Persistence is
  still absent.
- Kicker scoring: league-exact (FG 3/4/5 by distance, XP 1). Data:
  nflverse FG distance splits.
- Reproduce: `venv/bin/python -m simfl analyze kickers`.

## Caveats

- Median-rank persistence isn't literally zero. Tucker 2021 and
  Aubrey 2024 — elite kickers on strong offenses — held up. Knowing
  the *offense* has some value; knowing last week's box score has
  none.
- Kickers do score points. K1 averaged 11.5 PPG, more than TE1. You
  just cannot *select* the good one early, so paying anything for the
  attempt is waste.
