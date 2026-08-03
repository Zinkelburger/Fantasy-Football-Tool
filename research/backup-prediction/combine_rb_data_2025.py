#!/usr/bin/env python3

import pandas as pd
import numpy as np
import nflreadpy as nfl

def combine_rb_efficiency_with_oline_2025():
    """Combine RB efficiency data with 2025 team O-line quality"""

    print("Loading RB points over expected data...")
    rb_data = pd.read_csv('rb_points_over_expected_2024.csv')
    print(f"Loaded {len(rb_data)} RBs")

    print("Loading O-line metrics data...")
    oline_player_data = pd.read_csv('simple_oline_metrics_2024.csv')
    print(f"Loaded {len(oline_player_data)} O-line player records")

    # Aggregate O-line data by team (weighted by total_plays)
    team_oline = oline_player_data.groupby('teams').apply(
        lambda x: pd.Series({
            'pct_positive_plays': np.average(x['pct_positive_plays'], weights=x['total_plays']),
            'mean_yards': np.average(x['mean_yards'], weights=x['total_plays']),
            'total_plays': x['total_plays'].sum()
        })
    ).reset_index()
    team_oline = team_oline.rename(columns={'teams': 'team'})

    print(f"Aggregated to {len(team_oline)} team O-line records")
    oline_data = team_oline

    # Load 2025 team assignments
    print("Loading 2025 roster data for team assignments...")
    rosters_2025 = nfl.load_rosters([2025]).to_pandas()
    rb_rosters_2025 = rosters_2025[rosters_2025['position'] == 'RB'][['gsis_id', 'full_name', 'team']].copy()

    print(f"Found {len(rb_rosters_2025)} RBs with 2025 team assignments")

    # Merge RB data with 2025 team assignments using player_id
    combined = rb_data.merge(
        rb_rosters_2025[['gsis_id', 'team']],
        left_on='player_id',
        right_on='gsis_id',
        how='left'
    )

    print(f"After merging with 2025 rosters: {len(combined)} RBs")

    # Check for RBs without 2025 team assignments (likely retired/cut)
    no_team_count = combined['team'].isna().sum()
    if no_team_count > 0:
        print(f"Warning: {no_team_count} RBs from 2024 don't have 2025 team assignments")
        missing_teams = combined[combined['team'].isna()]['player_name'].tolist()
        print(f"RBs without 2025 teams: {missing_teams[:10]}...")

    # Filter to only RBs with 2025 team assignments
    combined = combined[combined['team'].notna()].copy()
    print(f"RBs with 2025 team assignments: {len(combined)}")

    # Merge with O-line data
    combined = combined.merge(
        oline_data[['team', 'pct_positive_plays', 'mean_yards', 'total_plays']],
        on='team',
        how='left'
    )

    # Rename O-line columns for clarity
    combined = combined.rename(columns={
        'pct_positive_plays': 'team_pct_positive_plays',
        'mean_yards': 'team_mean_yards',
        'total_plays': 'team_total_plays'
    })

    # Clean up columns - keep only essential ones
    final_columns = [
        'player_name', 'team', 'actual_fantasy_points', 'expected_fantasy_points',
        'points_over_expected', 'pct_of_expected', 'total_touches', 'games_played',
        'team_pct_positive_plays', 'team_mean_yards', 'team_total_plays'
    ]

    combined = combined[final_columns].copy()

    # Sort by points over expected
    combined = combined.sort_values('points_over_expected', ascending=False)

    print(f"Final combined dataset: {len(combined)} RBs")
    print(f"Sample data:")
    print(combined[['player_name', 'team', 'points_over_expected', 'team_pct_positive_plays']].head())

    # Save the combined data
    output_file = 'rb_efficiency_vs_oline_2025.csv'
    combined.to_csv(output_file, index=False)
    print(f"Saved combined data to {output_file}")

    return combined

if __name__ == "__main__":
    combined_data = combine_rb_efficiency_with_oline_2025()