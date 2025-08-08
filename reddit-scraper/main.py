from OpenAIQuery import OpenAIQuery
from RedditQuery import RedditQuery
from FootballPlayer import FootballPlayer

import re
import os
import time
import praw
from typing import Set, Tuple, Optional

# Clean player names for Reddit search
SUFFIXES = ["Jr\.", "Sr\.", "II", "III", "IV", "V"]
SUBREDDIT = "fantasyfootball"
POST_LIMIT = 50


def clean_name(name: str) -> str:
    # Remove suffixes and strip whitespace
    name = re.sub(
        r"\s+(?:" + "|".join(SUFFIXES) + r")$", "", name
    ).strip()  # explain this more, what
    return re.escape(name)


def generate_player_names(player: FootballPlayer) -> list[str]:
    player_full_name = clean_name(player.player_name)
    player_last_name = player_full_name.split()[-1]
    player_first_name = player_full_name.split()[0]
    return list(
        filter(
            None,
            [
                player_full_name,
                player_last_name,
                player_first_name,
                (player.player_nickname or "").strip(),
            ],
        )
    )


def get_reddit_submissions(
    reddit_client: RedditQuery, search_terms: list[str]
) -> list[praw.models.Submission]:
    all_submissions = []
    seen_submission_ids = set()

    for term in set(search_terms):
        print(f"Searching for posts with term: '{term}'...")
        # Use quotes for exact matches
        submissions = reddit_client.search_subreddit(
            SUBREDDIT, f'"{term}"', limit=POST_LIMIT
        )
        for sub in submissions:
            if sub.id not in seen_submission_ids:
                all_submissions.append(sub)
                seen_submission_ids.add(sub.id)

    return all_submissions


def get_relevant_posts(
    reddit_client: RedditQuery,
    recent_posts: list[praw.models.Submission],
    search_terms: list[str],
) -> list[praw.models.Submission]:
    discussion_texts = []
    player_keywords = [kw.lower() for kw in search_terms]
    for post in recent_posts:
        # Check if the post body itself is relevant
        post_content = reddit_client.fetch_post_content(post)
        if any(keyword in post_content.lower() for keyword in player_keywords):
            discussion_texts.append(f"--- Post Content ---\n{post_content}")

        # Fetch and filter comment chains for relevance
        comment_chains = reddit_client.fetch_comments_chains(post)
        filtered_chains = reddit_client.filter_comment_chains_by_keywords(
            comment_chains, player_keywords
        )

        if filtered_chains:
            # Combine relevant comments into a single text block for this post
            chain_texts = ["\n".join(chain) for chain in filtered_chains]
            discussion_texts.append(
                f"--- Relevant Comments from Post: {post.title} ---\n"
                + "\n---\n".join(chain_texts)
            )

        # Polite delay: PRAW handles mandatory rate limits, but this prevents
        # slamming the API with heavy requests (fetching full comment trees) back-to-back.
        time.sleep(0.5)

    return discussion_texts


def get_processed_slugs(out_dir: str) -> Set[str]:
    """
    Detect already-processed players by the presence of their summary files.
    We treat "<slug>_summary.txt" as the completion marker.
    """
    processed: Set[str] = set()
    if not os.path.isdir(out_dir):
        return processed

    for filename in os.listdir(out_dir):
        if filename.endswith("_summary.txt") and len(filename) > len("_summary.txt"):
            slug = filename[: -len("_summary.txt")]
            processed.add(slug)
    return processed


def get_last_processed_slug(out_dir: str) -> Optional[str]:
    """
    Find the most recently modified "<slug>_summary.txt" and return its slug.
    If none found, return None.
    """
    if not os.path.isdir(out_dir):
        return None

    newest_mtime: float = -1.0
    newest_slug: Optional[str] = None

    for filename in os.listdir(out_dir):
        if not filename.endswith("_summary.txt"):
            continue
        path = os.path.join(out_dir, filename)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime > newest_mtime:
            newest_mtime = mtime
            newest_slug = filename[: -len("_summary.txt")]

    return newest_slug


def main():
    DAYS_BACK = 60
    OUT_DIR = "data"
    os.makedirs(OUT_DIR, exist_ok=True)

    reddit_client = RedditQuery()
    openai_client = OpenAIQuery()
    players: list[FootballPlayer] = FootballPlayer.from_csv("combined_with_depth.csv")

    # Detect previously processed players and determine a starting point
    processed_slugs = get_processed_slugs(OUT_DIR)
    last_processed = get_last_processed_slug(OUT_DIR)

    start_index = 0
    if last_processed is not None:
        # Build slug -> index mapping to resume from the next player in original order
        slug_to_index = {p.slug: idx for idx, p in enumerate(players)}
        start_index = slug_to_index.get(last_processed, -1) + 1
        if start_index < 0:
            start_index = 0

    if start_index > 0:
        print(f"Resuming from index {start_index} (after '{last_processed}').")
    elif processed_slugs:
        print("Detected existing results; previously processed players will be skipped.")

    for player in players[start_index:]:
        # Skip any player already processed (idempotent/resumable)
        if player.slug in processed_slugs:
            print(f"Skipping {player.player_name} (already processed).")
            continue

        # 1) Find reddit posts about the player
        search_terms = generate_player_names(player)

        all_submissions = get_reddit_submissions(reddit_client, search_terms)
        recent_posts = reddit_client.filter_posts_by_date(
            all_submissions, days_back=DAYS_BACK
        )

        print(
            f"Found {len(recent_posts)} unique, recent posts for {player.player_name}."
        )

        if not recent_posts:
            print(f"No recent posts found for {player.player_name}. Skipping.")
            continue

        # === 2. Gather Relevant Discussion from Posts and Comments ===
        discussion_texts = get_relevant_posts(reddit_client, recent_posts, search_terms)

        if not discussion_texts:
            print(f"No relevant discussion found for {player.player_name}. Skipping.")
            continue

        # === 3. Save Combined Text and Summarize with OpenAI ===
        reddit_text = "\n\n".join(discussion_texts)
        reddit_file = os.path.join(OUT_DIR, f"{player.slug}_discussion.txt")
        with open(reddit_file, "w", encoding="utf-8") as f:
            f.write(reddit_text)

        prompt = (
            f"Player: {player.player_name} | Team: {player.team_name} | Position/Depth: {player.player_depth}\n"
            "Analyze the following Reddit posts and comments. "
            "Provide detailed notes of the 2025 fantasy football outlook, sentiment, and key discussion points for this player.\n\n"
            f"--- Reddit Discussion ---\n{reddit_text}"
        )

        # Save the prompt for inspection
        with open(
            os.path.join(OUT_DIR, f"{player.slug}_gpt_query.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(prompt)

        messages = openai_client.create_system_user_query(
            "You are a sharp fantasy football analyst providing draft advice.", prompt
        )
        summary = openai_client.query(messages)

        # Save both the debug summary and the .md file for Go code
        summary_file = os.path.join(OUT_DIR, f"{player.slug}_summary.txt")
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary)
        
        # Also save as .md file with clean name for Go code compatibility
        md_file = os.path.join(OUT_DIR, f"{player.clean_name}.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(summary)

        # === 4. Report Status ===
        # PRAW tracks your rate limit status automatically.
        limits = reddit_client.reddit.auth.limits
        print(f"Successfully generated summary for {player.player_name}.")
        print(f"Reddit API requests remaining: {limits['remaining']}\n")


if __name__ == "__main__":
    main()
