#!/usr/bin/env python3
"""
Submit-only batch processing script.
Creates and submits a batch to OpenAI, saves the batch ID for later retrieval.
"""

from OpenAIQuery import OpenAIQuery, BatchRequest
from FootballPlayer import FootballPlayer
from pipeline_utils import (
    SYSTEM_PROMPT,
    build_summary_prompt,
    extract_discussion_content,
    find_discussion_file,
    get_processed_slugs,
)
import json
import os
import pathlib
from datetime import datetime
from typing import Set, List, Dict

# Configuration
OPENAI_MODEL = os.getenv("OPENAI_BATCH_MODEL", "gpt-5-mini")  # Batch uses gpt-5-mini, live uses gpt-5-nano
EXCLUDED_POSITIONS = ["DST", "K"]
BATCH_ID_FILE = "batch_info.json"


def prepare_batch_requests(
    players: List[FootballPlayer], filtered_data_dir_abs: str, processed_slugs: Set[str]
) -> List[Dict]:
    """Prepare data for batch processing by collecting player data and creating prompts."""
    batch_data = []

    for player in players:
        if player.slug in processed_slugs:
            continue

        discussion_file = find_discussion_file(filtered_data_dir_abs, player.slug)

        if discussion_file is None:
            continue

        try:
            with open(discussion_file, "r", encoding="utf-8") as f:
                filtered_text = f.read().strip()
        except Exception:
            continue

        discussion_content = extract_discussion_content(filtered_text)

        if not discussion_content:
            continue

        batch_data.append(
            {"player": player, "prompt": build_summary_prompt(player, discussion_content)}
        )

    return batch_data


def save_batch_info(batch_id: str, batch_name: str, player_count: int):
    """Save batch information to a JSON file for later retrieval."""
    batch_info = {
        "batch_id": batch_id,
        "batch_name": batch_name,
        "player_count": player_count,
        "submitted_at": datetime.now().isoformat(),
        "status": "submitted"
    }
    
    with open(BATCH_ID_FILE, "w") as f:
        json.dump(batch_info, f, indent=2)
    
    print(f"✅ Batch info saved to {BATCH_ID_FILE}")
    print(f"   Batch ID: {batch_id}")
    print(f"   Players: {player_count}")


def main():
    FILTERED_DATA_DIR = "filtered_data"
    OUT_DIR = "markdown_data"

    # Setup directories
    script_dir = pathlib.Path(__file__).resolve().parent
    filtered_data_dir_abs = str((script_dir / FILTERED_DATA_DIR).resolve())
    out_dir_abs = str((script_dir / OUT_DIR).resolve())

    if not os.path.isdir(filtered_data_dir_abs):
        print(f"❌ Error: Filtered data directory '{filtered_data_dir_abs}' does not exist.")
        return

    os.makedirs(out_dir_abs, exist_ok=True)

    # Check if batch is already submitted
    if os.path.exists(BATCH_ID_FILE):
        with open(BATCH_ID_FILE, "r") as f:
            existing_batch = json.load(f)
        
        print(f"⚠️  Batch already submitted!")
        print(f"   Batch ID: {existing_batch['batch_id']}")
        print(f"   Submitted: {existing_batch['submitted_at']}")
        print(f"   Status: {existing_batch.get('status', 'unknown')}")
        print(f"\nUse 'python get_batch_results.py' to retrieve results.")
        print(f"Or delete '{BATCH_ID_FILE}' to submit a new batch.")
        return

    # Initialize OpenAI client
    openai_client = OpenAIQuery(model=OPENAI_MODEL, verbose=True)
    
    # Load and filter players
    all_players: List[FootballPlayer] = FootballPlayer.from_csv("combined_with_depth.csv")
    filtered_players = [
        player for player in all_players
        if not any(player.player_position.startswith(pos) for pos in EXCLUDED_POSITIONS)
    ]
    players = filtered_players[:200]  # Limit to first 200 players

    print(f"📊 Loaded {len(all_players)} total players from CSV")
    print(f"🚫 Filtered out {len(all_players) - len(filtered_players)} defenses/kickers")
    print(f"📝 Processing first {len(players)} players (limited to 200)")

    # Detect previously processed players
    processed_slugs = get_processed_slugs(out_dir_abs)
    print(f"✅ Found {len(processed_slugs)} already processed players")

    # Prepare batch data
    print("🔍 Preparing batch data from filtered high-confidence content...")
    batch_data = prepare_batch_requests(players, filtered_data_dir_abs, processed_slugs)

    if not batch_data:
        print("ℹ️  No players need processing. All players either already processed or missing high-confidence data.")
        return

    print(f"📦 Prepared {len(batch_data)} players for batch processing")

    # Create batch requests
    batch_requests = []
    for data in batch_data:
        player = data["player"]
        messages = openai_client.create_system_user_query(SYSTEM_PROMPT, data["prompt"])

        batch_requests.append(
            BatchRequest(
                custom_id=player.slug,
                messages=messages,
                metadata={"player_name": player.player_name},
            )
        )

    # Submit batch (upload file + create batch, but don't wait)
    batch_name = f"fantasy_high_confidence_batch"
    print(f"🚀 Submitting batch with {len(batch_requests)} requests to OpenAI...")
    
    try:
        # Create JSONL file
        jsonl_filename = f"{batch_name}_input.jsonl"
        openai_client.create_batch_jsonl(batch_requests, jsonl_filename)
        
        # Upload file
        file_id = openai_client.upload_batch_file(jsonl_filename)
        
        # Create batch
        batch_id = openai_client.create_batch(file_id, f"Fantasy Football Analysis - {batch_name}")
        
        # Save batch info for later retrieval
        save_batch_info(batch_id, batch_name, len(batch_requests))
        
        print(f"✅ Batch successfully submitted!")
        print(f"   OpenAI will process {len(batch_requests)} requests")
        print(f"   Processing typically takes up to 24 hours")
        print(f"\n📥 To get results later, run: python get_batch_results.py")
        
        # Clean up local JSONL file
        if os.path.exists(jsonl_filename):
            os.remove(jsonl_filename)

    except Exception as e:
        print(f"❌ Error submitting batch: {e}")
        return


if __name__ == "__main__":
    main()
