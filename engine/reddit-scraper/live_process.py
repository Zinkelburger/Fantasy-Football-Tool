#!/usr/bin/env python3
"""
Live processing script for fantasy football player analysis.
Queries the OpenAI API player-by-player instead of batch processing.
Processes the first 200 non-kicker, non-defense players.
"""

import os
import sys
import pathlib
from datetime import datetime
from typing import List

from OpenAIQuery import OpenAIQuery
from FootballPlayer import FootballPlayer
from pipeline_utils import (
    SYSTEM_PROMPT,
    build_summary_prompt,
    extract_discussion_content,
    find_discussion_file,
    get_processed_slugs,
)


# Configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
EXCLUDED_POSITIONS = ["DST", "K"]
FILTERED_DATA_DIR = "filtered_data"
OUT_DIR = "markdown_data"
MAX_PLAYERS = 200


def main():
    """Main live processing function."""
    print("⚡ LIVE FANTASY FOOTBALL PROCESSING")
    print(f"   Model: {OPENAI_MODEL}")
    print(f"   Target: First {MAX_PLAYERS} non-kicker/defense players")
    print("=" * 60)
    
    # Setup directories
    script_dir = pathlib.Path(__file__).resolve().parent
    filtered_data_dir_abs = str((script_dir / FILTERED_DATA_DIR).resolve())
    out_dir_abs = str((script_dir / OUT_DIR).resolve())
    
    # Validate directories
    if not os.path.isdir(filtered_data_dir_abs):
        print(f"❌ Error: Filtered data directory '{filtered_data_dir_abs}' does not exist.")
        print(f"   Run the Reddit scraper first to generate filtered discussion data.")
        sys.exit(1)
    
    os.makedirs(out_dir_abs, exist_ok=True)
    
    # Initialize OpenAI client
    try:
        openai_client = OpenAIQuery(model=OPENAI_MODEL, verbose=True)
        print(f"✅ Connected to {OPENAI_MODEL}")
    except Exception as e:
        print(f"❌ Error connecting to OpenAI: {e}")
        print(f"   Check your API key and model name in .env file")
        sys.exit(1)
    
    # Load and filter players
    try:
        all_players: List[FootballPlayer] = FootballPlayer.from_csv("combined_with_depth.csv")
        print(f"📊 Loaded {len(all_players)} total players from CSV")
    except Exception as e:
        print(f"❌ Error loading players: {e}")
        sys.exit(1)
    
    # Filter out kickers and defenses
    filtered_players = [
        player for player in all_players
        if not any(player.player_position.startswith(pos) for pos in EXCLUDED_POSITIONS)
    ]
    print(f"🚫 Filtered out {len(all_players) - len(filtered_players)} kickers/defenses")
    
    # Limit to first 200 players
    players = filtered_players[:MAX_PLAYERS]
    print(f"🎯 Processing first {len(players)} players (limited to {MAX_PLAYERS})")
    
    # Detect previously processed players
    processed_slugs = get_processed_slugs(out_dir_abs)
    print(f"✅ Found {len(processed_slugs)} already processed players")
    
    # Ask user for confirmation
    remaining_players = [p for p in players if p.slug not in processed_slugs]
    print(f"📝 {len(remaining_players)} players need processing")
    
    if len(remaining_players) == 0:
        print("🎉 All target players are already processed!")
        return
    
    try:
        confirm = input(f"\nProceed with processing {len(remaining_players)} players? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("👋 Cancelled!")
            return
    except KeyboardInterrupt:
        print("\n👋 Cancelled!")
        return
    
    # Process players one by one
    processed_count = 0
    error_count = 0
    skipped_count = 0
    start_time = datetime.now()
    
    print(f"\n🚀 Starting live processing...")
    print("=" * 60)
    
    for i, player in enumerate(players, 1):
        print(f"\n🏈 [{i:3d}/{len(players)}] {player.player_name}")
        print(f"    Team: {player.team_name} | Position: {player.player_position}")
        
        if player.slug in processed_slugs:
            print(f"    ⏭️  Already processed - skipping")
            skipped_count += 1
            continue
        
        discussion_file = find_discussion_file(filtered_data_dir_abs, player.slug)

        if discussion_file is None:
            print(f"    ⚠️  No discussion file found - skipping")
            skipped_count += 1
            continue

        try:
            with open(discussion_file, "r", encoding="utf-8") as f:
                filtered_text = f.read().strip()
        except Exception as e:
            print(f"    ❌ Error reading discussion file: {e}")
            error_count += 1
            continue

        discussion_content = extract_discussion_content(filtered_text)

        if not discussion_content:
            print(f"    ⚠️  No discussion content found - skipping")
            skipped_count += 1
            continue

        prompt = build_summary_prompt(player, discussion_content)

        # Query OpenAI
        try:
            print(f"    🤖 Querying {OPENAI_MODEL}...")
            messages = openai_client.create_system_user_query(SYSTEM_PROMPT, prompt)
            
            response = openai_client.query(messages, stream=False)
            
            # Save result as markdown
            md_file = os.path.join(out_dir_abs, f"{player.clean_name}.md")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(response)
            
            print(f"    ✅ Saved to {player.clean_name}.md")
            processed_count += 1
            
        except Exception as e:
            print(f"    ❌ Error processing: {e}")
            # Write error stub
            md_file = os.path.join(out_dir_abs, f"{player.clean_name}.md")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(f"Error processing {player.player_name}: {e}\n")
            error_count += 1
    
    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*60}")
    print(f"🏁 LIVE PROCESSING COMPLETE")
    print(f"   ⏱️  Duration: {duration}")
    print(f"   ✅ Successfully processed: {processed_count}")
    print(f"   ⏭️  Skipped (already done): {skipped_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📁 Files saved to: {out_dir_abs}")
    print(f"   🎯 Total target players: {len(players)} (first {MAX_PLAYERS} non-K/DST)")
    
    if processed_count > 0:
        avg_time = duration.total_seconds() / processed_count
        print(f"   📊 Average time per player: {avg_time:.1f} seconds")


if __name__ == "__main__":
    main()
