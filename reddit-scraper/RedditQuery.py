from typing import list, Optional
from dotenv import load_dotenv
import os
import praw
from datetime import datetime, timedelta


class RedditQuery:
    """A class for querying Reddit using PRAW."""

    client_id: Optional[str]
    client_secret: Optional[str]
    user_agent: Optional[str]
    reddit: praw.Reddit

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize the Reddit query client.

        Args: If None, loads from environment
        """
        load_dotenv()

        self.client_id = client_id or os.getenv("CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("USER_AGENT")

        if not all([self.client_id, self.client_secret, self.user_agent]):
            raise ValueError(
                "Reddit credentials not found in environment variables or parameters"
            )

        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
        except Exception as e:
            raise RuntimeError(f"Error initializing Reddit: {e}")

    def search_subreddit(
        self, subreddit: str, query: str, sort: str = "new", limit: int = 100
    ) -> list[praw.models.Submission]:
        """
        Search a subreddit for posts matching a query.

        sort (str): Sort method ('new', 'relevance', 'top', etc.)
        limit (int): Maximum number of posts to return
        """
        try:
            submissions = list(
                self.reddit.subreddit(subreddit).search(query, sort=sort, limit=limit)
            )
            return submissions
        except Exception as e:
            print(f"Error searching subreddit: {e}")
            raise

    def fetch_post_content(self, submission: praw.models.Submission) -> str:
        """
        Returns the combined title and body of a post as a single string.
        """
        title = submission.title
        body = submission.selftext
        return f"Title:{title}\n\nBody:{body}"

    def fetch_comments_flattened(
        self, submission: praw.models.Submission, limit: int = 100
    ) -> list[str]:
        """
        Fetch comments from a Reddit submission.

        Args:
            submission (praw.models.Submission): The Reddit submission
            limit (int): Maximum number of comments to fetch

        Returns:
            list[str]: list of comment bodies
        """
        try:
            submission.comments.replace_more(limit=0)
            comments = submission.comments.list()[:limit]
            return [comment.body for comment in comments]
        except Exception as e:
            print(f"Error fetching comments: {e}")
            return []

    def _traverse_chain(self, comment: praw.models.Comment, current_chain: list[str]):
        """
        A recursive helper to traverse a comment chain and add comment bodies to a list.
        """
        if isinstance(comment, praw.models.MoreComments):
            return

        current_chain.append(comment.body)

        for reply in comment.replies:
            self._traverse_chain(reply, current_chain)

    def fetch_comments_chains(
        self, submission: praw.models.Submission
    ) -> list[list[str]]:
        """
        Fetches all comments and organizes them into chains.

        Each inner list is a separate comment chain, starting with the top-level comment.
        Example: [ ["Root Comment 1", "Reply 1.1", "Reply 1.2"], ["Root Comment 2"] ]

        Returns:
            list[list[str]]: A list of comment chains.
        """
        try:
            # This is crucial: it replaces all "load more comments" links.
            # limit=None will attempt to fetch every single comment. This can be slow.
            submission.comments.replace_more(limit=None)

            all_chains = []
            # Iterate through only the top-level comments
            for top_level_comment in submission.comments:
                if isinstance(top_level_comment, praw.models.MoreComments):
                    continue

                # Start a new list for this specific chain
                current_chain = []
                # Use the recursive helper to populate it
                self._traverse_chain(top_level_comment, current_chain)
                all_chains.append(current_chain)

            return all_chains
        except Exception as e:
            print(f"Error fetching comment chains: {e}")
            return []

    def filter_posts_by_date(
        self, submissions: list[praw.models.Submission], days_back: int = 7
    ) -> list[praw.models.Submission]:
        """
        Filter submissions by keywords in title and creation date.

        Args:
            submissions (list[praw.models.Submission]): list of submissions to filter
            days_back (int): Number of days to look back

        Returns:
            list[praw.models.Submission]: Filtered submissions
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cutoff_timestamp = cutoff_date.timestamp()

        filtered_posts = []
        for submission in submissions:
            if submission.created_utc >= cutoff_timestamp:
                filtered_posts.append(submission)

        return filtered_posts

    def filter_posts_by_keywords(
        self, submissions: list[praw.models.Submission], keywords: set
    ) -> list[praw.models.Submission]:
        """
        Filter submissions by keywords in title and creation date.

        Args:
            submissions (list[praw.models.Submission]): list of submissions to filter
            keywords (set): Set of keywords to search for in titles

        Returns:
            list[praw.models.Submission]: Filtered submissions
        """

        filtered_posts = []
        for submission in submissions:
            if any(keyword in submission.title.lower() for keyword in keywords):
                filtered_posts.append(submission)

        return filtered_posts

    def filter_comment_chains_by_keywords(
        self, chains: list[list[str]], keywords: list[str]
    ) -> list[list[str]]:
        """
        Filters comment chains, keeping only those containing specified keywords.

        Args:
            chains (list[list[str]]): The comment chains to filter.
            keywords (list[str]): Keywords to search for (case-insensitive).

        Returns:
            list[list[str]]: A new list of the matching comment chains.
        """
        if not keywords:
            return chains

        lower_keywords = [k.lower() for k in keywords]
        filtered_chains = []

        for chain in chains:
            # Check if any comment in the chain contains any of the keywords
            if any(
                keyword in comment.lower()
                for comment in chain
                for keyword in lower_keywords
            ):
                filtered_chains.append(chain)

        return filtered_chains

    def save_posts_to_file(
        self, submissions: list[praw.models.Submission], filename: str
    ):
        """
        Save submission details to a file.

        Args:
            submissions (list[praw.models.Submission]): list of submissions to save
            filename (str): Output filename
        """
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for submission in submissions:
                    f.write(f"Title: {submission.title}\n")
                    f.write(f"URL: {submission.url}\n")
                    f.write(f"Created at: {submission.created_utc}\n")
                    f.write("-" * 40 + "\n")
        except Exception as e:
            print(f"Error saving posts to file: {e}")
            raise
