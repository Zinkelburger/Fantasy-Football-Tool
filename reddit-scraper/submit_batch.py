#!/usr/bin/env python3
"""
Submit-only batch processing script.
Creates and submits a batch to OpenAI, saves the batch ID for later retrieval.
"""

from OpenAIQuery import OpenAIQuery, BatchRequest
from FootballPlayer import FootballPlayer
import json
import os
import pathlib
from datetime import datetime
from typing import Set, List, Dict

# Configuration
OPENAI_MODEL = "gpt-5-mini"  # Batch processing uses gpt-5-mini, live uses gpt-5-nano-2025-08-07
EXCLUDED_POSITIONS = ["DST", "K"]
BATCH_ID_FILE = "batch_info.json"


def get_processed_slugs(out_dir: str) -> Set[str]:
    """Detect already-processed players by the presence of their summary files."""
    processed: Set[str] = set()
    if not os.path.isdir(out_dir):
        return processed

    for filename in os.listdir(out_dir):
        if filename.endswith(".md") and len(filename) > len(".md"):
            base = filename[: -len(".md")]
            import re
            slug = re.sub(r"[^a-z0-9]", "_", base.lower()).strip("_")
            processed.add(slug)
    return processed


def extract_high_confidence_content(filtered_text: str) -> str:
    """Extract the HIGH CONFIDENCE sections from filtered discussion text (now includes ff-hound data)."""
    lines = filtered_text.split('\n')
    high_confidence_content = []
    in_high_confidence_section = False
    current_section = []
    
    for line in lines:
        if "--- HIGH CONFIDENCE SECTION ---" in line:
            in_high_confidence_section = True
            current_section = []
            continue
            
        # Stop when we hit processing metadata or end of file
        if line.startswith("--- PROCESSING METADATA ---"):
            if in_high_confidence_section and current_section:
                high_confidence_content.extend(current_section)
            break
            
        if in_high_confidence_section:
            current_section.append(line)
    
    if in_high_confidence_section and current_section:
        high_confidence_content.extend(current_section)
    
    return '\n'.join(high_confidence_content).strip()


def prepare_batch_requests(
    players: List[FootballPlayer], filtered_data_dir_abs: str, processed_slugs: Set[str]
) -> List[Dict]:
    """Prepare data for batch processing by collecting player data and creating prompts."""
    batch_data = []

    for player in players:
        if player.slug in processed_slugs:
            continue

        discussion_file = os.path.join(
            filtered_data_dir_abs, f"{player.slug}_filtered_discussion.txt"
        )

        if not os.path.exists(discussion_file):
            continue

        try:
            with open(discussion_file, "r", encoding="utf-8") as f:
                filtered_text = f.read().strip()
        except Exception:
            continue

        if not filtered_text:
            continue

        high_confidence_content = extract_high_confidence_content(filtered_text)
        
        if not high_confidence_content:
            continue

        prompt = (
            f"Player: {player.player_name} | Team: {player.team_name} | Position/Depth: {player.player_depth}\n"
            "Analyze the following Reddit posts/comments and FF Hound expert analysis about this player. "
            "Provide extremely concise and detailed notes of the 2025 fantasy football outlook, sentiment, and key discussion points for this player.\n\n"
            "Don't spew random optimistic bullshit. Be realistic and focus on actionable insights. "
            "There may be extraneous details or players with the same names. Be precise in your analysis.\n\n"
            f"--- Combined High Confidence Data ---\n{high_confidence_content}"
        )

        batch_data.append(
            {"player": player, "prompt": prompt, "high_confidence_content": high_confidence_content}
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
        messages = openai_client.create_system_user_query(
            "You are a sharp fantasy football analyst providing draft advice based on Reddit community insights.",
            data["prompt"],
        )

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
