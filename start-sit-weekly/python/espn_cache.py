#!/usr/bin/env python3
"""
ESPN data caching utility.

Caches league and roster data to CSV files to avoid repeated API calls.
"""

import json
import sys
import os
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv
from espn_api.football import League


def load_env():
    """Load environment variables from parent directory .env file"""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        return True
    return False


def cache_league_data():
    """Cache league and team information to CSV"""
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

        # Cache directory
        cache_dir = Path("espn_cache")
        cache_dir.mkdir(exist_ok=True)

        # Cache league info
        league_file = cache_dir / "league_info.csv"
        with open(league_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['league_id', 'league_name', 'year', 'cached_at'])
            writer.writerow([league_id, league.settings.name, year, datetime.now().isoformat()])

        # Cache teams info
        teams_file = cache_dir / "teams.csv"
        with open(teams_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['team_id', 'team_name', 'owner_name'])

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

                writer.writerow([team.team_id, team.team_name, owner_name])

        # Cache all rosters
        rosters_file = cache_dir / "rosters.csv"
        with open(rosters_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['team_id', 'team_name', 'player_name', 'position', 'pro_team', 'status'])

            for team in league.teams:
                for player in team.roster:
                    injury_status = "Active"
                    if hasattr(player, 'injuryStatus') and player.injuryStatus:
                        injury_status = player.injuryStatus
                    elif hasattr(player, 'injured') and player.injured:
                        injury_status = "Injured"

                    pro_team = "N/A"
                    if hasattr(player, 'proTeam'):
                        pro_team = player.proTeam

                    writer.writerow([
                        team.team_id,
                        team.team_name,
                        player.name,
                        player.position,
                        pro_team,
                        injury_status
                    ])

        print(f"ESPN data cached successfully to {cache_dir}")

        return {
            "success": True,
            "league_name": league.settings.name,
            "teams_count": len(league.teams),
            "cache_dir": str(cache_dir),
            "cached_at": datetime.now().isoformat()
        }

    except Exception as e:
        return {"error": str(e)}


def load_cached_league_info() -> Dict:
    """Load cached league information"""
    cache_dir = Path("espn_cache")
    league_file = cache_dir / "league_info.csv"

    if not league_file.exists():
        return {"error": "No cached league data found"}

    try:
        with open(league_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            return {
                "league_id": row['league_id'],
                "league_name": row['league_name'],
                "year": row['year'],
                "cached_at": row['cached_at']
            }
    except Exception as e:
        return {"error": str(e)}


def load_cached_teams() -> List[Dict]:
    """Load cached teams information"""
    cache_dir = Path("espn_cache")
    teams_file = cache_dir / "teams.csv"

    if not teams_file.exists():
        return []

    try:
        teams = []
        with open(teams_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                teams.append({
                    "id": int(row['team_id']),
                    "name": row['team_name'],
                    "owner": row['owner_name']
                })
        return teams
    except Exception as e:
        print(f"Error loading cached teams: {e}")
        return []


def load_cached_roster(team_id: int) -> List[Dict]:
    """Load cached roster for a specific team"""
    cache_dir = Path("espn_cache")
    rosters_file = cache_dir / "rosters.csv"

    if not rosters_file.exists():
        return []

    try:
        players = []
        with open(rosters_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['team_id']) == team_id:
                    players.append({
                        "name": row['player_name'],
                        "position": row['position'],
                        "team": row['pro_team'],
                        "status": row['status']
                    })
        return players
    except Exception as e:
        print(f"Error loading cached roster: {e}")
        return []


def is_cache_fresh(max_age_hours: int = 24) -> bool:
    """Check if the cached data is fresh enough"""
    cache_dir = Path("espn_cache")
    league_file = cache_dir / "league_info.csv"

    if not league_file.exists():
        return False

    try:
        info = load_cached_league_info()
        if "error" in info:
            return False

        cached_time = datetime.fromisoformat(info["cached_at"])
        age_hours = (datetime.now() - cached_time).total_seconds() / 3600

        return age_hours < max_age_hours
    except Exception:
        return False


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: espn_cache.py <cache|load_teams|load_roster> [team_id]"}))
        sys.exit(1)

    load_env()
    command = sys.argv[1]

    if command == "cache":
        result = cache_league_data()
        print(json.dumps(result, indent=2))

    elif command == "load_teams":
        teams = load_cached_teams()
        league_info = load_cached_league_info()
        result = {
            "league_name": league_info.get("league_name", "Unknown"),
            "teams": teams,
            "cached_at": league_info.get("cached_at", "Unknown")
        }
        print(json.dumps(result, indent=2))

    elif command == "load_roster" and len(sys.argv) >= 3:
        try:
            team_id = int(sys.argv[2])
            players = load_cached_roster(team_id)

            # Get team name
            teams = load_cached_teams()
            team_name = "Unknown"
            for team in teams:
                if team["id"] == team_id:
                    team_name = team["name"]
                    break

            result = {
                "team_name": team_name,
                "players": players
            }
            print(json.dumps(result, indent=2))
        except ValueError:
            print(json.dumps({"error": "Invalid team ID"}))

    elif command == "check_cache":
        fresh = is_cache_fresh()
        info = load_cached_league_info()
        result = {
            "cache_exists": "error" not in info,
            "cache_fresh": fresh,
            "cache_info": info if "error" not in info else None
        }
        print(json.dumps(result, indent=2))

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))


if __name__ == "__main__":
    main()