#!/usr/bin/env python3

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from simple_oline_analysis import create_simple_oline_metrics

def run_f_test_validation():
    """Run F-test to validate % positive plays as predictor of mean yards"""

    # Get the data
    df = create_simple_oline_metrics()

    print('=== F-TEST VALIDATION: % POSITIVE PLAYS PREDICTING MEAN YARDS ===')
    print(f'Sample size: {len(df)} O-line players (2020-2024)')
    print()

    # Set up the regression
    X = df['pct_positive_plays'].values.reshape(-1, 1)
    y = df['mean_yards'].values
    n = len(df)

    # Fit the model
    model = LinearRegression().fit(X, y)
    r_squared = model.score(X, y)

    # Calculate F-statistic
    k = 1  # One predictor
    f_statistic = (r_squared / k) / ((1 - r_squared) / (n - k - 1))
    p_value = 1 - stats.f.cdf(f_statistic, k, n - k - 1)

    # Results
    print(f'STATISTICAL RESULTS:')
    print(f'R-squared: {r_squared:.4f} ({r_squared*100:.1f}% variance explained)')
    print(f'F-statistic: {f_statistic:.2f}')
    print(f'p-value: {p_value:.2e}')
    print(f'Degrees of freedom: {k}, {n-k-1}')
    print()

    # Significance interpretation
    if p_value < 0.001:
        significance = 'HIGHLY SIGNIFICANT (p < 0.001)'
    elif p_value < 0.01:
        significance = 'VERY SIGNIFICANT (p < 0.01)'
    elif p_value < 0.05:
        significance = 'SIGNIFICANT (p < 0.05)'
    else:
        significance = 'NOT SIGNIFICANT (p >= 0.05)'

    print(f'CONCLUSION: {significance}')
    print()

    # Practical interpretation
    slope = model.coef_[0]
    print(f'PRACTICAL IMPACT:')
    print(f'For every 1% increase in positive plays: +{slope:.3f} yards per play')
    print(f'Panthers (82.3%) vs Raiders (80.2%) difference: {slope * 2.1:.3f} yards per play')
    print()

    # Compare to mode
    X_mode = df['mode_yards'].values.reshape(-1, 1)
    model_mode = LinearRegression().fit(X_mode, y)
    r2_mode = model_mode.score(X_mode, y)

    print(f'COMPARISON TO MODE YARDS:')
    print(f'% Positive plays R²: {r_squared:.4f}')
    print(f'Mode yards R²: {r2_mode:.4f}')
    print(f'% Positive is {r_squared/r2_mode:.1f}x better at predicting mean yards')

    return {
        'r_squared': r_squared,
        'f_statistic': f_statistic,
        'p_value': p_value,
        'slope': slope,
        'is_significant': p_value < 0.05
    }

if __name__ == "__main__":
    results = run_f_test_validation()