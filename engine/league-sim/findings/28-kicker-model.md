# 28 — Kicker weekly model: half as predictable as D/ST, and skill isn't the signal

**Confidence: High.** 4,215 kicker-weeks, 8 seasons, LOYO.

Kickers are the least predictable position in fantasy. The kicker
himself is the least important part of the prediction.

Ranking kickers by their own scoring history barely beats guessing
(.079). Adding Vegas lines, weather and coach tendencies reaches .186
— still half as predictable as defenses. The model ladder (within-week
Spearman, ESPN scoring, tested on held-out seasons):

| model | Spearman | Pearson | MAE |
|---|---|---|---|
| naive (kicker's own ppg) | **.079** | .053 | 3.56 |
| Vegas (own implied total + win prob) | .164 | .158 | 3.53 |
| + weather (dome, wind) | .180 | .173 | 3.51 |
| **+ team traits (FG-drive share, TD-drive share)** | **.186** | .174 | 3.51 |
| + kicker form | .183 | .173 | 3.51 |

- **The kicker himself is nearly irrelevant** (.079 naive; his form
  adds nothing to the full model) — finding 04's "kickers are noise"
  quantified. Kicker points are a *situation*, so stream the
  situation.
- The situation = **win probability** (+4.9 pts per unit — winning
  teams kick), **dome** (+0.7), **wind** (−0.5), and two coach/team
  traits: share of drives ending in FG attempts (+5.1 — the
  stall/aggressiveness trait) and TD share (−2.9 — great offenses
  steal PAT-only games from their kicker).
- Ceiling is low everywhere: best model .186 within-week rank corr,
  **half of D/ST's .304** (finding 27). Do not agonize between
  comparable kickers. The model is a tilt, not an answer.

## vs subvertadown

His published K material (see Attribution) matches on every axis we
can check:

- He calls kickers the least predictable position ("predictability ~
  individual WR1s").
- He reports average score ~7.5 with typical error ±3. Ours: mean 8.1
  ESPN scoring, MAE 3.51.
- He names win chance, coaching aggressiveness and dome/wind as
  inputs. All three carry real coefficients here.
- He claims his model beats "normal kicker models, represented by
  betting line accuracy." Our ladder confirms that direction and sizes
  it: everything beyond Vegas is worth **+0.02 rank corr**.

His kicker page shows no free numeric ranks, unlike D/ST's top-2,
which matched us exactly. So the head-to-head goes through the
September accuracy log like everything else.

## Methodology

`analysis/kicker_model.py`. Targets from weekly stat parquets (FG
distance bins + PATs). Vegas from `games.csv` (implied total,
devigged moneyline win prob, roof, wind). Team traits from pbp drives
(`fixed_drive_result`): FG-attempt share and TD share of drives,
season-to-date with a 4-game prior-season blend. OLS ladder, LOYO by
season.

## Caveats

- ESPN distance scoring only; per-platform configs needed for the
  site (Yahoo differs slightly at 0-19).
- No FG% / leg-strength modeling (subvertadown's "long FGs are a real
  trait") — a possible +epsilon, bounded by the .186 → ~.20 ceiling
  his own material implies.
- Closing lines; Tuesday decisions see softer numbers.
