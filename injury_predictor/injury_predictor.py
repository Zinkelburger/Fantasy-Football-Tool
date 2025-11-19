import nflreadpy as nfl
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score, classification_report

# ==========================================
# 1. CONFIGURATION & LOADING
# ==========================================
SEASONS = [2021, 2022, 2023, 2024]

print(f"🏈 Loading NFL data for seasons: {SEASONS}...")

# Load Injury Reports
# Note: nflreadr/py injury data is typically one row per player-week (Final Report)
injuries = nfl.load_injuries(seasons=SEASONS).to_pandas()

# Load Weekly Stats (to calculate the Target: Did they actually play?)
stats = nfl.load_player_stats(seasons=SEASONS).to_pandas()

# ==========================================
# 2. DATA PREPROCESSING
# ==========================================
print("⚙️  Processing data...")

# --- A. Prepare Target Variable (Did they Play?) ---
# We check if the player exists in the weekly stats for that specific week
stats['played_game'] = 1
target_cols = ['season', 'week', 'player_id', 'played_game']
stats_reduced = stats[target_cols].drop_duplicates()

# Merge Injuries with Stats to get the Ground Truth
# Left join because we only care about players ON the injury report
df = pd.merge(
    injuries,
    stats_reduced,
    how='left',
    left_on=['season', 'week', 'gsis_id'],
    right_on=['season', 'week', 'player_id']
)

# If they didn't match in stats, they likely didn't play (or had 0 stats)
# We assume NaN in 'played_game' means they sat out (0)
df['played_game'] = df['played_game'].fillna(0).astype(int)

# --- B. Filter Irrelevant Positions ---
# We usually only care about fantasy-relevant positions for this model
relevant_positions = ['QB', 'RB', 'WR', 'TE']
df = df[df['position'].isin(relevant_positions)].copy()

# --- C. Feature Engineering ---

# 1. Clean Practice Status (Ordinal)
# Map string descriptions to integers: DNP=0, Limited=1, Full=2
practice_map = {
    'Did Not Participate In Practice': 0,
    'Limited Participation in Practice': 1,
    'Full Participation in Practice': 2
}
df['practice_status_encoded'] = df['practice_status'].map(practice_map)
# Fill missing practice status with -1 or keep NaN (HistGradientBoosting handles NaNs)
# We will keep NaNs as they might imply "Not listed on practice report but on injury report"

# 2. Clean Report Status (Categorical)
# Standardize status (sometimes 'Note' exists for minor issues)
df['report_status'] = df['report_status'].fillna('Unspecified')

# 3. Days Since Update (Proxy for "Freshness")
# If date_modified is available, calculate days since report relative to Sunday
# (Skipping complex date math for brevity, relying on status)

# ==========================================
# 3. MODEL SETUP
# ==========================================

# Define Features
NUMERIC_FEATURES = ['week', 'practice_status_encoded']
CATEGORICAL_FEATURES = ['position', 'report_status', 'report_primary_injury']

X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
y = df['played_game']

# Split Data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# --- Define Transformers ---
# Ordinal Features are already encoded as integers, but we want the model to treat them as numeric
# Categorical Features need One-Hot Encoding (handling unknown categories gracefully)
categorical_transformer = OneHotEncoder(handle_unknown='ignore', sparse_output=False)

preprocessor = ColumnTransformer(
    transformers=[
        ('cat', categorical_transformer, CATEGORICAL_FEATURES),
        ('num', 'passthrough', NUMERIC_FEATURES)
    ],
    verbose_feature_names_out=False
)

# --- Define Model ---
# HistGradientBoostingClassifier is excellent for this:
# - Handles NaNs natively (great for missing practice data)
# - Fast on large datasets
# - Often outperforms Random Forest for tabular data
hgb = HistGradientBoostingClassifier(
    learning_rate=0.1,
    max_iter=100,
    max_depth=5,
    random_state=42,
    # Monotonic constraint: We force the model to learn that
    # Higher Practice Status (0->2) should generally increase probability
    # monotonic_cst params depend on the column order after preprocessing,
    # which is tricky with OneHotEncoder, so we skip explicit constraints here for simplicity.
)

# Wrap in CalibratedClassifierCV for accurate probabilities
# "Isotonic" is usually better for large data, "Sigmoid" for smaller
calibrated_model = CalibratedClassifierCV(hgb, method='isotonic', cv=5)

pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', calibrated_model)
])

# ==========================================
# 4. TRAINING & EVALUATION
# ==========================================
print(f"🏋️  Training model on {len(X_train)} injury reports...")
pipeline.fit(X_train, y_train)

# Predict on Test Set
probs = pipeline.predict_proba(X_test)[:, 1]
preds = pipeline.predict(X_test)

print("\n📊 Model Evaluation:")
print(f"ROC AUC Score: {roc_auc_score(y_test, probs):.4f}")
print(f"Brier Score (Lower is better): {brier_score_loss(y_test, probs):.4f}")
print("\nClassification Report:")
print(classification_report(y_test, preds))

# ==========================================
# 5. DEMO: PREDICTING A HYPOTHETICAL PLAYER
# ==========================================
print("\n🔮 Demo Predictions:")

scenarios = pd.DataFrame([
    # Case 1: The "Questionable" WR with Limited Practice
    {'week': 10, 'practice_status_encoded': 1, 'position': 'WR', 'report_status': 'Questionable', 'report_primary_injury': 'Hamstring'},
    # Case 2: The "Doubtful" RB with DNP
    {'week': 14, 'practice_status_encoded': 0, 'position': 'RB', 'report_status': 'Doubtful', 'report_primary_injury': 'Knee'},
    # Case 3: The "Questionable" QB with Full Practice (Often plays)
    {'week': 5, 'practice_status_encoded': 2, 'position': 'QB', 'report_status': 'Questionable', 'report_primary_injury': 'Ankle'},
])

# Predict
scenario_probs = pipeline.predict_proba(scenarios)[:, 1]

for i, prob in enumerate(scenario_probs):
    print(f"Scenario {i+1}: {scenarios.iloc[i]['position']} | Status: {scenarios.iloc[i]['report_status']} | Practice: {scenarios.iloc[i]['practice_status_encoded']} -> Play Probability: {prob:.1%}")