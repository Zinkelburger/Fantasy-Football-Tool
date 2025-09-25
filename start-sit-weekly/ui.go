package main

import (
	"encoding/csv"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
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
	Name            string
	Position        string
	TeamName        string
	Status          string
	WeeklyOppScore  string // Most recent week opportunity score
	AvgOppScore     string // Average opportunity score
}

// ESPNUI holds the Fyne UI components
type ESPNUI struct {
	app    fyne.App
	window fyne.Window

	// Clients
	pythonClient   *PythonESPNClient
	ramalamaClient *RamalamaClient

	// UI Components
	statusLabel        *widget.Label
	connectButton      *widget.Button
	teamSelector       *widget.Select
	rosterTable        *widget.List
	rosterHeaderLabel  *widget.Label
	refreshButton      *widget.Button
	redditButton       *widget.Button
	ffhoundButton      *widget.Button
	summarizeButton    *widget.Button
	refreshDataButton  *widget.Button
	dataAnalysisMenu   *fyne.Menu
	dataAnalysisButton *widget.Button
	settingsPanel      *fyne.Container
	settingsVisible    bool

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

	// Data Analysis menu and button
	ui.setupDataAnalysisMenu()

	// Settings button
	settingsButton := widget.NewButton("⚙ Settings", ui.toggleSettings)

	// Control panel
	controlPanel := container.NewHBox(
		ui.connectButton,
		ui.refreshDataButton,
		ui.teamSelector,
		ui.refreshButton,
		ui.dataAnalysisButton,
		widget.NewSeparator(),
		settingsButton,
	)

	// Settings panel (initially hidden)
	ui.setupSettingsPanel()

	// Player notes setup
	ui.setupPlayerNotes()

	// Roster table
	ui.setupRosterTable()

	// Create roster panel with header
	rosterPanel := container.NewBorder(
		ui.rosterHeaderLabel, // top header
		nil,                  // bottom
		nil,                  // left
		nil,                  // right
		container.NewScroll(ui.rosterTable), // center
	)

	// Main layout
	content := container.NewBorder(
		container.NewVBox(controlPanel, ui.settingsPanel), // top
		ui.statusLabel, // bottom
		nil,            // left
		nil,            // right
		rosterPanel, // center
	)

	ui.window.SetContent(content)
}

// setupDataAnalysisMenu creates the data analysis menu and button
func (ui *ESPNUI) setupDataAnalysisMenu() {
	// Create menu items for data analysis actions
	redditMenuItem := fyne.NewMenuItem("🔍 Scrape Reddit", ui.handleRedditScrape)
	ffhoundMenuItem := fyne.NewMenuItem("📰 Scrape FF Hound", ui.handleFFHoundScrape)
	opportunityMenuItem := fyne.NewMenuItem("📈 Get Opportunity Score", ui.handleOpportunityScore)
	freeAgentsMenuItem := fyne.NewMenuItem("⭐ View Free Agents", ui.handleFreeAgents)
	summarizeMenuItem := fyne.NewMenuItem("🤖 Summarize Notes", ui.handleSummarizeNotes)

	// Initially disable menu items
	redditMenuItem.Disabled = true
	ffhoundMenuItem.Disabled = true
	opportunityMenuItem.Disabled = true
	freeAgentsMenuItem.Disabled = true
	summarizeMenuItem.Disabled = true

	// Create the popup menu
	ui.dataAnalysisMenu = fyne.NewMenu("Data Analysis",
		redditMenuItem,
		ffhoundMenuItem,
		opportunityMenuItem,
		freeAgentsMenuItem,
		fyne.NewMenuItemSeparator(),
		summarizeMenuItem,
	)

	// Create the button that shows the menu
	ui.dataAnalysisButton = widget.NewButton("📊 Data Analysis", func() {
		// Position the menu below the button
		pos := fyne.NewPos(
			ui.dataAnalysisButton.Position().X,
			ui.dataAnalysisButton.Position().Y+ui.dataAnalysisButton.Size().Height,
		)
		widget.ShowPopUpMenuAtPosition(ui.dataAnalysisMenu, ui.window.Canvas(), pos)
	})
	ui.dataAnalysisButton.Disable()
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

// setupRosterTable creates the roster table with header
func (ui *ESPNUI) setupRosterTable() {
	// Create header label
	ui.rosterHeaderLabel = widget.NewLabel(
		fmt.Sprintf("%-4s %-30s %-4s %-3s %-9s %-8s",
			"Pos", "Name", "Team", "St", "Week OPP", "Avg OPP"))
	ui.rosterHeaderLabel.TextStyle = fyne.TextStyle{Bold: true}

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

				// Convert status to emoji
				statusEmoji := ui.getStatusEmoji(player.Status)

				label.SetText(fmt.Sprintf("%-4s %-30s %-4s %-3s %-9s %-8s",
					player.Position, player.Name, player.TeamName, statusEmoji,
					player.WeeklyOppScore, player.AvgOppScore))
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
	ui.dataAnalysisButton.Enable()

	// Enable menu items
	ui.dataAnalysisMenu.Items[0].Disabled = !ui.pythonClient.HasRedditCredentials() // Reddit
	ui.dataAnalysisMenu.Items[1].Disabled = false                                    // FF Hound
	ui.dataAnalysisMenu.Items[2].Disabled = false                                    // Opportunity Score
	ui.dataAnalysisMenu.Items[3].Disabled = false                                    // Free Agents
	ui.dataAnalysisMenu.Items[5].Disabled = false                                    // Summarize (after separator)
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

		// Load opportunity score data
		ui.updateStatus(fmt.Sprintf("Loading opportunity scores for %s...", team.Name))
		opportunityData := ui.loadOpportunityScoreData()

		// Convert Python client format to local format and apply opportunity scores
		roster := make([]Player, 0, len(rosterInfo.Players))
		for _, p := range rosterInfo.Players {
			player := Player{
				Name:            strings.TrimSpace(p.Name),
				Position:        strings.TrimSpace(p.Position),
				TeamName:        strings.TrimSpace(p.Team),
				Status:          strings.TrimSpace(p.Status),
				WeeklyOppScore:  "N/A",
				AvgOppScore:     "N/A",
			}

			// Look up opportunity scores for this player
			if oppScores, found := opportunityData[p.Name]; found {
				if weekly, hasWeekly := oppScores["weekly"]; hasWeekly && weekly != "" {
					player.WeeklyOppScore = weekly
				}
				if avg, hasAvg := oppScores["avg"]; hasAvg && avg != "" {
					player.AvgOppScore = avg
				}
			}

			roster = append(roster, player)
		}

		ui.mutex.Lock()
		ui.currentRoster = roster
		ui.mutex.Unlock()

		ui.rosterTable.Refresh()
		ui.updateStatus(fmt.Sprintf("Loaded %d players for %s with opportunity scores", len(roster), team.Name))
	}()
}

// getStatusEmoji converts player status to emoji
func (ui *ESPNUI) getStatusEmoji(status string) string {
	statusUpper := strings.ToUpper(strings.TrimSpace(status))
	switch statusUpper {
	case "ACTIVE", "HEALTHY":
		return "✓"
	case "QUESTIONABLE", "Q":
		return "❓"
	case "DOUBTFUL", "OUT", "INJURED", "IR", "SUSPENDED", "D", "O":
		return "❌"
	default:
		return "  " // Two spaces for alignment
	}
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
	ramalamaAnalysisPath := fmt.Sprintf("ramalama_analysis/%s_ramalama_analysis.txt", safePlayerName)
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

	// Try to load Ramalama analysis
	if ramalamaData, err := os.ReadFile(ramalamaAnalysisPath); err == nil {
		content.WriteString("## Ramalama Analysis\n\n")
		content.WriteString(string(ramalamaData))
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

	// Create a proper split view like the 2025 go code - player list on left, notes on right
	// Get the main control panel first
	controlPanel := container.NewHBox(
		ui.connectButton,
		ui.refreshDataButton,
		ui.teamSelector,
		ui.refreshButton,
		ui.dataAnalysisButton,
		widget.NewSeparator(),
		widget.NewButton("⚙ Settings", ui.toggleSettings),
	)

	// Create roster panel with header for split view
	splitRosterPanel := container.NewBorder(
		ui.rosterHeaderLabel, // top header
		nil,                  // bottom
		nil,                  // left
		nil,                  // right
		container.NewScroll(ui.rosterTable), // center
	)

	// Create left panel with roster
	leftPanel := container.NewBorder(
		controlPanel, // top
		ui.statusLabel, // bottom
		nil, // left
		nil, // right
		splitRosterPanel, // center
	)

	// Create main horizontal split - left panel (roster) and right panel (notes)
	mainSplit := container.NewHSplit(leftPanel, ui.playerNoteContainer)
	mainSplit.SetOffset(0.5) // 50/50 split

	ui.window.SetContent(mainSplit)
}

// hidePlayerNotes hides the player notes viewer
func (ui *ESPNUI) hidePlayerNotes() {
	ui.mutex.Lock()
	ui.playerNoteVisible = false
	ui.currentViewedPlayer = ""
	ui.mutex.Unlock()

	// Create roster panel with header for restore
	restoreRosterPanel := container.NewBorder(
		ui.rosterHeaderLabel, // top header
		nil,                  // bottom
		nil,                  // left
		nil,                  // right
		container.NewScroll(ui.rosterTable), // center
	)

	// Restore original layout
	content := container.NewBorder(
		container.NewVBox(ui.getControlPanel(), ui.settingsPanel),
		ui.statusLabel,
		nil,
		nil,
		restoreRosterPanel,
	)
	ui.window.SetContent(content)
}

// getControlPanel returns the control panel for reuse
func (ui *ESPNUI) getControlPanel() *fyne.Container {
	settingsButton := widget.NewButton("⚙ Settings", ui.toggleSettings)
	return container.NewHBox(
		ui.connectButton,
		ui.refreshDataButton,
		ui.teamSelector,
		ui.refreshButton,
		ui.dataAnalysisButton,
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
		// Show error dialog with installation instructions
		errorMsg := `Ramalama AI tool is not installed.

Please install it manually using one of these methods:

Fedora/RHEL/CentOS:
  dnf install ramalama

Ubuntu/Debian:
  sudo apt install ramalama

From source:
  curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | bash

After installation, restart the application.`

		dialog.ShowInformation("Ramalama Not Installed", errorMsg, ui.window)
		return
	}

	// Check if model is available and pull if needed, then proceed to summarization
	model := ui.ramalamaClient.GetDefaultModel()
	if !ui.ramalamaClient.IsModelAvailable(model) {
		// Pull model automatically without prompting, then proceed to summarization
		ui.pullModelAndSummarize(model)
		return
	}

	// Start summarization process directly if model is available
	ui.startSummarizationProcess()
}


// pullModelAndSummarize pulls a model and then starts summarization
func (ui *ESPNUI) pullModelAndSummarize(model string) {
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
			return
		}

		ui.updateStatus("Model downloaded successfully! Starting summarization...")

		// Continue with summarization in the same goroutine
		ui.performSummarization()
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

		ui.performSummarization()
	}()
}

// performSummarization performs the actual summarization work without UI state management
func (ui *ESPNUI) performSummarization() {
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

		// Save raw analysis to ramalama_analysis/ directory
		err = ui.ramalamaClient.SaveRamalamaAnalysisToFile(playerName, summary)
		if err != nil {
			ui.updateStatus(fmt.Sprintf("Failed to save ramalama analysis for %s: %v", playerName, err))
			// Continue anyway, still try to save the summary
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
}

// handleOpportunityScore downloads opportunity score CSV files from Google Sheets
func (ui *ESPNUI) handleOpportunityScore() {
	ui.mutex.RLock()
	loading := ui.loading
	ui.mutex.RUnlock()

	if loading {
		return
	}

	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.updateStatus("Downloading opportunity score data...")

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
		}()

		// Create opportunity_score directory if it doesn't exist
		dir := "opportunity_score"
		if err := os.MkdirAll(dir, 0755); err != nil {
			ui.updateStatus(fmt.Sprintf("Failed to create directory: %v", err))
			dialog.ShowError(fmt.Errorf("Failed to create directory: %v", err), ui.window)
			return
		}

		// Define the CSV files to download with their GIDs and filenames
		csvFiles := []struct {
			gid      string
			filename string
			name     string
		}{
			{"414196352", "sheet1.csv", "Sheet 1"},
			{"1838248273", "sheet2.csv", "Sheet 2"},
			{"0", "sheet3.csv", "Sheet 3"},
		}

		baseURL := "https://docs.google.com/spreadsheets/d/1iYCnfRp4sStn2FaX-X9zNQW7rCD1VBwxceySD0kDhDY/export?format=csv"
		successCount := 0

		for _, csvFile := range csvFiles {
			ui.updateStatus(fmt.Sprintf("Downloading %s...", csvFile.name))

			// Construct URL with GID
			url := fmt.Sprintf("%s&gid=%s", baseURL, csvFile.gid)

			// Create HTTP client with redirect following
			client := &http.Client{}

			// Download the CSV file
			resp, err := client.Get(url)
			if err != nil {
				ui.updateStatus(fmt.Sprintf("Failed to download %s: %v", csvFile.name, err))
				continue
			}
			defer resp.Body.Close()

			if resp.StatusCode != http.StatusOK {
				ui.updateStatus(fmt.Sprintf("Failed to download %s: HTTP %d", csvFile.name, resp.StatusCode))
				continue
			}

			// Create the output file
			filePath := filepath.Join(dir, csvFile.filename)
			outFile, err := os.Create(filePath)
			if err != nil {
				ui.updateStatus(fmt.Sprintf("Failed to create file %s: %v", csvFile.filename, err))
				continue
			}
			defer outFile.Close()

			// Copy the content
			_, err = io.Copy(outFile, resp.Body)
			if err != nil {
				ui.updateStatus(fmt.Sprintf("Failed to write file %s: %v", csvFile.filename, err))
				continue
			}

			successCount++
			ui.updateStatus(fmt.Sprintf("Downloaded %s successfully", csvFile.name))
		}

		if successCount == len(csvFiles) {
			ui.updateStatus("All opportunity score files downloaded successfully!")
			dialog.ShowInformation("Download Complete",
				fmt.Sprintf("Successfully downloaded %d CSV files to opportunity_score/ directory", successCount),
				ui.window)
		} else {
			ui.updateStatus(fmt.Sprintf("Download completed with %d/%d files successful", successCount, len(csvFiles)))
			dialog.ShowInformation("Download Completed",
				fmt.Sprintf("Downloaded %d out of %d CSV files to opportunity_score/ directory", successCount, len(csvFiles)),
				ui.window)
		}
	}()
}

// loadOpportunityScoreData loads opportunity score data from CSV files and returns a map of player names to their scores
func (ui *ESPNUI) loadOpportunityScoreData() map[string]map[string]string {
	opportunityData := make(map[string]map[string]string)

	// Define CSV files to read
	csvFiles := []string{
		"opportunity_score/sheet1.csv",
		"opportunity_score/sheet2.csv",
		"opportunity_score/sheet3.csv",
	}

	for _, filename := range csvFiles {
		file, err := os.Open(filename)
		if err != nil {
			log.Printf("Could not open %s: %v", filename, err)
			continue
		}
		defer file.Close()

		reader := csv.NewReader(file)
		records, err := reader.ReadAll()
		if err != nil {
			log.Printf("Could not read CSV %s: %v", filename, err)
			continue
		}

		if len(records) < 2 { // Need header + at least one data row
			continue
		}

		header := records[0]
		// Find column indices
		var playerCol, weeklyOppCol, avgOppCol int = -1, -1, -1
		var foundWeekCol string

		for i, col := range header {
			colLower := strings.ToLower(col)
			if colLower == "player" {
				playerCol = i
			} else if colLower == "avg opp" {
				avgOppCol = i
			} else if strings.HasPrefix(colLower, "week") && len(colLower) > 4 {
				// Find the highest numbered week column (Week1, Week2, Week3, etc.)
				// Compare week numbers to get the most recent
				if weeklyOppCol == -1 || strings.Compare(col, foundWeekCol) > 0 {
					weeklyOppCol = i
					foundWeekCol = col
				}
			}
		}

		if playerCol == -1 || weeklyOppCol == -1 || avgOppCol == -1 {
			log.Printf("Could not find required columns in %s", filename)
			continue
		}

		// Process data rows
		for _, record := range records[1:] {
			minRequiredCols := max(playerCol, max(weeklyOppCol, avgOppCol))
			if len(record) > minRequiredCols {
				playerName := strings.TrimSpace(record[playerCol])
				// Clean player name - remove team info in parentheses
				if idx := strings.Index(playerName, " ("); idx != -1 {
					playerName = playerName[:idx]
				}

				if playerName != "" {
					if opportunityData[playerName] == nil {
						opportunityData[playerName] = make(map[string]string)
					}
					opportunityData[playerName]["weekly"] = strings.TrimSpace(record[weeklyOppCol])
					opportunityData[playerName]["avg"] = strings.TrimSpace(record[avgOppCol])
				}
			}
		}
	}

	return opportunityData
}

// max returns the maximum of two integers
func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// handleFreeAgents handles the free agents menu item click
func (ui *ESPNUI) handleFreeAgents() {
	ui.mutex.RLock()
	loading := ui.loading
	ui.mutex.RUnlock()

	if loading {
		return
	}

	ui.mutex.Lock()
	ui.loading = true
	ui.mutex.Unlock()

	ui.updateStatus("Loading free agents...")

	go func() {
		defer func() {
			ui.mutex.Lock()
			ui.loading = false
			ui.mutex.Unlock()
		}()

		var freeAgents *FreeAgentsResult
		var err error

		// Try cached data first if it's fresh
		if ui.pythonClient.IsCacheFresh() {
			ui.updateStatus("Loading free agents from cache...")
			freeAgents, err = ui.pythonClient.GetFreeAgentsFromCache("", 50)
		}

		// Fall back to API call if cache is stale or failed
		if freeAgents == nil || err != nil {
			ui.updateStatus("Fetching free agents from ESPN API...")
			freeAgents, err = ui.pythonClient.GetFreeAgents("", 50)
			if err != nil {
				ui.updateStatus(fmt.Sprintf("Failed to load free agents: %v", err))
				dialog.ShowError(fmt.Errorf("failed to load free agents: %w", err), ui.window)
				return
			}
		}

		// Show success with count
		ui.updateStatus(fmt.Sprintf("Loaded %d free agents successfully!", freeAgents.Count))

		// Create a simple info dialog showing top free agents
		var content strings.Builder
		content.WriteString(fmt.Sprintf("Top %d Free Agents:\n\n", min(len(freeAgents.Players), 20)))

		for i, player := range freeAgents.Players {
			if i >= 20 { // Show top 20 only in dialog
				break
			}

			content.WriteString(fmt.Sprintf("%s (%s, %s) - %.1f%% owned\n",
				player.Name,
				player.Position,
				player.Team,
				player.PercentOwned,
			))
		}

		dialog.ShowInformation("Free Agents", content.String(), ui.window)
	}()
}

// min returns the minimum of two integers
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// Show displays the UI window
func (ui *ESPNUI) Show() {
	ui.window.ShowAndRun()
}