"""Shared helpers for the scrape -> combine -> summarize pipeline.

Both the live (live_process.py) and batch (submit_batch.py) summarizers import
from here so the file naming, stub detection, and prompt stay in sync.
"""

import datetime
import os
import re
from typing import Optional, Set

SYSTEM_PROMPT = (
    "You are a sharp fantasy football analyst providing draft advice "
    "based on Reddit community insights."
)

# Lines that mean a section exists but found nothing.
STUB_PREFIXES = (
    "No relevant Reddit discussion",
    "No recent discussion",
    "No FF Hound analysis",
)

# Preferred first: the combined Reddit + FF Hound file from combine_analyses.py,
# falling back to the Reddit-only file if the combine step wasn't run.
DISCUSSION_SUFFIXES = ("_final_discussion.txt", "_reddit_discussion.txt")


def current_season_year() -> int:
    """The NFL season a run belongs to (Jan/Feb runs are the prior season)."""
    today = datetime.date.today()
    return today.year if today.month >= 3 else today.year - 1


def find_discussion_file(filtered_dir: str, slug: str) -> Optional[str]:
    """Locate the best available discussion file for a player."""
    for suffix in DISCUSSION_SUFFIXES:
        path = os.path.join(filtered_dir, f"{slug}{suffix}")
        if os.path.exists(path):
            return path
    return None


def extract_discussion_content(text: str) -> str:
    """Return usable discussion text, or '' if the file only contains stubs.

    Discussion files hold high-confidence content only (the scraper drops
    medium/low confidence before saving), so the whole body is usable once
    headers, separators, and no-data stub lines are set aside.
    """
    body = text.split("--- PROCESSING METADATA ---")[0]

    def is_noise(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if set(stripped) <= {"="}:
            return True
        if stripped.startswith("---") and stripped.endswith("---"):
            return True
        if stripped.startswith(("REDDIT FANTASY FOOTBALL ANALYSIS FOR",
                                "FANTASY FOOTBALL ANALYSIS FOR",
                                "FF HOUND EXPERT ANALYSIS FOR")):
            return True
        return stripped.startswith(STUB_PREFIXES)

    has_content = any(not is_noise(line) for line in body.splitlines())
    return body.strip() if has_content else ""


def build_summary_prompt(player, content: str) -> str:
    """The summarization prompt shared by live and batch processing (player: FootballPlayer)."""
    season = current_season_year()
    return (
        f"Player: {player.player_name} | Team: {player.team_name} | Position/Depth: {player.player_depth}\n"
        "Analyze the following Reddit posts/comments and FF Hound expert analysis about this player. "
        f"Provide extremely concise and detailed notes of the {season} fantasy football outlook, "
        "sentiment, and key discussion points for this player.\n\n"
        "Don't spew random optimistic bullshit. Be realistic and focus on actionable insights. "
        "There may be extraneous details or players with the same names. Be precise in your analysis.\n\n"
        f"--- Combined High Confidence Data ---\n{content}"
    )


def get_processed_slugs(out_dir: str) -> Set[str]:
    """Detect already-summarized players by their markdown files in out_dir."""
    processed: Set[str] = set()
    if not os.path.isdir(out_dir):
        return processed

    for filename in os.listdir(out_dir):
        if filename.endswith(".md") and len(filename) > len(".md"):
            base = filename[: -len(".md")]
            slug = re.sub(r"[^a-z0-9]", "_", base.lower()).strip("_")
            processed.add(slug)
    return processed
