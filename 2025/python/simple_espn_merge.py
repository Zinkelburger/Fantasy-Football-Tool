#!/usr/bin/env python3
"""
Simple script to add just ESPN ranking to players.csv
"""

import pandas as pd

def main():
    print("Adding ESPN ranking to players.csv...")
    
    # Load JuiceBoxOne data
    import glob
    juicebox_files = glob.glob("./JuiceBoxOne*.csv")
    if not juicebox_files:
        print("Error: Could not find JuiceBoxOne CSV file")
        return
    juicebox_df = pd.read_csv(juicebox_files[0])
    
    # Load existing players data
    players_df = pd.read_csv("./players.csv")
    
    # Create a mapping from name to ESPN rank
    espn_mapping = {}
    for _, row in juicebox_df.iterrows():
        name = str(row['Name']).strip()
        espn_rank = str(row['ESPN']).strip()
        if name and espn_rank:
            espn_mapping[name.lower()] = espn_rank
    
    # Add ESPN_Rank column
    players_df['ESPN_Rank'] = ''
    
    # Match players and add ESPN ranking
    matches = 0
    for idx, row in players_df.iterrows():
        player_name = str(row['Player']).strip().lower()
        if player_name in espn_mapping:
            players_df.at[idx, 'ESPN_Rank'] = espn_mapping[player_name]
            matches += 1
    
    # Backup original and save updated
    players_df.to_csv('./players_backup.csv', index=False)
    players_df.to_csv('./players.csv', index=False)
    
    print(f"✅ Added ESPN rankings for {matches} players")
    print("✅ Backup saved as players_backup.csv")
    print("✅ Updated players.csv")

if __name__ == "__main__":
    main()
