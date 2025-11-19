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

Class 1 (Played) Recall: 0.98: Your model captures 98% of the players who actually played. It almost never misses a starter.

Class 0 (Didn't Play) Recall: 0.56: This is the trade-off. It only catches 56% of the players who sat out.
