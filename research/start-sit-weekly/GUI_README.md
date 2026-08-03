# Start/Sit Weekly GUI

A modern Custom Tkinter interface for analyzing ESPN Fantasy Football rosters.

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the GUI application:
```bash
python start_sit_gui.py
```

2. Click "Connect to ESPN League" - this will use the Chrome extension authentication system from the existing ESPN roster analyzer

3. Once connected, select your team from the dropdown menu

4. View your roster in the table format with columns:
   - **Name**: Player name
   - **Position**: Player position (QB, RB, WR, TE, etc.)
   - **Team**: NFL team abbreviation
   - **Status**: Player status (Active, Injured, etc.)

## Features

- **Dark Theme**: Modern dark UI using Custom Tkinter
- **Live Data**: Connects to ESPN Fantasy API for real-time roster data
- **Team Selection**: Dropdown to choose any team in your league
- **Refresh**: Update roster data with current information
- **Responsive**: Scrollable table that adapts to window size

## Prerequisites

- Chrome browser with the Fantasy Football Tool extension
- Active ESPN Fantasy Football league
- Must be logged into ESPN in your browser

## Troubleshooting

- If connection fails, ensure you're logged into ESPN Fantasy in Chrome
- Make sure the Chrome extension is active on an ESPN Fantasy page
- Check that port 8001 is not being used by another application 