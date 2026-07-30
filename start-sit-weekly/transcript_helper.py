#!/usr/bin/env python3
"""
YouTube Transcript Helper for Fantasy Football Analysis

This helper provides transcript extraction and analysis functionality
for YouTube videos, specifically for parsing player mentions and analysis.
"""

import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    TRANSCRIPT_API_AVAILABLE = False
    print("youtube-transcript-api not installed. Run: pip install youtube-transcript-api")


@dataclass
class PlayerMention:
    """Data class for player mentions in transcripts"""
    player_name: str
    timestamp: float
    text_snippet: str
    context_before: str
    context_after: str


@dataclass
class TranscriptAnalysis:
    """Data class for transcript analysis results"""
    video_id: str
    video_title: str
    total_duration: float
    player_mentions: List[PlayerMention]
    key_phrases: List[str]
    injury_mentions: List[str]
    sentiment_keywords: Dict[str, List[str]]


class TranscriptHelper:
    """Helper class for YouTube transcript extraction and analysis"""

    def __init__(self):
        if not TRANSCRIPT_API_AVAILABLE:
            raise ImportError("youtube-transcript-api required. Install with: pip install youtube-transcript-api")

        # Fantasy football keywords for analysis
        self.injury_keywords = [
            'injury', 'injured', 'hurt', 'questionable', 'doubtful', 'out',
            'ir', 'injured reserve', 'dnp', 'limited', 'full practice',
            'concussion', 'ankle', 'knee', 'hamstring', 'shoulder', 'back',
            'groin', 'calf', 'quad', 'wrist', 'finger', 'foot'
        ]

        self.positive_keywords = [
            'healthy', 'good to go', 'cleared', 'practicing', 'full go',
            'no injury designation', 'probable', 'ready', 'green light'
        ]

        self.performance_keywords = [
            'targets', 'carries', 'snaps', 'usage', 'touches', 'looks',
            'opportunity', 'workload', 'volume', 'role', 'red zone',
            'goal line', 'passing down', 'third down'
        ]

    def get_transcript(self, video_id: str, languages: List[str] = ['en']) -> Optional[List[Dict]]:
        """Get transcript for a YouTube video"""
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try to get manual transcript first, then auto-generated
            for language in languages:
                try:
                    transcript = transcript_list.find_transcript([language])
                    return transcript.fetch()
                except:
                    continue

            # If no manual transcript, try auto-generated
            try:
                transcript = transcript_list.find_generated_transcript(languages)
                return transcript.fetch()
            except:
                return None

        except Exception as e:
            print(f"Error getting transcript for video {video_id}: {e}")
            return None

    def search_player_in_transcript(self, transcript: List[Dict], player_name: str,
                                  context_window: int = 30) -> List[PlayerMention]:
        """Search for a specific player in the transcript"""
        if not transcript:
            return []

        mentions = []
        player_variations = self._get_player_name_variations(player_name)

        for i, entry in enumerate(transcript):
            text = entry['text'].lower()
            timestamp = entry['start']

            # Check if any player variation is mentioned
            for variation in player_variations:
                if variation.lower() in text:
                    # Get context
                    context_before = self._get_context(transcript, i, -context_window)
                    context_after = self._get_context(transcript, i, context_window)

                    mention = PlayerMention(
                        player_name=player_name,
                        timestamp=timestamp,
                        text_snippet=entry['text'],
                        context_before=context_before,
                        context_after=context_after
                    )
                    mentions.append(mention)
                    break  # Don't double-count same segment

        return mentions

    def analyze_transcript_for_player(self, video_id: str, video_title: str,
                                    player_name: str) -> Optional[TranscriptAnalysis]:
        """Comprehensive analysis of transcript for a specific player"""
        transcript = self.get_transcript(video_id)
        if not transcript:
            return None

        # Get player mentions
        mentions = self.search_player_in_transcript(transcript, player_name)
        if not mentions:
            return None

        # Analyze content around player mentions
        injury_mentions = []
        key_phrases = []
        sentiment_keywords = {'positive': [], 'negative': [], 'neutral': []}

        for mention in mentions:
            full_context = f"{mention.context_before} {mention.text_snippet} {mention.context_after}".lower()

            # Check for injury-related content
            for keyword in self.injury_keywords:
                if keyword in full_context:
                    injury_mentions.append(f"{keyword} (at {mention.timestamp:.1f}s)")

            # Check for positive sentiment
            for keyword in self.positive_keywords:
                if keyword in full_context:
                    sentiment_keywords['positive'].append(f"{keyword} (at {mention.timestamp:.1f}s)")

            # Extract key phrases (sentences containing the player)
            sentences = self._extract_sentences_with_player(full_context, player_name)
            key_phrases.extend(sentences)

        # Calculate total duration
        total_duration = transcript[-1]['start'] + transcript[-1]['duration'] if transcript else 0

        return TranscriptAnalysis(
            video_id=video_id,
            video_title=video_title,
            total_duration=total_duration,
            player_mentions=mentions,
            key_phrases=list(set(key_phrases)),  # Remove duplicates
            injury_mentions=list(set(injury_mentions)),
            sentiment_keywords=sentiment_keywords
        )

    def batch_analyze_videos(self, video_data: List[Dict], player_name: str) -> List[TranscriptAnalysis]:
        """Analyze multiple videos for a specific player"""
        results = []

        for video in video_data:
            video_id = video.get('video_id') or video.get('id')
            video_title = video.get('title', 'Unknown Title')

            if video_id:
                analysis = self.analyze_transcript_for_player(video_id, video_title, player_name)
                if analysis:
                    results.append(analysis)

        return results

    def generate_player_report(self, analyses: List[TranscriptAnalysis], player_name: str) -> str:
        """Generate a summary report for a player based on transcript analyses"""
        if not analyses:
            return f"No transcript data found for {player_name}"

        report = f"=== {player_name} Analysis Report ===\n\n"
        report += f"Videos analyzed: {len(analyses)}\n"

        # Summary stats
        total_mentions = sum(len(analysis.player_mentions) for analysis in analyses)
        report += f"Total mentions: {total_mentions}\n\n"

        # Injury concerns
        all_injuries = []
        for analysis in analyses:
            all_injuries.extend(analysis.injury_mentions)

        if all_injuries:
            report += "🚨 INJURY MENTIONS:\n"
            for injury in set(all_injuries):
                report += f"  - {injury}\n"
            report += "\n"

        # Key insights by video
        report += "📺 VIDEO BREAKDOWN:\n"
        for analysis in analyses:
            if analysis.player_mentions:
                report += f"\n'{analysis.video_title}' ({analysis.video_id}):\n"
                report += f"  Mentions: {len(analysis.player_mentions)}\n"

                if analysis.injury_mentions:
                    report += "  Injury notes: " + ", ".join(analysis.injury_mentions) + "\n"

                if analysis.sentiment_keywords['positive']:
                    report += "  Positive notes: " + ", ".join(analysis.sentiment_keywords['positive']) + "\n"

                # Show key phrases (limited)
                if analysis.key_phrases:
                    report += "  Key phrases:\n"
                    for phrase in analysis.key_phrases[:3]:  # Limit to 3 phrases
                        report += f"    - {phrase}\n"

        return report

    def _get_player_name_variations(self, player_name: str) -> List[str]:
        """Generate common variations of a player name"""
        variations = [player_name]

        # Split name and add variations
        parts = player_name.split()
        if len(parts) >= 2:
            # First name only
            variations.append(parts[0])
            # Last name only
            variations.append(parts[-1])
            # Nickname variations (simple)
            first = parts[0].lower()
            if first in ['michael', 'mike']:
                variations.extend(['michael', 'mike'])
            elif first in ['robert', 'bob', 'bobby']:
                variations.extend(['robert', 'bob', 'bobby'])
            elif first in ['william', 'will', 'bill']:
                variations.extend(['william', 'will', 'bill'])

        return variations

    def _get_context(self, transcript: List[Dict], index: int, window: int) -> str:
        """Get context text around a specific transcript entry"""
        if window > 0:
            # Get text after
            end_idx = min(index + window, len(transcript))
            return " ".join([entry['text'] for entry in transcript[index+1:end_idx]])
        else:
            # Get text before
            start_idx = max(0, index + window)
            return " ".join([entry['text'] for entry in transcript[start_idx:index]])

    def _extract_sentences_with_player(self, text: str, player_name: str) -> List[str]:
        """Extract sentences that mention the player"""
        sentences = re.split(r'[.!?]+', text)
        player_sentences = []

        player_variations = self._get_player_name_variations(player_name)

        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and any(var.lower() in sentence.lower() for var in player_variations):
                if len(sentence) > 10:  # Filter out very short sentences
                    player_sentences.append(sentence)

        return player_sentences


# Integration function for the main YouTube helper
def analyze_player_videos(youtube_helper, player_name: str, channel_handles: List[str],
                         days_back: int = 7) -> Dict[str, List[TranscriptAnalysis]]:
    """Analyze videos for a player across multiple channels with transcript analysis"""
    if not TRANSCRIPT_API_AVAILABLE:
        print("Transcript analysis requires youtube-transcript-api")
        return {}

    transcript_helper = TranscriptHelper()
    results = {}

    for handle in channel_handles:
        channel_id = youtube_helper.get_channel_id(handle)
        if not channel_id:
            print(f"Could not find channel: {handle}")
            continue

        # Get videos mentioning the player
        videos = youtube_helper.search_channel_for_player(channel_id, player_name, days_back)

        if videos:
            # Convert VideoInfo objects to dicts for batch analysis
            video_data = [{'video_id': v.video_id, 'title': v.title} for v in videos]
            analyses = transcript_helper.batch_analyze_videos(video_data, player_name)

            if analyses:
                results[handle] = analyses

    return results


# Example usage
if __name__ == "__main__":
    if TRANSCRIPT_API_AVAILABLE:
        helper = TranscriptHelper()

        # Example: Analyze a specific video
        video_id = "dQw4w9WgXcQ"  # Replace with actual video ID
        player = "Tyreek Hill"

        analysis = helper.analyze_transcript_for_player(video_id, "Test Video", player)
        if analysis:
            print(helper.generate_player_report([analysis], player))
        else:
            print(f"No mentions of {player} found in video transcript")
    else:
        print("Install youtube-transcript-api to use transcript functionality")