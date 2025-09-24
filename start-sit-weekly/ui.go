package main

import (
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"
)

// Team represents a fantasy team
type Team struct {
	ID        int
	Name      string
	OwnerName string
}

// Player represents a fantasy player
type Player struct {
	Name     string
	Position string
	TeamName string
	Status   string
}

// ESPNUI holds the Fyne UI components
type ESPNUI struct {
	app    fyne.App
	window fyne.Window

	// Python ESPN client
	pythonClient *PythonESPNClient

	// UI Components
	statusLabel     *widget.Label
	connectButton   *widget.Button
	teamSelector    *widget.Select
	rosterTable     *widget.List
	refreshButton   *widget.Button
	settingsPanel   *fyne.Container
	settingsVisible bool

	// Settings UI components
	leagueIDEntry *widget.Entry
	yearEntry     *widget.Entry
	swidEntry     *widget.Entry
	espns2Entry   *widget.Entry
	saveButton    *widget.Button
	cancelButton  *widget.Button

	// Data
	currentTeam   *Team
	currentRoster []Player
	teams         []Team

	// State
	mutex      sync.RWMutex
	connecting bool
	loading    bool
}

// NewESPNUI creates a new ESPN UI
func NewESPNUI(app fyne.App, pythonClient *PythonESPNClient) *ESPNUI {
	window := app.NewWindow("ESPN Fantasy Football Tool")
	window.Resize(fyne.NewSize(1000, 700))

	ui := &ESPNUI{
		app:          app,
		window:       window,
		pythonClient: pythonClient,
	}

	ui.setupUI()
	ui.autoConnect()

	return ui
}

// setupUI creates and arranges all UI components
func (ui *ESPNUI) setupUI() {
	// Status label
	ui.statusLabel = widget.NewLabel("Ready to connect...")

	// Connect button
	ui.connectButton = widget.NewButton("Connect to ESPN", ui.handleConnect)

	// Team selector (initially disabled)
	ui.teamSelector = widget.NewSelect([]string{}, ui.handleTeamSelection)
	ui.teamSelector.PlaceHolder = "Select a team..."
	ui.teamSelector.Disable()

	// Refresh button (initially disabled)
	ui.refreshButton = widget.NewButton("Refresh Roster", ui.handleRefresh)
	ui.refreshButton.Disable()

	// Settings button
	settingsButton := widget.NewButton("⚙ Settings", ui.toggleSettings)

	// Control panel
	controlPanel := container.NewHBox(
		ui.connectButton,
		ui.teamSelector,
		ui.refreshButton,
		widget.NewSeparator(),
		settingsButton,
	)

	// Settings panel (initially hidden)
	ui.setupSettingsPanel()

	// Roster table
	ui.setupRosterTable()

	// Main layout
	content := container.NewBorder(
		container.NewVBox(controlPanel, ui.settingsPanel), // top
		ui.statusLabel, // bottom
		nil,            // left
		nil,            // right
		container.NewScroll(ui.rosterTable), // center
	)

	ui.window.SetContent(content)
}

// setupSettingsPanel creates the settings panel
func (ui *ESPNUI) setupSettingsPanel() {
	// Settings entries
	ui.leagueIDEntry = widget.NewEntry()
	ui.leagueIDEntry.SetPlaceHolder("ESPN League ID")

	ui.yearEntry = widget.NewEntry()
	ui.yearEntry.SetPlaceHolder("Year (e.g., 2025)")

	ui.swidEntry = widget.NewEntry()
	ui.swidEntry.SetPlaceHolder("SWID Cookie")

	ui.espns2Entry = widget.NewEntry()
	ui.espns2Entry.SetPlaceHolder("ESPN_S2 Cookie")

	// Settings buttons
	ui.saveButton = widget.NewButton("Save Settings", ui.handleSaveSettings)
	ui.cancelButton = widget.NewButton("Cancel", ui.hideSettings)

	// Settings form
	settingsForm := container.NewVBox(
		widget.NewCard("ESPN Connection Settings", "",
			container.NewVBox(
				widget.NewForm(
					widget.NewFormItem("League ID", ui.leagueIDEntry),
					widget.NewFormItem("Year", ui.yearEntry),
					widget.NewFormItem("SWID", ui.swidEntry),
					widget.NewFormItem("ESPN_S2", ui.espns2Entry),
				),
				container.NewHBox(ui.saveButton, ui.cancelButton),
			),
		),
	)

	ui.settingsPanel = settingsForm
	ui.settingsPanel.Hide()
}

// setupRosterTable creates the roster table
func (ui *ESPNUI) setupRosterTable() {
	ui.rosterTable = widget.NewList(
		func() int {
			ui.mutex.RLock()
			defer ui.mutex.RUnlock()
			return len(ui.currentRoster)
		},
		func() fyne.CanvasObject {
			return widget.NewLabel("Template")
		},
		func(id widget.ListItemID, obj fyne.CanvasObject) {
			ui.mutex.RLock()
			defer ui.mutex.RUnlock()

			if id < len(ui.currentRoster) {
				player := ui.currentRoster[id]
				label := obj.(*widget.Label)
				label.SetText(fmt.Sprintf("%-3s  %-20s  %-4s  %-10s",
					player.Position, player.Name, player.TeamName, player.Status))
			}
		},
	)
}

// toggleSettings shows/hides the settings panel
func (ui *ESPNUI) toggleSettings() {
	if ui.settingsVisible {
		ui.hideSettings()
	} else {
		ui.showSettings()
	}
}

// showSettings displays the settings panel
func (ui *ESPNUI) showSettings() {
	// Load current credentials from environment
	ui.leagueIDEntry.SetText(os.Getenv("ESPN_LEAGUE_ID"))
	ui.yearEntry.SetText(os.Getenv("ESPN_YEAR"))
	ui.swidEntry.SetText(os.Getenv("ESPN_SWID"))
	ui.espns2Entry.SetText(os.Getenv("ESPN_S2"))

	ui.settingsPanel.Show()
	ui.settingsVisible = true
}

// hideSettings hides the settings panel
func (ui *ESPNUI) hideSettings() {
	ui.settingsPanel.Hide()
	ui.settingsVisible = false
}

// handleSaveSettings saves the ESPN settings
func (ui *ESPNUI) handleSaveSettings() {
	leagueID := strings.TrimSpace(ui.leagueIDEntry.Text)
	year := strings.TrimSpace(ui.yearEntry.Text)
	swid := strings.TrimSpace(ui.swidEntry.Text)
	espns2 := strings.TrimSpace(ui.espns2Entry.Text)

	if leagueID == "" || swid == "" || espns2 == "" {
		dialog.ShowError(fmt.Errorf("please fill in all required fields"), ui.window)
		return
	}

	if year == "" {
		year = "2025"
	}

	// Save credentials to .env file
	if err := ui.saveCredentials(leagueID, year, swid, espns2); err != nil {
		dialog.ShowError(fmt.Errorf("failed to save settings: %w", err), ui.window)
		return
	}

	ui.hideSettings()
	ui.updateStatus("Settings saved successfully")

	// Auto-connect after saving
	go ui.connectToESPN()
}

// saveCredentials saves ESPN credentials to .env file
func (ui *ESPNUI) saveCredentials(leagueID, year, swid, espns2 string) error {
	envPath := ".env"

	// Read existing .env content
	content := ""
	if data, err := os.ReadFile(envPath); err == nil {
		content = string(data)
	}

	// Update credentials
	envMap := map[string]string{
		"ESPN_LEAGUE_ID": leagueID,
		"ESPN_YEAR":      year,
		"ESPN_SWID":      swid,
		"ESPN_S2":        espns2,
	}

	lines := strings.Split(content, "\n")

	// Update existing or add new lines
	for key, value := range envMap {
		found := false
		for i, line := range lines {
			if strings.HasPrefix(line, key+"=") {
				lines[i] = fmt.Sprintf("%s=%s", key, value)
				found = true
				break
			}
		}
		if !found {
			lines = append(lines, fmt.Sprintf("%s=%s", key, value))
		}
	}

	// Write back to file
	newContent := strings.Join(lines, "\n")
	return os.WriteFile(envPath, []byte(newContent), 0644)
}

// handleConnect handles the connect button click
func (ui *ESPNUI) handleConnect() {
	ui.mutex.Lock()
	if ui.connecting {
		ui.mutex.Unlock()
		return
	}
	ui.connecting = true
	ui.mutex.Unlock()

	if !ui.pythonClient.HasCredentials() {
		ui.showSettings()
		ui.mutex.Lock()
		ui.connecting = false
		ui.mutex.Unlock()
		return
	}

	go ui.connectToESPN()
}

// connectToESPN connects to ESPN in a goroutine
func (ui *ESPNUI) connectToESPN() {
	ui.updateStatus("Connecting to ESPN...")
	ui.connectButton.SetText("Connecting...")
	ui.connectButton.Disable()

	defer func() {
		ui.mutex.Lock()
		ui.connecting = false
		ui.mutex.Unlock()
		ui.connectButton.Enable()
		ui.connectButton.SetText("Reconnect")
	}()

	// Connect via Python ESPN client
	leagueInfo, err := ui.pythonClient.ConnectToLeague()
	if err != nil {
		ui.updateStatus(fmt.Sprintf("Connection failed: %v", err))
		dialog.ShowError(fmt.Errorf("failed to connect to ESPN: %w", err), ui.window)
		return
	}

	// Store league info
	ui.mutex.Lock()
	ui.teams = make([]Team, 0, len(leagueInfo.Teams))
	for _, team := range leagueInfo.Teams {
		ui.teams = append(ui.teams, Team{
			ID:        team.ID,
			Name:      team.Name,
			OwnerName: team.Owner,
		})
	}
	ui.mutex.Unlock()

	ui.updateStatus("Connected successfully!")
	ui.populateTeamSelector()

	// Try to auto-select saved team
	savedTeam := ui.getSelectedTeam()
	if savedTeam != "" {
		ui.autoSelectTeam(savedTeam)
	}
}

// populateTeamSelector fills the team dropdown
func (ui *ESPNUI) populateTeamSelector() {
	ui.mutex.RLock()
	teams := ui.teams
	ui.mutex.RUnlock()

	var teamNames []string
	for _, team := range teams {
		teamNames = append(teamNames, fmt.Sprintf("%s (%s)", team.Name, team.OwnerName))
	}

	ui.teamSelector.Options = teamNames
	ui.teamSelector.Enable()
	ui.refreshButton.Enable()
}

// autoSelectTeam automatically selects a team by name
func (ui *ESPNUI) autoSelectTeam(savedTeamName string) {
	for i, teamOption := range ui.teamSelector.Options {
		if strings.Contains(teamOption, savedTeamName) {
			ui.teamSelector.SetSelectedIndex(i)
			ui.handleTeamSelection(teamOption)
			break
		}
	}
}

// handleTeamSelection handles team selection
func (ui *ESPNUI) handleTeamSelection(selected string) {
	if selected == "" {
		return
	}

	// Extract team name (before the parentheses)
	teamName := strings.Split(selected, " (")[0]

	// Find the team
	ui.mutex.RLock()
	var selectedTeam *Team
	for i := range ui.teams {
		if ui.teams[i].Name == teamName {
			selectedTeam = &ui.teams[i]
			break
		}
	}
	ui.mutex.RUnlock()

	if selectedTeam == nil {
		ui.updateStatus("Team not found")
		return
	}

	ui.mutex.Lock()
	ui.currentTeam = selectedTeam
	ui.mutex.Unlock()

	// Save selected team (implement simple file save)
	ui.saveSelectedTeam(teamName)

	// Load roster
	ui.loadTeamRoster()
}

// loadTeamRoster loads the roster for the selected team
func (ui *ESPNUI) loadTeamRoster() {
	ui.mutex.RLock()
	team := ui.currentTeam
	ui.mutex.RUnlock()

	if team == nil {
		return
	}

	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.updateStatus(fmt.Sprintf("Loading roster for %s...", team.Name))

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
		}()

		rosterInfo, err := ui.pythonClient.GetTeamRoster(team.ID)
		if err != nil {
			ui.updateStatus(fmt.Sprintf("Failed to load roster: %v", err))
			return
		}

		// Convert Python client format to local format
		roster := make([]Player, 0, len(rosterInfo.Players))
		for _, p := range rosterInfo.Players {
			roster = append(roster, Player{
				Name:     p.Name,
				Position: p.Position,
				TeamName: p.Team,
				Status:   p.Status,
			})
		}

		ui.mutex.Lock()
		ui.currentRoster = roster
		ui.mutex.Unlock()

		ui.rosterTable.Refresh()
		ui.updateStatus(fmt.Sprintf("Loaded %d players for %s", len(roster), team.Name))
	}()
}

// handleRefresh refreshes the current team's roster
func (ui *ESPNUI) handleRefresh() {
	ui.mutex.RLock()
	loading := ui.loading
	ui.mutex.RUnlock()

	if loading {
		return
	}

	ui.loadTeamRoster()
}

// autoConnect tries to auto-connect on startup
func (ui *ESPNUI) autoConnect() {
	go func() {
		// Small delay to let UI render
		time.Sleep(100 * time.Millisecond)

		if ui.pythonClient.HasCredentials() {
			ui.connectToESPN()
		} else {
			ui.updateStatus(ui.pythonClient.GetStatus())
		}
	}()
}

// saveSelectedTeam saves the selected team name to .env file
func (ui *ESPNUI) saveSelectedTeam(teamName string) {
	// Simple implementation - could be enhanced
	envPath := ".env"

	// Read existing .env content
	content := ""
	if data, err := os.ReadFile(envPath); err == nil {
		content = string(data)
	}

	// Update or add SELECTED_TEAM
	lines := strings.Split(content, "\n")
	found := false
	for i, line := range lines {
		if strings.HasPrefix(line, "SELECTED_TEAM=") {
			lines[i] = fmt.Sprintf("SELECTED_TEAM=%s", teamName)
			found = true
			break
		}
	}

	if !found {
		lines = append(lines, fmt.Sprintf("SELECTED_TEAM=%s", teamName))
	}

	// Write back to file
	newContent := strings.Join(lines, "\n")
	os.WriteFile(envPath, []byte(newContent), 0644)
}

// getSelectedTeam loads the selected team name from .env file
func (ui *ESPNUI) getSelectedTeam() string {
	return os.Getenv("SELECTED_TEAM")
}

// updateStatus safely updates the status label
func (ui *ESPNUI) updateStatus(message string) {
	ui.statusLabel.SetText(message)
}

// Show displays the UI window
func (ui *ESPNUI) Show() {
	ui.window.ShowAndRun()
}