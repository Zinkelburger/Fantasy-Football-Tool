#!/usr/bin/env python3
"""
What Kicker Do I Pick?

Displays kicker rankings for 2025 filtered to only show kickers available
in your ESPN fantasy league.
"""

import pandas as pd
import os
import argparse
import nflreadpy as nfl
from pathlib import Path
from dotenv import load_dotenv
from espn_api.football import League

# ANSI escape codes for formatting
BOLD = '\033[1m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'
HIGHLIGHT = f'{BOLD}{GREEN}'


def parse_args():
    parser = argparse.ArgumentParser(description='What Kicker Do I Pick? - ESPN Fantasy Kicker Rankings')
    parser.add_argument('--all', action='store_true', help='Show all available kickers (no truncation)')
    return parser.parse_args()


def load_env():
    """Load environment variables from .env file"""
    # Try multiple locations for .env file
    possible_paths = [
        Path(__file__).parent / '.env',
        Path(__file__).parent.parent / 'start-sit-weekly' / '.env'
    ]

    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded .env from: {env_path}")
            return True
    return False


def get_rostered_kickers_and_my_kicker():
    """Get all kickers currently on teams in the ESPN league, and identify MY kicker"""
    league_id = os.getenv('ESPN_LEAGUE_ID')
    year = os.getenv('ESPN_YEAR', '2025')
    swid = os.getenv('ESPN_SWID')
    espn_s2 = os.getenv('ESPN_S2')
    my_team_id = os.getenv('ESPN_TEAM_ID')
    selected_team = os.getenv('SELECTED_TEAM')

    if not all([league_id, swid, espn_s2]):
        print("Error: Missing ESPN credentials in .env file")
        return [], None

    try:
        league = League(
            league_id=int(league_id),
            year=int(year),
            espn_s2=espn_s2,
            swid=swid
        )

        rostered_kickers = []
        my_kicker = None
        print(f"Found {len(league.teams)} teams in league")

        for team in league.teams:
            team_kickers = []
            is_my_team = False
            
            # Check if this is my team
            if my_team_id and str(team.team_id) == str(my_team_id):
                is_my_team = True
            elif selected_team and team.team_name == selected_team:
                is_my_team = True
            
            for player in team.roster:
                if player.position == 'K':
                    full_name = player.name
                    rostered_kickers.append(full_name)
                    team_kickers.append(full_name)
                    
                    # If this is my team, this is my kicker
                    if is_my_team:
                        my_kicker = full_name

            if team_kickers:
                team_label = f"{HIGHLIGHT}{team.team_name} (YOUR TEAM){RESET}" if is_my_team else team.team_name
                kicker_label = f"{HIGHLIGHT}{', '.join(team_kickers)}{RESET}" if is_my_team else ', '.join(team_kickers)
                print(f"  {team_label}: {kicker_label}")
            else:
                print(f"  {team.team_name}: No kickers")

        print(f"\nTotal rostered kickers found: {len(rostered_kickers)}")
        if rostered_kickers:
            print(f"Kickers: {', '.join(sorted(rostered_kickers))}")
        
        if my_kicker:
            print(f"\n{CYAN}Your kicker: {HIGHLIGHT}{my_kicker}{RESET}")

        return rostered_kickers, my_kicker

    except Exception as e:
        print(f"Error connecting to ESPN league: {e}")
        return [], None


def get_short_name(full_name):
    """Convert full name to first initial + last name format"""
    parts = full_name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}.{parts[-1]}"
    return full_name


def is_kicker_rostered(kicker_name, rostered_list):
    """Check if a kicker is rostered using first initial + last name matching"""
    # If kicker_name is already in short format (like "C.Dicker"), use as-is
    if '.' in kicker_name and len(kicker_name.split()) == 1:
        short_kicker = kicker_name
    else:
        short_kicker = get_short_name(kicker_name)

    # Convert all rostered names to short format for comparison
    rostered_short = [get_short_name(name) for name in rostered_list]

    is_rostered = short_kicker in rostered_short

    if not is_rostered:
        print(f"  {kicker_name} ({short_kicker}) - AVAILABLE")
    else:
        print(f"  {kicker_name} ({short_kicker}) - ROSTERED")

    return is_rostered


def get_nflelo_data():
    """Get latest NFL Elo implied scores and matchup data"""
    url = "https://raw.githubusercontent.com/greerreNFL/nfelo/main/output_data/nfelo_games.csv"

    try:
        df = pd.read_csv(url)

        # Filter 2025 games
        df_2025 = df[df['game_id'].str.startswith('2025_')].copy()

        if len(df_2025) == 0:
            print("No 2025 NFL Elo data available")
            return {}

        # Parse week from game_id and get latest week
        df_2025['week'] = df_2025['game_id'].str.split('_').str[1].astype(int)
        latest_week = df_2025['week'].max()

        # Get current week data (latest week + 1 for upcoming games)
        current_week = latest_week + 1

        print(f"Getting matchup data for Week {current_week}")

        # For current week predictions, we need the most recent completed week's data
        # and extrapolate for upcoming matchups
        week_data = df_2025[df_2025['week'] == latest_week].copy()
        week_data = week_data.drop_duplicates(subset=['game_id'])

        team_data = {}

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
            home_implied = (total_line - home_line) / 2
            away_implied = (total_line + home_line) / 2

            team_data[home_team] = {
                'opponent': away_team,
                'implied_score': home_implied,
                'is_home': True,
                'total': total_line,
                'week': current_week
            }

            team_data[away_team] = {
                'opponent': home_team,
                'implied_score': away_implied,
                'is_home': False,
                'total': total_line,
                'week': current_week
            }

        return team_data

    except Exception as e:
        print(f"Error fetching NFL Elo data: {e}")
        return {}


def get_kicker_team_mapping():
    """Get kicker teams from most recent week's NFL play-by-play data"""
    try:
        print("Loading NFL play-by-play data to determine kicker teams...")
        pbp = nfl.load_pbp(seasons=[2025]).to_pandas()

        # Get most recent week
        latest_week = pbp['week'].max()
        print(f"Using Week {latest_week} data for team assignments")

        # Filter to most recent week for current team assignments
        recent_pbp = pbp[pbp['week'] == latest_week].copy()

        # Get kicker data from field goals and extra points
        kicker_data = []

        # Field goals
        fg_data = recent_pbp[recent_pbp['field_goal_attempt'] == 1]
        for _, row in fg_data.iterrows():
            if pd.notna(row['kicker_player_name']) and pd.notna(row['posteam']):
                kicker_data.append({
                    'kicker': row['kicker_player_name'],
                    'team': row['posteam']
                })

        # Extra points
        xp_data = recent_pbp[recent_pbp['extra_point_attempt'] == 1]
        for _, row in xp_data.iterrows():
            if pd.notna(row['kicker_player_name']) and pd.notna(row['posteam']):
                kicker_data.append({
                    'kicker': row['kicker_player_name'],
                    'team': row['posteam']
                })

        if not kicker_data:
            print("No kicker data found, falling back to full season data...")
            # Fall back to full season if no recent week data
            fg_data = pbp[pbp['field_goal_attempt'] == 1]
            xp_data = pbp[pbp['extra_point_attempt'] == 1]

            for _, row in fg_data.iterrows():
                if pd.notna(row['kicker_player_name']) and pd.notna(row['posteam']):
                    kicker_data.append({
                        'kicker': row['kicker_player_name'],
                        'team': row['posteam']
                    })

            for _, row in xp_data.iterrows():
                if pd.notna(row['kicker_player_name']) and pd.notna(row['posteam']):
                    kicker_data.append({
                        'kicker': row['kicker_player_name'],
                        'team': row['posteam']
                    })

        # Create mapping, using most recent team for each kicker
        kicker_df = pd.DataFrame(kicker_data)
        if not kicker_df.empty:
            # Get the most common team for each kicker (in case of trades)
            kicker_teams = kicker_df.groupby('kicker')['team'].agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[-1]).to_dict()
            print(f"Found {len(kicker_teams)} kickers with team assignments")
            return kicker_teams
        else:
            print("No kicker data found")
            return {}

    except Exception as e:
        print(f"Error getting kicker teams from game data: {e}")
        return {}


def match_kicker_name(short_name, kicker_teams_dict):
    """Match abbreviated kicker name (C.Dicker) with full name from game data"""
    # First try exact match
    if short_name in kicker_teams_dict:
        return kicker_teams_dict[short_name]

    # Extract first initial and last name from short format
    if '.' in short_name and len(short_name.split()) == 1:
        parts = short_name.split('.')
        if len(parts) == 2:
            first_initial = parts[0]
            last_name = parts[1]

            # Look for matching full names
            for full_name, team in kicker_teams_dict.items():
                name_parts = full_name.split()
                if len(name_parts) >= 2:
                    if (name_parts[0][0].upper() == first_initial.upper() and
                        name_parts[-1].upper() == last_name.upper()):
                        return team

    # No fallback to static mapping - just return N/A if not found in game data
    return 'N/A'


def add_matchup_data(rankings_df):
    """Add NFL Elo matchup data to kicker rankings"""
    nflelo_data = get_nflelo_data()
    kicker_teams = get_kicker_team_mapping()

    if not nflelo_data:
        # Add empty columns if no data available
        rankings_df['team'] = 'N/A'
        rankings_df['opponent'] = 'N/A'
        rankings_df['implied_score'] = 0
        rankings_df['game_total'] = 0
        rankings_df['is_home'] = False
        return rankings_df

    # Add matchup data for each kicker
    matchup_data = []
    for _, row in rankings_df.iterrows():
        kicker = row['kicker']
        team = match_kicker_name(kicker, kicker_teams)

        if team != 'N/A' and team in nflelo_data:
            team_info = nflelo_data[team]
            matchup_data.append({
                'team': team,
                'opponent': team_info['opponent'],
                'implied_score': round(team_info['implied_score'], 1),
                'game_total': round(team_info['total'], 1),
                'is_home': team_info['is_home']
            })
        else:
            matchup_data.append({
                'team': team,
                'opponent': 'N/A',
                'implied_score': 0,
                'game_total': 0,
                'is_home': False
            })

    # Add to dataframe
    matchup_df = pd.DataFrame(matchup_data)
    rankings_df = pd.concat([rankings_df.reset_index(drop=True), matchup_df], axis=1)

    return rankings_df


def load_kicker_rankings():
    """Load the 2025 kicker rankings from CSV file"""
    rankings_file = Path(__file__).parent / 'kicker_rankings_2025.csv'

    if not rankings_file.exists():
        print(f"Error: Kicker rankings file not found at {rankings_file}")
        return None

    try:
        df = pd.read_csv(rankings_file)
        return df
    except Exception as e:
        print(f"Error loading kicker rankings: {e}")
        return None


def print_rankings_with_highlight(display_df, my_kicker):
    """Print rankings table with your kicker highlighted"""
    table_str = display_df.to_string(index=False)
    lines = table_str.split('\n')
    
    # Print header
    print(lines[0])
    
    # Normalize my kicker name for comparison
    my_kicker_last = my_kicker.split()[-1].lower() if my_kicker else None
    
    for line in lines[1:]:
        # Check if this line contains my kicker
        if my_kicker_last:
            # Extract kicker name from the line (second column)
            parts = line.split()
            if len(parts) >= 2:
                line_kicker = parts[1]  # Kicker name
                line_kicker_last = line_kicker.split('.')[-1].lower() if '.' in line_kicker else line_kicker.lower()
                if line_kicker_last == my_kicker_last:
                    print(f"{HIGHLIGHT}{line}{RESET}  ← YOUR KICKER")
                    continue
        print(line)


def main():
    """Main function to display available kicker rankings"""
    args = parse_args()
    
    print("🏈 WHAT KICKER DO I PICK? 🏈")
    print("=" * 50)

    # Load environment variables
    if not load_env():
        print("Warning: .env file not found. Make sure ESPN credentials are set.")

    # Load kicker rankings
    rankings_df = load_kicker_rankings()
    if rankings_df is None:
        return

    # Add NFL Elo matchup data
    print("Fetching NFL Elo matchup data...")
    rankings_df = add_matchup_data(rankings_df)

    # Get rostered kickers from ESPN league (and identify my kicker)
    print("Fetching rostered kickers from your ESPN league...")
    rostered_kickers, my_kicker = get_rostered_kickers_and_my_kicker()

    if not rostered_kickers:
        print("Could not fetch rostered kickers. Showing all rankings instead.")
        available_df = rankings_df
    else:
        print(f"Found {len(rostered_kickers)} rostered kickers")

        # Filter out rostered kickers using improved matching
        available_mask = ~rankings_df['kicker'].apply(lambda x: is_kicker_rostered(x, rostered_kickers))
        available_df = rankings_df[available_mask].copy()

        if available_df.empty:
            print("No available kickers found in rankings!")
            return

    # Reset rank for available kickers
    available_df = available_df.reset_index(drop=True)
    available_df['available_rank'] = range(1, len(available_df) + 1)

    # Display results - first show MY kicker's ranking
    if my_kicker:
        my_kicker_short = get_short_name(my_kicker)
        my_kicker_row = rankings_df[rankings_df['kicker'].apply(lambda x: get_short_name(x) if '.' not in x else x) == my_kicker_short]
        if my_kicker_row.empty:
            # Try matching by last name
            my_kicker_last = my_kicker.split()[-1].lower()
            my_kicker_row = rankings_df[rankings_df['kicker'].str.lower().str.contains(my_kicker_last)]
        
        if not my_kicker_row.empty:
            my_rank = my_kicker_row.iloc[0]['rank']
            my_pts = my_kicker_row.iloc[0]['total_fantasy_points']
            print(f"\n{HIGHLIGHT}📍 YOUR KICKER: {my_kicker} - Rank #{int(my_rank)}, {my_pts:.1f} total pts{RESET}")

    print(f"\n📊 AVAILABLE KICKER RANKINGS - 2025 SEASON")
    print("=" * 100)
    print(f"Showing available kickers (filtered from ESPN league)")
    print("=" * 100)

    # Show kickers with matchup data
    # Use columns that exist in the CSV
    display_cols = ['available_rank', 'kicker', 'fg_made', 'fg_pct', 'team', 'opponent', 'implied_score',
                    'game_total', 'total_fantasy_points']
    
    if args.all:
        display_df = available_df[display_cols].copy()
    else:
        display_df = available_df.head(15)[display_cols].copy()

    # Format display
    display_df.columns = ['Rank', 'Kicker', 'FG Made', 'FG%', 'Team', 'Opp', 'Team Score', 'Game Total', 'Total Pts']
    display_df['FG%'] = display_df['FG%'].round(0).astype(int)

    # Print with highlighting
    print_rankings_with_highlight(display_df, my_kicker)

    if not args.all and len(available_df) > 15:
        print(f"\n... and {len(available_df) - 15} more available kickers (use --all to show all)")

    # Show summary
    if rostered_kickers:
        print(f"\n📋 ROSTERED KICKERS ({len(rostered_kickers)}):")
        print(", ".join(sorted(rostered_kickers)))

    # Recommendation
    best_available = display_df.iloc[0]['Kicker']
    print(f"\n🎯 RECOMMENDATION: Consider picking up {best_available} (Rank #{display_df.iloc[0]['Rank']})")
    
    if my_kicker:
        # Compare your kicker to best available
        my_kicker_short = get_short_name(my_kicker)
        my_kicker_last = my_kicker.split()[-1].lower()
        my_kicker_row = rankings_df[rankings_df['kicker'].str.lower().str.contains(my_kicker_last)]
        best_row = available_df.iloc[0]
        
        if not my_kicker_row.empty:
            my_rank = int(my_kicker_row.iloc[0]['rank'])
            best_rank = int(best_row['rank'])
            
            if best_rank < my_rank:
                diff = my_rank - best_rank
                print(f"{YELLOW}⚠️  {best_available} is ranked {diff} spots higher than your kicker ({my_kicker}){RESET}")
            else:
                print(f"{GREEN}✅ Your kicker ({my_kicker}) is ranked higher than the best available!{RESET}")


if __name__ == "__main__":
    main()