import os
import logging
from datetime import datetime
import csv
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define directories
log_dir = "log"
filtered_dir = "filtered"

# Function to clean player names by removing suffixes like "Jr.", "Sr.", "II", "III"
def clean_name(name):
    suffixes = ['Jr.', 'Sr.', 'II', 'III', 'IV', 'V']
    # Use regex to remove suffixes if they appear at the end of the name
    name = re.sub(r'\s+(?:' + '|'.join(suffixes) + r')$', '', name)
    return name

# Function to get the most recent player names file
def get_latest_player_file(log_dir):
    files = [f for f in os.listdir(log_dir) if f.startswith("players_") and f.endswith(".txt")]
    if not files:
        logging.error("No player files found in the log directory.")
        return None
    # Extract the timestamp part after "players_" and before ".txt"
    latest_file = max(files, key=lambda f: datetime.strptime(f.split('_')[1].replace('.txt', ''), "%Y%m%d-%H%M%S"))
    return os.path.join(log_dir, latest_file)

# Function to read player names from the latest file into a set
def load_player_names(latest_file):
    player_names = set()
    if not latest_file:
        return player_names
    try:
        with open(latest_file, "r") as file:
            for line in file:
                name = clean_name(line.strip())
                if name in player_names:
                    logging.warning(f"Duplicate player name found and ignored: {name}")
                else:
                    player_names.add(name)
        logging.info(f"Loaded player names from {latest_file}")
    except Exception as e:
        logging.error(f"Failed to load player names: {e}")
    return player_names

# Function to load pick number from log/pick.txt
def load_pick_number(log_dir):
    try:
        with open(os.path.join(log_dir, 'pick.txt'), 'r') as file:
            pick_number = int(file.read().strip())
        logging.info(f"Loaded pick number: {pick_number}")
        return pick_number
    except Exception as e:
        logging.error(f"Failed to load pick number: {e}")
        return None

# Function to load the CSV into a data structure and filter players based on criteria
def filter_players_from_csv(csv_file, player_names, pick_number):
    filtered_players = []
    try:
        with open(csv_file, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                cleaned_name = clean_name(row['Name'])
                if cleaned_name not in player_names:
                    # Apply additional filtering based on pick number and +/- 30 picks
                    adp = int(row['ADP'])
                    ecr = int(row['ECR'])
                    espn = int(row['ESPN'])
                    if (adp < pick_number + 30 or ecr < pick_number + 30 or espn < pick_number + 30):
                        filtered_players.append(row)
        logging.info(f"Filtered players, total remaining: {len(filtered_players)}")
    except Exception as e:
        logging.error(f"Failed to load or filter CSV file: {e}")
    return filtered_players

# Function to sort the filtered players by ECR and save them to a new CSV file
def save_filtered_players(filtered_players):
    if not filtered_players:
        logging.error("No players to save.")
        return
    try:
        os.makedirs(filtered_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filtered_file = os.path.join(filtered_dir, f"filtered_{timestamp}.csv")
        with open(filtered_file, "w", newline='') as file:
            fieldnames = filtered_players[0].keys()
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for player in sorted(filtered_players, key=lambda x: int(x['ECR'])):
                writer.writerow(player)
        logging.info(f"Filtered players saved to {filtered_file}")
    except Exception as e:
        logging.error(f"Failed to save filtered players: {e}")

def main():
    latest_file = get_latest_player_file(log_dir)
    if latest_file:
        player_names = load_player_names(latest_file)
        pick_number = load_pick_number(log_dir)
        if pick_number is not None:
            filtered_players = filter_players_from_csv("combined_with_depth.csv", player_names, pick_number)
            save_filtered_players(filtered_players)

if __name__ == "__main__":
    main()
