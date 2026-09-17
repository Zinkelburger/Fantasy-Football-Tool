# Injury predictor — NOT USABLE, DO NOT MAKE DECISIONS WITH THIS

**Status: abandoned research. Not wired into the weekly engine, and it should
not be.** There is no trained `model.pkl` here, `unified_injury_predictor.py` is
not imported by anything in `engine/` or `webapp/`, and the numbers below do not
support using it. If you want a "chance to play" number, this does not give you
one you can trust. Read the official Wed–Fri practice reports and the Friday
game designation instead.

The only thing in this directory anything else depends on is
`panel_position_age.parquet`, which `engine/league-sim/analysis/bust_model.py`
reads as data. That dependency is on the panel, not on the predictor.

## Why it does not work

The headline metrics look respectable and are misleading:

| Metric | Value |
|---|---|
| ROC AUC | 0.8729 |
| Brier | 0.1287 |
| Accuracy | 0.81 |

The classification report is the real story:

| Class | Precision | Recall | Support |
|---|---|---|---|
| 0 — did not play | 0.95 | **0.56** | 562 |
| 1 — played | 0.77 | **0.98** | 843 |

It catches 98% of players who played and **56% of players who sat**. It has
largely learned the base rate — "a questionable player usually plays" — which is
true and nearly useless. The only question anyone asks an availability model is
*"will my guy sit?"*, and that is precisely the class it is close to a coin flip
on. AUC measures ranking across thresholds; it does not establish useful
recall at the threshold used for a lineup decision.

A 56% recall on the sit class also fails asymmetrically: the miss costs you a
zero in an active lineup slot, which is far more expensive than the upside of
correctly starting a player who was going to play anyway.

## The other, older problem

The feature set only considers Friday practice reports, which aren't that
useful. We want the week-by-week data.

And to get real facts from youtube videos: `youtube-transcript-api`

## Raw training output (2021–2024, 5619 injury reports)

```
🏈 Loading NFL data for seasons: [2021, 2022, 2023, 2024]...
⚙️  Processing data...
🏋️  Training model on 5619 injury reports...

📊 Model Evaluation:
ROC AUC Score: 0.8729
Brier Score (Lower is better): 0.1287

Classification Report:
              precision    recall  f1-score   support

           0       0.95      0.56      0.70       562
           1       0.77      0.98      0.86       843

    accuracy                           0.81      1405
   macro avg       0.86      0.77      0.78      1405
weighted avg       0.84      0.81      0.80      1405
```

## If this is ever revived

It needs, at minimum: week-by-week practice participation rather than Friday
only; evaluation reported on the sit class, not on AUC or accuracy; calibration
checked against the Friday game designation as a baseline; and a demonstration
that it beats "questionable plays, doubtful sits" before anything reads it.
