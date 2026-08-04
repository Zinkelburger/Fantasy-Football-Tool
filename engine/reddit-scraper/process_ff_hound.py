#!/usr/bin/env python3
"""
Separate FF Hound processing script that extracts player mentions from FF Hound files
and outputs clean analysis files with only lines mentioning the specific player.

This script:
1. Loads the player list from combined_with_depth.csv
2. Processes FF Hound HTML files for each player (skips already-processed players)
3. Extracts only lines that mention the player
4. Outputs to {player_slug}_ff_hound_discussion.txt files
"""

import os
import re
import glob
from typing import List, Dict
from bs4 import BeautifulSoup
from FootballPlayer import FootballPlayer
from main_scrape_reddit_api import generate_player_search_terms

def extract_ff_hound_player_mentions(ff_hound_dir: str, player: FootballPlayer) -> List[str]:
    """Extract player mentions from ff-hound HTML files, keeping only lines with player mentions"""
    if not os.path.exists(ff_hound_dir):
        print(f"FF Hound directory {ff_hound_dir} does not exist")
        return []
    
    # Generate search terms for this player
    search_terms = generate_player_search_terms(player)
    
    # Create regex patterns
    patterns = []
    for term_type, term in search_terms.items():
        if not term:
            continue
        
        escaped_term = re.escape(term)
        patterns.append(re.compile(rf'\b{escaped_term}\b', re.IGNORECASE))
        
        # For names with spaces, also try without spaces
        if ' ' in term:
            no_space_term = term.replace(' ', '')
            if len(no_space_term) > 2:
                patterns.append(re.compile(rf'\b{re.escape(no_space_term)}\b', re.IGNORECASE))
        
        # For names with initials, create variations
        if len(term.split()) > 1:
            first_part = term.split()[0]
            rest_parts = ' '.join(term.split()[1:])
            
            if len(first_part) <= 2:
                if len(first_part) == 2:
                    char1, char2 = first_part[0], first_part[1]
                    variations = [
                        f"{char1}\\.{char2}\\. {re.escape(rest_parts)}",
                        f"{char1}\\. {char2}\\. {re.escape(rest_parts)}",
                        f"{char1} {char2} {re.escape(rest_parts)}",
                    ]
                    for var in variations:
                        patterns.append(re.compile(rf'\b{var}\b', re.IGNORECASE))
    
    mentions = []
    
    # Process all HTML files in the ff-hound directory
    html_files = glob.glob(os.path.join(ff_hound_dir, "*.html"))
    
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            # Extract all text and split into lines
            text_content = soup.get_text()
            lines = text_content.split('\n')
            
            # Find lines that mention the player
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this line mentions the player
                for pattern in patterns:
                    if pattern.search(line):
                        mentions.append(line)
                        break
                        
        except Exception as e:
            print(f"Error processing {html_file}: {e}")
    
    return mentions

def process_player_ff_hound(player: FootballPlayer, ff_hound_dir: str, output_dir: str) -> bool:
    """Process FF Hound data for a single player"""
    
    # Extract mentions
    ff_hound_mentions = extract_ff_hound_player_mentions(ff_hound_dir, player)
    
    if not ff_hound_mentions:
        print(f"No FF Hound mentions found for {player.player_name}")
        return False
    
    # Create output file
    output_file = os.path.join(output_dir, f"{player.slug}_ff_hound_discussion.txt")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"FF HOUND EXPERT ANALYSIS FOR {player.player_name.upper()}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("--- FF HOUND EXPERT ANALYSIS ---\n\n")
        
        # Number the mentions for easier reading
        for i, mention in enumerate(ff_hound_mentions, 1):
            f.write(f"{i}. {mention}\n\n")
        
        f.write(f"\n--- PROCESSING METADATA ---\n")
        f.write(f"FF Hound mentions found: {len(ff_hound_mentions)}\n")
    
    print(f"Saved {len(ff_hound_mentions)} FF Hound mentions for {player.player_name} to {output_file}")
    return True

def main():
    """Process FF Hound data for all players"""

    # Configuration
    filtered_dir = "filtered_data"
    ff_hound_dir = "ff-hound"

    if not os.path.exists(ff_hound_dir):
        print(f"FF Hound directory {ff_hound_dir} does not exist")
        return

    # Create output directory
    os.makedirs(filtered_dir, exist_ok=True)

    players = FootballPlayer.from_csv("combined_with_depth.csv")

    processed_count = 0
    skipped_count = 0

    for player in players:
        output_file = os.path.join(filtered_dir, f"{player.slug}_ff_hound_discussion.txt")

        if os.path.exists(output_file):
            print(f"Skipping {player.player_name} - FF Hound already processed")
            skipped_count += 1
            continue

        print(f"Processing FF Hound data for {player.player_name}...")

        if process_player_ff_hound(player, ff_hound_dir, filtered_dir):
            processed_count += 1

    print(f"\nProcessing complete!")
    print(f"Processed: {processed_count} players")
    print(f"Skipped: {skipped_count} players (already processed)")

if __name__ == "__main__":
    main()
