#!/usr/bin/env python3
"""
Start/Sit Weekly GUI - Custom Tkinter Interface

This GUI application displays ESPN fantasy football roster information
using a modern Custom Tkinter interface with player data in a table format.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
from typing import Optional, List, Dict, Any
from espn_roster_analyzer import ESPNRosterAnalyzer

# Configure CustomTkinter appearance
ctk.set_appearance_mode("dark")  # "light", "dark", or "system"
ctk.set_default_color_theme("blue")  # "blue", "green", or "dark-blue"

class StartSitGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Start/Sit Weekly Tool")
        self.root.geometry("1000x700")
        
        # Initialize ESPN analyzer
        self.analyzer = ESPNRosterAnalyzer()
        self.current_team = None
        self.player_data = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the main UI components."""
        # Title frame
        self.title_frame = ctk.CTkFrame(self.root)
        self.title_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        self.title_label = ctk.CTkLabel(
            self.title_frame, 
            text="Start/Sit Weekly Tool", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=20)
        
        # Control frame
        self.control_frame = ctk.CTkFrame(self.root)
        self.control_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        # Connect button
        self.connect_btn = ctk.CTkButton(
            self.control_frame,
            text="Connect to ESPN League",
            command=self.connect_to_league,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.connect_btn.pack(side="left", padx=10, pady=10)
        
        # Team selection
        self.team_var = tk.StringVar()
        self.team_dropdown = ctk.CTkComboBox(
            self.control_frame,
            variable=self.team_var,
            values=["Select a team..."],
            command=self.on_team_selected,
            width=200
        )
        self.team_dropdown.pack(side="left", padx=10, pady=10)
        
        # Refresh button
        self.refresh_btn = ctk.CTkButton(
            self.control_frame,
            text="Refresh Roster",
            command=self.refresh_roster,
            state="disabled"
        )
        self.refresh_btn.pack(side="right", padx=10, pady=10)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.control_frame,
            text="Ready to connect...",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="right", padx=10, pady=10)
        
        # Main content frame
        self.content_frame = ctk.CTkFrame(self.root)
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Player table frame
        self.table_frame = ctk.CTkFrame(self.content_frame)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Create table
        self.setup_player_table()
        
        # Initially show welcome message
        self.show_welcome_message()
        
    def setup_player_table(self):
        """Setup the player data table using Treeview."""
        # Create a frame for the table and scrollbar
        table_container = tk.Frame(self.table_frame, bg='#212121')
        table_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Configure style for the treeview
        style = ttk.Style()
        style.theme_use("clam")
        
        # Configure colors to match dark theme
        style.configure("Treeview",
                       background="#2b2b2b",
                       foreground="white",
                       rowheight=25,
                       fieldbackground="#2b2b2b",
                       borderwidth=0,
                       relief="flat")
        
        style.configure("Treeview.Heading",
                       background="#1f538d",
                       foreground="white",
                       relief="flat",
                       borderwidth=1)
        
        style.map("Treeview",
                 background=[('selected', '#1f538d')])
        
        style.map("Treeview.Heading",
                 background=[('active', '#144870')])
        
        # Create treeview with columns
        columns = ("Name", "Position", "Team", "Status")
        self.tree = ttk.Treeview(table_container, columns=columns, show='headings', height=15)
        
        # Configure column headings and widths
        self.tree.heading("Name", text="Player Name")
        self.tree.heading("Position", text="Position")
        self.tree.heading("Team", text="NFL Team")
        self.tree.heading("Status", text="Status")
        
        self.tree.column("Name", width=200, minwidth=150)
        self.tree.column("Position", width=80, minwidth=60)
        self.tree.column("Team", width=80, minwidth=60)
        self.tree.column("Status", width=100, minwidth=80)
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack table and scrollbar
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def show_welcome_message(self):
        """Show welcome message in the table area."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add welcome message
        self.tree.insert("", "end", values=("Welcome! Connect to your ESPN league to get started.", "", "", ""))
        
    def connect_to_league(self):
        """Connect to ESPN league in a separate thread."""
        def connect_thread():
            try:
                self.update_status("Connecting to ESPN league...")
                self.connect_btn.configure(state="disabled")
                
                # Initialize league connection
                success = self.analyzer.initialize_league()
                
                if success:
                    self.update_status("Connected successfully!")
                    self.populate_team_dropdown()
                    self.connect_btn.configure(text="Reconnect", state="normal")
                else:
                    self.update_status("Connection failed!")
                    self.connect_btn.configure(state="normal")
                    messagebox.showerror("Connection Error", 
                                       "Failed to connect to ESPN league. Check your credentials and try again.")
                    
            except Exception as e:
                self.update_status(f"Error: {str(e)}")
                self.connect_btn.configure(state="normal")
                messagebox.showerror("Error", f"An error occurred: {str(e)}")
        
        # Run connection in separate thread to prevent UI blocking
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
        
    def populate_team_dropdown(self):
        """Populate the team dropdown with available teams."""
        if not self.analyzer.league:
            return
            
        try:
            team_names = [f"{team.team_name} ({team.owners})" for team in self.analyzer.league.teams]
            self.team_dropdown.configure(values=team_names)
            self.team_dropdown.set("Select a team...")
        except Exception as e:
            print(f"Error populating teams: {e}")
            
    def on_team_selected(self, selection):
        """Handle team selection from dropdown."""
        if not selection or "Select a team" in selection:
            return
            
        try:
            # Find the selected team
            team_name = selection.split(" (")[0]  # Extract team name before owner info
            
            for team in self.analyzer.league.teams:
                if team.team_name == team_name:
                    self.current_team = team
                    self.load_roster_data()
                    self.refresh_btn.configure(state="normal")
                    break
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load team: {str(e)}")
            
    def load_roster_data(self):
        """Load and display roster data for the selected team."""
        if not self.current_team:
            return
            
        try:
            self.update_status(f"Loading roster for {self.current_team.team_name}...")
            
            # Clear existing data
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            # Load player data
            self.player_data = []
            
            for player in self.current_team.roster:
                player_info = {
                    "name": player.name,
                    "position": player.position,
                    "team": getattr(player, 'proTeam', 'N/A'),
                    "status": self.get_player_status(player)
                }
                self.player_data.append(player_info)
                
                # Add to tree
                self.tree.insert("", "end", values=(
                    player_info["name"],
                    player_info["position"],
                    player_info["team"],
                    player_info["status"]
                ))
                
            self.update_status(f"Loaded {len(self.player_data)} players for {self.current_team.team_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load roster: {str(e)}")
            self.update_status("Error loading roster")
            
    def get_player_status(self, player) -> str:
        """Get player status (injury, active, etc.)."""
        try:
            # Try to get injury status if available
            if hasattr(player, 'injuryStatus') and player.injuryStatus:
                return player.injuryStatus
            elif hasattr(player, 'injured') and player.injured:
                return "Injured"
            else:
                return "Active"
        except:
            return "Unknown"
            
    def refresh_roster(self):
        """Refresh the current roster data."""
        if self.current_team:
            self.load_roster_data()
        else:
            messagebox.showwarning("Warning", "No team selected to refresh.")
            
    def update_status(self, message: str):
        """Update the status label with a message."""
        self.status_label.configure(text=message)
        self.root.update()
        
    def run(self):
        """Start the GUI application."""
        try:
            self.root.mainloop()
        finally:
            # Clean up
            if hasattr(self.analyzer, 'stop_auth_server'):
                self.analyzer.stop_auth_server()

def main():
    """Main entry point for the GUI application."""
    try:
        app = StartSitGUI()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Application Error", f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main() 