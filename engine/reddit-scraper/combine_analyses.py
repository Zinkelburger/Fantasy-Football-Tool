#!/usr/bin/env python3
"""
Combine Reddit and FF Hound analysis files into final discussion files.

This script:
1. Finds all _reddit_discussion.txt files
2. Looks for corresponding _ff_hound_discussion.txt files
3. Combines them into _final_discussion.txt files
4. Maintains proper formatting and structure
"""

import os
import glob
from typing import Optional

def read_file_content(filepath: str) -> Optional[str]:
    """Read file content safely"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def combine_player_analyses(player_slug: str, filtered_dir: str) -> bool:
    """Combine Reddit and FF Hound analyses for a single player"""
    
    reddit_file = os.path.join(filtered_dir, f"{player_slug}_reddit_discussion.txt")
    ff_hound_file = os.path.join(filtered_dir, f"{player_slug}_ff_hound_discussion.txt")
    final_file = os.path.join(filtered_dir, f"{player_slug}_final_discussion.txt")
    
    # Check if Reddit file exists
    if not os.path.exists(reddit_file):
        print(f"Reddit file not found: {reddit_file}")
        return False
    
    # Read Reddit content
    reddit_content = read_file_content(reddit_file)
    if not reddit_content:
        return False
    
    # Read FF Hound content if available
    ff_hound_content = None
    if os.path.exists(ff_hound_file):
        ff_hound_content = read_file_content(ff_hound_file)
    
    # Extract player name from Reddit content
    lines = reddit_content.split('\n')
    player_name = "UNKNOWN PLAYER"
    for line in lines:
        if line.startswith("REDDIT FANTASY FOOTBALL ANALYSIS FOR "):
            player_name = line.replace("REDDIT FANTASY FOOTBALL ANALYSIS FOR ", "").strip()
            break
    
    # Create combined content
    with open(final_file, 'w', encoding='utf-8') as f:
        f.write(f"FANTASY FOOTBALL ANALYSIS FOR {player_name}\n")
        f.write("=" * 80 + "\n\n")
        
        # Add Reddit content (skip the header)
        reddit_lines = reddit_content.split('\n')
        # Skip the first two lines (header and separator)
        reddit_body = '\n'.join(reddit_lines[2:])
        
        if reddit_body.strip():
            f.write(reddit_body)
            f.write("\n\n")
        
        # Add FF Hound content if available
        if ff_hound_content:
            ff_hound_lines = ff_hound_content.split('\n')
            # Skip the first two lines (header and separator)
            ff_hound_body = '\n'.join(ff_hound_lines[2:])
            
            if ff_hound_body.strip():
                f.write(ff_hound_body)
                f.write("\n\n")
        else:
            f.write("--- FF HOUND EXPERT ANALYSIS ---\n\n")
            f.write("No FF Hound analysis available for this player.\n\n")
    
    print(f"Combined analysis saved to {final_file}")
    return True

def extract_player_slug_from_reddit_file(filepath: str) -> Optional[str]:
    """Extract player slug from Reddit discussion filename"""
    filename = os.path.basename(filepath)
    if filename.endswith('_reddit_discussion.txt'):
        return filename.replace('_reddit_discussion.txt', '')
    return None

def main():
    """Combine all player analyses"""
    
    filtered_dir = "filtered_data"
    
    if not os.path.exists(filtered_dir):
        print(f"Filtered directory {filtered_dir} does not exist")
        return
    
    # Find all Reddit discussion files
    reddit_files = glob.glob(os.path.join(filtered_dir, "*_reddit_discussion.txt"))
    
    if not reddit_files:
        print("No Reddit discussion files found")
        return
    
    print(f"Found {len(reddit_files)} Reddit discussion files")
    
    successful_combinations = 0
    failed_combinations = 0
    
    for reddit_file in reddit_files:
        player_slug = extract_player_slug_from_reddit_file(reddit_file)
        
        if not player_slug:
            print(f"Could not extract player slug from {reddit_file}")
            failed_combinations += 1
            continue
        
        print(f"Combining analyses for {player_slug}...")
        
        if combine_player_analyses(player_slug, filtered_dir):
            successful_combinations += 1
        else:
            failed_combinations += 1
    
    print(f"\nCombination complete!")
    print(f"Successful: {successful_combinations}")
    print(f"Failed: {failed_combinations}")

if __name__ == "__main__":
    main()
