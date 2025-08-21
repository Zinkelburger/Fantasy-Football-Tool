from OpenAIQuery import OpenAIQuery, BatchRequest, BatchResult
from FootballPlayer import FootballPlayer

import re
import os
import pathlib
from typing import Set, Optional, List, Dict

# ChatGPT API Configuration
OPENAI_MODEL = "gpt-5-mini"

# Processing limits
MAX_PLAYERS = 192

# Positions to exclude
EXCLUDED_POSITIONS = ["DST", "K"]

# Batch processing configuration - OpenAI allows up to 50,000 requests per batch
BATCH_SIZE = 50  # We'll process all at once, but keeping this for potential chunking
CLEANUP_BATCH_FILES = True  # Whether to clean up temporary batch files


def get_processed_slugs(out_dir: str) -> Set[str]:
    """
    Detect already-processed players by the presence of their summary files.
    We treat "<slug>.md" as the completion marker.
    """
    processed: Set[str] = set()
    if not os.path.isdir(out_dir):
        return processed

    for filename in os.listdir(out_dir):
        if filename.endswith(".md") and len(filename) > len(".md"):
            base = filename[: -len(".md")]
            # Convert the md base name to a slug in the same way as FootballPlayer.slug
            slug = re.sub(r"[^a-z0-9]", "_", base.lower()).strip("_")
            processed.add(slug)
    return processed


def extract_high_confidence_content(filtered_text: str) -> str:
    """
    Extract only the HIGH CONFIDENCE sections from filtered Reddit discussion text.
    
    Args:
        filtered_text: The full filtered text content
        
    Returns:
        str: Only the high confidence sections
    """
    lines = filtered_text.split('\n')
    high_confidence_content = []
    in_high_confidence_section = False
    current_section = []
    
    for line in lines:
        # Check if we're starting a high confidence section
        if "--- HIGH CONFIDENCE SECTION ---" in line:
            in_high_confidence_section = True
            current_section = []
            continue
            
        # Check if we're ending a section (next POST or section marker)
        if line.startswith("=== POST:") or line.startswith("--- MEDIUM CONFIDENCE SECTION ---") or line.startswith("--- LOW CONFIDENCE SECTION ---"):
            if in_high_confidence_section and current_section:
                # Add the accumulated section content
                high_confidence_content.extend(current_section)
                high_confidence_content.append("")  # Add separator
            in_high_confidence_section = False
            current_section = []
            continue
            
        # If we're in a high confidence section, collect the content
        if in_high_confidence_section:
            current_section.append(line)
    
    # Don't forget the last section if it was high confidence
    if in_high_confidence_section and current_section:
        high_confidence_content.extend(current_section)
    
    return '\n'.join(high_confidence_content).strip()


def _write_stub_md(out_dir: str, player: FootballPlayer, message: str) -> None:
    md_file = os.path.join(out_dir, f"{player.clean_name}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(message + "\n")


def prepare_batch_requests(
    players: List[FootballPlayer], filtered_data_dir_abs: str, processed_slugs: Set[str]
) -> List[Dict]:
    """
    Prepare data for batch processing by collecting player data and creating prompts.
    Now uses the filtered_data directory and extracts only high confidence content.

    Returns:
        List of dicts containing player info and prompts for batch processing
    """
    batch_data = []

    for player in players:
        # Skip any player already processed
        if player.slug in processed_slugs:
            continue

        # Look for existing filtered discussion file
        discussion_file = os.path.join(
            filtered_data_dir_abs, f"{player.slug}_filtered_discussion.txt"
        )

        if not os.path.exists(discussion_file):
            continue

        # Read the filtered discussion text
        try:
            with open(discussion_file, "r", encoding="utf-8") as f:
                filtered_text = f.read().strip()
        except Exception as e:
            continue

        if not filtered_text:
            continue

        # Extract only high confidence content
        high_confidence_content = extract_high_confidence_content(filtered_text)
        
        if not high_confidence_content:
            # Skip players with no high confidence content
            continue

        # Create the prompt for OpenAI
        prompt = (
            f"Player: {player.player_name} | Team: {player.team_name} | Position/Depth: {player.player_depth}\n"
            "Analyze the following Reddit posts and comments about this player. "
            "Provide extremely concise and detailed notes of the 2025 fantasy football outlook, sentiment, and key discussion points for this player.\n\n"
            "Don't spew random optimistic bullshit. Be realistic and focus on actionable insights. "
            "There may be extraneous details or players with the same names. Be precise in your analysis.\n\n"
            f"--- High Confidence Reddit Discussion ---\n{high_confidence_content}"
        )

        batch_data.append(
            {"player": player, "prompt": prompt, "high_confidence_content": high_confidence_content}
        )

    return batch_data


def process_batch_results(
    batch_results: List[BatchResult], batch_data: List[Dict], out_dir_abs: str
) -> Dict[str, int]:
    """
    Process batch results and save to files.

    Returns:
        Dict with processing statistics
    """
    stats = {"processed": 0, "errors": 0, "missing": 0}

    # Create a mapping from custom_id to batch data
    id_to_data = {data["player"].slug: data for data in batch_data}

    for result in batch_results:
        if result.custom_id not in id_to_data:
            stats["missing"] += 1
            continue

        player_data = id_to_data[result.custom_id]
        player = player_data["player"]

        if result.success:
            try:
                # Save the prompt for inspection
                prompt_file = os.path.join(out_dir_abs, f"{player.slug}_gpt_query.txt")
                with open(prompt_file, "w", encoding="utf-8") as f:
                    f.write(player_data["prompt"])

                # Save as .md file with clean name
                md_file = os.path.join(out_dir_abs, f"{player.clean_name}.md")
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(result.content)

                print(f"Successfully processed {player.player_name}")
                stats["processed"] += 1

            except Exception as e:
                print(f"Error saving results for {player.player_name}: {e}")
                _write_stub_md(
                    out_dir_abs,
                    player,
                    f"Error saving results for {player.player_name}: {e}",
                )
                stats["errors"] += 1
        else:
            print(f"API error for {player.player_name}: {result.error_message}")
            _write_stub_md(
                out_dir_abs,
                player,
                f"API error for {player.player_name}: {result.error_message}",
            )
            stats["errors"] += 1

    return stats


def main():
    FILTERED_DATA_DIR = "filtered_data"  # Changed from raw_data to filtered_data
    OUT_DIR = "markdown_data"

    # Ensure directories exist relative to this script's directory
    script_dir = pathlib.Path(__file__).resolve().parent
    filtered_data_dir_abs = str((script_dir / FILTERED_DATA_DIR).resolve())
    out_dir_abs = str((script_dir / OUT_DIR).resolve())

    if not os.path.isdir(filtered_data_dir_abs):
        print(f"Error: Filtered data directory '{filtered_data_dir_abs}' does not exist.")
        return

    os.makedirs(out_dir_abs, exist_ok=True)

    openai_client = OpenAIQuery(model=OPENAI_MODEL, verbose=True)
    all_players: list[FootballPlayer] = FootballPlayer.from_csv(
        "combined_with_depth.csv"
    )

    # Filter out defenses and kickers
    filtered_players = [
        player
        for player in all_players
        if not any(player.player_position.startswith(pos) for pos in EXCLUDED_POSITIONS)
    ]

    # Limit to first MAX_PLAYERS
    players = filtered_players[:MAX_PLAYERS]

    print(f"Loaded {len(all_players)} total players from CSV")
    print(f"Filtered out {len(all_players) - len(filtered_players)} defenses/kickers")
    print(f"Processing first {len(players)} players (limit: {MAX_PLAYERS})")

    # Detect previously processed players
    processed_slugs = get_processed_slugs(out_dir_abs)
    print(f"Found {len(processed_slugs)} already processed players")

    # Prepare data for batch processing
    print("Preparing batch data from filtered high-confidence content...")
    batch_data = prepare_batch_requests(players, filtered_data_dir_abs, processed_slugs)

    if not batch_data:
        print(
            "No players need processing. All players either already processed or missing high-confidence data."
        )
        return

    print(f"Prepared {len(batch_data)} players for batch processing with high-confidence content")

    # Process all players in a single large batch (OpenAI supports up to 50,000 requests)
    total_stats = {
        "processed": 0,
        "errors": 0,
        "missing": 0,
        "skipped": len(processed_slugs),
    }

    print(f"\n=== Processing Single Large Batch ({len(batch_data)} players) ===")

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

    try:
        # Process the entire batch at once
        batch_name = f"fantasy_high_confidence_batch"
        print(f"Submitting batch with {len(batch_requests)} requests to OpenAI...")
        batch_results = openai_client.process_batch(batch_requests, batch_name)

        # Process results and save files
        batch_stats = process_batch_results(
            batch_results, batch_data, out_dir_abs
        )

        # Update total stats
        for key in batch_stats:
            total_stats[key] += batch_stats[key]

        print(
            f"Batch completed: {batch_stats['processed']} processed, {batch_stats['errors']} errors"
        )

        # Clean up batch files if requested
        if CLEANUP_BATCH_FILES:
            openai_client.cleanup_batch_files(batch_name)

    except Exception as e:
        print(f"Error processing batch: {e}")
        # Write error stubs for this batch
        for data in batch_data:
            _write_stub_md(
                out_dir_abs,
                data["player"],
                f"Batch processing error for {data['player'].player_name}: {e}",
            )
            total_stats["errors"] += len(batch_data)

    print(f"\n=== Final Summary ===")
    print(f"Players processed: {total_stats['processed']}")
    print(f"Players skipped (already processed): {total_stats['skipped']}")
    print(f"Players with errors: {total_stats['errors']}")
    print(f"Missing results: {total_stats['missing']}")
    print(f"Total players in dataset: {len(players)}")
    print(f"Players that needed processing: {len(batch_data)}")
    print(f"Players with high-confidence content: {len(batch_data)}")


if __name__ == "__main__":
    main()