# ESPN Fantasy Football Tool

A clean, fast fantasy football tool built in Go with Fyne UI for ESPN league management.

## Features

- **Clean UI**: No popup windows, inline settings panel
- **ESPN Integration**: Direct API connection to ESPN fantasy leagues
- **Team Persistence**: Remembers your selected team across sessions
- **Auto-Connect**: Automatically connects on startup if credentials are saved
- **Real-time Data**: Fetch and refresh team rosters

## Quick Start

1. **Install Go** (if not already installed)
2. **Run the application:**
   ```bash
   go run .
   ```
3. **First-time setup:**
   - Click "⚙ Settings" to expand the settings panel
   - Enter your ESPN League ID, SWID, and ESPN_S2 cookies
   - Click "Save Settings" - the app will auto-connect
4. **Select your team** from the dropdown and view your roster

## Getting ESPN Credentials

You'll need these values from your ESPN account:

- **League ID**: Found in your ESPN league URL
- **SWID**: Your ESPN SWID cookie
- **ESPN_S2**: Your ESPN_S2 cookie

*See the `poc/` folder for Python scripts that can help extract these credentials.*

## Project Structure

- `main.go` - Application entry point
- `ui.go` - Fyne GUI implementation
- `espn.go` - ESPN API client
- `resource.go` - Application resources
- `poc/` - Python proof-of-concept scripts for ESPN API exploration

## Dependencies

- Go 1.23+
- Fyne v2 (GUI framework)
- godotenv (environment variable management)

All dependencies are automatically managed by Go modules.