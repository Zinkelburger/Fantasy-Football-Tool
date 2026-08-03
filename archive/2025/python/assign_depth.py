import pandas as pd
import re

def clean_player_name(name: str) -> str:
    """Removes common suffixes (Jr., Sr., II, etc.) from a player's name."""
    if not isinstance(name, str):
        return '' # Return an empty string for non-string inputs like NaN
    return re.sub(r'\s+(?:Jr\.|Sr\.|II|III|IV|V)$', '', name, flags=re.IGNORECASE).strip()

try:
    # --- 1. Load and Clean Data ---
    df = pd.read_csv("FantasyPros_2025_Overall_ADP_Rankings.csv")

    df.rename(columns={"AVG": "Average_ADP"}, inplace=True)
    
    df['Player'] = df['Player'].apply(clean_player_name)
    df['POS'] = df['POS'].fillna('UNK')

    # --- 2. Filter Out Unwanted Positions ---
    df = df[~df['POS'].isin(['DST', 'K'])].copy()

    # --- 3. Calculate Depth Ranks and Handle No-Team Players ---
    df.sort_values('Average_ADP', inplace=True)
    df['Base_POS'] = df['POS'].str.replace(r'\d+', '', regex=True)
    
    # Calculate depth rank. This will create NaN for players without a team.
    df['Depth_Rank'] = df.groupby(['Team', 'Base_POS']).cumcount() + 1

    # Identify players without a team.
    no_team_mask = df['Team'].isnull()

    # **FIX 1: Handle NaN values BEFORE type conversion.**
    # For players with no team, set their NaN Depth_Rank to 0.
    df.loc[no_team_mask, 'Depth_Rank'] = 0

    # **FIX 2: Convert the entire column to integer now that NaNs are gone.**
    df['Depth_Rank'] = df['Depth_Rank'].astype(int)

    # Create the final 'Depth' string (e.g., 'RB1').
    df['Depth'] = df['Base_POS'] + df['Depth_Rank'].astype(str)
    
    # **FIX 3: Set the final 'Depth' string for no-team players.**
    df.loc[no_team_mask, 'Depth'] = 'NO TEAM'

    # --- 4. Finalize and Save ---
    # Select and reorder the final columns for the output file.
    final_cols = ['Player', 'Team', 'POS', 'Average_ADP', 'Depth', 'Depth_Rank']
    final_df = df[final_cols]

    final_df.to_csv("players_with_depth.csv", index=False)

    print("✅ Success! 'players_with_depth.csv' created.")
    print("\nPreview of the final data:")
    print(final_df.head(10))

except FileNotFoundError:
    print("❌ Error: 'FantasyPros_2025_Overall_ADP_Rankings.csv' not found.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")