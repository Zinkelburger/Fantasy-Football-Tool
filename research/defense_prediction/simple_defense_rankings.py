#!/usr/bin/env python3
"""
Simple Defense Rankings based on NFL Elo implied scores.
"""

import pandas as pd
import requests


def get_latest_2025_defense_rankings():
    """Get defense rankings for latest 2025 week with actual totals."""

    url = "https://raw.githubusercontent.com/greerreNFL/nfelo/main/output_data/nfelo_games.csv"

    try:
        df = pd.read_csv(url)
        print(f"Loaded {len(df)} games")
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

    # Filter 2025 games
    df_2025 = df[df['game_id'].str.startswith('2025_')].copy()

    if len(df_2025) == 0:
        print("No 2025 data available")
        return pd.DataFrame()

    # Parse week from game_id and get latest week
    df_2025['week'] = df_2025['game_id'].str.split('_').str[1].astype(int)
    latest_week = df_2025['week'].max()

    print(f"Latest week: {latest_week}")

    # Filter to latest week and remove duplicates
    week_data = df_2025[df_2025['week'] == latest_week].copy()
    week_data = week_data.drop_duplicates(subset=['game_id'])

    # Calculate defense rankings
    defense_rankings = []

    for _, row in week_data.iterrows():
        # Parse teams from game_id: YYYY_WW_AWAY_HOME
        game_parts = row['game_id'].split('_')
        away_team = game_parts[2]
        home_team = game_parts[3]

        home_line = row['home_line_close']
        total_line = row['total_line_close']

        if pd.isna(home_line) or pd.isna(total_line):
            continue

        # Calculate implied scores
        # When home_line is negative, home team is favored (scores more)
        home_implied = (total_line - home_line) / 2  # Subtract because negative line means home favored
        away_implied = (total_line + home_line) / 2  # Add because away gets less when home favored

        # Add both defense perspectives
        defense_rankings.extend([
            {
                'defense_team': home_team,
                'opponent': away_team,
                'week': latest_week,
                'is_home': True,
                'points_allowed': away_implied,  # Home defense allows away score
                'spread': home_line,
                'total': total_line
            },
            {
                'defense_team': away_team,
                'opponent': home_team,
                'week': latest_week,
                'is_home': False,
                'points_allowed': home_implied,  # Away defense allows home score
                'spread': home_line,
                'total': total_line
            }
        ])

    if not defense_rankings:
        print("No valid games found")
        return pd.DataFrame()

    # Create DataFrame and rank by fewest points allowed
    df_rankings = pd.DataFrame(defense_rankings)
    df_rankings = df_rankings.sort_values('points_allowed')
    df_rankings['rank'] = range(1, len(df_rankings) + 1)

    return df_rankings


if __name__ == "__main__":
    print("🏈 LATEST 2025 DEFENSE RANKINGS")
    print("=" * 50)

    rankings = get_latest_2025_defense_rankings()

    if not rankings.empty:
        week = rankings['week'].iloc[0]
        print(f"\nWEEK {week} DEFENSE RANKINGS (2025)")
        print("=" * 60)
        print(f"Rank Team vs   Points Allow  Spread  Total")
        print("-" * 50)

        for _, row in rankings.iterrows():
            print(f"{int(row['rank']):>2}   {row['defense_team']} {row['opponent']}  "
                  f"{row['points_allowed']:>10.1f}  {row['spread']:>6.1f}  {row['total']:>5.1f}")