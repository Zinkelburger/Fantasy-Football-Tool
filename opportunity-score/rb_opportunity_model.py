#!/usr/bin/env python3

import nflreadpy as nfl
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import warnings
import pickle
import os
warnings.filterwarnings('ignore')

def load_nfl_data(years=[2022, 2023, 2024]):
    """Load NFL play-by-play data"""
    print(f"Loading NFL data for years: {years}")
    # nflreadpy returns Polars DataFrames by default, convert to pandas
    pbp = nfl.load_pbp(seasons=years).to_pandas()
    print(f"Loaded {pbp.shape[0]:,} plays with {pbp.shape[1]} columns")
    return pbp

def prepare_rb_player_games(pbp):
    """Aggregate RB opportunities and performance by player-game (RBs only)"""

    # Fill NaN values with 0 for key columns
    fill_cols = ['rush_attempt', 'pass_attempt', 'complete_pass', 'rush_touchdown',
                 'pass_touchdown', 'fumble_lost', 'rushing_yards', 'receiving_yards',
                 'air_yards', 'yardline_100']
    for col in fill_cols:
        if col in pbp.columns:
            pbp[col] = pbp[col].fillna(0)

    # Create dataset for rushing plays (this defines our RB universe)
    rush_plays = pbp[
        (pbp['rush_attempt'] == 1) &
        (pbp['rusher_player_name'].notna()) &
        (pbp['play_type'] == 'run')
    ].copy()

    # Get unique RB names from rushing plays
    rb_names = set(rush_plays['rusher_player_name'].unique())
    print(f"Identified {len(rb_names)} unique RBs from rushing plays")

    # Create dataset for ALL TARGETS to RBs (not just completions!)
    target_plays = pbp[
        (pbp['pass_attempt'] == 1) &
        (pbp['receiver_player_name'].notna()) &  # A target must have a receiver
        (pbp['play_type'] == 'pass') &
        (pbp['receiver_player_name'].isin(rb_names))  # KEY: Only include RBs
    ].copy()

    print(f"Processing {len(rush_plays):,} rush plays and {len(target_plays):,} RB target plays")

    # Clean aggregation with named agg for rushing - bins only
    rush_agg = rush_plays.groupby(['rusher_player_name', 'game_id', 'week']).agg(
        total_carries=('rush_attempt', 'sum'),
        rushing_yards=('rushing_yards', 'sum'),
        rushing_tds=('rush_touchdown', 'sum'),
        fumbles_lost=('fumble_lost', 'sum'),
        # Binned features (proven red zone signals)
        carries_inside_10=('yardline_100', lambda x: (x <= 10).sum())
    ).reset_index()

    # Clean aggregation with named agg for targets (not just receptions!)
    if len(target_plays) > 0:
        rec_agg = target_plays.groupby(['receiver_player_name', 'game_id', 'week']).agg(
            targets=('pass_attempt', 'sum'),  # KEY: Total targets, not just completions
            receptions=('complete_pass', 'sum'),
            receiving_yards=('receiving_yards', 'sum'),
            receiving_tds=('pass_touchdown', 'sum'),
            air_yards=('air_yards', 'sum'),
            # Binned features (proven red zone signals)
            targets_inside_10=('yardline_100', lambda x: (x <= 10).sum()),
            # Interaction feature: high-value air yards
            air_yards_inside_10=('air_yards', lambda x: x[target_plays.loc[x.index, 'yardline_100'] <= 10].sum())
        ).reset_index()
    else:
        # If no target plays, create empty DataFrame with correct structure
        rec_agg = pd.DataFrame(columns=['receiver_player_name', 'game_id', 'week', 'targets',
                                       'receptions', 'receiving_yards', 'receiving_tds', 'air_yards',
                                       'targets_inside_10', 'air_yards_inside_10'])

    # Merge rushing and receiving data
    player_games = rush_agg.merge(
        rec_agg,
        left_on=['rusher_player_name', 'game_id', 'week'],
        right_on=['receiver_player_name', 'game_id', 'week'],
        how='left'
    )

    # Fill NaN receiving stats with 0 (RBs who didn't get targets)
    rec_cols = ['targets', 'receptions', 'receiving_yards', 'receiving_tds', 'air_yards',
                'targets_inside_10', 'air_yards_inside_10']
    for col in rec_cols:
        if col in player_games.columns:
            player_games[col] = player_games[col].fillna(0)

    # Calculate total fantasy points (standard 0.5 PPR)
    player_games['total_fantasy_points'] = (
        player_games['rushing_yards'] * 0.1 +
        player_games['rushing_tds'] * 6 +
        player_games['receiving_yards'] * 0.1 +
        player_games['receiving_tds'] * 6 +
        player_games['receptions'] * 0.5 +  # PPR
        player_games['fumbles_lost'] * -2
    )

    # Clean up column names
    player_games = player_games.rename(columns={
        'rusher_player_name': 'player_name'
    })

    # Drop the duplicate receiver_player_name column if it exists
    if 'receiver_player_name' in player_games.columns:
        player_games = player_games.drop('receiver_player_name', axis=1)

    # Calculate opportunity share metrics (crucial for role/usage context)
    # First get team totals by game
    team_totals = player_games.groupby(['game_id', 'week']).agg({
        'total_carries': 'sum',
        'targets': 'sum'
    }).reset_index()
    team_totals = team_totals.rename(columns={
        'total_carries': 'team_total_carries',
        'targets': 'team_total_targets'
    })

    # Merge team totals back to player games
    player_games = player_games.merge(team_totals, on=['game_id', 'week'], how='left')

    # Calculate opportunity shares
    player_games['rush_attempt_share'] = player_games['total_carries'] / player_games['team_total_carries'].replace(0, 1)
    player_games['target_share'] = player_games['targets'] / player_games['team_total_targets'].replace(0, 1)

    # Fill any NaN shares with 0
    player_games['rush_attempt_share'] = player_games['rush_attempt_share'].fillna(0)
    player_games['target_share'] = player_games['target_share'].fillna(0)

    # Filter to actual RB games (exclude QBs with just a few rushes)
    before_filter = len(player_games)
    player_games = player_games[player_games['total_carries'] >= 3].copy()  # At least 3 carries to be considered RB usage
    after_filter = len(player_games)

    print(f"Filtered from {before_filter:,} to {after_filter:,} player-game records (RBs with 3+ carries)")
    print(f"Average carries per game: {player_games['total_carries'].mean():.1f}")
    print(f"Average fantasy points per game: {player_games['total_fantasy_points'].mean():.2f}")

    return player_games

def create_rb_features(df):
    """Create features for RB player-game modeling using raw yardline data"""

    # Simple, effective binned features
    feature_cols = [
        # Volume metrics (TRUE OPPORTUNITY)
        'total_carries',
        'targets',             # KEY: Use targets not receptions!

        # High-value opportunity features (no multicollinearity)
        'carries_inside_10',   # High-value carries (model learns baseline from total_carries)
        'targets_inside_10',   # High-value targets (model learns baseline from targets)

        # Receiving opportunity quality
        'air_yards',           # Total air yards (crucial for valuing targets)
        'air_yards_inside_10', # INTERACTION: High-leverage air yards inside 10-yard line

        # Opportunity share metrics (role/usage context)
        'rush_attempt_share',  # Share of team's rushing attempts
        'target_share',        # Share of team's passing targets
    ]

    # Filter to available columns
    available_cols = [col for col in feature_cols if col in df.columns]
    features = df[available_cols].copy()

    # Check for missing values (there shouldn't be any with proper aggregation)
    missing_counts = features.isna().sum()
    if missing_counts.sum() > 0:
        print("Warning: Missing values found:")
        print(missing_counts[missing_counts > 0])
        # Fill any unexpected missing values
        features = features.fillna(0)

    return features, available_cols

def build_rb_model(player_games):
    """Build XGBoost model for RB player-game opportunity scoring"""

    print("Building RB Player-Game Opportunity Score Model")
    print("=" * 50)

    # Create features and target
    X, feature_names = create_rb_features(player_games)
    y = player_games['total_fantasy_points']

    print(f"Features: {feature_names}")
    print(f"Training samples: {len(X):,} player-games")
    print(f"Average fantasy points per game: {y.mean():.2f}")
    print(f"Fantasy points std: {y.std():.2f}")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Scale features for reliable coefficient comparison
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Build Linear Regression model
    model = LinearRegression()

    # Train model on scaled features
    model.fit(X_train_scaled, y_train)

    # Make predictions
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)

    # Calculate metrics
    train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    train_mae = mean_absolute_error(y_train, y_pred_train)
    test_mae = mean_absolute_error(y_test, y_pred_test)
    train_r2 = r2_score(y_train, y_pred_train)
    test_r2 = r2_score(y_test, y_pred_test)

    print(f"\nModel Performance:")
    print(f"Train RMSE: {train_rmse:.2f} fantasy points")
    print(f"Test RMSE:  {test_rmse:.2f} fantasy points")
    print(f"Train MAE:  {train_mae:.2f} fantasy points")
    print(f"Test MAE:   {test_mae:.2f} fantasy points")
    print(f"Train R²:   {train_r2:.3f}")
    print(f"Test R²:    {test_r2:.3f}")

    # Calculate correlation for comparison with benchmark
    correlation = np.corrcoef(y_test, y_pred_test)[0, 1]
    print(f"Test Correlation: {correlation:.3f}")

    # Feature coefficients (linear regression equivalent of importance)
    importance = pd.DataFrame({
        'feature': feature_names,
        'importance': np.abs(model.coef_)  # Use absolute values of coefficients
    }).sort_values('importance', ascending=False)

    # Normalize to percentages like XGBoost importance
    importance['importance'] = importance['importance'] / importance['importance'].sum()

    print(f"\nFeature Importance (based on coefficient magnitude):")
    for _, row in importance.iterrows():
        print(f"  {row['feature']}: {row['importance']:.3f}")

    return model, scaler, feature_names, {
        'train_rmse': train_rmse,
        'test_rmse': test_rmse,
        'train_mae': train_mae,
        'test_mae': test_mae,
        'train_r2': train_r2,
        'test_r2': test_r2,
        'correlation': correlation,
        'feature_importance': importance
    }

def predict_opportunity_score(model, scaler, feature_names, player_game_opportunities):
    """Predict opportunity score for given player-game opportunities"""

    # Create feature vector from opportunities
    feature_values = [player_game_opportunities.get(feat, 0) for feat in feature_names]
    X = np.array([feature_values])

    # Scale features using the fitted scaler
    X_scaled = scaler.transform(X)

    # Predict expected fantasy points
    expected_fp = model.predict(X_scaled)[0]

    return expected_fp

def save_model(model, scaler, feature_names, filename='rb_opportunity_model.pkl'):
    """Save the trained model, scaler, and feature names"""
    model_data = {
        'model': model,
        'scaler': scaler,
        'feature_names': feature_names
    }
    with open(filename, 'wb') as f:
        pickle.dump(model_data, f)
    print(f"Model saved to {filename}")

def load_model(filename='rb_opportunity_model.pkl'):
    """Load the trained model, scaler, and feature names"""
    with open(filename, 'rb') as f:
        model_data = pickle.load(f)
    print(f"Model loaded from {filename}")
    return model_data['model'], model_data['scaler'], model_data['feature_names']

def main():
    """Main function to build and demonstrate the RB player-game model"""

    # Load data
    pbp = load_nfl_data()  # Use default multi-season data

    # Prepare player-game aggregated data
    player_games = prepare_rb_player_games(pbp)

    # Build model
    model, scaler, feature_names, metrics = build_rb_model(player_games)

    # Example predictions
    print("\n" + "=" * 50)
    print("EXAMPLE PLAYER-GAME OPPORTUNITY SCORES")
    print("=" * 50)

    scenarios = [
        {
            'name': 'High-Volume Game with Red Zone Opportunities',
            'total_carries': 20,
            'targets': 4,
            'carries_inside_10': 2,  # 2 high-value carries
            'targets_inside_10': 1,  # 1 high-value target
            'air_yards': 15,
            'air_yards_inside_10': 8,  # 8 high-leverage air yards inside 10
            'rush_attempt_share': 0.65,  # 65% of team's rushing attempts
            'target_share': 0.12  # 12% of team's passing targets
        },
        {
            'name': 'Standard Workload Game',
            'total_carries': 15,
            'targets': 3,
            'carries_inside_10': 0,  # 0 high-value carries
            'targets_inside_10': 0,  # 0 high-value targets
            'air_yards': 8,
            'air_yards_inside_10': 0,  # 0 high-leverage air yards
            'rush_attempt_share': 0.50,  # 50% of team's rushing attempts
            'target_share': 0.09  # 9% of team's passing targets
        },
        {
            'name': 'Goal Line Specialist Game',
            'total_carries': 8,
            'targets': 0,
            'carries_inside_10': 4,  # 4 high-value carries
            'targets_inside_10': 0,  # 0 high-value targets
            'air_yards': 0,
            'air_yards_inside_10': 0,  # 0 high-leverage air yards
            'rush_attempt_share': 0.25,  # 25% of team's rushing attempts
            'target_share': 0.0  # 0% of team's passing targets
        },
        {
            'name': 'Pass-Catching Back Game',
            'total_carries': 8,
            'targets': 8,
            'carries_inside_10': 0,  # 0 high-value carries
            'targets_inside_10': 1,  # 1 high-value target
            'air_yards': 45,
            'air_yards_inside_10': 12,  # 12 high-leverage air yards
            'rush_attempt_share': 0.25,  # 25% of team's rushing attempts
            'target_share': 0.24  # 24% of team's passing targets
        }
    ]

    for scenario in scenarios:
        expected_fp = predict_opportunity_score(model, scaler, feature_names, scenario)
        print(f"\n{scenario['name']}:")
        print(f"  Expected Fantasy Points: {expected_fp:.1f}")

        # Show key opportunity details
        key_details = {
            'carries': scenario['total_carries'],
            'targets': scenario['targets'],
            'inside_10_carries': scenario.get('carries_inside_10', 0),
            'inside_10_targets': scenario.get('targets_inside_10', 0),
            'air_yards': scenario['air_yards']
        }
        print(f"  Opportunities: {key_details}")

    # Show some sample actual vs predicted
    print("\n" + "=" * 50)
    print("SAMPLE ACTUAL vs PREDICTED COMPARISONS")
    print("=" * 50)

    sample_games = player_games.sample(5, random_state=42)
    X_sample, _ = create_rb_features(sample_games)
    X_sample_scaled = scaler.transform(X_sample)  # CRITICAL: Scale the sample data!
    predictions = model.predict(X_sample_scaled)

    for i, (_, game) in enumerate(sample_games.iterrows()):
        print(f"\n{game['player_name']} (Week {game['week']}):")
        print(f"  Actual: {game['total_fantasy_points']:.1f} points")
        print(f"  Expected: {predictions[i]:.1f} points")
        print(f"  Difference: {(game['total_fantasy_points'] - predictions[i]):+.1f}")
        print(f"  Opportunities: {game['total_carries']} carries, {game['targets']} targets, inside 10: {game['carries_inside_10']} carries + {game['targets_inside_10']} targets")

    print("\n" + "=" * 50)
    print("MODEL INTERPRETATION")
    print("=" * 50)
    print(f"""
This player-game model predicts expected fantasy points based on opportunities:

BENCHMARK TO BEAT:
- RB Model Correlation: 0.969/0.953/0.957 (2022/2023/2024)

CURRENT MODEL:
- Test Correlation: {metrics['correlation']:.3f}
- Test R²: {metrics['test_r2']:.3f}
- Test RMSE: {metrics['test_rmse']:.1f} fantasy points

Key Factors (in order of importance):
{chr(10).join([f'{i+1}. {row["feature"]}: {row["importance"]:.1%}' for i, (_, row) in enumerate(metrics['feature_importance'].head(5).iterrows())])}
    """)

    # Save the trained model
    save_model(model, scaler, feature_names, 'rb_opportunity_model_2022_2024.pkl')

    return model, scaler, feature_names, player_games

def predict_2025_week5():
    """Load 2025 week 5 data and predict opportunity scores using trained model"""
    print("\n" + "=" * 60)
    print("PREDICTING 2025 WEEK 5 RB OPPORTUNITY SCORES")
    print("=" * 60)

    # Load the trained model
    model, scaler, feature_names = load_model('rb_opportunity_model_2022_2024.pkl')

    # Load 2025 week 5 data
    print("\nLoading 2025 Week 5 data...")
    pbp_2025 = load_nfl_data([2025])

    # Filter to only week 5 data
    pbp_week5 = pbp_2025[pbp_2025['week'] == 5].copy()
    print(f"Week 5 has {len(pbp_week5):,} plays")

    if len(pbp_week5) == 0:
        print("No Week 5 data found for 2025!")
        return

    # Prepare RB player-game data for week 5
    player_games_2025 = prepare_rb_player_games(pbp_week5)

    if len(player_games_2025) == 0:
        print("No RB games found in Week 5 2025!")
        return

    # Create features for prediction
    X_2025, _ = create_rb_features(player_games_2025)
    X_2025_scaled = scaler.transform(X_2025)

    # Make predictions
    predictions_2025 = model.predict(X_2025_scaled)

    # Add predictions to dataframe
    player_games_2025['predicted_opportunity_score'] = predictions_2025

    # Sort by predicted opportunity score (highest first)
    top_opportunities = player_games_2025.sort_values('predicted_opportunity_score', ascending=False)

    # Save to CSV
    csv_filename = f'rb_opportunity_scores_2025_week5.csv'
    output_df = top_opportunities[['player_name', 'predicted_opportunity_score', 'total_carries', 'targets',
                                  'carries_inside_10', 'targets_inside_10', 'rush_attempt_share', 'target_share',
                                  'total_fantasy_points', 'game_id', 'week']].copy()
    output_df.columns = ['player_name', 'opportunity_score', 'carries', 'targets', 'carries_inside_10',
                        'targets_inside_10', 'rush_share', 'target_share', 'fantasy_points', 'game_id', 'week']
    output_df.to_csv(csv_filename, index=False)
    print(f"\nAll {len(output_df)} RB opportunity scores saved to {csv_filename}")

    print(f"\nTOP 20 RB OPPORTUNITY SCORES - 2025 WEEK 5")
    print("-" * 80)
    print(f"{'Rank':<4} {'Player':<20} {'Predicted':<10} {'Carries':<8} {'Targets':<8} {'Inside10':<9} {'Rush%':<8} {'Tgt%':<8}")
    print("-" * 80)

    for i, (_, player) in enumerate(top_opportunities.head(20).iterrows()):
        rank = i + 1
        name = player['player_name'][:19]  # Truncate long names
        pred_score = player['predicted_opportunity_score']
        carries = int(player['total_carries'])
        targets = int(player['targets'])
        inside_10 = int(player['carries_inside_10'] + player['targets_inside_10'])
        rush_pct = player['rush_attempt_share'] * 100
        tgt_pct = player['target_share'] * 100

        print(f"{rank:<4} {name:<20} {pred_score:<10.1f} {carries:<8} {targets:<8} {inside_10:<9} {rush_pct:<8.1f} {tgt_pct:<8.1f}")

    return player_games_2025

def get_rb_opportunity_scores(year, week, save_csv=True, show_top_n=20):
    """
    Get RB opportunity scores for any specified year and week

    Args:
        year (int): The NFL season year
        week (int): The week number
        save_csv (bool): Whether to save results to CSV
        show_top_n (int): Number of top players to display

    Returns:
        pandas.DataFrame: Player games with opportunity scores
    """
    print(f"\n{'='*60}")
    print(f"RB OPPORTUNITY SCORES - {year} WEEK {week}")
    print(f"{'='*60}")

    # Load the trained model
    model_file = 'rb_opportunity_model_2022_2024.pkl'
    if not os.path.exists(model_file):
        print(f"Error: Model file {model_file} not found!")
        print("Please run the training script first to create the model.")
        return None

    model, scaler, feature_names = load_model(model_file)

    # Load specified year data
    print(f"\nLoading {year} data...")
    try:
        pbp_year = load_nfl_data([year])
    except Exception as e:
        print(f"Error loading {year} data: {e}")
        return None

    # Filter to specified week
    pbp_week = pbp_year[pbp_year['week'] == week].copy()
    print(f"{year} Week {week} has {len(pbp_week):,} plays")

    if len(pbp_week) == 0:
        print(f"No Week {week} data found for {year}!")
        return None

    # Prepare RB player-game data
    try:
        player_games = prepare_rb_player_games(pbp_week)
    except Exception as e:
        print(f"Error preparing player games: {e}")
        return None

    if len(player_games) == 0:
        print(f"No RB games found in {year} Week {week}!")
        return None

    # Create features for prediction
    try:
        X_features, _ = create_rb_features(player_games)
        X_scaled = scaler.transform(X_features)
        predictions = model.predict(X_scaled)
        player_games['opportunity_score'] = predictions
    except Exception as e:
        print(f"Error making predictions: {e}")
        return None

    # Sort by opportunity score
    top_opportunities = player_games.sort_values('opportunity_score', ascending=False)

    # Save to CSV if requested
    if save_csv:
        csv_filename = f'rb_opportunity_scores_{year}_week{week}.csv'
        output_df = top_opportunities[['player_name', 'opportunity_score', 'total_carries', 'targets',
                                      'carries_inside_10', 'targets_inside_10', 'rush_attempt_share', 'target_share',
                                      'total_fantasy_points', 'game_id', 'week']].copy()
        output_df.columns = ['player_name', 'opportunity_score', 'carries', 'targets', 'carries_inside_10',
                            'targets_inside_10', 'rush_share', 'target_share', 'fantasy_points', 'game_id', 'week']
        output_df.to_csv(csv_filename, index=False)
        print(f"\nAll {len(output_df)} RB opportunity scores saved to {csv_filename}")

    # Display top results
    print(f"\nTOP {show_top_n} RB OPPORTUNITY SCORES - {year} WEEK {week}")
    print("-" * 80)
    print(f"{'Rank':<4} {'Player':<20} {'Score':<8} {'Carries':<8} {'Targets':<8} {'Inside10':<9} {'Rush%':<8} {'Tgt%':<8}")
    print("-" * 80)

    for i, (_, player) in enumerate(top_opportunities.head(show_top_n).iterrows()):
        rank = i + 1
        name = player['player_name'][:19]
        score = player['opportunity_score']
        carries = int(player['total_carries'])
        targets = int(player['targets'])
        inside_10 = int(player['carries_inside_10'] + player['targets_inside_10'])
        rush_pct = player['rush_attempt_share'] * 100
        tgt_pct = player['target_share'] * 100

        print(f"{rank:<4} {name:<20} {score:<8.1f} {carries:<8} {targets:<8} {inside_10:<9} {rush_pct:<8.1f} {tgt_pct:<8.1f}")

    return top_opportunities

if __name__ == "__main__":
    # Train model on 2022-2024 data
    print("Training model on 2022-2024 data...")
    model, scaler, features, data = main()

    # Predict on 2025 week 5 data
    predict_2025_week5()