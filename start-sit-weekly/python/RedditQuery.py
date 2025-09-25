# reddit-scraper/RedditQuery.py

import os
from typing import List, Optional
from datetime import datetime

import praw
from dotenv import load_dotenv
from thefuzz import fuzz # We now use fuzzy matching inside the class

class RedditQuery:
    """
    A specialized class for finding player mentions on Reddit using PRAW.
    """
    def __init__(self):
        """Initializes the Reddit client using credentials from a .env file."""
        load_dotenv()
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        user_agent = os.getenv("USER_AGENT")

        if not all([client_id, client_secret, user_agent]):
            raise ValueError("Reddit credentials not found in environment variables.")

        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                read_only=True # Good practice for scraping
            )
            print("🔑 Reddit client initialized successfully.")
        except Exception as e:
            raise RuntimeError(f"Error initializing Reddit: {e}")

    def find_all_mentions(
        self,
        subreddit: str,
        search_query: str,
        keywords: List[str],
        since_timestamp: float,
        confidence_threshold: int = 90
    ) -> List[str]:
        """
        Finds all comments in a subreddit that mention given keywords with a
        certain confidence score since a specific time.

        This is the primary workhorse method, handling search, filtering,
        and matching all in one place for maximum efficiency.

        Args:
            subreddit (str): The subreddit to search (e.g., 'fantasyfootball').
            search_query (str): The initial query to find relevant posts.
            keywords (List[str]): A list of names/nicknames to match in comments.
            since_timestamp (float): The UTC timestamp to search from.
            confidence_threshold (int): The fuzzy matching score required (0-100).

        Returns:
            List[str]: A list of unique comment bodies that matched the criteria.
        """
        if not keywords:
            return []

        # Use a set to store comments to automatically handle duplicates
        found_mentions = set()
        lower_keywords = [k.lower() for k in keywords]

        try:
            # 1. Search for relevant posts
            submissions = self.reddit.subreddit(subreddit).search(
                query=search_query, sort="new", limit=50
            )

            for post in submissions:
                # 2. Filter posts by date first (most efficient filter)
                if post.created_utc < since_timestamp:
                    continue # Skip posts that are too old

                # 3. Get a flat list of all comments for recent posts
                post.comments.replace_more(limit=0) # Expands "load more comments"
                comments = post.comments.list()

                # 4. Perform fuzzy matching on each comment
                for comment in comments:
                    comment_body = comment.body.lower()
                    for keyword in lower_keywords:
                        score = fuzz.partial_ratio(keyword, comment_body)
                        if score >= confidence_threshold:
                            found_mentions.add(comment.body.strip())
                            # Once a comment matches, no need to check other keywords
                            break
            
            return list(found_mentions)

        except Exception as e:
            print(f"❌ An error occurred during Reddit search: {e}")
            return []