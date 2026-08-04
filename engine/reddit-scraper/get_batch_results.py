#!/usr/bin/env python3
"""
Get-results-only batch processing script.
Reads a saved batch ID and downloads/processes the results.
"""

from OpenAIQuery import OpenAIQuery, BatchResult
from FootballPlayer import FootballPlayer
import json
import os
import pathlib
import re
from datetime import datetime
from typing import List, Dict


# Configuration
OPENAI_MODEL = os.getenv("OPENAI_BATCH_MODEL", "gpt-5-mini")  # Should match submit script
BATCH_ID_FILE = "batch_info.json"


def _write_stub_md(out_dir: str, player: 'FootballPlayer', message: str) -> None:
    """Write a stub markdown file for players with errors."""
    md_file = os.path.join(out_dir, f"{player.clean_name}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(message + "\n")


def process_batch_results(
    batch_results: List[BatchResult], out_dir_abs: str
) -> Dict[str, int]:
    """Process batch results and save to files."""
    stats = {"processed": 0, "errors": 0, "missing": 0}

    # Load player data to map custom_ids back to players
    all_players: List[FootballPlayer] = FootballPlayer.from_csv("combined_with_depth.csv")
    slug_to_player = {player.slug: player for player in all_players}

    for result in batch_results:
        if result.custom_id not in slug_to_player:
            print(f"⚠️  Unknown player slug: {result.custom_id}")
            stats["missing"] += 1
            continue

        player = slug_to_player[result.custom_id]

        if result.success:
            try:
                # Save as .md file with clean name
                md_file = os.path.join(out_dir_abs, f"{player.clean_name}.md")
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(result.content)

                print(f"✅ Successfully processed {player.player_name}")
                stats["processed"] += 1

            except Exception as e:
                print(f"❌ Error saving results for {player.player_name}: {e}")
                _write_stub_md(
                    out_dir_abs,
                    player,
                    f"Error saving results for {player.player_name}: {e}",
                )
                stats["errors"] += 1
        else:
            print(f"❌ API error for {player.player_name}: {result.error_message}")
            _write_stub_md(
                out_dir_abs,
                player,
                f"API error for {player.player_name}: {result.error_message}",
            )
            stats["errors"] += 1

    return stats


def update_batch_info(status: str, completion_time: str = None):
    """Update the batch info file with completion status."""
    if not os.path.exists(BATCH_ID_FILE):
        return
    
    with open(BATCH_ID_FILE, "r") as f:
        batch_info = json.load(f)
    
    batch_info["status"] = status
    if completion_time:
        batch_info["completed_at"] = completion_time
    
    with open(BATCH_ID_FILE, "w") as f:
        json.dump(batch_info, f, indent=2)


def main():
    OUT_DIR = "markdown_data"

    # Setup directories
    script_dir = pathlib.Path(__file__).resolve().parent
    out_dir_abs = str((script_dir / OUT_DIR).resolve())
    os.makedirs(out_dir_abs, exist_ok=True)

    # Check for saved batch info
    if not os.path.exists(BATCH_ID_FILE):
        print(f"❌ No batch info found!")
        print(f"   Expected file: {BATCH_ID_FILE}")
        print(f"   Run 'python submit_batch.py' first to submit a batch.")
        return

    # Load batch info
    with open(BATCH_ID_FILE, "r") as f:
        batch_info = json.load(f)

    batch_id = batch_info["batch_id"]
    batch_name = batch_info["batch_name"]
    player_count = batch_info["player_count"]
    submitted_at = batch_info["submitted_at"]

    print(f"📥 Retrieving batch results...")
    print(f"   Batch ID: {batch_id}")
    print(f"   Submitted: {submitted_at}")
    print(f"   Expected players: {player_count}")

    # Initialize OpenAI client
    openai_client = OpenAIQuery(model=OPENAI_MODEL, verbose=True)

    try:
        # Check batch status first
        print(f"🔍 Checking batch status...")
        batch = openai_client.client.batches.retrieve(batch_id)
        
        print(f"   Status: {batch.status}")
        print(f"   Request counts: {batch.request_counts}")
        
        if batch.status == "completed":
            print(f"✅ Batch completed! Downloading results...")
            
            # Download results
            batch_results = openai_client.download_batch_results(batch_id)
            
            # Process and save results
            stats = process_batch_results(batch_results, out_dir_abs)
            
            # Update batch info
            update_batch_info("downloaded", datetime.now().isoformat())
            
            print(f"\n📊 Results Summary:")
            print(f"   ✅ Players processed: {stats['processed']}")
            print(f"   ❌ Players with errors: {stats['errors']}")
            print(f"   ⚠️  Missing results: {stats['missing']}")
            print(f"   📁 Files saved to: {out_dir_abs}")
            
            # Clean up batch files
            openai_client.cleanup_batch_files(batch_name)
            
        elif batch.status == "failed":
            print(f"❌ Batch failed!")
            if hasattr(batch, 'errors') and batch.errors:
                print(f"   Error: {batch.errors}")
            update_batch_info("failed")
            
        elif batch.status in ["validating", "in_progress", "finalizing"]:
            print(f"⏳ Batch is still processing...")
            print(f"   Current status: {batch.status}")
            print(f"   Check again later or wait for completion.")
            if hasattr(batch, 'completed_at') and batch.completed_at:
                print(f"   Estimated completion: {batch.completed_at}")
            update_batch_info(batch.status)
            
        elif batch.status == "cancelling" or batch.status == "cancelled":
            print(f"🚫 Batch was cancelled.")
            update_batch_info("cancelled")
            
        else:
            print(f"❓ Unknown batch status: {batch.status}")
            update_batch_info(batch.status)

    except Exception as e:
        print(f"❌ Error retrieving batch results: {e}")
        return


if __name__ == "__main__":
    main()
