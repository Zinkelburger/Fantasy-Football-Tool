"""
Unified NFL Injury Predictor
Predicts probability a player will play based on practice participation (Days 1-3)
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score, classification_report
import pickle
from pathlib import Path

class InjuryPredictor:
    """
    Predicts whether an injured player will play based on practice progression
    """

    def __init__(self, use_position_specific=False):
        """
        Args:
            use_position_specific: If True, train separate models per position
        """
        self.use_position_specific = use_position_specific
        self.models = {}
        self.status_map = {
            'Full': 2,
            'Limited': 1,
            'DNP': 0,
            '--': -1,
            '': -1,
            np.nan: -1
        }

    def _engineer_features(self, df):
        """Create practice progression features"""
        # Encode practice status for each day
        df['day_1_encoded'] = df['day_1_status'].map(self.status_map).fillna(-1)
        df['day_2_encoded'] = df['day_2_status'].map(self.status_map).fillna(-1)
        df['day_3_encoded'] = df['day_3_status'].map(self.status_map).fillna(-1)

        # Practice progression features
        df['practice_trend'] = df['day_3_encoded'] - df['day_1_encoded']
        df['final_practice_status'] = df['day_3_encoded']
        df['avg_practice_status'] = df[['day_1_encoded', 'day_2_encoded', 'day_3_encoded']].replace(-1, np.nan).mean(axis=1).fillna(-1)
        df['num_practice_days'] = ((df['day_1_encoded'] > 0) +
                                    (df['day_2_encoded'] > 0) +
                                    (df['day_3_encoded'] > 0))
        df['progression_pattern'] = (df['day_1_status'].fillna('--') + '->' +
                                      df['day_2_status'].fillna('--') + '->' +
                                      df['day_3_status'].fillna('--'))

        # Target: Did they play?
        df['game_status_clean'] = df['game_status'].fillna('--')
        df['played'] = (~df['game_status_clean'].str.contains('Out', case=False, na=False)).astype(int)

        return df

    def _build_pipeline(self):
        """Build sklearn pipeline"""
        categorical_transformer = OneHotEncoder(
            handle_unknown='ignore',
            sparse_output=False,
            max_categories=50
        )

        preprocessor = ColumnTransformer(
            transformers=[
                ('cat', categorical_transformer, self.categorical_features),
                ('num', 'passthrough', self.numeric_features)
            ],
            verbose_feature_names_out=False
        )

        hgb = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=200,
            max_depth=6,
            random_state=42,
            min_samples_leaf=20
        )

        calibrated_model = CalibratedClassifierCV(hgb, method='isotonic', cv=5)

        return Pipeline([
            ('preprocessor', preprocessor),
            ('classifier', calibrated_model)
        ])

    def train(self, csv_path='injury_predictor/nfl_injuries_2021_2025.csv',
              positions=['QB', 'RB', 'WR', 'TE', 'K']):
        """
        Train the model(s)

        Args:
            csv_path: Path to injury data CSV
            positions: List of positions to include
        """
        print("🏈 Loading injury data...")
        df = pd.read_csv(csv_path)

        # Engineer features
        df = self._engineer_features(df)

        # Filter positions
        df = df[df['position'].isin(positions)].copy()
        df = df.dropna(subset=['injury', 'position'])

        print(f"Loaded {len(df)} injury reports for positions: {positions}")
        print(f"Play rate: {df['played'].mean():.1%}")

        # Define features
        self.numeric_features = [
            'week',
            'day_1_encoded',
            'day_2_encoded',
            'day_3_encoded',
            'practice_trend',
            'final_practice_status',
            'avg_practice_status',
            'num_practice_days'
        ]

        if self.use_position_specific:
            # Train separate model per position
            self.categorical_features = ['injury', 'progression_pattern']

            for position in positions:
                print(f"\n{'='*80}")
                print(f"Training model for: {position}")
                print('='*80)

                pos_df = df[df['position'] == position].copy()

                if len(pos_df) < 50:
                    print(f"Not enough data ({len(pos_df)} samples), skipping...")
                    continue

                X = pos_df[self.numeric_features + self.categorical_features]
                y = pos_df['played']

                # Check class balance
                if y.value_counts().min() < 10:
                    print(f"Not enough minority class samples, skipping...")
                    continue

                # Split
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42, stratify=y
                )

                # Build and train pipeline
                pipeline = self._build_pipeline()
                pipeline.fit(X_train, y_train)

                # Evaluate
                probs = pipeline.predict_proba(X_test)[:, 1]
                auc = roc_auc_score(y_test, probs)

                print(f"Training: {len(X_train)} | Test: {len(X_test)}")
                print(f"ROC AUC: {auc:.4f}")

                self.models[position] = pipeline

        else:
            # Train unified model with position as feature
            self.categorical_features = ['position', 'injury', 'progression_pattern']

            print(f"\n{'='*80}")
            print("Training UNIFIED model (all positions)")
            print('='*80)

            X = df[self.numeric_features + self.categorical_features]
            y = df['played']

            # Split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Build and train pipeline
            pipeline = self._build_pipeline()
            pipeline.fit(X_train, y_train)

            # Evaluate
            probs = pipeline.predict_proba(X_test)[:, 1]
            preds = pipeline.predict(X_test)

            auc = roc_auc_score(y_test, probs)
            brier = brier_score_loss(y_test, probs)

            print(f"\nTraining: {len(X_train)} | Test: {len(X_test)}")
            print(f"ROC AUC: {auc:.4f}")
            print(f"Brier Score: {brier:.4f}")
            print("\nClassification Report:")
            print(classification_report(y_test, preds, target_names=['Sat Out', 'Played']))

            self.models['unified'] = pipeline

        print(f"\n✅ Training complete! Trained {len(self.models)} model(s)")

    def predict(self, player_data):
        """
        Predict probability to play

        Args:
            player_data: Dict or DataFrame with player injury info

        Returns:
            Probability to play (0-1)
        """
        if isinstance(player_data, dict):
            player_data = pd.DataFrame([player_data])

        # Ensure all required features are present
        required = self.numeric_features + self.categorical_features
        missing = set(required) - set(player_data.columns)
        if missing:
            raise ValueError(f"Missing required features: {missing}")

        X = player_data[required]

        if self.use_position_specific:
            # Use position-specific model if available
            position = player_data['position'].iloc[0]
            if position in self.models:
                return self.models[position].predict_proba(X)[:, 1][0]
            else:
                raise ValueError(f"No model trained for position: {position}")
        else:
            # Use unified model
            return self.models['unified'].predict_proba(X)[:, 1][0]

    def save(self, filepath='injury_predictor/model.pkl'):
        """Save model to disk"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)
        print(f"💾 Model saved to {filepath}")

    @staticmethod
    def load(filepath='injury_predictor/model.pkl'):
        """Load model from disk"""
        with open(filepath, 'rb') as f:
            model = pickle.load(f)
        print(f"📂 Model loaded from {filepath}")
        return model


def main():
    """Main execution"""
    print("="*100)
    print("NFL INJURY PREDICTOR - Unified Model")
    print("="*100)

    # Train unified model
    print("\n1️⃣  Training UNIFIED model (recommended)...")
    print("-"*100)
    unified_model = InjuryPredictor(use_position_specific=False)
    unified_model.train()
    unified_model.save('injury_predictor/unified_model.pkl')

    # Demo predictions
    print("\n" + "="*100)
    print("DEMO PREDICTIONS")
    print("="*100)

    scenarios = [
        {
            'name': 'WR - Hamstring - Limited all week',
            'data': {
                'week': 10,
                'day_1_encoded': 1, 'day_2_encoded': 1, 'day_3_encoded': 1,
                'practice_trend': 0,
                'final_practice_status': 1,
                'avg_practice_status': 1.0,
                'num_practice_days': 3,
                'position': 'WR',
                'injury': 'Hamstring',
                'progression_pattern': 'Limited->Limited->Limited'
            }
        },
        {
            'name': 'RB - Ankle - DNP to Full',
            'data': {
                'week': 12,
                'day_1_encoded': 0, 'day_2_encoded': 1, 'day_3_encoded': 2,
                'practice_trend': 2,
                'final_practice_status': 2,
                'avg_practice_status': 1.0,
                'num_practice_days': 2,
                'position': 'RB',
                'injury': 'Ankle',
                'progression_pattern': 'DNP->Limited->Full'
            }
        },
        {
            'name': 'QB - Knee - Full to DNP (declining)',
            'data': {
                'week': 8,
                'day_1_encoded': 2, 'day_2_encoded': 1, 'day_3_encoded': 0,
                'practice_trend': -2,
                'final_practice_status': 0,
                'avg_practice_status': 1.0,
                'num_practice_days': 2,
                'position': 'QB',
                'injury': 'Knee',
                'progression_pattern': 'Full->Limited->DNP'
            }
        },
        {
            'name': 'K - Groin - DNP all week',
            'data': {
                'week': 5,
                'day_1_encoded': 0, 'day_2_encoded': 0, 'day_3_encoded': 0,
                'practice_trend': 0,
                'final_practice_status': 0,
                'avg_practice_status': 0.0,
                'num_practice_days': 0,
                'position': 'K',
                'injury': 'Groin',
                'progression_pattern': 'DNP->DNP->DNP'
            }
        },
    ]

    for scenario in scenarios:
        prob = unified_model.predict(scenario['data'])
        print(f"\n{scenario['name']}")
        print(f"  → Probability to PLAY: {prob:.1%}")


if __name__ == '__main__':
    main()
