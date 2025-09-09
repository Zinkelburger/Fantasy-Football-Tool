#!/usr/bin/env python3
"""
ESPN Roster Weekly Analysis Tool

This program analyzes your ESPN fantasy football roster using the ESPN API.
It requests authentication cookies from the Chrome extension when needed.
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv, set_key
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from espn_api.football import League
except ImportError:
    print("ERROR: espn_api not installed. Run: pip install espn-api")
    sys.exit(1)

class AuthRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for ESPN authentication"""
    
    def do_GET(self):
        if self.path == '/espn-auth-request':
            # Extension is checking if we need auth
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {'requestAuth': self.server.auth_requested}
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/espn-auth':
            # Extension is checking for auth data
            if self.server.auth_data:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(self.server.auth_data).encode())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/espn-auth-request':
            # Python program requesting auth
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            if data.get('requestAuth'):
                self.server.auth_requested = True
                print("Auth request signal sent to extension")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            
        elif self.path == '/espn-auth':
            # Extension sending auth data
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            self.server.auth_data = json.loads(post_data.decode())
            print("Received ESPN auth from extension")
            print("Raw data received:", self.server.auth_data)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status": "received"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

class AuthServer(HTTPServer):
    """Custom HTTP server that stores auth state"""
    
    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        self.auth_requested = False
        self.auth_data = None

class ESPNRosterAnalyzer:
    def __init__(self):
        self.env_file = Path(__file__).parent / '.env'
        load_dotenv(self.env_file)
        
        self.league_id = os.getenv('ESPN_LEAGUE_ID')
        self.year = os.getenv('ESPN_YEAR', '2024')
        self.swid = os.getenv('ESPN_SWID')
        self.espn_s2 = os.getenv('ESPN_S2')
        
        self.league = None
        self.auth_server = None
        self.server_thread = None
        
    def start_auth_server(self):
        """Start the HTTP server for extension communication."""
        try:
            print("Creating auth server...")
            self.auth_server = AuthServer(('localhost', 8001), AuthRequestHandler)
            print("Starting server thread...")
            self.server_thread = threading.Thread(target=self.auth_server.serve_forever, daemon=True)
            self.server_thread.start()
            print("Server thread started, waiting for it to bind...")
            time.sleep(1.0)  # Give server more time to start
            
            # Test if server is actually responding
            try:
                import urllib.request
                urllib.request.urlopen('http://localhost:8001/espn-auth-request', timeout=2)
                print("✅ Auth server confirmed running on localhost:8001")
            except Exception as e:
                print(f"⚠️  Server started but not responding: {e}")
            
            return True
        except OSError as e:
            if "Address already in use" in str(e):
                print("ERROR: Port 8001 is already in use. Make sure no other ESPN roster analyzer is running.")
            else:
                print(f"ERROR: Could not start auth server: {e}")
            return False
            
    def stop_auth_server(self):
        """Stop the auth server."""
        if self.auth_server:
            self.auth_server.shutdown()
            self.auth_server = None
        
    def request_auth_from_extension(self) -> Optional[Dict[str, str]]:
        """Request ESPN auth cookies from the Chrome extension."""
        print("Requesting ESPN authentication from Chrome extension...")
        print("Make sure you have the Chrome extension active on an ESPN Fantasy page")
        
        # Start the auth server if not already running
        if not self.auth_server:
            if not self.start_auth_server():
                return None
        
        # Signal to extension that we need auth
        self.auth_server.auth_requested = True
        self.auth_server.auth_data = None
        
        # Wait for extension to provide data (poll for up to 30 seconds)
        print("Waiting for ESPN data from extension...")
        for i in range(30):
            if self.auth_server.auth_data:
                data = self.auth_server.auth_data
                if 'swid' in data and 'espn_s2' in data and 'league_id' in data:
                    self.auth_server.auth_requested = False  # Reset flag
                    return data
            time.sleep(1)
            if (i + 1) % 5 == 0:
                print(f"Still waiting... ({i + 1}/30 seconds)")
            
        print("ERROR: Timeout waiting for ESPN data from extension")
        print("Make sure:")
        print("1. Chrome extension is installed and active")
        print("2. You're on an ESPN Fantasy Football page")
        print("3. You're logged into ESPN")
        return None
    
    def save_espn_data_to_env(self, data: Dict[str, str]) -> None:
        """Save ESPN data to .env file."""
        print("Saving ESPN data to .env file...")
        
        # Create .env file if it doesn't exist
        if not self.env_file.exists():
            self.env_file.touch()
            
        # Save auth data
        swid = data.get('swid', '')
        espn_s2 = data.get('espn_s2', '')
        league_id = data.get('league_id', '')
        season_id = data.get('season_id', '')
        
        set_key(self.env_file, 'ESPN_SWID', swid)
        set_key(self.env_file, 'ESPN_S2', espn_s2)
        set_key(self.env_file, 'ESPN_LEAGUE_ID', str(league_id))
        set_key(self.env_file, 'ESPN_YEAR', str(season_id))
        
        # Update instance variables
        self.swid = swid
        self.espn_s2 = espn_s2
        self.league_id = str(league_id)
        self.year = str(season_id)
    
    def get_league_info(self) -> bool:
        """Get league ID and year from user if not in .env."""
        if not self.league_id:
            self.league_id = input("Enter your ESPN League ID: ").strip()
            if self.league_id:
                set_key(self.env_file, 'ESPN_LEAGUE_ID', self.league_id)
        
        year_input = input(f"Enter league year (default: {self.year}): ").strip()
        if year_input:
            self.year = year_input
            set_key(self.env_file, 'ESPN_YEAR', self.year)
            
        return bool(self.league_id)
    
    def initialize_league(self) -> bool:
        """Initialize ESPN League connection."""
        # Check if we have all required data
        if not self.league_id or not self.swid or not self.espn_s2:
            print("Getting ESPN data from extension...")
            espn_data = self.request_auth_from_extension()
            if not espn_data:
                print("ERROR: Could not obtain ESPN data from extension")
                return False
                
            # Check if extension provided valid data
            print("Validating ESPN data...")
            swid = str(espn_data.get('swid', '')).strip()
            espn_s2 = str(espn_data.get('espn_s2', '')).strip()
            league_id = str(espn_data.get('league_id', '')).strip()
            season_id = str(espn_data.get('season_id', '')).strip()
            
            print(f"SWID: '{swid}'")
            print(f"ESPN_S2: '{espn_s2}'") 
            print(f"League ID: '{league_id}'")
            print(f"Season ID: '{season_id}'")
            
            if (swid == "Could not load SWID" or espn_s2 == "Could not load S2" or 
                league_id == "Could not load League ID" or season_id == "Could not load Season ID"):
                print("ERROR: Extension could not read ESPN data")
                print("Make sure you're logged into ESPN Fantasy in your browser")
                return False
                
            self.save_espn_data_to_env(espn_data)
        
        # Initialize league
        try:
            # Use current year if season_id couldn't be loaded
            year = self.year if self.year != "Could not load Season ID" else "2025"
            print(f"Connecting to ESPN League {self.league_id} for year {year}...")
            self.league = League(
                league_id=int(self.league_id),
                year=int(year),
                espn_s2=self.espn_s2,
                swid=self.swid
            )
            print(f"✓ Connected to league: {self.league.settings.name}")
            return True
            
        except Exception as e:
            print(f"ERROR: Could not connect to ESPN league: {e}")
            return False
    
    def analyze_roster(self, team_name: Optional[str] = None) -> None:
        """Analyze a specific team's roster."""
        if not self.league:
            print("ERROR: League not initialized")
            return
            
        # Find the team
        target_team = None
        if team_name:
            for team in self.league.teams:
                if team_name.lower() in team.team_name.lower():
                    target_team = team
                    break
        else:
            # Show all teams and let user choose
            print("\nAvailable teams:")
            for i, team in enumerate(self.league.teams, 1):
                print(f"{i}. {team.team_name} ({team.owners})")
                
            try:
                choice = int(input("\nSelect team number: ")) - 1
                target_team = self.league.teams[choice]
            except (ValueError, IndexError):
                print("Invalid selection")
                return
        
        if not target_team:
            print(f"Team '{team_name}' not found")
            return
            
        print(f"\n=== {target_team.team_name} Roster Analysis ===")
        print(f"Owner: {target_team.owners}")
        print(f"Record: {target_team.wins}-{target_team.losses}")
        print(f"Points For: {target_team.points_for}")
        print(f"Points Against: {target_team.points_against}")
        
        print(f"\n--- Current Roster ---")
        for player in target_team.roster:
            print(f"{player.name} ({player.position}) - {player.proTeam}")
            
        print(f"\n--- Recent Moves ---")
        for activity in self.league.recent_activity()[:5]:
            if hasattr(activity, 'team') and activity.team == target_team:
                print(f"- {activity}")

def main():
    print("ESPN Fantasy Football Roster Analyzer")
    print("====================================")
    
    analyzer = ESPNRosterAnalyzer()
    
    try:
        if not analyzer.initialize_league():
            sys.exit(1)
            
        # Run analysis
        team_name = input("\nEnter team name to analyze (or press Enter to choose from list): ").strip()
        analyzer.analyze_roster(team_name if team_name else None)
        
    finally:
        # Clean up the auth server
        analyzer.stop_auth_server()
        print("\nAnalysis complete!")

if __name__ == "__main__":
    main()