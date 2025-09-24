#!/usr/bin/env python3
"""
Reddit scraper for fantasy football player analysis.

This script integrates with the ESPN API to get full player names
from a user's fantasy team and scrapes Reddit for posts about them
since the previous Sunday.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import re

# Add the reddit-scraper directory to the Python path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
REDDIT_SCRAPER_DIR = ROOT_DIR / "reddit-scraper"
sys.path.append(str(REDDIT_SCRAPER_DIR))

from RedditQuery import RedditQuery
from dotenv import load_dotenv
from espn_api.football import League


def load_env():
    """Load environment variables from parent directory .env file"""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        return True
    return False


def get_previous_sunday():
    """Get the date of the previous Sunday (or today if today is Sunday)"""
    today = datetime.now()
    days_since_sunday = today.weekday() + 1  # Monday is 0, Sunday is 6
    if days_since_sunday == 7:  # Today is Sunday
        return today.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        sunday = today - timedelta(days=days_since_sunday)
        return sunday.replace(hour=0, minute=0, second=0, microsecond=0)


def get_team_players(team_id: int) -> List[Dict]:
    """Get full player names from ESPN API for a specific team"""
    league_id = os.getenv('ESPN_LEAGUE_ID')
    year = os.getenv('ESPN_YEAR', '2025')
    swid = os.getenv('ESPN_SWID')
    espn_s2 = os.getenv('ESPN_S2')

    if not all([league_id, swid, espn_s2]):
        raise ValueError("Missing ESPN credentials")

    try:
        league = League(
            league_id=int(league_id),
            year=int(year),
            espn_s2=espn_s2,
            swid=swid
        )

        # Find the team
        target_team = None
        for team in league.teams:
            if team.team_id == int(team_id):
                target_team = team
                break

        if not target_team:
            raise ValueError(f"Team {team_id} not found")

        players = []
        for player in target_team.roster:
            # Get full name from ESPN API - no nicknames, just the official name
            full_name = player.name.strip()

            # Skip players with obviously incomplete names
            if len(full_name.split()) < 2:
                continue

            position = getattr(player, 'position', 'Unknown')
            pro_team = getattr(player, 'proTeam', 'N/A')

            players.append({
                "name": full_name,
                "position": position,
                "team": pro_team
            })

        return players

    except Exception as e:
        raise RuntimeError(f"Error fetching team roster: {e}")


def normalize_name_for_matching(name: str) -> str:
    """
    Normalize name for robust matching by removing punctuation and standardizing.
    Based on the reddit-scraper implementation.
    """
    if not name:
        return ""

    # Remove suffixes first
    suffixes = ["Jr.", "Sr.", "II", "III", "IV", "V"]
    suffix_pattern = r"\s+(?:" + "|".join(map(re.escape, suffixes)) + r")$"
    name = re.sub(suffix_pattern, "", name).strip()

    # Convert to lowercase
    name = name.lower()

    # Remove periods and hyphens from initials/names
    # A.J. -> aj, D.K. -> dk, Amon-Ra -> amonra
    name = re.sub(r'\.', '', name)
    name = re.sub(r'-', '', name)

    # Clean up extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def create_search_patterns(player_name: str) -> List[re.Pattern]:
    """Create regex patterns for finding player mentions in Reddit posts"""
    patterns = []

    # Normalize the name
    normalized = normalize_name_for_matching(player_name)
    name_parts = normalized.split()

    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1]

        # Full name pattern
        escaped_full = re.escape(normalized)
        patterns.append(re.compile(rf'\b{escaped_full}\b', re.IGNORECASE))

        # Handle initials (e.g., "aj brown" should match "a.j. brown")
        if len(first_name) <= 2:
            if len(first_name) == 2:
                char1, char2 = first_name[0], first_name[1]
                variations = [
                    f"{char1}\\.{char2}\\. {re.escape(last_name)}",
                    f"{char1}\\. {char2}\\. {re.escape(last_name)}",
                    f"{char1} {char2} {re.escape(last_name)}",
                ]
                for var in variations:
                    patterns.append(re.compile(rf'\b{var}\b', re.IGNORECASE))

        # First + Last name (skip middle names/initials)
        first_last = f"{first_name} {last_name}"
        if first_last != normalized:
            patterns.append(re.compile(rf'\b{re.escape(first_last)}\b', re.IGNORECASE))

    return patterns


def scrape_reddit_for_player(player: Dict, reddit_client: RedditQuery, since_date: datetime) -> Dict:
    """Scrape Reddit for posts about a specific player since the given date"""
    player_name = player["name"]
    print(f"Scraping Reddit for {player_name}...")

    # Create search patterns
    patterns = create_search_patterns(player_name)

    # Search Reddit using the full name
    subreddit = "fantasyfootball"
    search_queries = [
        f'"{player_name}"'
    ]

    all_submissions = []
    seen_ids = set()

    for query in search_queries:
        try:
            submissions = reddit_client.search_subreddit(subreddit, query, limit=25)
            for sub in submissions:
                if sub.id not in seen_ids:
                    all_submissions.append(sub)
                    seen_ids.add(sub.id)
        except Exception as e:
            print(f"Search failed for query '{query}': {e}")
            continue

    # Filter by date (since previous Sunday)
    since_timestamp = since_date.timestamp()
    recent_posts = [sub for sub in all_submissions if sub.created_utc >= since_timestamp]

    print(f"Found {len(recent_posts)} recent posts for {player_name}")

    relevant_content = []

    for post in recent_posts:
        # Check if any pattern matches in the post
        post_content = reddit_client.fetch_post_content(post)
        has_player_mention = any(pattern.search(post_content) for pattern in patterns)

        if not has_player_mention:
            # Check comments for mentions
            try:
                comment_chains = reddit_client.fetch_comments_chains(post)
                for chain in comment_chains:
                    chain_text = '\n'.join(chain)
                    if any(pattern.search(chain_text) for pattern in patterns):
                        has_player_mention = True
                        break
            except Exception as e:
                print(f"Error checking comments for post {post.id}: {e}")

        if has_player_mention:
            post_data = {
                "title": post.title,
                "url": post.url,
                "created": datetime.fromtimestamp(post.created_utc).isoformat(),
                "content": post_content,
                "comments": []
            }

            # Get relevant comments
            try:
                comment_chains = reddit_client.fetch_comments_chains(post)
                for chain in comment_chains:
                    chain_text = '\n'.join(chain)
                    if any(pattern.search(chain_text) for pattern in patterns):
                        # Extract only the relevant lines from the chain
                        relevant_lines = []
                        for comment in chain:
                            if any(pattern.search(comment) for pattern in patterns):
                                relevant_lines.append(comment)

                        if relevant_lines:
                            post_data["comments"].extend(relevant_lines)
            except Exception as e:
                print(f"Error processing comments for post {post.id}: {e}")

            relevant_content.append(post_data)

    return {
        "player": player,
        "posts_found": len(relevant_content),
        "content": relevant_content
    }


def save_player_results(player_results: Dict, output_dir: Path):
    """Save the scraping results for a player to a file"""
    player_name = player_results["player"]["name"]
    # Create a safe filename
    safe_name = re.sub(r'[^a-zA-Z0-9\s]', '', player_name).replace(' ', '_').lower()

    filename = output_dir / f"{safe_name}_reddit_analysis.json"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(player_results, f, indent=2, ensure_ascii=False)

    # Also create a readable text summary
    txt_filename = output_dir / f"{safe_name}_reddit_summary.txt"

    with open(txt_filename, 'w', encoding='utf-8') as f:
        f.write(f"REDDIT ANALYSIS FOR {player_name.upper()}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Position: {player_results['player']['position']}\n")
        f.write(f"Team: {player_results['player']['team']}\n")
        f.write(f"Posts found: {player_results['posts_found']}\n\n")

        if player_results["content"]:
            for i, post in enumerate(player_results["content"], 1):
                f.write(f"POST {i}: {post['title']}\n")
                f.write(f"URL: {post['url']}\n")
                f.write(f"Created: {post['created']}\n")
                f.write("-" * 40 + "\n")
                f.write(f"Content:\n{post['content']}\n\n")

                if post["comments"]:
                    f.write("Relevant Comments:\n")
                    for comment in post["comments"]:
                        f.write(f"- {comment}\n")
                f.write("\n" + "=" * 60 + "\n\n")
        else:
            f.write("No relevant Reddit discussion found.\n")


def scrape_team_reddit(team_id: int):
    """Main function to scrape Reddit for all players on a team"""
    load_env()

    # Get the date of the previous Sunday
    since_sunday = get_previous_sunday()
    print(f"Looking for posts since: {since_sunday}")

    # Create output directory
    output_dir = Path("reddit_analysis")
    output_dir.mkdir(exist_ok=True)

    try:
        # Get team players from ESPN API
        players = get_team_players(team_id)
        print(f"Found {len(players)} players on the team")

        # Initialize Reddit client
        reddit_client = RedditQuery()

        results = {
            "team_id": team_id,
            "scraped_at": datetime.now().isoformat(),
            "since_date": since_sunday.isoformat(),
            "players": []
        }

        # Scrape Reddit for each player
        for i, player in enumerate(players, 1):
            print(f"\nProcessing player {i}/{len(players)}: {player['name']}")

            player_results = scrape_reddit_for_player(player, reddit_client, since_sunday)
            results["players"].append(player_results)

            # Save individual player results
            save_player_results(player_results, output_dir)

            # Brief pause to be respectful to Reddit API
            import time
            time.sleep(0.5)

        # Save summary results
        summary_file = output_dir / f"team_{team_id}_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\nScraping complete! Results saved to {output_dir}")

        # Print summary
        total_posts = sum(p["posts_found"] for p in results["players"])
        players_with_content = sum(1 for p in results["players"] if p["posts_found"] > 0)

        print(f"Summary:")
        print(f"- Total players: {len(players)}")
        print(f"- Players with Reddit content: {players_with_content}")
        print(f"- Total posts found: {total_posts}")

        return results

    except Exception as e:
        return {"error": str(e)}


def main():
    """CLI entry point"""
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: reddit_scraper.py scrape <team_id>"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "scrape":
        try:
            team_id = int(sys.argv[2])
            result = scrape_team_reddit(team_id)
            print(json.dumps(result, indent=2))
        except ValueError:
            print(json.dumps({"error": "Invalid team ID - must be a number"}))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))


if __name__ == "__main__":
    main()