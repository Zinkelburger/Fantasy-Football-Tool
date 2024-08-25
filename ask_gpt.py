import os
import sys
import openai
import pandas as pd
from datetime import datetime
import re
from thefuzz import fuzz, process
from dotenv import load_dotenv

GPT_MODEL = "gpt-4o"

load_dotenv()


def clean_name(name):
    suffixes = ["Jr.", "Sr.", "II", "III", "IV", "V"]
    name = re.sub(r"\s+(?:" + "|".join(suffixes) + r")$", "", name)
    return name.strip()


def get_most_recent_file(directory, prefix):
    files = []
    for filename in os.listdir(directory):
        if filename.startswith(prefix) and filename.endswith(".csv"):
            try:
                timestamp_str = filename.split(prefix)[1].split(".csv")[0]
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                files.append((timestamp, os.path.join(directory, filename)))
            except ValueError:
                continue

    if not files:
        raise FileNotFoundError(
            f"No files found with the prefix '{prefix}' in '{directory}'."
        )

    files.sort(reverse=True, key=lambda x: x[0])
    return files[0][1]


def extract_player_names_from_file(file_path):
    df = pd.read_csv(file_path)
    player_names = set(clean_name(name) for name in df["Name"].tolist())
    return player_names


# Get the ADP, depth for the player
def extract_player_stats(csv_path, player_name):
    df = pd.read_csv(csv_path)
    cleaned_player = clean_name(player_name)
    escaped_player = re.escape(cleaned_player)
    player_row = df[df["Name"].str.contains(escaped_player, case=False, na=False)]
    if not player_row.empty:
        row = player_row.iloc[0]
        player_stat = f"Name: {row['Name']}, Team: {row['Team']}, ADP: {row['ADP']}, FantasyPros: {row['FantasyPros']}, ESPN: {row['ESPN']}, Pos: {row['Pos']}, FantasyPros Tier: {row['FantasyPros Tier']}, ECR: {row['ECR']}, ECR vs ADP: {row['ECR vs ADP']}, Depth: {row['Depth']}"
        return player_stat
    else:
        return "No stats found for this player."


def get_current_team(team_file_path):
    try:
        with open(team_file_path, "r") as file:
            # Read all lines and strip any extra whitespace
            current_team = [line.strip() for line in file.readlines()]
            return current_team
    except FileNotFoundError:
        raise FileNotFoundError(f"Team file not found: {team_file_path}")
    except Exception as e:
        raise e


def load_playername_file(analysis_dir, player_name):
    """Load contents of a markdown file in the analysis directory."""
    md_files = [f for f in os.listdir(analysis_dir) if f.endswith(".md")]
    clean_player_name = clean_name(player_name)

    exact_matches = [
        f for f in md_files if clean_name(f.replace(".md", "")) == clean_player_name
    ]

    if exact_matches:
        chosen_file = exact_matches[0]
    else:
        chosen_file, match_score = process.extractOne(
            clean_player_name, md_files, scorer=fuzz.token_sort_ratio
        )
        if match_score < 80:  # Adjust threshold as needed
            print(
                f"Low confidence fuzzy match ({match_score}%): {player_name} -> {chosen_file}"
            )
        else:
            print(f"Fuzzy matched: {player_name} -> {chosen_file} ({match_score}%)")

    if chosen_file:
        filepath = os.path.join(analysis_dir, chosen_file)
        with open(filepath, "r") as f:
            content = f.read()
            return content
    return None


def get_relevant_context(
    recent_filtered_file, analysis_dir, stats_csv_file, current_team
):
    player_names = extract_player_names_from_file(recent_filtered_file)

    # Add player stats to the "Current Team" section
    combined_content = f"Current Team: {current_team}\n\n"
    for player_name in current_team:
        combined_content += f"-- Player Stats for {player_name} --\n"
        player_stats = extract_player_stats(stats_csv_file, player_name)
        combined_content += f"{player_stats}\n-- end stats --\n"

    combined_content += "\n\nDetailed Player Contexts:\n\n"

    # Add detailed player contexts and stats
    for player_name in player_names:
        player_context = load_playername_file(analysis_dir, player_name)
        if player_context:
            combined_content += f"-- {player_name} --\n"
            combined_content += player_context
            combined_content += f"\n-- end file for {player_name} --\n"

        # Add the player stats after the context
        combined_content += f"-- Player Stats for {player_name} --\n"
        player_stats = extract_player_stats(stats_csv_file, player_name)
        combined_content += f"{player_stats}\n-- end stats --\n"

    return combined_content


def stream_response(messages, api_key):
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model=GPT_MODEL,
        messages=messages,
        stream=True,
    )

    concat_response = ""
    for chunk in response:
        content = chunk.choices[0].get("delta", {}).get("content", "")
        if content:
            print(content, end="")
            concat_response += content

    return concat_response


def suggest_players(pick_number, api_key, context):
    prompt = f"""
It is pick {pick_number} of a 2024 fantasy football draft. 
Based on the following player stats and given these articles, output the top several players you think could help me the most along with an explanation, considering their value, upside, and drawbacks.
Consider players from different positions, e.g. TEs and QBs, just give me an overview of the situation. STD format.
The comments given are often relative to a player's ADP, keep the ADP and current pick in mind.
Finally, note the players I have on my team currently, and suggest handcuffs for them if you think its a good idea. Don't suggest a QB if I already have one, etc. Give useful advice.
In your response, note the ADP, ECR, and ESPN rankings for the player and consider their value relative to the pick. Give a summary of the most important players at the end once you are finished your explanations.

Here are the articles and stats:
{context}
\n
    """

    # Write the prompt to a file for inspection
    with open("gpt_query.txt", "w") as file:
        file.write(prompt)

    messages = [
        {
            "role": "system",
            "content": "You are a fantasy football expert giving draft advice.",
        },
        {"role": "user", "content": prompt},
    ]

    response = stream_response(messages, api_key)
    return response


def get_pick_number(log_file_path):
    try:
        with open(log_file_path, "r") as file:
            pick_number = file.readline().strip()
            if not pick_number.isdigit():
                raise ValueError(
                    f"Invalid pick number in {log_file_path}: {pick_number}"
                )
            return pick_number
    except FileNotFoundError:
        raise FileNotFoundError(f"Log file not found: {log_file_path}")
    except Exception as e:
        raise e


if __name__ == "__main__":
    filtered_dir = "filtered"
    file_prefix = "filtered_"
    log_file_path = "log/pick.txt"
    current_team_file = "log/current_team.txt"
    stats_csv_file = "combined_with_depth.csv"
    analysis_dir = "analysis"

    # Get the most recent filtered players file
    try:
        recent_filtered_file = get_most_recent_file(filtered_dir, file_prefix)
        print(f"Using file: {recent_filtered_file}")
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        sys.exit(1)

    # Get the pick number
    try:
        pick_number = get_pick_number(log_file_path)
        print(f"Pick number retrieved: {pick_number}")
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        sys.exit(1)

    # Get the drafting player's team
    try:
        current_team = get_current_team(current_team_file)
        print(f"Current team retrieved: {current_team}")
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        sys.exit(1)

    # Get the OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)

    print(f"Using OpenAI API Key: {api_key}")
    context = get_relevant_context(
        recent_filtered_file, analysis_dir, stats_csv_file, current_team
    )
    suggest_players(pick_number, api_key, context)
