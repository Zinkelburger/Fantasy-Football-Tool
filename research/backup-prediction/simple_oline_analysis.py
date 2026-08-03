#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import nflreadpy as nfl

def create_simple_oline_metrics(years=[2024]):
    """Create simple, meaningful O-line metrics for 2024"""

    print(f"Loading O-line data for {years}...")

    # Load PBP and participation data
    pbp = nfl.load_pbp(seasons=years).to_pandas()
    participation = nfl.load_participation(seasons=years).to_pandas()

    # Filter to rushing plays only
    rush_plays = pbp[
        (pbp['rush_attempt'] == 1) &
        (pbp['rushing_yards'].notna()) &
        (pbp['play_type'] == 'run')
    ].copy()

    print(f"Found {len(rush_plays)} rushing plays")

    # Merge with participation data to get O-line players
    merged = rush_plays.merge(
        participation[['old_game_id', 'play_id', 'offense_players']],
        on=['old_game_id', 'play_id'],
        how='inner'
    )

    print(f"Merged {len(merged)} plays with participation data")

    # Get depth chart data to map player IDs to names and filter O-line positions
    depth_charts = nfl.load_depth_charts(seasons=years).to_pandas()
    oline_positions = ['C', 'LG', 'RG', 'LT', 'RT', 'G', 'T']
    oline_rosters = depth_charts[depth_charts['depth_position'].isin(oline_positions)][['gsis_id', 'full_name', 'club_code', 'depth_position']].copy()
    oline_rosters = oline_rosters.drop_duplicates(subset=['gsis_id'])  # Remove duplicates
    print(f"Found {len(oline_rosters)} O-line players in depth charts")

    # Expand O-line players and map IDs to names
    oline_plays = []
    for _, play in merged.iterrows():
        if pd.notna(play['offense_players']):
            player_ids = play['offense_players'].split(';')
            for player_id in player_ids:
                player_id = player_id.strip()
                if player_id and player_id in oline_rosters['gsis_id'].values:
                    player_info = oline_rosters[oline_rosters['gsis_id'] == player_id].iloc[0]
                    oline_plays.append({
                        'player_name': player_info['full_name'],
                        'player_id': player_id,
                        'team': player_info['club_code'],
                        'position': player_info['depth_position'],
                        'rushing_yards': play['rushing_yards'],
                        'posteam': play['posteam']
                    })

    oline_df = pd.DataFrame(oline_plays)
    print(f"Created {len(oline_df)} O-line player-play records")

    # Calculate simple metrics per player
    simple_metrics = []

    for player_name in oline_df['player_name'].unique():
        player_plays = oline_df[oline_df['player_name'] == player_name]
        yards = player_plays['rushing_yards']

        if len(yards) >= 100:  # Minimum sample size
            # Calculate simple metrics
            mean_yards = yards.mean()
            median_yards = yards.median()
            mode_yards = yards.mode().iloc[0] if len(yards.mode()) > 0 else 0
            std_yards = yards.std()
            pct_positive = (yards > 0).mean() * 100
            total_plays = len(yards)

            # Get teams
            teams = ','.join(player_plays['posteam'].unique())

            # Get position
            positions = ','.join(player_plays['position'].unique())

            simple_metrics.append({
                'player_name': player_name,
                'position': positions,
                'teams': teams,
                'total_plays': total_plays,
                'mean_yards': mean_yards,
                'median_yards': median_yards,
                'mode_yards': mode_yards,
                'std_yards': std_yards,
                'pct_positive_plays': pct_positive
            })

    simple_df = pd.DataFrame(simple_metrics)
    simple_df = simple_df.sort_values('pct_positive_plays', ascending=False)

    print(f"Found {len(simple_df)} O-line players with 100+ plays")
    return simple_df

def create_scatter_plots(df):
    """Create scatter plots for each metric"""

    # Set up the plots
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('O-Line Player Metrics - Each Dot is a Player', fontsize=16)

    # Create x-axis (just player index for scatter)
    x = range(len(df))

    # 1. Mean Yards
    axes[0,0].scatter(x, df['mean_yards'], alpha=0.6, color='blue', s=30)
    axes[0,0].set_title('Mean Yards Per Play')
    axes[0,0].set_ylabel('Average Yards')
    axes[0,0].grid(True, alpha=0.3)
    axes[0,0].axhline(y=df['mean_yards'].mean(), color='red', linestyle='--', alpha=0.7, label=f'League Avg: {df["mean_yards"].mean():.2f}')
    axes[0,0].legend()

    # 2. Median Yards
    axes[0,1].scatter(x, df['median_yards'], alpha=0.6, color='green', s=30)
    axes[0,1].set_title('Median Yards Per Play')
    axes[0,1].set_ylabel('Median Yards')
    axes[0,1].grid(True, alpha=0.3)
    axes[0,1].axhline(y=df['median_yards'].mean(), color='red', linestyle='--', alpha=0.7, label=f'League Avg: {df["median_yards"].mean():.2f}')
    axes[0,1].legend()

    # 3. Mode Yards
    axes[0,2].scatter(x, df['mode_yards'], alpha=0.6, color='purple', s=30)
    axes[0,2].set_title('Mode Yards Per Play (Most Common)')
    axes[0,2].set_ylabel('Mode Yards')
    axes[0,2].grid(True, alpha=0.3)
    axes[0,2].axhline(y=df['mode_yards'].mean(), color='red', linestyle='--', alpha=0.7, label=f'League Avg: {df["mode_yards"].mean():.2f}')
    axes[0,2].legend()

    # 4. Standard Deviation
    axes[1,0].scatter(x, df['std_yards'], alpha=0.6, color='orange', s=30)
    axes[1,0].set_title('Standard Deviation (Consistency)')
    axes[1,0].set_ylabel('Std Deviation (Lower = More Consistent)')
    axes[1,0].grid(True, alpha=0.3)
    axes[1,0].axhline(y=df['std_yards'].mean(), color='red', linestyle='--', alpha=0.7, label=f'League Avg: {df["std_yards"].mean():.2f}')
    axes[1,0].legend()

    # 5. % Positive Plays
    axes[1,1].scatter(x, df['pct_positive_plays'], alpha=0.6, color='red', s=30)
    axes[1,1].set_title('% Plays > 0 Yards (Stuff Prevention)')
    axes[1,1].set_ylabel('% Positive Plays')
    axes[1,1].grid(True, alpha=0.3)
    axes[1,1].axhline(y=df['pct_positive_plays'].mean(), color='red', linestyle='--', alpha=0.7, label=f'League Avg: {df["pct_positive_plays"].mean():.1f}%')
    axes[1,1].legend()

    # 6. Total Plays (sample size)
    axes[1,2].scatter(x, df['total_plays'], alpha=0.6, color='brown', s=30)
    axes[1,2].set_title('Total Plays (Sample Size)')
    axes[1,2].set_ylabel('Number of Plays')
    axes[1,2].grid(True, alpha=0.3)
    axes[1,2].axhline(y=df['total_plays'].mean(), color='red', linestyle='--', alpha=0.7, label=f'League Avg: {df["total_plays"].mean():.0f}')
    axes[1,2].legend()

    # Remove x-axis labels since they're just indices
    for ax in axes.flat:
        ax.set_xlabel('Players (sorted by mean yards)')

    plt.tight_layout()
    plt.savefig('/var/home/bigman/Documents/CodingProjects/Fantasy-Football-Tool/backup-prediction/simple_oline_plots.png',
                dpi=150, bbox_inches='tight')
    plt.show()

def show_top_bottom_simple(df):
    """Show top and bottom performers in simple terms"""

    print("\n" + "="*100)
    print("TOP 10 O-LINE PLAYERS - SIMPLE METRICS")
    print("="*100)

    # Sort by mean yards for top performers
    top10 = df.nlargest(10, 'mean_yards')

    print(f"{'Player':<25} {'Pos':<3} {'Team':<8} {'Mean':<6} {'Median':<7} {'Mode':<5} {'StdDev':<7} {'%Pos':<6} {'Plays':<6}")
    print("-" * 100)

    for _, player in top10.iterrows():
        print(f"{player['player_name'][:24]:<25} {player['position']:<3} {player['teams'][:7]:<8} "
              f"{player['mean_yards']:<6.2f} {player['median_yards']:<7.1f} {int(player['mode_yards']):<5} "
              f"{player['std_yards']:<7.2f} {player['pct_positive_plays']:<6.1f} {int(player['total_plays']):<6}")

    print(f"\nBOTTOM 10 O-LINE PLAYERS - SIMPLE METRICS")
    print("-" * 100)

    # Sort by mean yards for bottom performers
    bottom10 = df.nsmallest(10, 'mean_yards')

    for _, player in bottom10.iterrows():
        print(f"{player['player_name'][:24]:<25} {player['position']:<3} {player['teams'][:7]:<8} "
              f"{player['mean_yards']:<6.2f} {player['median_yards']:<7.1f} {int(player['mode_yards']):<5} "
              f"{player['std_yards']:<7.2f} {player['pct_positive_plays']:<6.1f} {int(player['total_plays']):<6}")

def analyze_raiders_simple(df):
    """Simple Raiders analysis"""

    print("\n" + "="*80)
    print("RAIDERS O-LINE - SIMPLE ANALYSIS")
    print("="*80)

    raiders_names = ['Miller', 'James', 'Parham', 'Powers-Johnson', 'Moore']

    print(f"{'Player':<25} {'Mean':<6} {'Median':<7} {'Mode':<5} {'StdDev':<7} {'%Pos':<6} {'vs Avg':<8}")
    print("-" * 75)

    league_avg_mean = df['mean_yards'].mean()

    for name in raiders_names:
        matches = df[df['player_name'].str.contains(name, case=False, na=False)]
        if len(matches) > 0:
            player = matches.iloc[0]
            vs_avg = "+" if player['mean_yards'] > league_avg_mean else "-"
            diff = abs(player['mean_yards'] - league_avg_mean)

            print(f"{player['player_name'][:24]:<25} {player['mean_yards']:<6.2f} {player['median_yards']:<7.1f} "
                  f"{int(player['mode_yards']):<5} {player['std_yards']:<7.2f} {player['pct_positive_plays']:<6.1f} "
                  f"{vs_avg}{diff:.2f}")

    raiders_data = []
    for name in raiders_names:
        matches = df[df['player_name'].str.contains(name, case=False, na=False)]
        if len(matches) > 0:
            raiders_data.append(matches.iloc[0])

    if raiders_data:
        raiders_df = pd.DataFrame(raiders_data)
        team_avg_mean = raiders_df['mean_yards'].mean()
        team_avg_pos = raiders_df['pct_positive_plays'].mean()

        print(f"\nRAIDERS TEAM AVERAGES:")
        print(f"  Mean yards per play: {team_avg_mean:.2f} (League: {league_avg_mean:.2f})")
        print(f"  % positive plays: {team_avg_pos:.1f}% (League: {df['pct_positive_plays'].mean():.1f}%)")
        print(f"  Grade: {'Above Average' if team_avg_mean > league_avg_mean else 'Below Average'}")

def main():
    """Main function for simple analysis"""

    # Create simple metrics
    df = create_simple_oline_metrics()

    # Sort by mean yards for plotting
    df = df.sort_values('mean_yards', ascending=True)

    print(f"Analyzing {len(df)} O-line players with 100+ plays...")

    # Show summary stats
    print(f"\nLEAGUE AVERAGES:")
    print(f"Mean yards per play: {df['mean_yards'].mean():.2f}")
    print(f"Median yards per play: {df['median_yards'].mean():.2f}")
    print(f"Mode yards per play: {df['mode_yards'].mean():.2f}")
    print(f"Standard deviation: {df['std_yards'].mean():.2f}")
    print(f"% positive plays: {df['pct_positive_plays'].mean():.1f}%")

    # Create plots
    create_scatter_plots(df)

    # Show top/bottom performers
    show_top_bottom_simple(df)

    # Raiders analysis
    analyze_raiders_simple(df)

    # Save data
    df.to_csv('/var/home/bigman/Documents/CodingProjects/Fantasy-Football-Tool/backup-prediction/simple_oline_metrics.csv', index=False)
    print(f"\nSimple metrics saved to simple_oline_metrics.csv")
    print(f"Plot saved to simple_oline_plots.png")

if __name__ == "__main__":
    main()