#!/usr/bin/env python3
"""
ESPN Fantasy Football CLI Tool

Simple command-line interface for ESPN API calls.
Returns JSON data for Go to consume.
"""

import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from espn_api.football import League

def load_env():
    """Load environment variables from parent directory .env file"""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        return True
    return False

def connect_to_league():
    """Connect to ESPN league and return basic info"""
    league_id = os.getenv('ESPN_LEAGUE_ID')
    year = os.getenv('ESPN_YEAR', '2025')
    swid = os.getenv('ESPN_SWID')
    espn_s2 = os.getenv('ESPN_S2')

    if not all([league_id, swid, espn_s2]):
        return {"error": "Missing ESPN credentials"}

    try:
        league = League(
            league_id=int(league_id),
            year=int(year),
            espn_s2=espn_s2,
            swid=swid
        )

        teams = []
        for team in league.teams:
            owner_name = "Unknown"
            if team.owners:
                owner = team.owners[0]
                if hasattr(owner, 'displayName'):
                    owner_name = owner.displayName
                elif isinstance(owner, dict) and 'displayName' in owner:
                    owner_name = owner['displayName']
                else:
                    owner_name = str(owner)

            teams.append({
                "id": team.team_id,
                "name": team.team_name,
                "owner": owner_name
            })

        return {
            "league_name": league.settings.name,
            "teams": teams
        }

    except Exception as e:
        return {"error": str(e)}

def get_team_roster(team_id):
    """Get roster for a specific team"""
    league_id = os.getenv('ESPN_LEAGUE_ID')
    year = os.getenv('ESPN_YEAR', '2025')
    swid = os.getenv('ESPN_SWID')
    espn_s2 = os.getenv('ESPN_S2')

    if not all([league_id, swid, espn_s2]):
        return {"error": "Missing ESPN credentials"}

    try:
        league = League(
            league_id=int(league_id),
            year=int(year),
            espn_s2=espn_s2,
            swid=swid
        )

        # Find the team
        target_team = None
        for team in league.teams:
            if team.team_id == int(team_id):
                target_team = team
                break

        if not target_team:
            return {"error": f"Team {team_id} not found"}

        players = []
        for player in target_team.roster:
            injury_status = "Active"
            if hasattr(player, 'injuryStatus') and player.injuryStatus:
                injury_status = player.injuryStatus
            elif hasattr(player, 'injured') and player.injured:
                injury_status = "Injured"

            pro_team = "N/A"
            if hasattr(player, 'proTeam'):
                pro_team = player.proTeam

            players.append({
                "name": player.name,
                "position": player.position,
                "team": pro_team,
                "status": injury_status
            })

        return {
            "team_name": target_team.team_name,
            "players": players
        }

    except Exception as e:
        return {"error": str(e)}

def get_free_agents(position=None, week=None, size=50):
    """Get free agents/waiver wire players"""
    league_id = os.getenv('ESPN_LEAGUE_ID')
    year = os.getenv('ESPN_YEAR', '2025')
    swid = os.getenv('ESPN_SWID')
    espn_s2 = os.getenv('ESPN_S2')

    if not all([league_id, swid, espn_s2]):
        return {"error": "Missing ESPN credentials"}

    try:
        league = League(
            league_id=int(league_id),
            year=int(year),
            espn_s2=espn_s2,
            swid=swid
        )

        # Convert position name to position_id if needed
        position_id = None
        if position:
            position_mapping = {
                'QB': 0, 'RB': 2, 'WR': 4, 'TE': 6,
                'K': 17, 'DST': 16, 'D/ST': 16
            }
            position_id = position_mapping.get(position.upper())

        # Get free agents
        free_agents = league.free_agents(
            week=week,
            size=size,
            position_id=position_id
        )

        players = []
        for player in free_agents:
            injury_status = "ACTIVE"
            if hasattr(player, 'injuryStatus') and player.injuryStatus:
                injury_status = player.injuryStatus
            elif hasattr(player, 'injury_status') and player.injury_status:
                injury_status = player.injury_status

            # Get pro team abbreviation
            pro_team = "FA"
            if hasattr(player, 'proTeam') and player.proTeam:
                pro_team = player.proTeam
            elif hasattr(player, 'pro_team') and player.pro_team:
                pro_team = player.pro_team

            players.append({
                "name": player.name,
                "position": player.position,
                "team": pro_team,
                "status": injury_status,
                "player_id": player.playerId if hasattr(player, 'playerId') else None,
                "percent_owned": getattr(player, 'percent_owned', 0),
                "percent_started": getattr(player, 'percent_started', 0)
            })

        return {
            "players": players,
            "count": len(players),
            "position_filter": position,
            "week": week
        }

    except Exception as e:
        return {"error": str(e)}

def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: espn_cli.py <command> [args]"}))
        sys.exit(1)

    # Load environment variables
    load_env()

    command = sys.argv[1]

    if command == "connect":
        result = connect_to_league()
    elif command == "roster" and len(sys.argv) >= 3:
        team_id = sys.argv[2]
        result = get_team_roster(team_id)
    elif command == "free_agents":
        # Parse optional arguments
        position = None
        week = None
        size = 50

        for i, arg in enumerate(sys.argv[2:], 2):
            if arg.startswith("--position="):
                position = arg.split("=", 1)[1]
            elif arg.startswith("--week="):
                week = int(arg.split("=", 1)[1])
            elif arg.startswith("--size="):
                size = int(arg.split("=", 1)[1])

        result = get_free_agents(position=position, week=week, size=size)
    else:
        result = {"error": f"Unknown command: {command}. Available: connect, roster <team_id>, free_agents [--position=QB] [--week=3] [--size=50]"}

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()