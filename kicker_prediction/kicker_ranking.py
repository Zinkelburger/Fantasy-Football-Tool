import pandas as pd
import nflreadpy as nfl
import numpy as np
from scipy import stats

# Load 2025 play-by-play data
print("Loading 2025 NFL data...")
pbp = nfl.load_pbp(seasons=[2025]).to_pandas()

# Filter for field goal attempts
print("Filtering field goal attempts...")
fg_data = pbp[pbp['field_goal_attempt'] == 1].copy()

# Filter for extra point attempts
print("Filtering extra point attempts...")
xp_data = pbp[pbp['extra_point_attempt'] == 1].copy()

# Select relevant columns for field goals
fg_kicks = fg_data[['kicker_player_name', 'kick_distance', 'field_goal_result']].copy()
fg_kicks = fg_kicks.dropna(subset=['kicker_player_name', 'kick_distance'])

# Select relevant columns for extra points
xp_kicks = xp_data[['kicker_player_name', 'extra_point_result']].copy()
xp_kicks = xp_kicks.dropna(subset=['kicker_player_name'])

print(f"\nTotal field goal attempts in 2025: {len(fg_kicks)}")
print(f"Total extra point attempts in 2025: {len(xp_kicks)}")

# Calculate FG stats for each kicker
fg_stats = fg_kicks.groupby('kicker_player_name').agg({
    'kick_distance': ['count', 'mean', 'max', 'min'],
    'field_goal_result': lambda x: (x == 'made').sum()
}).reset_index()
fg_stats.columns = ['kicker', 'fg_attempts', 'avg_distance', 'longest', 'shortest', 'fg_made']
fg_stats['fg_pct'] = (fg_stats['fg_made'] / fg_stats['fg_attempts'] * 100).round(2)

# Calculate XP stats for each kicker
xp_stats = xp_kicks.groupby('kicker_player_name').agg({
    'extra_point_result': ['count', lambda x: (x == 'good').sum()]
}).reset_index()
xp_stats.columns = ['kicker', 'xp_attempts', 'xp_made']
xp_stats['xp_pct'] = (xp_stats['xp_made'] / xp_stats['xp_attempts'] * 100).round(2)

# Merge FG and XP stats
kicker_stats = fg_stats.merge(xp_stats, on='kicker', how='outer').fillna(0)

# Calculate fantasy points using distance-based scoring
# 0-39 yards = 3 points, 40-49 = 4 points, 50-59 = 5 points, 60+ = 6 points
def get_fg_points(row):
    if row['field_goal_result'] != 'made':
        return 0
    distance = row['kick_distance']
    if distance < 40:
        return 3
    elif distance < 50:
        return 4
    elif distance < 60:
        return 5
    else:
        return 6

fg_kicks['fg_points'] = fg_kicks.apply(get_fg_points, axis=1)

# Calculate total FG points per kicker
fg_points_by_kicker = fg_kicks.groupby('kicker_player_name')['fg_points'].sum().reset_index()
fg_points_by_kicker.columns = ['kicker', 'fg_fantasy_points']

# Merge FG fantasy points
kicker_stats = kicker_stats.merge(fg_points_by_kicker, on='kicker', how='left')
kicker_stats['fg_fantasy_points'] = kicker_stats['fg_fantasy_points'].fillna(0)

# Calculate total fantasy points (distance-based FG points + XP=1pt each)
kicker_stats['total_fantasy_points'] = kicker_stats['fg_fantasy_points'] + kicker_stats['xp_made']

# Calculate game-by-game statistics
print("Calculating game-by-game statistics...")

# Get game information - need to add week/game columns for analysis
fg_kicks['week'] = pbp[pbp['field_goal_attempt'] == 1]['week'].values
xp_kicks['week'] = pbp[pbp['extra_point_attempt'] == 1]['week'].values

# Calculate weekly fantasy points for each kicker
weekly_stats = []

for kicker in kicker_stats['kicker']:
    # Get this kicker's FG points by week
    kicker_fg = fg_kicks[fg_kicks['kicker_player_name'] == kicker]
    kicker_xp = xp_kicks[xp_kicks['kicker_player_name'] == kicker]

    if len(kicker_fg) > 0 or len(kicker_xp) > 0:
        # Get all weeks this kicker played
        fg_weeks = kicker_fg['week'].unique() if len(kicker_fg) > 0 else []
        xp_weeks = kicker_xp['week'].unique() if len(kicker_xp) > 0 else []
        all_weeks = sorted(set(list(fg_weeks) + list(xp_weeks)))

        weekly_points = []
        for week in all_weeks:
            week_fg_points = kicker_fg[kicker_fg['week'] == week]['fg_points'].sum()
            week_xp_points = len(kicker_xp[kicker_xp['week'] == week])
            week_total = week_fg_points + week_xp_points
            weekly_points.append(week_total)

        if weekly_points:
            games_played = len(weekly_points)
            mean_points = np.mean(weekly_points)
            median_points = np.median(weekly_points)
            std_points = np.std(weekly_points, ddof=1) if len(weekly_points) > 1 else 0

            # Calculate mode (most frequent score)
            if len(weekly_points) > 0:
                mode_result = stats.mode(weekly_points, keepdims=True)
                mode_points = mode_result.mode[0] if len(mode_result.mode) > 0 else 0
            else:
                mode_points = 0

            weekly_stats.append({
                'kicker': kicker,
                'games_played': games_played,
                'points_per_game': round(mean_points, 2),
                'mean_points': round(mean_points, 2),
                'median_points': round(median_points, 2),
                'mode_points': round(mode_points, 2),
                'std_deviation': round(std_points, 2)
            })
        else:
            weekly_stats.append({
                'kicker': kicker,
                'games_played': 0,
                'points_per_game': 0,
                'mean_points': 0,
                'median_points': 0,
                'mode_points': 0,
                'std_deviation': 0
            })
    else:
        weekly_stats.append({
            'kicker': kicker,
            'games_played': 0,
            'points_per_game': 0,
            'mean_points': 0,
            'median_points': 0,
            'mode_points': 0,
            'std_deviation': 0
        })

# Convert to DataFrame and merge with main stats
weekly_df = pd.DataFrame(weekly_stats)
kicker_stats = kicker_stats.merge(weekly_df, on='kicker', how='left')

# Sort by total fantasy points
kicker_stats = kicker_stats.sort_values(['total_fantasy_points'], ascending=False).reset_index(drop=True)
kicker_stats['rank'] = range(1, len(kicker_stats) + 1)

# Reorder columns to include new statistics
kicker_stats = kicker_stats[['rank', 'kicker', 'games_played', 'fg_attempts', 'fg_made', 'fg_pct', 'avg_distance',
                              'xp_attempts', 'xp_made', 'xp_pct', 'fg_fantasy_points', 'total_fantasy_points',
                              'points_per_game', 'mean_points', 'median_points', 'mode_points', 'std_deviation']]

print("\n" + "="*120)
print("KICKER RANKINGS - 2025 SEASON (Field Goals + Extra Points)")
print("="*120)
print(kicker_stats.to_string(index=False))

# Save to CSV
output_file = 'kicker_prediction/kicker_rankings_2025.csv'
kicker_stats.to_csv(output_file, index=False)
print(f"\n\nRankings saved to {output_file}")

# Show all individual kicks for top 5 kickers
print("\n" + "="*120)
print("INDIVIDUAL KICKS - TOP 5 KICKERS")
print("="*120)

top_5_kickers = kicker_stats.head(5)['kicker'].tolist()
for kicker in top_5_kickers:
    print(f"\n{kicker}:")
    print("\nField Goals:")
    kicker_fg = fg_kicks[fg_kicks['kicker_player_name'] == kicker].copy()
    kicker_fg = kicker_fg.sort_values('kick_distance', ascending=False)
    print(kicker_fg[['kick_distance', 'field_goal_result']].to_string(index=False))

    print(f"\nExtra Points: ", end='')
    kicker_xp = xp_kicks[xp_kicks['kicker_player_name'] == kicker].copy()
    xp_made = (kicker_xp['extra_point_result'] == 'good').sum()
    xp_total = len(kicker_xp)
    print(f"{xp_made}/{xp_total}")
