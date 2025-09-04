#!/usr/bin/env python3

import pandas as pd
import os
import sys
import re

def clean_player_name(name: str) -> str:
    """Removes common suffixes (Jr., Sr., II, etc.) from a player's name."""
    if not isinstance(name, str):
        return ''
    return re.sub(r'\s+(?:Jr\.|Sr\.|II|III|IV|V)$', '', name, flags=re.IGNORECASE).strip()

def create_unified_csv(format_name):
    """
    Combine ESPN and Sleeper JuiceBoxOne data into unified format
    
    Args:
        format_name: 'PPR', 'Half PPR', or 'Standard'
    """
    print(f"Processing {format_name} format...")
    
    # File paths
    data_dir = "/home/bigman/Documents/CodingProjects/Fantasy-Football-Tool/2025/python/data"
    
    # Get all files and find the exact matches
    all_files = os.listdir(data_dir)
    
    espn_file = None
    sleeper_file = None
    
    # Find exact ESPN file
    for file in all_files:
        if "ESPN" in file and format_name in file:
            espn_file = os.path.join(data_dir, file)
            break
    
    # Find exact Sleeper file  
    for file in all_files:
        if "Sleeper" in file and format_name in file:
            sleeper_file = os.path.join(data_dir, file)
            break
    
    if not espn_file:
        print(f"ERROR: ESPN {format_name} file not found in {all_files}")
        return False
    if not sleeper_file:
        print(f"ERROR: Sleeper {format_name} file not found in {all_files}")
        return False
    
    # Load ESPN data
    print(f"Loading ESPN data from {espn_file}")
    espn_df = pd.read_csv(espn_file)
    
    # Load Sleeper data  
    print(f"Loading Sleeper data from {sleeper_file}")
    sleeper_df = pd.read_csv(sleeper_file)
    
    # Clean the dataframes - remove the first empty column if it exists
    if espn_df.columns[0].startswith('Unnamed') or espn_df.columns[0] == '':
        espn_df = espn_df.drop(espn_df.columns[0], axis=1)
    if sleeper_df.columns[0].startswith('Unnamed') or sleeper_df.columns[0] == '':
        sleeper_df = sleeper_df.drop(sleeper_df.columns[0], axis=1)
    
    print("ESPN columns:", list(espn_df.columns))
    print("Sleeper columns:", list(sleeper_df.columns))
    
    # Clean player names for matching
    espn_df['Name_Clean'] = espn_df['Name'].apply(clean_player_name)
    sleeper_df['Name_Clean'] = sleeper_df['Name'].apply(clean_player_name)
    
    # Use ESPN data as the base (it has ADP rank)
    base_df = espn_df.copy()
    
    # Create a lookup dictionary from Sleeper data
    sleeper_lookup = {}
    sleeper_rank_col = 'Sleeper ADP' if 'Sleeper ADP' in sleeper_df.columns else 'Sleeper'
    
    for _, row in sleeper_df.iterrows():
        clean_name = row['Name_Clean']
        sleeper_rank = row[sleeper_rank_col] if pd.notna(row[sleeper_rank_col]) else ""
        sleeper_lookup[clean_name] = str(sleeper_rank)
    
    # Create the unified dataframe
    unified_data = []
    
    for _, row in base_df.iterrows():
        clean_name = row['Name_Clean']
        
        # Get Sleeper rank for this player
        sleeper_rank = sleeper_lookup.get(clean_name, "")
        
        # Extract the data we need
        unified_row = {
            'Rank': row['ADP'] if pd.notna(row['ADP']) else "",
            'Player': row['Name'],
            'Team': row['Team'] if pd.notna(row['Team']) else "",
            'Bye': row['BYE'] if pd.notna(row['BYE']) else "",
            'POS': row['Pos'] if pd.notna(row['Pos']) else "",
            'ESPN_Rank': row['ESPN'] if pd.notna(row['ESPN']) else "",
            'Sleeper_Rank': sleeper_rank
        }
        
        unified_data.append(unified_row)
    
    # Create DataFrame
    unified_df = pd.DataFrame(unified_data)
    
    # Sort by Rank
    unified_df['Rank_Numeric'] = pd.to_numeric(unified_df['Rank'], errors='coerce')
    unified_df = unified_df.sort_values('Rank_Numeric').drop('Rank_Numeric', axis=1)
    
    # Determine output filename
    if format_name == "PPR":
        output_file = "ppr_with_depth.csv"
    elif format_name == "Half PPR":
        output_file = "0.5_ppr_with_depth.csv"
    elif format_name == "Standard":
        output_file = "std_with_depth.csv"
    else:
        print(f"ERROR: Unknown format {format_name}")
        return False
    
    # Save to CSV
    print(f"Saving to {output_file}")
    unified_df.to_csv(output_file, index=False)
    
    print(f"✅ Created {output_file} with {len(unified_df)} players")
    print(f"   Sample: {unified_df.iloc[0]['Player']} - ESPN: {unified_df.iloc[0]['ESPN_Rank']}, Sleeper: {unified_df.iloc[0]['Sleeper_Rank']}")
    
    return True

def main():
    """Main function to process all formats"""
    formats = ["PPR", "Half PPR", "Standard"]
    
    success_count = 0
    for format_name in formats:
        if create_unified_csv(format_name):
            success_count += 1
    
    print(f"\n✅ Successfully processed {success_count}/{len(formats)} formats")
    
    if success_count == len(formats):
        print("All files created successfully!")
        print("\nNext steps:")
        print("1. Run assign_depth.py if you want to add positional depth rankings")
        print("2. The Go application should now work with platform switching")
    else:
        print("Some files failed to process. Check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()