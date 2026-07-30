#!/usr/bin/env python3
"""
YouTube API Helper for Fantasy Football Analysis

This helper class provides easy access to YouTube API for searching channels,
finding recent videos, and extracting transcripts for player analysis.
"""

import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import requests
from dotenv import load_dotenv, set_key


@dataclass
class VideoInfo:
    """Data class for video information"""
    video_id: str
    title: str
    channel_title: str
    published_at: datetime
    description: str
    duration: str
    view_count: int
    url: str


class YouTubeHelper:
    """Helper class for YouTube API operations focused on fantasy football content"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube helper with API key"""
        load_dotenv()
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("YouTube API key required. Set YOUTUBE_API_KEY in .env file")

        self.base_url = "https://www.googleapis.com/youtube/v3"

    def get_channel_id(self, channel_handle: str) -> Optional[str]:
        """Get channel ID from channel handle/username"""
        # Remove @ if present
        handle = channel_handle.lstrip('@')

        # Try search first
        url = f"{self.base_url}/search"
        params = {
            'part': 'snippet',
            'type': 'channel',
            'q': handle,
            'key': self.api_key,
            'maxResults': 5
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('items'):
                for item in data['items']:
                    channel_title = item['snippet']['title'].lower()
                    if handle.lower() in channel_title:
                        return item['snippet']['channelId']

                # If no exact match, return first result
                return data['items'][0]['snippet']['channelId']

        except requests.RequestException as e:
            print(f"Error searching for channel: {e}")

        return None

    def get_videos_since_monday(self, channel_id: str, max_results: int = 50) -> List[VideoInfo]:
        """Get videos from a channel since the previous Monday"""
        # Calculate last Monday
        today = datetime.now()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday)
        last_monday = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)

        return self.get_videos_since_date(channel_id, last_monday, max_results)

    def get_videos_since_date(self, channel_id: str, since_date: datetime, max_results: int = 50) -> List[VideoInfo]:
        """Get videos from a channel since a specific date"""
        url = f"{self.base_url}/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'type': 'video',
            'publishedAfter': since_date.isoformat() + 'Z',
            'order': 'date',
            'maxResults': max_results,
            'key': self.api_key
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            videos = []
            for item in data.get('items', []):
                video_info = self._parse_video_item(item)
                if video_info:
                    videos.append(video_info)

            return videos

        except requests.RequestException as e:
            print(f"Error fetching videos: {e}")
            return []

    def search_channel_for_player(self, channel_id: str, player_name: str, days_back: int = 7) -> List[VideoInfo]:
        """Search a channel for videos mentioning a specific player in the last X days"""
        since_date = datetime.now() - timedelta(days=days_back)
        videos = self.get_videos_since_date(channel_id, since_date)

        # Filter videos that mention the player
        player_videos = []
        player_name_lower = player_name.lower()

        for video in videos:
            # Check title and description
            if (player_name_lower in video.title.lower() or
                player_name_lower in video.description.lower()):
                player_videos.append(video)

        return player_videos

    def get_video_transcript(self, video_id: str) -> Optional[str]:
        """Get transcript/captions for a video (requires additional setup)"""
        # Note: YouTube API v3 doesn't directly provide transcripts
        # This would require using youtube-transcript-api package or similar
        print(f"Transcript extraction for video {video_id} requires additional setup")
        print("Consider installing: pip install youtube-transcript-api")
        return None

    def search_videos_by_keyword(self, keyword: str, channel_id: Optional[str] = None,
                                days_back: int = 7, max_results: int = 25) -> List[VideoInfo]:
        """Search for videos by keyword, optionally within a specific channel"""
        since_date = datetime.now() - timedelta(days=days_back)

        url = f"{self.base_url}/search"
        params = {
            'part': 'snippet',
            'type': 'video',
            'q': keyword,
            'publishedAfter': since_date.isoformat() + 'Z',
            'order': 'relevance',
            'maxResults': max_results,
            'key': self.api_key
        }

        if channel_id:
            params['channelId'] = channel_id

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            videos = []
            for item in data.get('items', []):
                video_info = self._parse_video_item(item)
                if video_info:
                    videos.append(video_info)

            return videos

        except requests.RequestException as e:
            print(f"Error searching videos: {e}")
            return []

    def get_injury_reports(self, team_keywords: List[str], days_back: int = 7) -> List[VideoInfo]:
        """Search for injury report videos for specific teams"""
        all_videos = []

        for team in team_keywords:
            search_terms = [
                f"{team} injury report",
                f"{team} injuries",
                f"{team} injury update"
            ]

            for term in search_terms:
                videos = self.search_videos_by_keyword(term, days_back=days_back, max_results=10)
                all_videos.extend(videos)

        # Remove duplicates based on video_id
        seen_ids = set()
        unique_videos = []
        for video in all_videos:
            if video.video_id not in seen_ids:
                seen_ids.add(video.video_id)
                unique_videos.append(video)

        return unique_videos

    def _parse_video_item(self, item: Dict[str, Any]) -> Optional[VideoInfo]:
        """Parse a video item from YouTube API response"""
        try:
            snippet = item['snippet']
            video_id = item['id']['videoId']

            # Parse published date
            published_str = snippet['publishedAt']
            published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00'))

            return VideoInfo(
                video_id=video_id,
                title=snippet['title'],
                channel_title=snippet['channelTitle'],
                published_at=published_at,
                description=snippet.get('description', ''),
                duration='',  # Would need additional API call to get duration
                view_count=0,  # Would need additional API call to get view count
                url=f"https://www.youtube.com/watch?v={video_id}"
            )

        except (KeyError, ValueError) as e:
            print(f"Error parsing video item: {e}")
            return None

    def get_detailed_video_info(self, video_ids: List[str]) -> List[VideoInfo]:
        """Get detailed information for specific videos"""
        if not video_ids:
            return []

        url = f"{self.base_url}/videos"
        params = {
            'part': 'snippet,statistics,contentDetails',
            'id': ','.join(video_ids),
            'key': self.api_key
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            videos = []
            for item in data.get('items', []):
                video_info = self._parse_detailed_video_item(item)
                if video_info:
                    videos.append(video_info)

            return videos

        except requests.RequestException as e:
            print(f"Error fetching detailed video info: {e}")
            return []

    def _parse_detailed_video_item(self, item: Dict[str, Any]) -> Optional[VideoInfo]:
        """Parse detailed video item from YouTube API response"""
        try:
            snippet = item['snippet']
            statistics = item.get('statistics', {})
            content_details = item.get('contentDetails', {})
            video_id = item['id']

            # Parse published date
            published_str = snippet['publishedAt']
            published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00'))

            return VideoInfo(
                video_id=video_id,
                title=snippet['title'],
                channel_title=snippet['channelTitle'],
                published_at=published_at,
                description=snippet.get('description', ''),
                duration=content_details.get('duration', ''),
                view_count=int(statistics.get('viewCount', 0)),
                url=f"https://www.youtube.com/watch?v={video_id}"
            )

        except (KeyError, ValueError) as e:
            print(f"Error parsing detailed video item: {e}")
            return None


# Convenience functions for common use cases
def find_player_mentions(player_name: str, channel_handles: List[str],
                        youtube_api_key: Optional[str] = None, days_back: int = 7) -> Dict[str, List[VideoInfo]]:
    """Find mentions of a player across multiple channels"""
    helper = YouTubeHelper(youtube_api_key)
    results = {}

    for handle in channel_handles:
        channel_id = helper.get_channel_id(handle)
        if channel_id:
            videos = helper.search_channel_for_player(channel_id, player_name, days_back)
            if videos:
                results[handle] = videos
        else:
            print(f"Could not find channel: {handle}")

    return results


def get_injury_reports_for_teams(team_names: List[str], youtube_api_key: Optional[str] = None) -> List[VideoInfo]:
    """Get recent injury reports for specified teams"""
    helper = YouTubeHelper(youtube_api_key)
    return helper.get_injury_reports(team_names)


# Example usage
if __name__ == "__main__":
    # Example: Find Tyreek Hill mentions in specific channels
    player = "Tyreek Hill"
    channels = ["@FantasyFootballers", "@TheFantasyFootballAdvisors"]

    try:
        results = find_player_mentions(player, channels)

        for channel, videos in results.items():
            print(f"\n{channel} - {player} mentions:")
            for video in videos:
                print(f"  - {video.title}")
                print(f"    Published: {video.published_at}")
                print(f"    URL: {video.url}")

    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure to set YOUTUBE_API_KEY in your .env file")