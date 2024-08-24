import pandas as pd
import os
from thefuzz import fuzz 
import re

# Clean player names by removing suffixes
def clean_name(name):
    suffixes = ['Jr.', 'Sr.', 'II', 'III', 'IV', 'V']
    name = re.sub(r'\s+(?:' + '|'.join(suffixes) + r')$', '', name)
    return name.strip()

# Load the ADP list CSV
def load_adp_list(adp_csv_path):
    # Read the CSV file
    adp_df = pd.read_csv(adp_csv_path)
    
    # Rename columns to match the previous format if necessary
    adp_df.rename(columns={"Name": "Player"}, inplace=True)
    
    # Keep necessary columns (you can adjust as needed)
    adp_df = adp_df[["Player", "Team", "ADP", "Pos", "ECR"]]
    
    return adp_df

# Find the best note file for a player using fuzzy matching
def find_note_for_player(player_name, notes_dir):
    cleaned_player_name = clean_name(player_name).title()
    best_match = None
    highest_score = 0
    
    for note in os.listdir(notes_dir):
        note_name = os.path.splitext(note)[0].replace("_", " ").title()  # Remove the file extension and title-case it
        
        # First, try an exact match
        if cleaned_player_name == note_name:
            return note, 100  # Return only the filename, not the full path
        
        # If no exact match, use fuzzy matching to find the closest match
        score = fuzz.partial_ratio(cleaned_player_name, note_name)
        if score > highest_score:
            highest_score = score
            best_match = note
    
    # If no exact match was found, return the closest match with its score
    return best_match if best_match else None, highest_score

# Update the ADP list by removing drafted players
def update_adp_list(adp_df, drafted_players):
    return adp_df[~adp_df["Player"].isin(drafted_players)]

# Log missing notes
def log_missing_notes(players_df, notes_dir):
    not_found = []
    for _, row in players_df.iterrows():
        player = row["Player"]
        note_name, score = find_note_for_player(player, notes_dir)
        if not note_name or score < 100:  # Log only if no exact match or if fuzzy match isn't perfect
            closest_file = note_name if note_name else "N/A"
            not_found.append({"Player": player, "Fuzzy Score": score, "Closest File": closest_file})
    
    if not_found:
        not_found_df = pd.DataFrame(not_found)
        not_found_df.to_csv("not_found.csv", index=False)
        print("Players not found logged to not_found.csv")

def main(adp_csv_path, drafted_players, notes_dir):
    adp_df = load_adp_list(adp_csv_path)
    adp_df = update_adp_list(adp_df, drafted_players)

    # Convert remaining players to a DataFrame
    remaining_players_df = adp_df[["Player", "Team", "Pos", "ECR"]]

    # Log missing notes
    log_missing_notes(remaining_players_df, notes_dir)

    return adp_df

# Example usage
if __name__ == "__main__":
    remaining_players_df = main(
        adp_csv_path="combined_with_depth.csv",
        drafted_players=[""],  # Example drafted player
        notes_dir="analysis"
    )
    print(remaining_players_df)
