import pandas as pd
import nflreadpy as nfl

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

# Sort by total fantasy points
kicker_stats = kicker_stats.sort_values(['total_fantasy_points'], ascending=False).reset_index(drop=True)
kicker_stats['rank'] = range(1, len(kicker_stats) + 1)

# Reorder columns
kicker_stats = kicker_stats[['rank', 'kicker', 'fg_attempts', 'fg_made', 'fg_pct', 'avg_distance',
                              'xp_attempts', 'xp_made', 'xp_pct', 'fg_fantasy_points', 'total_fantasy_points']]

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
