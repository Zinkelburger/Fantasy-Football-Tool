package main

import (
	"fmt"
	"log"
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

	// Clients
	pythonClient   *PythonESPNClient
	ramalamaClient *RamalamaClient

	// UI Components
	statusLabel     *widget.Label
	connectButton   *widget.Button
	teamSelector    *widget.Select
	rosterTable     *widget.List
	refreshButton   *widget.Button
	redditButton    *widget.Button
	ffhoundButton   *widget.Button
	summarizeButton *widget.Button
	refreshDataButton *widget.Button
	settingsPanel   *fyne.Container
	settingsVisible bool

	// Player notes components
	playerNoteViewer      *widget.RichText
	playerNoteContainer   *fyne.Container
	closePlayerNoteButton *widget.Button
	playerNoteVisible     bool
	currentViewedPlayer   string

	// Settings UI components
	leagueIDEntry *widget.Entry
	yearEntry     *widget.Entry
	swidEntry     *widget.Entry
	espns2Entry   *widget.Entry
	clientIDEntry *widget.Entry
	clientSecretEntry *widget.Entry
	userAgentEntry *widget.Entry
	llamaModelEntry *widget.Entry
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
	window.Resize(fyne.NewSize(1200, 800))

	ui := &ESPNUI{
		app:            app,
		window:         window,
		pythonClient:   pythonClient,
		ramalamaClient: NewRamalamaClient(),
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

	// Reddit scrape button (initially disabled)
	ui.redditButton = widget.NewButton("🔍 Scrape Reddit", ui.handleRedditScrape)
	ui.redditButton.Disable()

	// FF Hound scrape button (initially disabled)
	ui.ffhoundButton = widget.NewButton("📰 Scrape FF Hound", ui.handleFFHoundScrape)
	ui.ffhoundButton.Disable()

	// Summarize button (initially disabled)
	ui.summarizeButton = widget.NewButton("🤖 Summarize Notes", ui.handleSummarizeNotes)
	ui.summarizeButton.Disable()

	// Refresh data button (initially disabled)
	ui.refreshDataButton = widget.NewButton("🔄 Refresh Data", ui.handleRefreshData)
	ui.refreshDataButton.Disable()

	// Settings button
	settingsButton := widget.NewButton("⚙ Settings", ui.toggleSettings)

	// Control panel
	controlPanel := container.NewHBox(
		ui.connectButton,
		ui.refreshDataButton,
		ui.teamSelector,
		ui.refreshButton,
		ui.redditButton,
		ui.ffhoundButton,
		ui.summarizeButton,
		widget.NewSeparator(),
		settingsButton,
	)

	// Settings panel (initially hidden)
	ui.setupSettingsPanel()

	// Player notes setup
	ui.setupPlayerNotes()

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

	// Reddit settings entries
	ui.clientIDEntry = widget.NewEntry()
	ui.clientIDEntry.SetPlaceHolder("Reddit Client ID")

	ui.clientSecretEntry = widget.NewEntry()
	ui.clientSecretEntry.SetPlaceHolder("Reddit Client Secret")

	ui.userAgentEntry = widget.NewEntry()
	ui.userAgentEntry.SetPlaceHolder("Reddit User Agent")

	// Llama model setting
	ui.llamaModelEntry = widget.NewEntry()
	ui.llamaModelEntry.SetPlaceHolder("llama3.2:3b")
	ui.llamaModelEntry.SetText("llama3.2:3b")

	// Settings buttons
	ui.saveButton = widget.NewButton("Save Settings", ui.handleSaveSettings)
	ui.cancelButton = widget.NewButton("Close", ui.hideSettings)

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
			),
		),
		widget.NewCard("Reddit API Settings", "",
			container.NewVBox(
				widget.NewForm(
					widget.NewFormItem("Client ID", ui.clientIDEntry),
					widget.NewFormItem("Client Secret", ui.clientSecretEntry),
					widget.NewFormItem("User Agent", ui.userAgentEntry),
				),
			),
		),
		widget.NewCard("AI Model Settings", "",
			container.NewVBox(
				widget.NewForm(
					widget.NewFormItem("Llama Model", ui.llamaModelEntry),
				),
			),
		),
		container.NewHBox(ui.saveButton, ui.cancelButton),
	)

	ui.settingsPanel = settingsForm
	ui.settingsPanel.Hide()
}

// setupPlayerNotes creates the player notes viewer
func (ui *ESPNUI) setupPlayerNotes() {
	ui.playerNoteViewer = widget.NewRichText()
	ui.playerNoteViewer.Scroll = container.ScrollBoth
	ui.playerNoteViewer.Wrapping = fyne.TextWrapWord
	ui.closePlayerNoteButton = widget.NewButton("Close Notes", ui.hidePlayerNotes)
	ui.playerNoteContainer = container.NewBorder(
		nil, // top
		ui.closePlayerNoteButton, // bottom
		nil, // left
		nil, // right
		container.NewScroll(ui.playerNoteViewer),
	)
	ui.playerNoteVisible = false
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

	// Add selection handler for clicking players to show notes
	ui.rosterTable.OnSelected = func(id widget.ListItemID) {
		ui.mutex.RLock()
		if int(id) < len(ui.currentRoster) {
			playerName := ui.currentRoster[id].Name
			ui.mutex.RUnlock()
			ui.showPlayerNotes(playerName)
		} else {
			ui.mutex.RUnlock()
		}
	}
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
	ui.clientIDEntry.SetText(os.Getenv("CLIENT_ID"))
	ui.clientSecretEntry.SetText(os.Getenv("CLIENT_SECRET"))
	ui.userAgentEntry.SetText(os.Getenv("USER_AGENT"))

	// Load Llama model setting (use default if not set)
	llamaModel := os.Getenv("LLAMA_MODEL")
	if llamaModel == "" {
		llamaModel = "llama3.2:3b"
	}
	ui.llamaModelEntry.SetText(llamaModel)

	ui.settingsPanel.Show()
	ui.settingsVisible = true
}

// hideSettings hides the settings panel
func (ui *ESPNUI) hideSettings() {
	ui.settingsPanel.Hide()
	ui.settingsVisible = false
}

// handleSaveSettings saves the ESPN, Reddit, and AI settings
func (ui *ESPNUI) handleSaveSettings() {
	leagueID := strings.TrimSpace(ui.leagueIDEntry.Text)
	year := strings.TrimSpace(ui.yearEntry.Text)
	swid := strings.TrimSpace(ui.swidEntry.Text)
	espns2 := strings.TrimSpace(ui.espns2Entry.Text)
	clientID := strings.TrimSpace(ui.clientIDEntry.Text)
	clientSecret := strings.TrimSpace(ui.clientSecretEntry.Text)
	userAgent := strings.TrimSpace(ui.userAgentEntry.Text)
	llamaModel := strings.TrimSpace(ui.llamaModelEntry.Text)

	if leagueID == "" || swid == "" || espns2 == "" {
		dialog.ShowError(fmt.Errorf("please fill in all ESPN required fields"), ui.window)
		return
	}

	if year == "" {
		year = "2025"
	}

	if llamaModel == "" {
		llamaModel = "llama3.2:3b"
	}

	// Save credentials to .env file
	if err := ui.saveCredentials(leagueID, year, swid, espns2, clientID, clientSecret, userAgent, llamaModel); err != nil {
		dialog.ShowError(fmt.Errorf("failed to save settings: %w", err), ui.window)
		return
	}

	// Update form fields to show what was actually saved (including defaults like year)
	ui.leagueIDEntry.SetText(leagueID)
	ui.yearEntry.SetText(year)
	ui.swidEntry.SetText(swid)
	ui.espns2Entry.SetText(espns2)
	ui.clientIDEntry.SetText(clientID)
	ui.clientSecretEntry.SetText(clientSecret)
	ui.userAgentEntry.SetText(userAgent)
	ui.llamaModelEntry.SetText(llamaModel)

	// Update ramalama client with new model
	ui.ramalamaClient.SetDefaultModel(llamaModel)

	ui.updateStatus("Settings saved successfully")

	// Don't auto-hide settings - let user see their saved values

	// Auto-connect after saving
	go ui.connectToESPN()
}

// saveCredentials saves ESPN, Reddit, and AI credentials to .env file
func (ui *ESPNUI) saveCredentials(leagueID, year, swid, espns2, clientID, clientSecret, userAgent, llamaModel string) error {
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
		"CLIENT_ID":      clientID,
		"CLIENT_SECRET":  clientSecret,
		"USER_AGENT":     userAgent,
		"LLAMA_MODEL":    llamaModel,
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
	if err := os.WriteFile(envPath, []byte(newContent), 0644); err != nil {
		return err
	}

	// Also update the current process environment variables
	for key, value := range envMap {
		os.Setenv(key, value)
	}

	return nil
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

	var leagueInfo *LeagueInfo
	var err error

	// Try cached data first if it's fresh
	if ui.pythonClient.IsCacheFresh() {
		ui.updateStatus("Loading from cache...")
		leagueInfo, err = ui.pythonClient.ConnectToLeagueFromCache()
		if err == nil {
			ui.updateStatus("Loaded from cache successfully")
		}
	}

	// Fall back to API call if cache is stale or failed
	if leagueInfo == nil || err != nil {
		ui.updateStatus("Fetching fresh data from ESPN API...")
		leagueInfo, err = ui.pythonClient.ConnectToLeague()
		if err != nil {
			ui.updateStatus(fmt.Sprintf("Connection failed: %v", err))
			dialog.ShowError(fmt.Errorf("failed to connect to ESPN: %w", err), ui.window)
			return
		}

		// Cache the fresh data in the background
		go func() {
			if cacheErr := ui.pythonClient.CacheESPNData(); cacheErr != nil {
				log.Printf("Failed to cache ESPN data: %v", cacheErr)
			}
		}()
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
	if ui.pythonClient.HasRedditCredentials() {
		ui.redditButton.Enable()
	}
	ui.ffhoundButton.Enable()
	ui.summarizeButton.Enable()
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

		var rosterInfo *RosterInfo
		var err error

		// Try cached data first if it's fresh
		if ui.pythonClient.IsCacheFresh() {
			ui.updateStatus(fmt.Sprintf("Loading %s roster from cache...", team.Name))
			rosterInfo, err = ui.pythonClient.GetTeamRosterFromCache(team.ID)
		}

		// Fall back to API call if cache is stale or failed
		if rosterInfo == nil || err != nil {
			ui.updateStatus(fmt.Sprintf("Fetching %s roster from ESPN API...", team.Name))
			rosterInfo, err = ui.pythonClient.GetTeamRoster(team.ID)
			if err != nil {
				ui.updateStatus(fmt.Sprintf("Failed to load roster: %v", err))
				return
			}
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

// handleRefreshData forces a refresh of cached ESPN data
func (ui *ESPNUI) handleRefreshData() {
	ui.mutex.RLock()
	connecting := ui.connecting
	loading := ui.loading
	ui.mutex.RUnlock()

	if connecting || loading {
		return
	}

	ui.refreshDataButton.SetText("Refreshing...")
	ui.refreshDataButton.Disable()

	go func() {
		defer func() {
			ui.refreshDataButton.SetText("🔄 Refresh Data")
			ui.refreshDataButton.Enable()
		}()

		ui.updateStatus("Refreshing ESPN data...")

		// Force cache refresh by calling ESPN API and caching results
		err := ui.pythonClient.CacheESPNData()
		if err != nil {
			ui.updateStatus(fmt.Sprintf("Failed to refresh data: %v", err))
			dialog.ShowError(fmt.Errorf("failed to refresh ESPN data: %w", err), ui.window)
			return
		}

		ui.updateStatus("Data refreshed successfully!")

		// Reload the current team's roster if one is selected
		ui.mutex.RLock()
		hasCurrentTeam := ui.currentTeam != nil
		ui.mutex.RUnlock()

		if hasCurrentTeam {
			ui.loadTeamRoster()
		}
	}()
}

// handleRedditScrape handles Reddit scraping for the selected team
func (ui *ESPNUI) handleRedditScrape() {
	ui.mutex.RLock()
	loading := ui.loading
	currentTeam := ui.currentTeam
	ui.mutex.RUnlock()

	if loading || currentTeam == nil {
		return
	}

	// Check if Reddit credentials are available
	if !ui.pythonClient.HasRedditCredentials() {
		dialog.ShowError(fmt.Errorf("Reddit API credentials not found. Please configure them in Settings."), ui.window)
		return
	}

	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.redditButton.SetText("Scraping...")
	ui.redditButton.Disable()
	ui.updateStatus("Scraping Reddit for team players...")

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
			ui.redditButton.SetText("🔍 Scrape Reddit")
			if ui.pythonClient.HasRedditCredentials() {
				ui.redditButton.Enable()
			}
		}()

		result, err := ui.pythonClient.ScrapeRedditForTeam(currentTeam.ID)
		if err != nil {
			ui.updateStatus(fmt.Sprintf("Reddit scraping failed: %v", err))
			dialog.ShowError(fmt.Errorf("Reddit scraping failed: %v", err), ui.window)
			return
		}

		// Show success dialog with summary
		totalPosts := 0
		playersWithContent := 0
		for _, player := range result.Players {
			totalPosts += player.PostsFound
			if player.PostsFound > 0 {
				playersWithContent++
			}
		}

		message := fmt.Sprintf("Reddit scraping completed!\n\n"+
			"Players: %d\n"+
			"Players with content: %d\n"+
			"Total posts found: %d\n\n"+
			"Results saved to reddit_analysis/ directory",
			len(result.Players), playersWithContent, totalPosts)

		ui.updateStatus("Reddit scraping completed successfully")
		dialog.ShowInformation("Reddit Scraping Complete", message, ui.window)
	}()
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

// showPlayerNotes shows notes for a specific player
func (ui *ESPNUI) showPlayerNotes(playerName string) {
	// Check if we have data for this player
	safePlayerName := strings.ReplaceAll(strings.ToLower(playerName), " ", "_")
	safePlayerName = strings.ReplaceAll(safePlayerName, ".", "")

	redditAnalysisPath := fmt.Sprintf("reddit_analysis/%s_reddit_summary.txt", safePlayerName)
	ffhoundAnalysisPath := fmt.Sprintf("ffhound_analysis/%s_ffhound_summary.txt", safePlayerName)
	summaryPath := fmt.Sprintf("player_summaries/%s_summary.md", safePlayerName)

	var content strings.Builder
	content.WriteString(fmt.Sprintf("# %s\n\n", playerName))

	// Try to load Reddit analysis
	if redditData, err := os.ReadFile(redditAnalysisPath); err == nil {
		content.WriteString("## Reddit Analysis\n\n")
		content.WriteString(string(redditData))
		content.WriteString("\n\n")
	}

	// Try to load FF Hound analysis
	if ffhoundData, err := os.ReadFile(ffhoundAnalysisPath); err == nil {
		content.WriteString("## FF Hound Analysis\n\n")
		content.WriteString(string(ffhoundData))
		content.WriteString("\n\n")
	}

	// Try to load AI summary
	if summaryData, err := os.ReadFile(summaryPath); err == nil {
		content.WriteString("## AI Summary\n\n")
		content.WriteString(string(summaryData))
		content.WriteString("\n\n")
	}

	if content.Len() == len(fmt.Sprintf("# %s\n\n", playerName)) {
		content.WriteString("No notes available for this player.\n\n")
		content.WriteString("Try scraping Reddit and FF Hound first, then use the Summarize button to generate AI insights.")
	}

	ui.mutex.Lock()
	ui.currentViewedPlayer = playerName
	ui.playerNoteVisible = true
	ui.mutex.Unlock()

	ui.playerNoteViewer.ParseMarkdown(content.String())
	ui.window.SetContent(container.NewBorder(
		nil,
		nil,
		ui.rosterTable,
		ui.playerNoteContainer,
		nil,
	))
}

// hidePlayerNotes hides the player notes viewer
func (ui *ESPNUI) hidePlayerNotes() {
	ui.mutex.Lock()
	ui.playerNoteVisible = false
	ui.currentViewedPlayer = ""
	ui.mutex.Unlock()

	// Restore original layout
	content := container.NewBorder(
		container.NewVBox(ui.getControlPanel(), ui.settingsPanel),
		ui.statusLabel,
		nil,
		nil,
		container.NewScroll(ui.rosterTable),
	)
	ui.window.SetContent(content)
}

// getControlPanel returns the control panel for reuse
func (ui *ESPNUI) getControlPanel() *fyne.Container {
	settingsButton := widget.NewButton("⚙ Settings", ui.toggleSettings)
	return container.NewHBox(
		ui.connectButton,
		ui.teamSelector,
		ui.refreshButton,
		ui.redditButton,
		ui.ffhoundButton,
		ui.summarizeButton,
		widget.NewSeparator(),
		settingsButton,
	)
}

// handleFFHoundScrape handles FF Hound scraping for the selected team
func (ui *ESPNUI) handleFFHoundScrape() {
	ui.mutex.RLock()
	loading := ui.loading
	currentTeam := ui.currentTeam
	ui.mutex.RUnlock()

	if loading || currentTeam == nil {
		return
	}

	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.ffhoundButton.SetText("Scraping...")
	ui.ffhoundButton.Disable()
	ui.updateStatus("Scraping FF Hound for team players...")

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
			ui.ffhoundButton.SetText("📰 Scrape FF Hound")
			ui.ffhoundButton.Enable()
		}()

		result, err := ui.pythonClient.ScrapeFFHoundForTeam(currentTeam.ID)
		if err != nil {
			ui.updateStatus(fmt.Sprintf("FF Hound scraping failed: %v", err))
			dialog.ShowError(fmt.Errorf("FF Hound scraping failed: %v", err), ui.window)
			return
		}

		// Show success dialog with summary
		totalPosts := 0
		playersWithContent := 0
		for _, player := range result.Players {
			totalPosts += player.PostsFound
			if player.PostsFound > 0 {
				playersWithContent++
			}
		}

		message := fmt.Sprintf("FF Hound scraping completed!\n\n"+
			"Players: %d\n"+
			"Players with content: %d\n"+
			"Total posts found: %d\n\n"+
			"Results saved to ffhound_analysis/ directory",
			len(result.Players), playersWithContent, totalPosts)

		ui.updateStatus("FF Hound scraping completed successfully")
		dialog.ShowInformation("FF Hound Scraping Complete", message, ui.window)
	}()
}

// handleSummarizeNotes handles the summarize notes button click
func (ui *ESPNUI) handleSummarizeNotes() {
	ui.mutex.RLock()
	loading := ui.loading
	ui.mutex.RUnlock()

	if loading {
		return
	}

	// Check if ramalama is installed
	if !ui.ramalamaClient.CheckInstallation() {
		// Show installation dialog
		confirmDialog := dialog.NewConfirm(
			"Install Ramalama",
			"Ramalama AI tool is not installed. Would you like to install it now?\n\nThis will download and install ramalama automatically.",
			func(install bool) {
				if install {
					ui.installRamalamaWithProgress()
				}
			},
			ui.window,
		)
		confirmDialog.Show()
		return
	}

	// Check if model is available
	model := ui.ramalamaClient.GetDefaultModel()
	if !ui.ramalamaClient.IsModelAvailable(model) {
		confirmDialog := dialog.NewConfirm(
			"Download AI Model",
			fmt.Sprintf("The AI model '%s' is not available locally. Would you like to download it?\n\nThis may take several minutes depending on your internet connection.", model),
			func(download bool) {
				if download {
					ui.pullModelWithProgress(model)
				}
			},
			ui.window,
		)
		confirmDialog.Show()
		return
	}

	// Start summarization process
	ui.startSummarizationProcess()
}

// installRamalamaWithProgress installs ramalama with progress updates
func (ui *ESPNUI) installRamalamaWithProgress() {
	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.summarizeButton.SetText("Installing...")
	ui.summarizeButton.Disable()

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
			ui.summarizeButton.SetText("🤖 Summarize Notes")
			ui.summarizeButton.Enable()
		}()

		err := ui.ramalamaClient.InstallRamalama(func(progress string) {
			ui.updateStatus("Installing: " + progress)
		})

		if err != nil {
			ui.updateStatus("Installation failed: " + err.Error())
			dialog.ShowError(fmt.Errorf("Failed to install ramalama: %v", err), ui.window)
		} else {
			ui.updateStatus("Ramalama installed successfully!")
		}
	}()
}

// pullModelWithProgress pulls a model with progress updates
func (ui *ESPNUI) pullModelWithProgress(model string) {
	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.summarizeButton.SetText("Downloading...")
	ui.summarizeButton.Disable()

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
			ui.summarizeButton.SetText("🤖 Summarize Notes")
			ui.summarizeButton.Enable()
		}()

		err := ui.ramalamaClient.PullModel(model, func(progress string) {
			ui.updateStatus("Model download: " + progress)
		})

		if err != nil {
			ui.updateStatus("Model download failed: " + err.Error())
			dialog.ShowError(fmt.Errorf("Failed to download model: %v", err), ui.window)
		} else {
			ui.updateStatus("Model downloaded successfully!")
		}
	}()
}

// startSummarizationProcess starts the AI summarization process
func (ui *ESPNUI) startSummarizationProcess() {
	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.summarizeButton.SetText("Summarizing...")
	ui.summarizeButton.Disable()

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
			ui.summarizeButton.SetText("🤖 Summarize Notes")
			ui.summarizeButton.Enable()
		}()

		// Process all players with Reddit or FF Hound data
		redditDir := "reddit_analysis"
		ffhoundDir := "ffhound_analysis"

		redditExists := false
		ffhoundExists := false

		if _, err := os.Stat(redditDir); err == nil {
			redditExists = true
		}
		if _, err := os.Stat(ffhoundDir); err == nil {
			ffhoundExists = true
		}

		if !redditExists && !ffhoundExists {
			ui.updateStatus("No analysis data found. Please scrape Reddit or FF Hound first.")
			dialog.ShowError(fmt.Errorf("No analysis data found. Please run Reddit or FF Hound scraping first."), ui.window)
			return
		}

		// Collect all unique players from both Reddit and FF Hound data
		playerDataMap := make(map[string][]string) // player -> []data_sources

		// Process Reddit data
		if redditExists {
			files, err := os.ReadDir(redditDir)
			if err == nil {
				for _, file := range files {
					if strings.HasSuffix(file.Name(), "_reddit_summary.txt") {
						playerName := strings.TrimSuffix(file.Name(), "_reddit_summary.txt")
						playerDataMap[playerName] = append(playerDataMap[playerName], "reddit")
					}
				}
			}
		}

		// Process FF Hound data
		if ffhoundExists {
			files, err := os.ReadDir(ffhoundDir)
			if err == nil {
				for _, file := range files {
					if strings.HasSuffix(file.Name(), "_ffhound_summary.txt") {
						playerName := strings.TrimSuffix(file.Name(), "_ffhound_summary.txt")
						playerDataMap[playerName] = append(playerDataMap[playerName], "ffhound")
					}
				}
			}
		}

		summariesCreated := 0
		for playerKey, dataSources := range playerDataMap {
			playerName := strings.ReplaceAll(playerKey, "_", " ")
			playerName = strings.Title(playerName)

			ui.updateStatus(fmt.Sprintf("Summarizing %s...", playerName))

			// Combine all available data for this player
			var combinedData strings.Builder
			combinedData.WriteString(fmt.Sprintf("Fantasy Football Analysis for %s:\n\n", playerName))

			// Read Reddit data if available
			for _, source := range dataSources {
				if source == "reddit" {
					redditFile := fmt.Sprintf("%s/%s_reddit_summary.txt", redditDir, playerKey)
					if redditData, err := os.ReadFile(redditFile); err == nil {
						combinedData.WriteString("=== REDDIT ANALYSIS ===\n")
						combinedData.WriteString(string(redditData))
						combinedData.WriteString("\n\n")
					}
				}

				if source == "ffhound" {
					ffhoundFile := fmt.Sprintf("%s/%s_ffhound_summary.txt", ffhoundDir, playerKey)
					if ffhoundData, err := os.ReadFile(ffhoundFile); err == nil {
						combinedData.WriteString("=== FF HOUND EXPERT ANALYSIS ===\n")
						combinedData.WriteString(string(ffhoundData))
						combinedData.WriteString("\n\n")
					}
				}
			}

			if combinedData.Len() == 0 {
				continue
			}

			// Generate combined summary
			model := ui.ramalamaClient.GetDefaultModel()
			summary, err := ui.ramalamaClient.SummarizeText(combinedData.String(), model)
			if err != nil {
				ui.updateStatus(fmt.Sprintf("Failed to summarize %s: %v", playerName, err))
				continue
			}

			// Save summary
			err = ui.ramalamaClient.SaveSummaryToFile(playerName, summary, "player_summaries")
			if err != nil {
				ui.updateStatus(fmt.Sprintf("Failed to save summary for %s: %v", playerName, err))
				continue
			}

			summariesCreated++
		}

		ui.updateStatus(fmt.Sprintf("Summarization complete! Created %d summaries.", summariesCreated))
		dialog.ShowInformation("Summarization Complete",
			fmt.Sprintf("Successfully created AI summaries for %d players.\n\nClick on any player to view their notes and AI summary.", summariesCreated),
			ui.window)
	}()
}

// Show displays the UI window
func (ui *ESPNUI) Show() {
	ui.window.ShowAndRun()
}