#!/usr/bin/env python3

import sys
import os
sys.path.append('/var/home/bigman/Documents/CodingProjects/Fantasy-Football-Tool/opportunity-score')

import pandas as pd
import numpy as np
import nflreadpy as nfl
from rb_opportunity_model import load_nfl_data, prepare_rb_player_games, create_rb_features, load_model
import warnings
warnings.filterwarnings('ignore')

def create_rb_points_over_expected_rankings(year=2024):
    """Create RB rankings based on fantasy points over expected using 2024 opportunity model"""

    print(f"Creating RB Points Over Expected rankings for {year}...")

    # Load the trained model from opportunity-score directory
    model_file = '/var/home/bigman/Documents/CodingProjects/Fantasy-Football-Tool/opportunity-score/rb_opportunity_model_2022_2024.pkl'
    if not os.path.exists(model_file):
        print(f"Error: Model file not found at {model_file}")
        return None

    model, scaler, feature_names = load_model(model_file)
    print(f"Loaded model with features: {feature_names}")

    # Load 2024 season data
    pbp = load_nfl_data([year])
    print(f"Loaded {len(pbp)} plays from {year}")

    # Prepare player-game data for entire season
    player_games = prepare_rb_player_games(pbp)
    print(f"Found {len(player_games)} RB player-game records")

    if len(player_games) == 0:
        print("No RB data found!")
        return None

    # Create features and predict expected points
    X_features, _ = create_rb_features(player_games)
    X_scaled = scaler.transform(X_features)
    expected_points = model.predict(X_scaled)

    # Add expected points and calculate points over expected
    player_games['expected_fantasy_points'] = expected_points
    player_games['points_over_expected'] = player_games['total_fantasy_points'] - player_games['expected_fantasy_points']

    # Aggregate by player for season-long rankings
    player_season_stats = player_games.groupby('player_id').agg({
        'total_fantasy_points': 'sum',
        'expected_fantasy_points': 'sum',
        'points_over_expected': 'sum',
        'total_carries': 'sum',
        'targets': 'sum',
        'carries_inside_10': 'sum',
        'targets_inside_10': 'sum',
        'rush_attempt_share': 'mean',
        'target_share': 'mean',
        'game_id': 'count'  # Number of games
    }).round(2)

    # Rename columns for clarity
    player_season_stats.columns = [
        'actual_fantasy_points', 'expected_fantasy_points', 'points_over_expected',
        'total_carries', 'total_targets', 'carries_inside_10', 'targets_inside_10',
        'avg_rush_share', 'avg_target_share', 'games_played'
    ]

    player_season_stats = player_season_stats.reset_index()

    # Load roster data to get actual positions and map IDs to full names
    rosters = nfl.load_rosters([year]).to_pandas()
    rb_rosters = rosters[rosters['position'] == 'RB'][['gsis_id', 'full_name']].copy()

    # Filter to only actual RBs using GSIS IDs
    rb_player_ids = set(rb_rosters['gsis_id'])

    print(f"Sample player_ids from model: {player_season_stats['player_id'].head().tolist()}")
    print(f"Sample RB IDs from rosters: {list(rb_player_ids)[:5]}")

    player_season_stats = player_season_stats[
        player_season_stats['player_id'].isin(rb_player_ids)
    ].copy()

    # Add full names by mapping player IDs to full names
    id_to_name = dict(zip(rb_rosters['gsis_id'], rb_rosters['full_name']))
    player_season_stats['player_name'] = player_season_stats['player_id'].map(id_to_name)
    player_season_stats['full_name'] = player_season_stats['player_name']

    # Filter to meaningful sample size (at least 20 total touches)
    min_touches = 20
    min_carries = 10  # Must have at least 10 carries to be considered an active RB
    player_season_stats['total_touches'] = player_season_stats['total_carries'] + player_season_stats['total_targets']

    # Filter to RBs with meaningful usage
    player_season_stats = player_season_stats[
        (player_season_stats['total_touches'] >= min_touches) &
        (player_season_stats['total_carries'] >= min_carries)
    ].copy()

    # Calculate per-game averages
    player_season_stats['fantasy_points_per_game'] = player_season_stats['actual_fantasy_points'] / player_season_stats['games_played']
    player_season_stats['expected_points_per_game'] = player_season_stats['expected_fantasy_points'] / player_season_stats['games_played']
    player_season_stats['points_over_expected_per_game'] = player_season_stats['points_over_expected'] / player_season_stats['games_played']

    # Calculate efficiency metrics
    player_season_stats['efficiency_ratio'] = player_season_stats['actual_fantasy_points'] / player_season_stats['expected_fantasy_points']
    player_season_stats['pct_of_expected'] = (player_season_stats['actual_fantasy_points'] / player_season_stats['expected_fantasy_points']) * 100

    # Sort by total points over expected
    player_season_stats = player_season_stats.sort_values('points_over_expected', ascending=False)

    print(f"Found {len(player_season_stats)} true RBs with {min_touches}+ touches and {min_carries}+ carries")

    return player_season_stats

def display_rb_rankings(df, ranking_type='points_over_expected', top_n=30):
    """Display RB rankings"""

    if ranking_type == 'points_over_expected':
        sort_col = 'points_over_expected'
        title = 'POINTS OVER EXPECTED (Season Total)'
        display_col = 'POE'
        display_val = lambda x: f"{x:.1f}"
    elif ranking_type == 'per_game':
        sort_col = 'points_over_expected_per_game'
        title = 'POINTS OVER EXPECTED PER GAME'
        display_col = 'POE/G'
        display_val = lambda x: f"{x:.2f}"
    elif ranking_type == 'efficiency':
        sort_col = 'pct_of_expected'
        title = '% OF EXPECTED POINTS'
        display_col = '% Exp'
        display_val = lambda x: f"{x:.1f}%"

    df_sorted = df.sort_values(sort_col, ascending=False)

    print(f"\n{'='*100}")
    print(f"TOP {top_n} RBs BY {title}")
    print(f"{'='*100}")

    print(f"{'Rank':<4} {'Player':<20} {display_col:<8} {'Actual':<8} {'Expected':<9} {'Touches':<8} {'Games':<6} {'FP/G':<6}")
    print("-" * 100)

    for i, (_, player) in enumerate(df_sorted.head(top_n).iterrows()):
        rank = i + 1
        name = player['player_name'][:19]

        if ranking_type == 'points_over_expected':
            metric_val = display_val(player['points_over_expected'])
        elif ranking_type == 'per_game':
            metric_val = display_val(player['points_over_expected_per_game'])
        elif ranking_type == 'efficiency':
            metric_val = display_val(player['pct_of_expected'])

        actual = player['actual_fantasy_points']
        expected = player['expected_fantasy_points']
        touches = int(player['total_touches'])
        games = int(player['games_played'])
        fpg = player['fantasy_points_per_game']

        print(f"{rank:<4} {name:<20} {metric_val:<8} {actual:<8.1f} {expected:<9.1f} {touches:<8} {games:<6} {fpg:<6.1f}")

def analyze_rb_skill_vs_opportunity(df):
    """Analyze relationship between opportunity and skill"""

    print(f"\n{'='*80}")
    print("RB SKILL vs OPPORTUNITY ANALYSIS")
    print(f"{'='*80}")

    # Top opportunity (expected points)
    top_opportunity = df.nlargest(10, 'expected_fantasy_points')
    print(f"\nTOP 10 RBs BY OPPORTUNITY (Expected Points):")
    print(f"{'Player':<20} {'Expected':<9} {'Actual':<8} {'POE':<8} {'% Exp'}")
    print("-" * 60)
    for _, player in top_opportunity.iterrows():
        name = player['player_name'][:19]
        expected = player['expected_fantasy_points']
        actual = player['actual_fantasy_points']
        poe = player['points_over_expected']
        pct_exp = player['pct_of_expected']
        print(f"{name:<20} {expected:<9.1f} {actual:<8.1f} {poe:<8.1f} {pct_exp:<8.1f}%")

    # Top skill (points over expected)
    top_skill = df.nlargest(10, 'points_over_expected')
    print(f"\nTOP 10 RBs BY SKILL (Points Over Expected):")
    print(f"{'Player':<20} {'POE':<8} {'Expected':<9} {'Actual':<8} {'% Exp'}")
    print("-" * 60)
    for _, player in top_skill.iterrows():
        name = player['player_name'][:19]
        poe = player['points_over_expected']
        expected = player['expected_fantasy_points']
        actual = player['actual_fantasy_points']
        pct_exp = player['pct_of_expected']
        print(f"{name:<20} {poe:<8.1f} {expected:<9.1f} {actual:<8.1f} {pct_exp:<8.1f}%")

    # Underperformers (worst points over expected)
    underperformers = df.nsmallest(10, 'points_over_expected')
    print(f"\nBIGGEST UNDERPERFORMERS (Negative Points Over Expected):")
    print(f"{'Player':<20} {'POE':<8} {'Expected':<9} {'Actual':<8} {'% Exp'}")
    print("-" * 60)
    for _, player in underperformers.iterrows():
        name = player['player_name'][:19]
        poe = player['points_over_expected']
        expected = player['expected_fantasy_points']
        actual = player['actual_fantasy_points']
        pct_exp = player['pct_of_expected']
        print(f"{name:<20} {poe:<8.1f} {expected:<9.1f} {actual:<8.1f} {pct_exp:<8.1f}%")

def identify_backup_rb_gems(df):
    """Identify backup RBs who showed skill despite limited opportunity"""

    print(f"\n{'='*80}")
    print("BACKUP RB GEMS (High Skill, Low Opportunity)")
    print(f"{'='*80}")

    # Filter to lower opportunity players (< 150 expected points, < 200 touches)
    backup_candidates = df[
        (df['expected_fantasy_points'] < 150) &
        (df['total_touches'] < 200) &
        (df['points_over_expected'] > 0)  # Still outperformed expectations
    ].copy()

    if len(backup_candidates) == 0:
        print("No backup RB gems found with current criteria")
        return

    # Sort by points over expected per game (efficiency)
    backup_candidates = backup_candidates.sort_values('points_over_expected_per_game', ascending=False)

    print(f"Found {len(backup_candidates)} backup RBs who outperformed expectations:")
    print(f"{'Player':<20} {'POE/G':<8} {'Touches':<8} {'Games':<6} {'Rush%':<7} {'Tgt%':<7} {'% Exp'}")
    print("-" * 80)

    for _, player in backup_candidates.head(15).iterrows():
        name = player['player_name'][:19]
        poe_per_game = player['points_over_expected_per_game']
        touches = int(player['total_touches'])
        games = int(player['games_played'])
        rush_pct = player['avg_rush_share'] * 100
        target_pct = player['avg_target_share'] * 100
        pct_exp = player['pct_of_expected']

        print(f"{name:<20} {poe_per_game:<8.2f} {touches:<8} {games:<6} {rush_pct:<7.1f} {target_pct:<7.1f} {pct_exp:<8.1f}%")

    return backup_candidates

def main():
    """Main function to create RB points over expected rankings"""

    # Create rankings
    rb_stats = create_rb_points_over_expected_rankings(2024)

    if rb_stats is None:
        return None

    # Display different ranking views
    display_rb_rankings(rb_stats, 'points_over_expected', top_n=25)
    display_rb_rankings(rb_stats, 'per_game', top_n=25)
    display_rb_rankings(rb_stats, 'efficiency', top_n=25)

    # Analysis
    analyze_rb_skill_vs_opportunity(rb_stats)
    backup_gems = identify_backup_rb_gems(rb_stats)

    # Save results
    output_file = '/var/home/bigman/Documents/CodingProjects/Fantasy-Football-Tool/backup-prediction/rb_points_over_expected_2024.csv'
    rb_stats.to_csv(output_file, index=False)
    print(f"\nRB Points Over Expected rankings saved to: rb_points_over_expected_2024.csv")

    return rb_stats

if __name__ == "__main__":
    rb_rankings = main()