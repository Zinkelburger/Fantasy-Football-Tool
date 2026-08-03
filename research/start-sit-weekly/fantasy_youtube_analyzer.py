#!/usr/bin/env python3
"""
Fantasy Football YouTube Analyzer

Combines ESPN roster analysis with YouTube content analysis for fantasy football insights.
Integrates with existing ESPN roster analyzer to get player data, then searches YouTube
for recent content about those players.
"""

import os
import sys
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Import our helpers
from youtube_helper import YouTubeHelper, VideoInfo, find_player_mentions
from transcript_helper import TranscriptHelper, analyze_player_videos, TRANSCRIPT_API_AVAILABLE
from espn_roster_analyzer import ESPNRosterAnalyzer


class FantasyYouTubeAnalyzer:
    """Main analyzer that combines ESPN roster data with YouTube content analysis"""

    def __init__(self, youtube_api_key: Optional[str] = None):
        """Initialize the analyzer with YouTube API key"""
        self.youtube_helper = YouTubeHelper(youtube_api_key)
        self.transcript_helper = TranscriptHelper() if TRANSCRIPT_API_AVAILABLE else None
        self.espn_analyzer = ESPNRosterAnalyzer()

        # Popular fantasy football channels (can be customized)
        self.default_channels = [
            "@FantasyFootballers",
            "@TheFantasyFootballAdvisors",
            "@FantasyPros",
            "@SleeperbotNFL",
            "@32BeatWriters",
            "@RotoWire",
            "@PFF",
            "@SharpsportsBets"
        ]

        # Injury report specific channels
        self.injury_channels = [
            "@NFL",
            "@AdamSchefter",
            "@RapSheet",
            "@JosinaAnderson"
        ]

    def analyze_roster_with_youtube(self, team_name: Optional[str] = None,
                                  custom_channels: Optional[List[str]] = None,
                                  days_back: int = 7) -> Dict:
        """Analyze ESPN roster and get YouTube insights for all players"""

        # Initialize ESPN connection
        if not self.espn_analyzer.initialize_league():
            return {"error": "Could not connect to ESPN league"}

        # Get roster
        team = self._get_team(team_name)
        if not team:
            return {"error": "Team not found"}

        players = [player.name for player in team.roster]
        channels = custom_channels or self.default_channels

        print(f"\nAnalyzing YouTube content for {len(players)} players...")
        print(f"Searching {len(channels)} channels for content from last {days_back} days")

        results = {
            "team_name": team.team_name,
            "players_analyzed": len(players),
            "channels_searched": channels,
            "analysis_date": datetime.now().isoformat(),
            "player_results": {}
        }

        # Analyze each player
        for player in players:
            print(f"\n🔍 Analyzing {player}...")
            player_data = self.analyze_single_player(player, channels, days_back)
            if player_data:
                results["player_results"][player] = player_data

        return results

    def analyze_single_player(self, player_name: str, channels: List[str],
                            days_back: int = 7) -> Dict:
        """Analyze YouTube content for a single player"""

        # Find video mentions
        video_mentions = find_player_mentions(player_name, channels, days_back=days_back)

        if not video_mentions:
            return {"mentions": 0, "videos": []}

        all_videos = []
        for channel, videos in video_mentions.items():
            for video in videos:
                video_data = {
                    "channel": channel,
                    "title": video.title,
                    "url": video.url,
                    "published": video.published_at.isoformat(),
                    "description": video.description[:200] + "..." if len(video.description) > 200 else video.description
                }
                all_videos.append(video_data)

        result = {
            "mentions": len(all_videos),
            "videos": all_videos
        }

        # Add transcript analysis if available
        if self.transcript_helper:
            print(f"  📝 Analyzing transcripts for {player_name}...")
            transcript_analyses = analyze_player_videos(
                self.youtube_helper, player_name, channels, days_back
            )

            if transcript_analyses:
                result["transcript_analysis"] = {}
                for channel, analyses in transcript_analyses.items():
                    if analyses:
                        report = self.transcript_helper.generate_player_report(analyses, player_name)
                        result["transcript_analysis"][channel] = report

        return result

    def get_injury_reports(self, team_keywords: Optional[List[str]] = None,
                          days_back: int = 3) -> List[VideoInfo]:
        """Get recent injury reports, optionally filtered by team"""
        if team_keywords:
            return self.youtube_helper.get_injury_reports(team_keywords, days_back)
        else:
            # General injury reports
            return self.youtube_helper.search_videos_by_keyword(
                "NFL injury report", days_back=days_back, max_results=20
            )

    def search_specific_channel_for_player(self, channel_handle: str, player_name: str,
                                         days_back: int = 7, include_transcripts: bool = True) -> Dict:
        """Deep dive analysis of a specific channel for a player"""

        channel_id = self.youtube_helper.get_channel_id(channel_handle)
        if not channel_id:
            return {"error": f"Channel {channel_handle} not found"}

        # Get videos
        videos = self.youtube_helper.search_channel_for_player(channel_id, player_name, days_back)

        if not videos:
            return {"channel": channel_handle, "player": player_name, "videos_found": 0}

        result = {
            "channel": channel_handle,
            "player": player_name,
            "videos_found": len(videos),
            "videos": []
        }

        for video in videos:
            video_data = {
                "title": video.title,
                "url": video.url,
                "published": video.published_at.isoformat(),
                "description": video.description
            }

            # Add transcript analysis if requested
            if include_transcripts and self.transcript_helper:
                analysis = self.transcript_helper.analyze_transcript_for_player(
                    video.video_id, video.title, player_name
                )
                if analysis:
                    video_data["transcript_summary"] = {
                        "mentions": len(analysis.player_mentions),
                        "injury_mentions": analysis.injury_mentions,
                        "key_phrases": analysis.key_phrases[:5]  # Top 5 phrases
                    }

            result["videos"].append(video_data)

        return result

    def _get_team(self, team_name: Optional[str]):
        """Get team from ESPN analyzer"""
        if not self.espn_analyzer.league:
            return None

        if team_name:
            for team in self.espn_analyzer.league.teams:
                if team_name.lower() in team.team_name.lower():
                    return team
        else:
            # Show all teams and let user choose
            print("\nAvailable teams:")
            for i, team in enumerate(self.espn_analyzer.league.teams, 1):
                print(f"{i}. {team.team_name} ({team.owners})")

            try:
                choice = int(input("\nSelect team number: ")) - 1
                return self.espn_analyzer.league.teams[choice]
            except (ValueError, IndexError):
                print("Invalid selection")
                return None

        return None

    def generate_weekly_report(self, team_name: Optional[str] = None) -> str:
        """Generate a comprehensive weekly report combining ESPN and YouTube data"""

        analysis = self.analyze_roster_with_youtube(team_name)

        if "error" in analysis:
            return f"Error: {analysis['error']}"

        report = f"=== Weekly Fantasy Report for {analysis['team_name']} ===\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += f"Players Analyzed: {analysis['players_analyzed']}\n\n"

        # Summary of players with mentions
        players_with_content = [p for p, data in analysis['player_results'].items() if data['mentions'] > 0]

        if players_with_content:
            report += f"🎥 PLAYERS WITH RECENT CONTENT ({len(players_with_content)} of {analysis['players_analyzed']}):\n"

            for player in players_with_content:
                data = analysis['player_results'][player]
                report += f"\n📺 {player} - {data['mentions']} video(s)\n"

                # Show most recent video
                if data['videos']:
                    latest = data['videos'][0]
                    report += f"  Latest: {latest['title']} ({latest['channel']})\n"
                    report += f"  URL: {latest['url']}\n"

                # Show transcript insights if available
                if 'transcript_analysis' in data:
                    for channel, analysis_text in data['transcript_analysis'].items():
                        if "INJURY MENTIONS" in analysis_text:
                            report += f"  🚨 {channel}: Injury mentions detected\n"

        else:
            report += "📺 No recent YouTube content found for roster players\n"

        # Add injury report section
        report += f"\n🏥 RECENT INJURY REPORTS:\n"
        injury_videos = self.get_injury_reports(days_back=3)
        if injury_videos:
            for video in injury_videos[:5]:  # Top 5 injury reports
                report += f"  - {video.title} ({video.channel_title})\n"
                report += f"    {video.url}\n"
        else:
            report += "  No recent injury reports found\n"

        return report


def main():
    """Main function for command-line usage"""
    print("Fantasy Football YouTube Analyzer")
    print("=================================")

    try:
        analyzer = FantasyYouTubeAnalyzer()

        print("\nOptions:")
        print("1. Full roster analysis")
        print("2. Single player analysis")
        print("3. Specific channel search")
        print("4. Weekly report")
        print("5. Injury reports only")

        choice = input("\nSelect option (1-5): ").strip()

        if choice == "1":
            team_name = input("Enter team name (or press Enter to choose): ").strip()
            result = analyzer.analyze_roster_with_youtube(team_name if team_name else None)
            print("\n" + str(result))

        elif choice == "2":
            player = input("Enter player name: ").strip()
            channels = input("Enter channel handles (comma-separated, or press Enter for defaults): ").strip()
            if channels:
                channel_list = [c.strip() for c in channels.split(",")]
            else:
                channel_list = analyzer.default_channels

            result = analyzer.analyze_single_player(player, channel_list)
            print("\n" + str(result))

        elif choice == "3":
            channel = input("Enter channel handle (e.g., @FantasyFootballers): ").strip()
            player = input("Enter player name: ").strip()
            result = analyzer.search_specific_channel_for_player(channel, player)
            print("\n" + str(result))

        elif choice == "4":
            team_name = input("Enter team name (or press Enter to choose): ").strip()
            report = analyzer.generate_weekly_report(team_name if team_name else None)
            print("\n" + report)

        elif choice == "5":
            teams = input("Enter team keywords (comma-separated, or press Enter for general): ").strip()
            if teams:
                team_list = [t.strip() for t in teams.split(",")]
                videos = analyzer.get_injury_reports(team_list)
            else:
                videos = analyzer.get_injury_reports()

            print(f"\n🏥 Found {len(videos)} injury reports:")
            for video in videos:
                print(f"  - {video.title}")
                print(f"    {video.url}")

        else:
            print("Invalid option")

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up ESPN analyzer
        if hasattr(analyzer, 'espn_analyzer'):
            analyzer.espn_analyzer.stop_auth_server()


if __name__ == "__main__":
    main()