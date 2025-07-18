from typing import List, Optional
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

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, 
                 user_agent: Optional[str] = None):
        """
        Initialize the Reddit query client.
        
        Args: If None, loads from environment
        """
        load_dotenv()

        self.client_id = client_id or os.getenv("CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("USER_AGENT")

        if not all([self.client_id, self.client_secret, self.user_agent]):
            raise ValueError("Reddit credentials not found in environment variables or parameters")

        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
        except Exception as e:
            raise RuntimeError(f"Error initializing Reddit: {e}")
    
    def search_subreddit(self, subreddit: str, query: str, sort: str = "new", 
                        limit: int = 100) -> List[praw.models.Submission]:
        """
        Search a subreddit for posts matching a query.

        sort (str): Sort method ('new', 'relevance', 'top', etc.)
        limit (int): Maximum number of posts to return
        """
        try:
            submissions = list(self.reddit.subreddit(subreddit).search(
                query, sort=sort, limit=limit
            ))
            return submissions
        except Exception as e:
            print(f"Error searching subreddit: {e}")
            raise

    def fetch_comments(self, submission: praw.models.Submission, limit: int = 100) -> List[str]:
        """
        Fetch comments from a Reddit submission.
        
        Args:
            submission (praw.models.Submission): The Reddit submission
            limit (int): Maximum number of comments to fetch
            
        Returns:
            List[str]: List of comment bodies
        """
        try:
            submission.comments.replace_more(limit=0)
            comments = submission.comments.list()[:limit]
            return [comment.body for comment in comments]
        except Exception as e:
            print(f"Error fetching comments: {e}")
            return []
    
    def filter_posts_by_date(self, submissions: List[praw.models.Submission], days_back: int = 7) -> List[praw.models.Submission]:
        """
        Filter submissions by keywords in title and creation date.
        
        Args:
            submissions (List[praw.models.Submission]): List of submissions to filter
            days_back (int): Number of days to look back
            
        Returns:
            List[praw.models.Submission]: Filtered submissions
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cutoff_timestamp = cutoff_date.timestamp()

        filtered_posts = []
        for submission in submissions:
            if (submission.created_utc >= cutoff_timestamp):
                filtered_posts.append(submission)

        return filtered_posts
    
    def filter_posts_by_keywords(self, submissions: List[praw.models.Submission], keywords: set) -> List[praw.models.Submission]:
        """
        Filter submissions by keywords in title and creation date.
        
        Args:
            submissions (List[praw.models.Submission]): List of submissions to filter
            keywords (set): Set of keywords to search for in titles

        Returns:
            List[praw.models.Submission]: Filtered submissions
        """

        filtered_posts = []
        for submission in submissions:
            if (any(keyword in submission.title.lower() for keyword in keywords)):
                filtered_posts.append(submission)

        return filtered_posts

    def save_posts_to_file(self, submissions: List[praw.models.Submission], filename: str):
        """
        Save submission details to a file.
        
        Args:
            submissions (List[praw.models.Submission]): List of submissions to save
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
