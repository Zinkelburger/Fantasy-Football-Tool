#!/usr/bin/env python3
"""
FF Hound Substack scraper for fantasy football player analysis.

This script scrapes FF Hound Substack posts from the last week (since previous Sunday)
and extracts relevant content for each player on the user's fantasy team.
"""

import json
import sys
import os
import csv
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import time
from difflib import SequenceMatcher

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException



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
    """Get player names from cached CSV data for a specific team"""
    cache_dir = Path("espn_cache")
    rosters_file = cache_dir / "rosters.csv"

    if not rosters_file.exists():
        raise FileNotFoundError("ESPN cache not found. Please refresh data first.")

    players = []
    try:
        with open(rosters_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['team_id']) == team_id:
                    players.append({
                        "name": row['player_name'].strip(),
                        "position": row['position'],
                        "team": row['pro_team']
                    })
        return players
    except Exception as e:
        raise RuntimeError(f"Error reading cached roster: {e}")


def fuzzy_match_player_in_text(player_name: str, text: str, threshold: float = 0.6) -> bool:
    """Simple fuzzy matching to find player mentions in text"""
    if not player_name or not text:
        return False

    player_lower = player_name.lower()
    text_lower = text.lower()

    # Direct substring match first
    if player_lower in text_lower:
        return True

    # Try first and last name separately
    name_parts = player_lower.split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1]

        # Check if both first and last name appear in text
        if first_name in text_lower and last_name in text_lower:
            return True

        # Check last name with decent similarity
        words = text_lower.split()
        for word in words:
            if len(word) > 2 and SequenceMatcher(None, last_name, word).ratio() > threshold:
                return True

    return False


def generate_ffhound_urls_since_sunday(since_date: datetime) -> List[str]:
    """Generate FF Hound Substack URLs to check since the given date"""
    urls = []
    current_date = datetime.now()

    # Check each day from since_date to today
    check_date = since_date
    while check_date <= current_date:
        # FF Hound format: MDDYY (e.g., "92325" for 9/23/25)
        date_str = check_date.strftime("%-m%d%y")
        url = f"https://ffhound.substack.com/p/ff-hound-{date_str}-full-notes"
        urls.append(url)
        check_date += timedelta(days=1)

    return urls


def save_webpage_to_file(url: str, content: str, output_dir: Path) -> str:
    """Save webpage content to a file and return the filename"""
    # Create a safe filename from the URL
    import hashlib
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

    # Extract date from URL if possible for better naming
    filename_base = url.split('/')[-1] if '/' in url else f"ffhound_{url_hash}"
    if not filename_base.endswith('.html'):
        filename_base += '.html'

    filepath = output_dir / "raw_pages" / filename_base
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Saved webpage: {filepath}")
    return str(filepath)


def get_saved_webpage_path(url: str, output_dir: Path) -> Path:
    """Get the file path where a webpage would be saved"""
    filename_base = url.split('/')[-1] if '/' in url else f"ffhound_{url}"
    if not filename_base.endswith('.html'):
        filename_base += '.html'
    return output_dir / "raw_pages" / filename_base


def create_headless_driver():
    """Create a headless Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except WebDriverException as e:
        print(f"Error creating Chrome driver: {e}")
        print("Make sure Chrome and chromedriver are installed")
        return None


def download_webpage_if_needed(url: str, driver: webdriver.Chrome, output_dir: Path) -> bool:
    """Download webpage with Selenium only if it doesn't already exist"""
    saved_path = get_saved_webpage_path(url, output_dir)

    # Check if file already exists
    if saved_path.exists():
        print(f"✓ Already saved: {url}")
        return True

    try:
        print(f"Loading with Selenium: {url}")

        # Load the page
        driver.get(url)

        # Wait for content to load - look for article content
        try:
            # Wait for Substack article content to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".available-content, .post-content, article, .markup"))
            )
            print(f"✓ Content loaded: {url}")
        except TimeoutException:
            # Quick check if it's a "Page not found" before giving up
            if "Page not found" in driver.page_source:
                print(f"- Page not found: {url}")
            else:
                print(f"- Content loading timeout: {url}")
            return False

        # Get the page source after JavaScript execution
        page_source = driver.page_source

        # Check if we got a valid page (quick check for "page not found")
        if "404" in driver.title or "not found" in driver.title.lower() or "<h2>Page not found</h2>" in page_source:
            print(f"- Page not found: {url}")
            return False

        save_webpage_to_file(url, page_source, output_dir)
        print(f"✓ Downloaded with JS rendering: {url}")
        return True

    except WebDriverException as e:
        print(f"Error downloading {url}: {e}")
        return False


def load_saved_webpage(url: str, output_dir: Path) -> Optional[str]:
    """Load content from a saved webpage file"""
    saved_path = get_saved_webpage_path(url, output_dir)

    if not saved_path.exists():
        return None

    try:
        with open(saved_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading saved file {saved_path}: {e}")
        return None


def extract_player_mentions_from_html(html_content: str, player_name: str) -> List[str]:
    """Extract paragraphs mentioning the player from HTML content"""
    if not html_content or not player_name:
        return []

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Target the main content area specifically
    content_div = soup.find('div', class_='available-content')
    if not content_div:
        # Fallback to other content containers
        content_div = soup.find('div', class_='body markup') or soup.find('article') or soup

    # Remove script and style elements
    for script in content_div(["script", "style"]):
        script.decompose()

    matching_paragraphs = []

    # Look for text within specific HTML elements (paragraphs, list items)
    content_elements = content_div.find_all(['p', 'li'])

    for element in content_elements:
        text = element.get_text().strip()
        # Skip very short text
        if len(text) < 15:
            continue

        # Check if this element contains the player name
        if fuzzy_match_player_in_text(player_name, text):
            # Clean up the text and add it
            clean_text = ' '.join(text.split())  # Normalize whitespace
            if clean_text not in matching_paragraphs:  # Avoid duplicates
                matching_paragraphs.append(clean_text)

    return matching_paragraphs


def download_all_ffhound_pages(since_date: datetime, output_dir: Path) -> List[str]:
    """Download all FF Hound pages since the given date (if not already saved)"""
    print("Phase 1: Downloading FF Hound webpages with Selenium...")

    # Get URLs to check
    urls_to_check = generate_ffhound_urls_since_sunday(since_date)

    # Create headless Chrome driver
    driver = create_headless_driver()
    if not driver:
        print("Failed to create Chrome driver - cannot download pages")
        return []

    available_urls = []

    try:
        for url in urls_to_check:
            if download_webpage_if_needed(url, driver, output_dir):
                available_urls.append(url)

            # Be respectful to the server
            time.sleep(2)

    finally:
        # Always close the driver
        driver.quit()

    print(f"Phase 1 complete: {len(available_urls)} webpages available")
    return available_urls


def analyze_player_from_saved_files(player: Dict, available_urls: List[str], output_dir: Path) -> Dict:
    """Analyze a player using already saved webpage files"""
    player_name = player["name"]
    print(f"Analyzing {player_name} from saved files...")

    relevant_content = []

    for url in available_urls:
        # Load content from saved file
        html_content = load_saved_webpage(url, output_dir)

        if html_content:
            # Extract matching paragraphs
            mentions = extract_player_mentions_from_html(html_content, player_name)

            if mentions:
                saved_path = get_saved_webpage_path(url, output_dir)
                post_data = {
                    "url": url,
                    "saved_file": str(saved_path),
                    "date_scraped": datetime.now().isoformat(),
                    "mentions": mentions,
                    "mention_count": len(mentions)
                }
                relevant_content.append(post_data)

    print(f"Found {len(relevant_content)} FF Hound posts mentioning {player_name}")

    return {
        "player": player,
        "posts_found": len(relevant_content),
        "content": relevant_content
    }


def save_ffhound_results(player_results: Dict, output_dir: Path):
    """Save the FF Hound scraping results for a player to files"""
    player_name = player_results["player"]["name"]
    # Create a safe filename
    safe_name = re.sub(r'[^a-zA-Z0-9\s]', '', player_name).replace(' ', '_').lower()

    # Save JSON data
    json_filename = output_dir / f"{safe_name}_ffhound_analysis.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(player_results, f, indent=2, ensure_ascii=False)

    # Create readable text summary
    txt_filename = output_dir / f"{safe_name}_ffhound_summary.txt"

    with open(txt_filename, 'w', encoding='utf-8') as f:
        f.write(f"FF HOUND ANALYSIS FOR {player_name.upper()}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Position: {player_results['player']['position']}\n")
        f.write(f"Team: {player_results['player']['team']}\n")
        f.write(f"Posts found: {player_results['posts_found']}\n\n")

        if player_results["content"]:
            for i, post in enumerate(player_results["content"], 1):
                f.write(f"POST {i}: {post['url']}\n")
                f.write(f"Saved File: {post.get('saved_file', 'N/A')}\n")
                f.write(f"Scraped: {post['date_scraped']}\n")
                f.write(f"Mentions: {post['mention_count']}\n")
                f.write("-" * 40 + "\n")

                for j, mention in enumerate(post["mentions"], 1):
                    f.write(f"Mention {j}:\n{mention}\n\n")

                f.write("=" * 60 + "\n\n")
        else:
            f.write("No relevant FF Hound content found.\n")

    print(f"Saved FF Hound analysis for {player_name}")


def scrape_ffhound_for_team(team_id: int):
    """Main function to scrape FF Hound for all players on a team"""
    # Get the date of the previous Sunday
    since_sunday = get_previous_sunday()
    print(f"Looking for FF Hound posts since: {since_sunday}")

    # Create output directory
    output_dir = Path("ffhound_analysis")
    output_dir.mkdir(exist_ok=True)

    try:
        # Get team players from cached CSV data
        players = get_team_players(team_id)
        print(f"Found {len(players)} players on the team")

        # Phase 1: Download all webpages (skip if already saved)
        available_urls = download_all_ffhound_pages(since_sunday, output_dir)

        if not available_urls:
            return {"error": "No FF Hound webpages found for the specified date range"}

        print(f"\nPhase 2: Analyzing players from {len(available_urls)} saved webpages...")

        results = {
            "team_id": team_id,
            "scraped_at": datetime.now().isoformat(),
            "since_date": since_sunday.isoformat(),
            "players": []
        }

        # Phase 2: Analyze each player from saved files
        for i, player in enumerate(players, 1):
            print(f"Processing player {i}/{len(players)}: {player['name']}")

            player_results = analyze_player_from_saved_files(player, available_urls, output_dir)
            results["players"].append(player_results)

            # Save individual player results
            save_ffhound_results(player_results, output_dir)

        # Save summary results
        summary_file = output_dir / f"team_{team_id}_ffhound_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\nFF Hound analysis complete! Results saved to {output_dir}")

        # Print summary
        total_posts = sum(p["posts_found"] for p in results["players"])
        players_with_content = sum(1 for p in results["players"] if p["posts_found"] > 0)

        print(f"Summary:")
        print(f"- Webpages analyzed: {len(available_urls)}")
        print(f"- Total players: {len(players)}")
        print(f"- Players with FF Hound content: {players_with_content}")
        print(f"- Total posts found: {total_posts}")

        return results

    except Exception as e:
        return {"error": str(e)}


def main():
    """CLI entry point"""
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: ffhound_scraper.py scrape <team_id>"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "scrape":
        try:
            team_id = int(sys.argv[2])
            result = scrape_ffhound_for_team(team_id)
            print(json.dumps(result, indent=2))
        except ValueError:
            print(json.dumps({"error": "Invalid team ID - must be a number"}))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))


if __name__ == "__main__":
    main()