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

    def find_mentions_with_metadata(
        self,
        subreddit: str,
        search_query: str,
        keywords: List[str],
        since_timestamp: float,
        confidence_threshold: int = 90
    ) -> List[dict]:
        """
        Finds all posts/comments that mention given keywords with metadata for UI display.

        Returns structured data with post titles, URLs, bodies, and matching comments.

        Args:
            subreddit (str): The subreddit to search (e.g., 'fantasyfootball').
            search_query (str): The initial query to find relevant posts.
            keywords (List[str]): A list of names/nicknames to match in comments.
            since_timestamp (float): The UTC timestamp to search from.
            confidence_threshold (int): The fuzzy matching score required (0-100).

        Returns:
            List[dict]: List of posts with their metadata and matching comments.
        """
        if not keywords:
            return []

        found_posts = []
        lower_keywords = [k.lower() for k in keywords]

        try:
            # 1. Search for relevant posts
            submissions = self.reddit.subreddit(subreddit).search(
                query=search_query, sort="new", limit=50
            )

            for post in submissions:
                # 2. Filter posts by date first
                if post.created_utc < since_timestamp:
                    continue

                # Check if post body itself mentions the player
                post_body_relevant = False
                if hasattr(post, 'selftext') and post.selftext:
                    post_body_lower = post.selftext.lower()
                    for keyword in lower_keywords:
                        if fuzz.partial_ratio(keyword, post_body_lower) >= confidence_threshold:
                            post_body_relevant = True
                            break

                # 3. Find relevant comments
                post.comments.replace_more(limit=0)
                comments = post.comments.list()
                relevant_comments = []

                for comment in comments:
                    if hasattr(comment, 'body') and comment.body != '[deleted]':
                        comment_body_lower = comment.body.lower()
                        for keyword in lower_keywords:
                            score = fuzz.partial_ratio(keyword, comment_body_lower)
                            if score >= confidence_threshold:
                                relevant_comments.append({
                                    "body": comment.body.strip(),
                                    "author": str(comment.author) if comment.author else "[deleted]",
                                    "score": comment.score,
                                    "created_utc": comment.created_utc,
                                    "permalink": f"https://reddit.com{comment.permalink}",
                                    "match_confidence": score
                                })
                                break

                # Only include posts that have either relevant body or comments
                if post_body_relevant or relevant_comments:
                    post_data = {
                        "post_title": post.title,
                        "post_url": f"https://reddit.com{post.permalink}",
                        "post_score": post.score,
                        "post_created_utc": post.created_utc,
                        "subreddit": str(post.subreddit),
                        "author": str(post.author) if post.author else "[deleted]",
                        "post_body": post.selftext if post_body_relevant else None,
                        "relevant_comments": relevant_comments,
                        "total_comments": len(relevant_comments)
                    }
                    found_posts.append(post_data)

            return found_posts

        except Exception as e:
            print(f"❌ An error occurred during Reddit search: {e}")
            return []

    # Keep old method for backwards compatibility
    def find_all_mentions(
        self,
        subreddit: str,
        search_query: str,
        keywords: List[str],
        since_timestamp: float,
        confidence_threshold: int = 90
    ) -> List[str]:
        """Legacy method - returns simple list of comment strings."""
        posts = self.find_mentions_with_metadata(subreddit, search_query, keywords, since_timestamp, confidence_threshold)

        mentions = []
        for post in posts:
            if post.get('post_body'):
                mentions.append(post['post_body'])
            for comment in post.get('relevant_comments', []):
                mentions.append(comment['body'])

        return mentions