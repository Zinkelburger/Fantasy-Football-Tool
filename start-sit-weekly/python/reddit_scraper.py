#!/usr/bin/env python3
"""
Reddit scraper using fuzzy matching for fantasy football player analysis.
"""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

# You must install this library: pip install thefuzz python-Levenshtein
from thefuzz import fuzz

from RedditQuery import RedditQuery
from dotenv import load_dotenv
from espn_api.football import League

# --- SETUP ---
SCRIPT_DIR = Path(__file__).resolve().parent  # <<< ADD THIS LINE

# --- CONFIGURATION ---
# How confident do we need to be for a match? (0-100)
# 90 is a good starting point for high-quality matches.
CONFIDENCE_THRESHOLD = 90
SUBREDDIT_TO_SEARCH = "fantasyfootball"
OUTPUT_DIR = Path("reddit_analysis")

def load_environment_variables():
    """Load environment variables from the .env file."""
    # Build the path to the .env file relative to the script's parent directory
    env_path = SCRIPT_DIR.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print("✅ Environment variables loaded.")
        return True
    print(f"⚠️  Warning: .env file not found at {env_path}")
    return False

# This is the NEW, corrected version
def load_nicknames() -> Dict[str, List[str]]:
    """Loads player nicknames from nicknames.json, located next to the script."""
    # Build the full path from the script's directory
    nicknames_path = SCRIPT_DIR / "nicknames.json" # <--- This path is now absolute
    if nicknames_path.exists():
        with open(nicknames_path, 'r', encoding='utf-8') as f:
            print("✅ Nicknames file loaded.")
            return json.load(f)
    print(f"ℹ️  Info: nicknames.json not found at {nicknames_path}, continuing without it.")
    return {}

def get_start_date() -> datetime:
    """Get the date of the previous Sunday."""
    today = datetime.now()
    # today.weekday() is 0 for Monday, 6 for Sunday
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    return sunday.replace(hour=0, minute=0, second=0, microsecond=0)

# --- ESPN API ---

def get_players_from_team(team_id: int) -> List[Dict]:
    """Gets a list of player dictionaries for a given ESPN fantasy team."""
    try:
        league = League(
            league_id=int(os.getenv('ESPN_LEAGUE_ID')),
            year=int(os.getenv('ESPN_YEAR', str(datetime.now().year))),
            espn_s2=os.getenv('ESPN_S2'),
            swid=os.getenv('ESPN_SWID')
        )
        target_team = next((t for t in league.teams if t.team_id == team_id), None)

        if not target_team:
            raise ValueError(f"Team with ID {team_id} not found in the league.")

        players = []
        for player in target_team.roster:
            if len(player.name.split()) >= 2: # Skip players with incomplete names
                players.append({
                    "name": player.name.strip(),
                    "position": player.position,
                    "team": player.proTeam
                })
        print(f"✅ Found {len(players)} players on team {team_id}.")
        return players
    except Exception as e:
        print(f"❌ Error fetching players from ESPN: {e}")
        return []

# --- REDDIT SCRAPING CORE ---

def find_player_mentions(player: Dict, nicknames: List[str], reddit: RedditQuery, since_ts: float) -> List[Dict]:
    """
    Uses the RedditQuery helper to find all mentions for a player with metadata.
    Returns structured data with post/comment details for UI display.
    """
    player_full_name = player["name"]
    names_to_check = [player_full_name] + nicknames

    print(f"   - Searching for '{player_full_name}' (and {len(nicknames)} nicknames)...")

    # Get structured mentions with metadata
    mentions = reddit.find_mentions_with_metadata(
        subreddit=SUBREDDIT_TO_SEARCH,
        search_query=f'"{player_full_name}"', # Use full name to find relevant threads
        keywords=names_to_check,
        since_timestamp=since_ts,
        confidence_threshold=CONFIDENCE_THRESHOLD
    )

    return mentions

# --- FILE SAVING & MAIN LOGIC ---

def save_results_to_file(player: Dict, mentions: List[Dict]):
    """Saves the found mentions as structured JSON data."""
    player_name = player["name"]
    safe_name = "".join(c for c in player_name if c.isalnum() or c in " ").replace(" ", "_").lower()

    # Save as JSON for structured access
    json_filename = OUTPUT_DIR / f"{safe_name}_reddit.json"

    data = {
        "player": {
            "name": player_name,
            "position": player['position'],
            "team": player['team']
        },
        "scraped_at": datetime.now().isoformat(),
        "posts": mentions
    }

    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Also save simple text summary for AI processing
    text_filename = OUTPUT_DIR / f"{safe_name}_reddit_summary.txt"
    with open(text_filename, 'w', encoding='utf-8') as f:
        if mentions:
            for mention in mentions:
                # Add post context if it exists
                if mention.get('post_body'):
                    f.write(f"Post: {mention['post_title']}\n{mention['post_body']}\n\n")

                # Add relevant comments
                for comment in mention.get('relevant_comments', []):
                    f.write(f"Comment: {comment['body']}\n\n")
        else:
            f.write("No relevant Reddit discussion found.\n")

    print(f"   - Saved {len(mentions)} posts to {json_filename}")
    print(f"   - Created text summary at {text_filename}")

def main():
    """Main script execution."""
    if len(sys.argv) < 2:
        print("Usage: python reddit_scraper.py <team_id>")
        sys.exit(1)
        
    try:
        team_id = int(sys.argv[1])
    except ValueError:
        print("Error: Team ID must be a number.")
        sys.exit(1)
        
    print("🚀 Starting Reddit Scraper...")
    
    load_environment_variables()
    nicknames_db = load_nicknames()
    start_date = get_start_date()
    start_timestamp = start_date.timestamp()
    
    print(f"🔍 Searching for posts since {start_date.strftime('%Y-%m-%d')}")
    
    players = get_players_from_team(team_id)
    if not players:
        print("No players found. Exiting.")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    reddit = RedditQuery()
    
    for i, player in enumerate(players, 1):
        print(f"\n({i}/{len(players)}) Processing {player['name']}...")
        player_nicknames = nicknames_db.get(player["name"], [])
        
        mentions = find_player_mentions(player, player_nicknames, reddit, start_timestamp)
        save_results_to_file(player, mentions)
        
        # Brief pause to be respectful to Reddit's API
        time.sleep(1)

    print("\n🎉 Scraping complete!")
    print(f"All results saved in the '{OUTPUT_DIR}' directory.")

if __name__ == "__main__":
    main()