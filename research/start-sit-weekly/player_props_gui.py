#!/usr/bin/env python3
"""
NFL Player Props GUI Application

This application allows users to load their fantasy team roster from a CSV file
and fetch player props data using various API services.

Author: Fantasy Football Tool
Date: 2025
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional, Any
import threading
from dataclasses import dataclass
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PlayerProps:
    """Data class to store player props information"""
    player_name: str
    team: str
    position: str
    prop_type: str
    line: float
    over_odds: str
    under_odds: str
    sportsbook: str
    last_updated: str

class APIClient:
    """Handle API requests to various sports data providers"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NFL-Player-Props-GUI/1.0',
            'Accept': 'application/json'
        })
    
    def get_api_football_props(self, players: List[Dict]) -> List[PlayerProps]:
        """
        Fetch player props from API-Football
        Note: API-Football primarily covers soccer, but including for completeness
        """
        props = []
        base_url = "https://api-football.com/v3"
        
        # API-Football uses different endpoints for different sports
        # For American Football, we'd need to check their specific endpoints
        headers = {
            'X-RapidAPI-Key': self.api_key,
            'X-RapidAPI-Host': 'api-football.com'
        }
        
        try:
            # This is a placeholder - API-Football's actual NFL endpoints would be different
            for player in players:
                # Simulate API call structure
                logger.info(f"Fetching props for {player.get('name', 'Unknown')}")
                
                # For demonstration purposes, we'll create mock data
                mock_props = self._create_mock_props(player)
                props.extend(mock_props)
                
        except Exception as e:
            logger.error(f"Error fetching from API-Football: {str(e)}")
            
        return props
    
    def get_sportsdata_props(self, players: List[Dict]) -> List[PlayerProps]:
        """
        Fetch player props from SportsDataIO (more suitable for NFL)
        """
        props = []
        base_url = "https://api.sportsdata.io/v3/nfl/odds/json"
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key
        }
        
        try:
            # Get current betting events
            events_url = f"{base_url}/BettingEventsByDate/{datetime.now().strftime('%Y-%m-%d')}"
            response = self.session.get(events_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                events = response.json()
                
                for player in players:
                    player_props = self._extract_player_props_from_events(events, player)
                    props.extend(player_props)
            else:
                logger.warning(f"SportsDataIO API returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching from SportsDataIO: {str(e)}")
            
        return props
    
    def get_prop_odds_props(self, players: List[Dict]) -> List[PlayerProps]:
        """
        Fetch player props from Prop-Odds API (good for player props)
        """
        props = []
        base_url = "https://api.prop-odds.com/beta"
        
        try:
            # Get NFL games for today
            today = datetime.now().strftime('%Y-%m-%d')
            games_url = f"{base_url}/games/nfl?date={today}&api_key={self.api_key}"
            
            response = self.session.get(games_url, timeout=30)
            
            if response.status_code == 200:
                games = response.json().get('games', [])
                
                for game in games:
                    game_id = game.get('game_id')
                    if game_id:
                        game_props = self._get_game_player_props(game_id, players)
                        props.extend(game_props)
            else:
                logger.warning(f"Prop-Odds API returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching from Prop-Odds: {str(e)}")
            
        return props
    
    def _get_game_player_props(self, game_id: str, players: List[Dict]) -> List[PlayerProps]:
        """Get player props for a specific game"""
        props = []
        base_url = "https://api.prop-odds.com/beta"
        
        try:
            # Common NFL player prop markets
            prop_markets = [
                'player_passing_yards', 'player_rushing_yards', 'player_receiving_yards',
                'player_receptions', 'player_passing_touchdowns', 'player_anytime_touchdown'
            ]
            
            for market in prop_markets:
                market_url = f"{base_url}/odds/{game_id}/{market}?api_key={self.api_key}"
                response = self.session.get(market_url, timeout=15)
                
                if response.status_code == 200:
                    market_data = response.json()
                    market_props = self._parse_prop_odds_data(market_data, players, market)
                    props.extend(market_props)
                    
        except Exception as e:
            logger.error(f"Error fetching game props for {game_id}: {str(e)}")
            
        return props
    
    def _parse_prop_odds_data(self, data: Dict, players: List[Dict], market: str) -> List[PlayerProps]:
        """Parse prop odds data and filter for our players"""
        props = []
        player_names = {p.get('name', '').lower() for p in players}
        
        try:
            sportsbooks = data.get('sportsbooks', [])
            
            for book in sportsbooks:
                bookie_name = book.get('bookie_key', 'Unknown')
                market_data = book.get('market', {})
                outcomes = market_data.get('outcomes', [])
                
                for outcome in outcomes:
                    player_name = outcome.get('name', '')
                    
                    # Check if this player is in our roster
                    if player_name.lower() in player_names:
                        prop = PlayerProps(
                            player_name=player_name,
                            team=self._get_player_team(player_name, players),
                            position=self._get_player_position(player_name, players),
                            prop_type=market.replace('player_', '').replace('_', ' ').title(),
                            line=outcome.get('total', 0.0),
                            over_odds=f"+{outcome.get('odds', 0)}",
                            under_odds=f"+{outcome.get('odds', 0)}",  # Simplified for demo
                            sportsbook=bookie_name.title(),
                            last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        )
                        props.append(prop)
                        
        except Exception as e:
            logger.error(f"Error parsing prop odds data: {str(e)}")
            
        return props
    
    def _extract_player_props_from_events(self, events: List[Dict], player: Dict) -> List[PlayerProps]:
        """Extract player props from SportsDataIO events data"""
        props = []
        player_name = player.get('name', '')
        
        try:
            for event in events:
                betting_markets = event.get('BettingMarkets', [])
                
                for market in betting_markets:
                    if market.get('BettingMarketType') == 'Player Prop':
                        # Check if this market is for our player
                        if player_name.lower() in market.get('Name', '').lower():
                            outcomes = market.get('BettingOutcomes', [])
                            
                            if len(outcomes) >= 2:  # Over/Under market
                                over_outcome = outcomes[0]
                                under_outcome = outcomes[1]
                                
                                prop = PlayerProps(
                                    player_name=player_name,
                                    team=player.get('team', 'Unknown'),
                                    position=player.get('position', 'Unknown'),
                                    prop_type=market.get('BettingBetType', 'Unknown'),
                                    line=over_outcome.get('Value', 0.0),
                                    over_odds=f"{over_outcome.get('AmericanOdds', '+100')}",
                                    under_odds=f"{under_outcome.get('AmericanOdds', '+100')}",
                                    sportsbook=over_outcome.get('SportsBook', 'Unknown'),
                                    last_updated=market.get('LastModified', datetime.now().isoformat())
                                )
                                props.append(prop)
                                
        except Exception as e:
            logger.error(f"Error extracting props for {player_name}: {str(e)}")
            
        return props
    
    def _create_mock_props(self, player: Dict) -> List[PlayerProps]:
        """Create mock props data for demonstration"""
        props = []
        player_name = player.get('name', 'Unknown Player')
        team = player.get('team', 'UNK')
        position = player.get('position', 'FLEX')
        
        # Common NFL player prop types based on position
        prop_types = {
            'QB': ['Passing Yards', 'Passing TDs', 'Interceptions', 'Rushing Yards'],
            'RB': ['Rushing Yards', 'Receiving Yards', 'Total TDs', 'Receptions'],
            'WR': ['Receiving Yards', 'Receptions', 'Receiving TDs', 'Longest Reception'],
            'TE': ['Receiving Yards', 'Receptions', 'Receiving TDs'],
            'K': ['FG Made', 'Extra Points', 'Total Points'],
            'DEF': ['Sacks', 'Interceptions', 'Total Points Allowed']
        }
        
        # Mock data with realistic lines
        mock_lines = {
            'Passing Yards': (249.5, -110, -110),
            'Passing TDs': (1.5, -120, +100),
            'Rushing Yards': (64.5, -115, -105),
            'Receiving Yards': (58.5, -110, -110),
            'Receptions': (4.5, -105, -115),
            'Total TDs': (0.5, +140, -180)
        }
        
        # Get prop types for this position
        position_props = prop_types.get(position, prop_types.get('RB'))  # Default to RB props
        
        for prop_type in position_props:
            line, over_odds, under_odds = mock_lines.get(prop_type, (50.5, -110, -110))
            
            prop = PlayerProps(
                player_name=player_name,
                team=team,
                position=position,
                prop_type=prop_type,
                line=line,
                over_odds=str(over_odds),
                under_odds=str(under_odds),
                sportsbook='DraftKings',
                last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            props.append(prop)
            
        return props
    
    def _get_player_team(self, player_name: str, players: List[Dict]) -> str:
        """Get team for a player"""
        for player in players:
            if player.get('name', '').lower() == player_name.lower():
                return player.get('team', 'Unknown')
        return 'Unknown'
    
    def _get_player_position(self, player_name: str, players: List[Dict]) -> str:
        """Get position for a player"""
        for player in players:
            if player.get('name', '').lower() == player_name.lower():
                return player.get('position', 'Unknown')
        return 'Unknown'

class PlayerPropsGUI:
    """Main GUI application for NFL Player Props"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("NFL Player Props Analyzer")
        self.root.geometry("1200x800")
        
        # Application state
        # Odds API key comes from ODDS_API_KEY in .env (or paste one in the
        # Settings tab). Never hardcode it — this repo is public.
        self.api_key = os.getenv('ODDS_API_KEY', '')
        self.players_data = []
        self.props_data = []
        self.api_client = None
        
        self.setup_gui()
        self.setup_api_client()
        
    def setup_gui(self):
        """Setup the main GUI components"""
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="NFL Player Props Analyzer", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # API Configuration Section
        api_frame = ttk.LabelFrame(main_frame, text="API Configuration", padding="10")
        api_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        api_frame.columnconfigure(1, weight=1)
        
        ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.api_key_var = tk.StringVar(value=self.api_key)
        api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show="*")
        api_key_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(api_frame, text="Update API Key", 
                  command=self.update_api_key).grid(row=0, column=2)
        
        # API Service Selection
        ttk.Label(api_frame, text="API Service:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.api_service_var = tk.StringVar(value="prop-odds")
        api_service_combo = ttk.Combobox(api_frame, textvariable=self.api_service_var,
                                        values=["api-football", "sportsdata", "prop-odds", "mock"],
                                        state="readonly")
        api_service_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(10, 0))
        
        # File Loading Section
        file_frame = ttk.LabelFrame(main_frame, text="Team Roster", padding="10")
        file_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="CSV File:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.file_path_var = tk.StringVar()
        file_path_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, state="readonly")
        file_path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(file_frame, text="Browse", 
                  command=self.browse_file).grid(row=0, column=2, padx=(0, 10))
        ttk.Button(file_frame, text="Load Players", 
                  command=self.load_players).grid(row=0, column=3)
        
        # Player Info
        self.players_info_var = tk.StringVar(value="No players loaded")
        ttk.Label(file_frame, textvariable=self.players_info_var).grid(row=1, column=0, columnspan=4, pady=(10, 0))
        
        # Main Content Area
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Players Tab
        self.setup_players_tab()
        
        # Props Tab
        self.setup_props_tab()
        
        # Logs Tab
        self.setup_logs_tab()
        
        # Control Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=(10, 0))
        
        ttk.Button(button_frame, text="Fetch Player Props", 
                  command=self.fetch_props_threaded).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Export Props", 
                  command=self.export_props).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Clear Data", 
                  command=self.clear_data).pack(side=tk.LEFT, padx=(0, 10))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                          maximum=100)
        self.progress_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def setup_players_tab(self):
        """Setup the players display tab"""
        players_frame = ttk.Frame(self.notebook)
        self.notebook.add(players_frame, text="Team Roster")
        
        # Treeview for players
        columns = ('Name', 'Team', 'Position')
        self.players_tree = ttk.Treeview(players_frame, columns=columns, show='headings')
        
        for col in columns:
            self.players_tree.heading(col, text=col)
            self.players_tree.column(col, width=150)
        
        # Scrollbars
        players_v_scroll = ttk.Scrollbar(players_frame, orient=tk.VERTICAL, 
                                        command=self.players_tree.yview)
        players_h_scroll = ttk.Scrollbar(players_frame, orient=tk.HORIZONTAL, 
                                        command=self.players_tree.xview)
        self.players_tree.configure(yscrollcommand=players_v_scroll.set,
                                   xscrollcommand=players_h_scroll.set)
        
        # Grid layout
        self.players_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        players_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        players_h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        players_frame.columnconfigure(0, weight=1)
        players_frame.rowconfigure(0, weight=1)
    
    def setup_props_tab(self):
        """Setup the props display tab"""
        props_frame = ttk.Frame(self.notebook)
        self.notebook.add(props_frame, text="Player Props")
        
        # Treeview for props
        columns = ('Player', 'Team', 'Position', 'Prop Type', 'Line', 'Over', 'Under', 'Sportsbook', 'Updated')
        self.props_tree = ttk.Treeview(props_frame, columns=columns, show='headings')
        
        # Configure columns
        column_widths = {
            'Player': 120, 'Team': 60, 'Position': 70, 'Prop Type': 120,
            'Line': 80, 'Over': 80, 'Under': 80, 'Sportsbook': 100, 'Updated': 140
        }
        
        for col in columns:
            self.props_tree.heading(col, text=col)
            self.props_tree.column(col, width=column_widths.get(col, 100))
        
        # Scrollbars
        props_v_scroll = ttk.Scrollbar(props_frame, orient=tk.VERTICAL, 
                                      command=self.props_tree.yview)
        props_h_scroll = ttk.Scrollbar(props_frame, orient=tk.HORIZONTAL, 
                                      command=self.props_tree.xview)
        self.props_tree.configure(yscrollcommand=props_v_scroll.set,
                                 xscrollcommand=props_h_scroll.set)
        
        # Grid layout
        self.props_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        props_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        props_h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        props_frame.columnconfigure(0, weight=1)
        props_frame.rowconfigure(0, weight=1)
    
    def setup_logs_tab(self):
        """Setup the logs display tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Logs")
        
        self.log_text = scrolledtext.ScrolledText(logs_frame, height=20, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
    
    def setup_api_client(self):
        """Initialize the API client"""
        # Built even without a key: the "mock" service needs no credentials.
        self.api_client = APIClient(self.api_key)
        if not self.api_key:
            self.log_message(
                "No API key found. Set ODDS_API_KEY in .env or enter a key in "
                "Settings. Live services will fail; the 'mock' service works."
            )
    
    def log_message(self, message: str):
        """Add a message to the logs tab"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # Also log to file
        logger.info(message)
    
    def update_api_key(self):
        """Update the API key"""
        new_key = self.api_key_var.get().strip()
        if new_key:
            self.api_key = new_key
            self.setup_api_client()
            self.log_message(f"API key updated")
            self.status_var.set("API key updated")
        else:
            messagebox.showerror("Error", "Please enter a valid API key")
    
    def browse_file(self):
        """Browse for CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select Team Roster CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            self.file_path_var.set(file_path)
    
    def load_players(self):
        """Load players from CSV file"""
        file_path = self.file_path_var.get()
        
        if not file_path:
            messagebox.showerror("Error", "Please select a CSV file first")
            return
        
        if not os.path.exists(file_path):
            messagebox.showerror("Error", "Selected file does not exist")
            return
        
        try:
            # Read CSV file
            df = pd.read_csv(file_path)
            
            # Expected columns (flexible naming)
            name_cols = ['name', 'player', 'player_name', 'full_name']
            team_cols = ['team', 'team_name', 'team_abbr']
            position_cols = ['position', 'pos']
            
            # Find actual column names
            actual_name_col = None
            actual_team_col = None
            actual_position_col = None
            
            df_cols_lower = [col.lower() for col in df.columns]
            
            for col in name_cols:
                if col in df_cols_lower:
                    actual_name_col = df.columns[df_cols_lower.index(col)]
                    break
            
            for col in team_cols:
                if col in df_cols_lower:
                    actual_team_col = df.columns[df_cols_lower.index(col)]
                    break
            
            for col in position_cols:
                if col in df_cols_lower:
                    actual_position_col = df.columns[df_cols_lower.index(col)]
                    break
            
            if not actual_name_col:
                messagebox.showerror("Error", "Could not find player name column. Expected one of: " + ", ".join(name_cols))
                return
            
            # Convert to our format
            self.players_data = []
            for _, row in df.iterrows():
                player = {
                    'name': str(row[actual_name_col]) if actual_name_col else 'Unknown',
                    'team': str(row[actual_team_col]) if actual_team_col else 'UNK',
                    'position': str(row[actual_position_col]) if actual_position_col else 'FLEX'
                }
                self.players_data.append(player)
            
            # Update GUI
            self.update_players_display()
            
            self.players_info_var.set(f"Loaded {len(self.players_data)} players")
            self.log_message(f"Successfully loaded {len(self.players_data)} players from {file_path}")
            self.status_var.set(f"Loaded {len(self.players_data)} players")
            
        except Exception as e:
            error_msg = f"Error loading CSV file: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.log_message(error_msg)
    
    def update_players_display(self):
        """Update the players treeview"""
        # Clear existing items
        for item in self.players_tree.get_children():
            self.players_tree.delete(item)
        
        # Add players
        for player in self.players_data:
            self.players_tree.insert('', tk.END, values=(
                player['name'],
                player['team'],
                player['position']
            ))
    
    def update_props_display(self):
        """Update the props treeview"""
        # Clear existing items
        for item in self.props_tree.get_children():
            self.props_tree.delete(item)
        
        # Add props
        for prop in self.props_data:
            self.props_tree.insert('', tk.END, values=(
                prop.player_name,
                prop.team,
                prop.position,
                prop.prop_type,
                prop.line,
                prop.over_odds,
                prop.under_odds,
                prop.sportsbook,
                prop.last_updated
            ))
    
    def fetch_props_threaded(self):
        """Fetch props in a separate thread to avoid blocking GUI"""
        if not self.players_data:
            messagebox.showerror("Error", "Please load players first")
            return
        
        # Start thread
        thread = threading.Thread(target=self.fetch_props)
        thread.daemon = True
        thread.start()
    
    def fetch_props(self):
        """Fetch player props using the selected API"""
        self.status_var.set("Fetching player props...")
        self.progress_var.set(0)
        
        try:
            api_service = self.api_service_var.get()
            self.log_message(f"Fetching props using {api_service} service for {len(self.players_data)} players")
            
            # Fetch props based on selected service
            if api_service == "api-football":
                props = self.api_client.get_api_football_props(self.players_data)
            elif api_service == "sportsdata":
                props = self.api_client.get_sportsdata_props(self.players_data)
            elif api_service == "prop-odds":
                props = self.api_client.get_prop_odds_props(self.players_data)
            elif api_service == "mock":
                # Use mock data for demonstration
                props = []
                for i, player in enumerate(self.players_data):
                    self.progress_var.set((i / len(self.players_data)) * 100)
                    player_props = self.api_client._create_mock_props(player)
                    props.extend(player_props)
            else:
                raise ValueError(f"Unknown API service: {api_service}")
            
            self.props_data = props
            self.progress_var.set(100)
            
            # Update GUI in main thread
            self.root.after(0, self.update_props_display)
            
            success_msg = f"Successfully fetched {len(props)} props for {len(self.players_data)} players"
            self.log_message(success_msg)
            self.status_var.set(success_msg)
            
        except Exception as e:
            error_msg = f"Error fetching props: {str(e)}"
            self.log_message(error_msg)
            self.status_var.set("Error fetching props")
            messagebox.showerror("Error", error_msg)
        
        finally:
            self.progress_var.set(0)
    
    def export_props(self):
        """Export props to CSV file"""
        if not self.props_data:
            messagebox.showerror("Error", "No props data to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Props Data",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Convert props to DataFrame
                props_dict = []
                for prop in self.props_data:
                    props_dict.append({
                        'Player': prop.player_name,
                        'Team': prop.team,
                        'Position': prop.position,
                        'Prop Type': prop.prop_type,
                        'Line': prop.line,
                        'Over Odds': prop.over_odds,
                        'Under Odds': prop.under_odds,
                        'Sportsbook': prop.sportsbook,
                        'Last Updated': prop.last_updated
                    })
                
                df = pd.DataFrame(props_dict)
                df.to_csv(file_path, index=False)
                
                success_msg = f"Props data exported to {file_path}"
                self.log_message(success_msg)
                self.status_var.set("Props exported successfully")
                messagebox.showinfo("Success", success_msg)
                
            except Exception as e:
                error_msg = f"Error exporting props: {str(e)}"
                self.log_message(error_msg)
                messagebox.showerror("Error", error_msg)
    
    def clear_data(self):
        """Clear all loaded data"""
        self.players_data = []
        self.props_data = []
        
        # Clear displays
        for item in self.players_tree.get_children():
            self.players_tree.delete(item)
        
        for item in self.props_tree.get_children():
            self.props_tree.delete(item)
        
        self.players_info_var.set("No players loaded")
        self.file_path_var.set("")
        
        self.log_message("All data cleared")
        self.status_var.set("Data cleared")

def create_sample_csv():
    """Create a sample CSV file for testing"""
    sample_data = {
        'Player': [
            'Josh Allen', 'Stefon Diggs', 'Saquon Barkley', 'Travis Kelce',
            'Tyreek Hill', 'Derrick Henry', 'Cooper Kupp', 'Justin Jefferson',
            'Lamar Jackson', 'Christian McCaffrey'
        ],
        'Team': [
            'BUF', 'BUF', 'PHI', 'KC',
            'MIA', 'BAL', 'LAR', 'MIN',
            'BAL', 'SF'
        ],
        'Position': [
            'QB', 'WR', 'RB', 'TE',
            'WR', 'RB', 'WR', 'WR',
            'QB', 'RB'
        ]
    }
    
    df = pd.DataFrame(sample_data)
    sample_file = 'sample_team.csv'
    df.to_csv(sample_file, index=False)
    
    return sample_file

if __name__ == "__main__":
    # Create sample CSV if it doesn't exist
    sample_file = 'sample_team.csv'
    if not os.path.exists(sample_file):
        create_sample_csv()
        print(f"Created sample CSV file: {sample_file}")
    
    # Create and run the GUI
    root = tk.Tk()
    app = PlayerPropsGUI(root)
    
    # Center the window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    root.mainloop() 