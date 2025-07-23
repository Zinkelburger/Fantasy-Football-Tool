from OpenAIQuery import OpenAIQuery
from RedditQuery import RedditQuery
from FootballPlayer import FootballPlayer

import pandas as pd
import re
import os
import time
from typing import List

# Clean player names for Reddit search
SUFFIXES = ["Jr\.", "Sr\.", "II", "III", "IV", "V"]


def clean_name(name: str) -> str:
    # Remove suffixes and strip whitespace
    name = re.sub(r"\s+(?:" + "|".join(SUFFIXES) + r")$", "", name).strip()
    return re.escape(name)


# Initialize FootballPlayer instances from CSV
def init_football_players(csv_path: str) -> List[FootballPlayer]:
    df = pd.read_csv(csv_path)
    players: List[FootballPlayer] = []
    for row in df.itertuples(index=False):
        players.append(
            FootballPlayer(
                player_name=row.Name,
                team_name=row.Team,
                player_position=row.Pos,
                player_adp=row.ADP,
                player_depth=row.Depth,
            )
        )
    return players


def main():
    SUBREDDIT = "fantasyfootball"
    DAYS_BACK = 30
    POST_LIMIT = 100
    COMMENT_LIMIT = 100

    OUT_DIR = "data"
    os.makedirs(OUT_DIR, exist_ok=True)

    reddit_client = RedditQuery()
    openai_client = OpenAIQuery()
    players = init_football_players("combined_with_depth.csv")

    for player in players:
        # 1) Search Reddit posts
        query = clean_name(player.player_name)
        submissions = reddit_client.search_subreddit(SUBREDDIT, query, limit=POST_LIMIT)
        recent = reddit_client.filter_posts_by_date(submissions, days_back=DAYS_BACK)

        # 2) Save raw posts
        raw_file = os.path.join(OUT_DIR, f"{player.slug}_all_posts.txt")
        reddit_client.save_posts_to_file(recent, raw_file)

        # 3) Fetch comments
        all_comments: List[str] = []
        for post in recent:
            all_comments.extend(reddit_client.fetch_comments(post, limit=COMMENT_LIMIT))
            time.sleep(1)

        if not all_comments:
            print(f"No comments for {player.player_name}")
            continue

        comments_text = "\n".join(all_comments)
        comments_file = os.path.join(OUT_DIR, f"{player.slug}_comments.txt")
        with open(comments_file, "w", encoding="utf-8") as f:
            f.write(comments_text)

        # 4) Summarize via OpenAI
        prompt = (
            f"Player: {player.player_name} | Team: {player.team_name} | "
            f"Position/Depth: {player.player_depth} | ADP: {player.player_adp}\n"
            "Summarize the Reddit discussion below focusing on 2025 draft-relevant info:\n\n"
            f"{comments_text}"
        )
        # optional: save prompt for inspection
        with open(
            os.path.join(OUT_DIR, f"{player.slug}_gpt_query.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(prompt)

        messages = openai_client.create_system_user_query(
            "You are a professional football analyst giving valuable advice.", prompt
        )
        summary = openai_client.query(messages)

        summary_file = os.path.join(OUT_DIR, f"{player.slug}_summary.txt")
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary)

        print(f"Done: {player.player_name}")


if __name__ == "__main__":
    main()
