package main

import (
	"fmt"
	"log"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/driver/desktop"
	"fyne.io/fyne/v2/widget"
)

// PlayerRowLabel extends widget.Label to support right-click for draft status toggle
type PlayerRowLabel struct {
	widget.Label
	ui          *FantasyUI
	playerIndex int
}

// NewPlayerRowLabel creates a new player row label with right-click support
func NewPlayerRowLabel(ui *FantasyUI) *PlayerRowLabel {
	label := &PlayerRowLabel{
		Label:       *widget.NewLabel("template"),
		ui:          ui,
		playerIndex: -1,
	}
	label.ExtendBaseWidget(label)
	return label
}

// MouseDown implements desktop.Mouseable interface for right-click detection
func (p *PlayerRowLabel) MouseDown(event *desktop.MouseEvent) {
	if p.playerIndex >= 0 && event.Button == desktop.MouseButtonSecondary {
		// Right-click detected - toggle draft status
		p.ui.mutex.Lock()
		p.ui.selectedPlayerIndex = p.playerIndex
		p.ui.lastSelectedPlayerIndex = p.playerIndex
		p.ui.mutex.Unlock()
		p.ui.handleDraftStatusToggle()
	}
}

// MouseUp implements desktop.Mouseable interface (required)
func (p *PlayerRowLabel) MouseUp(event *desktop.MouseEvent) {
	// Not needed for our use case
}

// MouseMoved implements desktop.Mouseable interface (required)
func (p *PlayerRowLabel) MouseMoved(event *desktop.MouseEvent) {
	// Not needed for our use case
}

// Tapped implements fyne.Tappable interface for primary click handling
func (p *PlayerRowLabel) Tapped(event *fyne.PointEvent) {
	if p.playerIndex >= 0 && p.ui.playerList.OnSelected != nil {
		p.ui.playerList.OnSelected(widget.ListItemID(p.playerIndex))
	}
}

// FantasyUI holds the Fyne UI components and application state
type FantasyUI struct {
	app        fyne.App
	window     fyne.Window
	
	// Data
	players     []Player
	dataLoader  *DataLoader
	llmManager  *LLMManager
	settings    *Settings
	
	// UI Components
	playerList     *widget.List
	outputText     *widget.RichText
	teamList       *widget.List
	statusLabel    *widget.Label
	queryButton        *widget.Button
	refreshButton      *widget.Button
	settingsButton     *widget.Button
	draftStatusButton  *widget.Button
	settingsUI     *SettingsUI
	
	// Note Viewer Components
	noteViewer      *widget.RichText
	noteViewerContainer *fyne.Container
	closeNoteButton *widget.Button
	noteViewerVisible bool
	currentViewedPlayer string
	selectedPlayerIndex int
	lastSelectedPlayerIndex int  // Keep track for 'd' key even when unselected
	
	// Collapsible controls
	llmCollapseBtn  *widget.Button
	teamCollapseBtn *widget.Button
	llmCollapsed    bool
	teamCollapsed   bool
	
	// Container references for collapsing
	rightVSplit     *container.Split
	llmPanel        *fyne.Container
	teamPanel       *fyne.Container
	mainContainer   *container.Split
	
	// State
	querying    bool
	refreshing  bool
	lastQuery   time.Time
	lastRefresh time.Time
	notice      string
	pickedPlayers []string  // Current list of picked players
	currentPick   int       // Current pick number
	teamPlayers   []Player  // Current team players
	
	// Concurrency
	mutex       sync.RWMutex
	stopChan    chan bool
	uiUpdateChan chan func()  // Channel for safe UI updates
	playerUpdateChan <-chan PlayerUpdate  // Channel for receiving player updates from HTTP server
	lastPlayerUpdate time.Time  // Throttling for player updates
}

// NewFantasyUI creates and initializes the Fyne UI
func NewFantasyUI(app fyne.App, players []Player, loader *DataLoader, llmManager *LLMManager, settings *Settings, playerUpdateChan <-chan PlayerUpdate) *FantasyUI {
	window := app.NewWindow("Fantasy Football Tool")
	window.Resize(fyne.NewSize(1200, 800))
	
	ui := &FantasyUI{
		app:         app,
		window:      window,
		players:     players,
		dataLoader:  loader,
		llmManager:  llmManager,
		settings:    settings,
		lastQuery:   time.Now().Add(-5 * time.Second),
		lastRefresh: time.Now(),
		stopChan:    make(chan bool, 1),  // Buffered to prevent blocking
		uiUpdateChan: make(chan func(), 100),  // Buffered channel for UI updates (increased from 10)
		playerUpdateChan: playerUpdateChan,
		pickedPlayers: make([]string, 0),
		currentPick:   0,
		teamPlayers:   make([]Player, 0),
		selectedPlayerIndex: -1,
		lastSelectedPlayerIndex: -1,
	}
	
	// Initialize settings UI
	ui.settingsUI = NewSettingsUI(window, settings, llmManager, ui.handleSettingsUpdate)
	
	ui.setupUI()
	ui.startUIUpdateHandler()
	ui.startPlayerUpdateListener()
	
	// Load draft status for all players on startup
	ui.loadDraftStatusForAllPlayers()
	
	// Load initial team data
	ui.loadTeamData()
	
	// Show LLM warning message by default if not configured
	if !ui.llmManager.IsConfigured() {
		ui.showLLMNotConfiguredMessage()
	}
	
	return ui
}

// startUIUpdateHandler processes UI updates safely on main thread
func (ui *FantasyUI) startUIUpdateHandler() {
	go func() {
		for {
			select {
			case updateFunc := <-ui.uiUpdateChan:
				updateFunc()  // Execute UI update on main thread
			case <-ui.stopChan:
				return
			}
		}
	}()
}

// safeUIUpdate queues a UI update to be executed on the main thread
func (ui *FantasyUI) safeUIUpdate(updateFunc func()) {
	select {
	case ui.uiUpdateChan <- updateFunc:
		// Update queued successfully
	default:
		// Channel full, skip this update
		log.Printf("Warning: UI update channel full, skipping update")
	}
}

// setupUI creates and arranges all the UI components
func (ui *FantasyUI) setupUI() {
	// Create player list
	ui.playerList = widget.NewList(
		func() int { 
			ui.mutex.RLock()
			defer ui.mutex.RUnlock()
			return len(ui.players) 
		},
		func() fyne.CanvasObject {
			return NewPlayerRowLabel(ui)
		},
					func(id widget.ListItemID, item fyne.CanvasObject) {
			ui.mutex.RLock()
			defer ui.mutex.RUnlock()
			
			if id < len(ui.players) {
				p := ui.players[id]
				playerLabel := item.(*PlayerRowLabel)
				// Update the player index for right-click handling
				playerLabel.playerIndex = int(id)
				
				// Handle emoji status
				var statusPart string
				if p.DraftStatus == "✅" {
					statusPart = "✅ "
				} else if p.DraftStatus == "❌" {
					statusPart = "❌ "
				} else {
					statusPart = "   "
				}
				playerLabel.SetText(fmt.Sprintf("%-5s %-4s %-25s %-3s%-6s %-4s %s", 
					p.Rank, p.ESPNRank, p.Name, statusPart, p.Depth, p.Team, p.Note))
			}
		},
	)
	
	// Add selection handler for clicking players to toggle note view
	ui.playerList.OnSelected = func(id widget.ListItemID) {
		ui.mutex.Lock()
		ui.selectedPlayerIndex = int(id)
		ui.lastSelectedPlayerIndex = int(id)  // Track for 'd' key
		if id < len(ui.players) {
			playerName := ui.players[id].Name
			// Always toggle - if we're viewing this player's notes, close them, otherwise open them
			isCurrentlyViewing := ui.noteViewerVisible && ui.currentViewedPlayer == playerName
			ui.mutex.Unlock()
			
			if isCurrentlyViewing {
				// Close the notes
				ui.hidePlayerNote()
			} else {
				// Open the notes
				ui.showPlayerNote(playerName)
			}
			
			// Always unselect after handling the click to allow repeated clicks
			ui.safeUIUpdate(func() {
				ui.playerList.UnselectAll()
			})
		} else {
			ui.mutex.Unlock()
		}
	}
	
	// Create output text area
	ui.outputText = widget.NewRichText()
	ui.outputText.Scroll = container.ScrollBoth
	ui.outputText.Wrapping = fyne.TextWrapWord
	
	// Create note viewer components
	ui.noteViewer = widget.NewRichText()
	ui.noteViewer.Scroll = container.ScrollBoth
	ui.noteViewer.Wrapping = fyne.TextWrapWord
	ui.closeNoteButton = widget.NewButton("Close Note View", ui.hidePlayerNote)
	ui.noteViewerContainer = container.NewBorder(
		nil, // top - will be set dynamically
		nil,
		nil,
		nil,
		container.NewScroll(ui.noteViewer),
	)
	ui.noteViewerVisible = false
	
	// Create team list
	ui.teamList = widget.NewList(
		func() int {
			ui.mutex.RLock()
			defer ui.mutex.RUnlock()
			displayData := ui.getTeamPlayerDisplayData()
			return len(displayData)
		},
		func() fyne.CanvasObject {
			return widget.NewLabel("template")
		},
		func(id widget.ListItemID, item fyne.CanvasObject) {
			ui.mutex.RLock()
			defer ui.mutex.RUnlock()
			
			displayData := ui.getTeamPlayerDisplayData()
			if id < len(displayData) {
				label := item.(*widget.Label)
				text := displayData[id]
				label.SetText(text)
			}
		},
	)
	
	// Create status label
	ui.statusLabel = widget.NewLabel("Ready - Listening for draft updates")
	
	// Create buttons
	ui.queryButton = widget.NewButton("Query LLM (q)", ui.handleLLMQuery)
	ui.refreshButton = widget.NewButton("Manual Refresh (r)", ui.handleManualRefresh)
	ui.draftStatusButton = widget.NewButton("Toggle Draft Status (d)", ui.handleDraftStatusToggle)
	ui.settingsButton = ui.settingsUI.CreateSettingsButton()
	
	// Create collapse buttons
	ui.llmCollapseBtn = widget.NewButton("  −  ", ui.toggleLLMCollapse)
	ui.teamCollapseBtn = widget.NewButton("  −  ", ui.toggleTeamCollapse)
	
	// Create button container
	buttonContainer := container.NewHBox(
		ui.queryButton,
		ui.refreshButton,
		widget.NewSeparator(),
		ui.settingsButton,
	)
	
	// Create header for player list
	headerLabel := widget.NewLabel(fmt.Sprintf("%-5s %-4s %-25s %-3s%-6s %-4s %s", 
		"Rank", "ESPN", "Name", "St", "Depth", "Team", "Note"))
	headerLabel.TextStyle = fyne.TextStyle{Bold: true}
	
	// Create left panel (player list)
	leftPanel := container.NewBorder(
		headerLabel, // top
		nil,         // bottom
		nil,         // left
		nil,         // right
		ui.playerList, // center
	)
	
	// Create LLM output panel with collapse button
	llmHeader := container.NewBorder(
		nil, nil, 
		widget.NewLabel("LLM Output:"), 
		ui.llmCollapseBtn,
		nil,
	)
	ui.llmPanel = container.NewBorder(
		llmHeader, // top
		nil,       // bottom
		nil,       // left
		nil,       // right
		container.NewScroll(ui.outputText), // center
	)
	
	// Create team header with position columns
	teamHeaderLabel := widget.NewLabel(fmt.Sprintf("%-4s  %-22s  %-4s", "Pos", "Name", "Team"))
	teamHeaderLabel.TextStyle = fyne.TextStyle{Bold: true}
	teamHeader := container.NewBorder(
		nil, nil,
		widget.NewLabel("Your Team:"),
		ui.teamCollapseBtn,
		nil,
	)
	
	// Create team panel with header and list
	ui.teamPanel = container.NewBorder(
		container.NewVBox(teamHeader, teamHeaderLabel), // top
		nil,                                           // bottom
		nil,                                           // left
		nil,                                           // right
		container.NewScroll(ui.teamList),              // center
	)
	
	// Create right panel as vertical split between LLM output and team
	ui.rightVSplit = container.NewVSplit(ui.llmPanel, ui.teamPanel)
	ui.rightVSplit.SetOffset(0.6) // 60% LLM output, 40% team
	
	// Create overall panel with buttons and status
	rightPanelWithControls := container.NewBorder(
		buttonContainer, // top
		ui.statusLabel,  // bottom
		nil,            // left
		nil,            // right
		ui.rightVSplit, // center
	)
	
	// Create main split container
	ui.mainContainer = container.NewHSplit(leftPanel, rightPanelWithControls)
	ui.mainContainer.SetOffset(0.5) // 50/50 split
	
	ui.window.SetContent(ui.mainContainer)
	
	// Set up keyboard shortcuts - use window-level handling to avoid focus issues
	ui.window.Canvas().SetOnTypedKey(ui.handleKeyPress)
	ui.window.Canvas().SetOnTypedRune(ui.handleTypedRune)
	
	// Add global shortcut handling that works regardless of focus
	ui.window.Canvas().AddShortcut(&desktop.CustomShortcut{
		KeyName: fyne.KeyD,
	}, func(shortcut fyne.Shortcut) {
		ui.handleDraftStatusToggle()
	})
	
	// Also add space key as global shortcut
	ui.window.Canvas().AddShortcut(&desktop.CustomShortcut{
		KeyName: fyne.KeySpace,
	}, func(shortcut fyne.Shortcut) {
		ui.handleDraftStatusToggle()
	})
	
	// Handle window close
	ui.window.SetCloseIntercept(func() {
		ui.stop()
		ui.window.Close()
	})
}

// handleKeyPress handles keyboard shortcuts
func (ui *FantasyUI) handleKeyPress(key *fyne.KeyEvent) {
	switch key.Name {
	case fyne.KeyQ:
		ui.handleLLMQuery()
	case fyne.KeyR:
		ui.handleManualRefresh()
	case fyne.KeySpace:
		ui.handleDraftStatusToggle()
	case fyne.KeyEscape:
		ui.stop()
		ui.window.Close()
	}
}

// handleTypedRune handles typed character input
func (ui *FantasyUI) handleTypedRune(r rune) {
	switch r {
	case 'd', 'D':
		ui.handleDraftStatusToggle()
	case 'q', 'Q':
		ui.handleLLMQuery()
	case 'r', 'R':
		ui.handleManualRefresh()
	}
}

// handleLLMQuery handles LLM query requests
func (ui *FantasyUI) handleLLMQuery() {
	ui.mutex.Lock()
	defer ui.mutex.Unlock()
	
	// Check if LLM is configured
	if !ui.llmManager.IsConfigured() {
		ui.showLLMNotConfiguredMessage()
		return
	}
	
	if ui.querying || ui.refreshing {
		return
	}
	
	if time.Since(ui.lastQuery) < 5*time.Second {
		providerType := ui.llmManager.GetProviderType()
		ui.notice = fmt.Sprintf("Wait 5 seconds between %s queries", providerType)
		ui.updateStatusInternal()
		return
	}
	
	ui.querying = true
	ui.lastQuery = time.Now()
	ui.updateStatusInternal()
	
	// Clear output safely
	ui.safeUIUpdate(func() {
		ui.outputText.ParseMarkdown("")
	})
	
	go ui.performLLMQuery()
}

// handleManualRefresh handles manual refresh requests
func (ui *FantasyUI) handleManualRefresh() {
	ui.mutex.Lock()
	defer ui.mutex.Unlock()
	
	if ui.querying || ui.refreshing {
		return
	}
	
	ui.refreshing = true
	ui.notice = ""
	ui.lastRefresh = time.Now()
	ui.updateStatusInternal()
	
	// Clear output safely
	ui.safeUIUpdate(func() {
		ui.outputText.ParseMarkdown("")
	})
	
	go func() {
		ui.performRefresh(true)
		ui.loadTeamData() // Also refresh team data
	}()
}

// performLLMQuery runs the LLM query in a goroutine
func (ui *FantasyUI) performLLMQuery() {
	// First refresh player data
	ui.performRefreshInternal()
	
	// Build the notes string using the updated players (limit to top 15)
	ui.mutex.RLock()
	currentPlayers := make([]Player, len(ui.players))  // Create safe copy
	copy(currentPlayers, ui.players)
	currentPick := ui.currentPick
	pickedPlayers := make([]string, len(ui.pickedPlayers))
	copy(pickedPlayers, ui.pickedPlayers)
	ui.mutex.RUnlock()
	
	// Limit to top 15 players for LLM analysis to keep prompt manageable
	topPlayers := currentPlayers
	if len(currentPlayers) > 15 {
		topPlayers = currentPlayers[:15]
	}
	
	allNotes, err := ui.dataLoader.BuildAllNotes(topPlayers)
	if err != nil {
		ui.handleError(fmt.Errorf("failed to build notes: %w", err))
		return
	}
	
	// Get current team from status file (fallback)
	currentTeam, err := ui.dataLoader.LoadCurrentTeam()
	if err != nil {
		log.Printf("Warning: could not load current team: %v", err)
		currentTeam = "[Team not available]"
	}
	
	// Build picked players string
	pickedPlayersStr := fmt.Sprintf("%s", pickedPlayers)
	if len(pickedPlayers) == 0 {
		pickedPlayersStr = "[No players picked yet]"
	}
	
	// Build the full user prompt with draft context
	prompt, err := ui.llmManager.BuildUserPrompt(currentPick, pickedPlayersStr, currentTeam, allNotes)
	if err != nil {
		log.Printf("Error building user prompt: %v", err)
		ui.handleError(fmt.Errorf("failed to build user prompt: %w", err))
		return
	}
	
	// Ask LLM and return the answer
	answer, err := ui.llmManager.Ask(prompt)
	if err != nil {
		providerType := ui.llmManager.GetProviderType()
		log.Printf("Error from %s: %v", providerType, err)
		ui.handleError(fmt.Errorf("%s error: %w", providerType, err))
		return
	}
	
	// Update UI safely
	ui.mutex.Lock()
	ui.querying = false
	ui.mutex.Unlock()
	
	ui.safeUIUpdate(func() {
		ui.outputText.ParseMarkdown(answer)
	})
	ui.updateStatus()
}

// performRefresh runs the refresh in a goroutine
func (ui *FantasyUI) performRefresh(manual bool) {
	ui.performRefreshInternal()
	
	ui.mutex.Lock()
	ui.refreshing = false
	playerCount := len(ui.players)
	ui.mutex.Unlock()
	
	if manual {
		ui.safeUIUpdate(func() {
			ui.outputText.ParseMarkdown(fmt.Sprintf("Refreshed: %d players (updated %s)", 
				playerCount, time.Now().Format("15:04:05")))
		})
	}
	
	ui.updateStatus()
}

// fuzzyMatchPlayer attempts to find a player in the CSV that matches the input name
// Returns the matched CSV player name and whether a match was found
func (ui *FantasyUI) fuzzyMatchPlayer(inputName string, allPlayers []Player) (string, bool) {
	inputLower := strings.ToLower(strings.TrimSpace(inputName))
	
	// First try exact match
	for _, player := range allPlayers {
		if strings.ToLower(player.Name) == inputLower {
			return player.Name, true
		}
	}
	
	// Try partial match (input contains CSV name or vice versa)
	for _, player := range allPlayers {
		playerLower := strings.ToLower(player.Name)
		if strings.Contains(inputLower, playerLower) || strings.Contains(playerLower, inputLower) {
			log.Printf("FUZZY MATCH: '%s' matched to '%s'", inputName, player.Name)
			return player.Name, true
		}
	}
	
	// Try matching individual words
	inputWords := strings.Fields(inputLower)
	for _, player := range allPlayers {
		playerWords := strings.Fields(strings.ToLower(player.Name))
		matchCount := 0
		
		for _, inputWord := range inputWords {
			for _, playerWord := range playerWords {
				if inputWord == playerWord {
					matchCount++
					break
				}
			}
		}
		
		// If at least 2 words match, consider it a match
		if matchCount >= 2 && matchCount >= len(inputWords)/2 {
			log.Printf("FUZZY MATCH: '%s' matched to '%s' (%d words)", inputName, player.Name, matchCount)
			return player.Name, true
		}
	}
	
	return "", false
}

// performRefreshInternal does the actual refresh work
func (ui *FantasyUI) performRefreshInternal() {
	// Generate filtered player list based on picked players
	ui.mutex.RLock()
	rawPickedPlayers := make([]string, len(ui.pickedPlayers))
	copy(rawPickedPlayers, ui.pickedPlayers)
	ui.mutex.RUnlock()
	
	// Load all players from static CSV file
	playerDataFiles := []string{
		getDataPath("players.csv"),
		getDataPath("combined_with_depth.csv"),
		"go/combined_with_depth.csv", // fallback if running from root
	}
	
	var allPlayers []Player
	var err error
	
	for _, filename := range playerDataFiles {
		if _, statErr := os.Stat(filename); statErr == nil {
			allPlayers, err = LoadPlayers(filename)
			if err == nil {
				break
			}
		}
	}
	
	if err != nil || len(allPlayers) == 0 {
		log.Printf("Failed to load player data for refresh: %v", err)
		return
	}
	
	// Create map of picked players with fuzzy matching
	pickedPlayers := make(map[string]bool)
	for _, rawPlayerName := range rawPickedPlayers {
		// Try exact match first
		found := false
		for _, player := range allPlayers {
			if player.Name == rawPlayerName {
				pickedPlayers[player.Name] = true
				found = true
				break
			}
		}
		
		// If no exact match, try fuzzy matching
		if !found {
			if matchedName, matched := ui.fuzzyMatchPlayer(rawPlayerName, allPlayers); matched {
				pickedPlayers[matchedName] = true
			} else {
				log.Printf("WARNING: No match found for picked player: '%s'", rawPlayerName)
			}
		}
	}
	
	// Filter out picked players
	var filteredPlayers []Player
	for _, player := range allPlayers {
		if !pickedPlayers[player.Name] {
			filteredPlayers = append(filteredPlayers, player)
		}
	}
	
	log.Printf("Filtered players: %d total, %d picked, %d remaining", len(allPlayers), len(ui.pickedPlayers), len(filteredPlayers))
	
	ui.mutex.Lock()
	// Only update if the data actually changed
	shouldUpdate := len(filteredPlayers) != len(ui.players)
	if !shouldUpdate && len(filteredPlayers) > 0 && len(ui.players) > 0 {
		shouldUpdate = filteredPlayers[0].Name != ui.players[0].Name
	}
	
	if shouldUpdate {
		log.Printf("Live update: Removing %d picked players from GUI (%d → %d players)", len(ui.pickedPlayers), len(ui.players), len(filteredPlayers))
		ui.players = filteredPlayers
		// Load draft status for all players
		ui.loadDraftStatusForAllPlayers()
		ui.mutex.Unlock()
		
		// Refresh UI safely
		ui.safeUIUpdate(func() {
			ui.playerList.Refresh()
		})
	} else {
		ui.mutex.Unlock()
	}
}

// handleError handles errors by updating the UI
func (ui *FantasyUI) handleError(err error) {
	ui.mutex.Lock()
	ui.querying = false
	ui.refreshing = false
	ui.mutex.Unlock()
	
	ui.safeUIUpdate(func() {
		ui.outputText.ParseMarkdown(fmt.Sprintf("**Error:** %s", err.Error()))
	})
	ui.updateStatus()
}

// showLLMNotConfiguredMessage shows a warning message when LLM is not configured
func (ui *FantasyUI) showLLMNotConfiguredMessage() {
	warningMessage := `# ⚠️ LLM Not Configured

No LLM provider is currently configured. To use the AI analysis features, you need to configure either:

## Option 1: OpenAI
- Get an API key from [OpenAI](https://platform.openai.com/api-keys)
- Enter it in the Settings

## Option 2: Local LLM (Ollama)
- Install and configure Ollama for local AI processing
- Configure it in the Settings

## How to Configure
1. Click the **Settings** button (⚙️ gear icon) in the top right
2. Choose your preferred LLM option
3. Enter the required credentials/settings
4. Test the connection
5. Save and start using AI analysis!

---

**Note:** All other features of the Fantasy Football Tool work perfectly without LLM configuration. The draft tracking, player filtering, and manual refresh functions are fully operational.`

	ui.safeUIUpdate(func() {
		ui.outputText.ParseMarkdown(warningMessage)
	})
}

// updateStatus updates the status label (public method)
func (ui *FantasyUI) updateStatus() {
	ui.mutex.Lock()
	ui.updateStatusInternal()
	ui.mutex.Unlock()
}

// updateStatusInternal updates the status label (must be called with mutex held)
func (ui *FantasyUI) updateStatusInternal() {
	var status string
	
	switch {
	case ui.notice != "":
		status = ui.notice
		ui.notice = "" // Clear notice after showing
	case ui.refreshing:
		status = "Refreshing player data..."
	case ui.querying:
		providerType := ui.llmManager.GetProviderType()
		status = fmt.Sprintf("Querying %s...", providerType)
	default:
		providerType := ui.llmManager.GetProviderType()
		if ui.llmManager.IsConfigured() {
			status = fmt.Sprintf("Ready - Listening for draft updates (q: %s, r: Refresh, d/Space: Toggle Draft Status, Esc: Quit)", providerType)
		} else {
			status = "Ready - Listening for draft updates (q: Configure LLM, r: Refresh, d/Space: Toggle Draft Status, Esc: Quit)"
		}
	}
	
	ui.safeUIUpdate(func() {
		ui.statusLabel.SetText(status)
	})
}

// startPlayerUpdateListener listens for player updates from the HTTP server
func (ui *FantasyUI) startPlayerUpdateListener() {
	go func() {
		for {
			select {
			case update := <-ui.playerUpdateChan:
				if update.TeamChanged {
					log.Printf("Received team update notification")
					// Reload team data when roster changes
					ui.loadTeamData()
				} else {
					log.Printf("Received player update: %d players, pick %d", len(update.PickedPlayers), update.PickNumber)
					
					// Throttle updates to max 1 per 200ms to prevent channel overflow
					ui.mutex.Lock()
					if time.Since(ui.lastPlayerUpdate) < 200*time.Millisecond {
						log.Printf("Throttling player update (too frequent)")
						ui.mutex.Unlock()
						continue
					}
					ui.lastPlayerUpdate = time.Now()
					
					ui.pickedPlayers = update.PickedPlayers
					ui.currentPick = update.PickNumber
					
					// Trigger a refresh to update the available players list
					canRefresh := !ui.refreshing && !ui.querying
					if canRefresh {
						ui.refreshing = true
					}
					ui.mutex.Unlock()
					
					if canRefresh {
						go ui.performRefresh(false)
					}
				}
				
			case <-ui.stopChan:
				return
			}
		}
	}()
}

// stop stops all background goroutines
func (ui *FantasyUI) stop() {
	// Non-blocking send to stop channel
	select {
	case ui.stopChan <- true:
	case <-time.After(100 * time.Millisecond):
		// If we can't send within 100ms, the goroutines are probably already stopped
	}
}

// handleSettingsUpdate handles updates to settings from the settings UI
func (ui *FantasyUI) handleSettingsUpdate(settings *Settings) error {
	// Update the LLM manager with new settings
	if err := ui.llmManager.UpdateSettings(settings); err != nil {
		return fmt.Errorf("failed to update LLM manager: %w", err)
	}
	
	// Update local settings reference
	ui.settings = settings
	
	// Update status to reflect new provider
	ui.updateStatus()
	
	// If LLM is now configured, clear the warning message
	if ui.llmManager.IsConfigured() {
		ui.safeUIUpdate(func() {
			ui.outputText.ParseMarkdown("✅ **LLM configured successfully!** You can now use the AI analysis features.")
		})
	} else {
		// Show the warning message if still not configured
		ui.showLLMNotConfiguredMessage()
	}
	
	log.Printf("Settings updated successfully. Now using %s", ui.llmManager.GetProviderType())
	return nil
}

// Show displays the UI window
func (ui *FantasyUI) Show() {
	ui.window.Show()
}

// sortTeamPlayersByPosition sorts team players by position groups and within each position
func (ui *FantasyUI) sortTeamPlayersByPosition() []Player {
	if len(ui.teamPlayers) == 0 {
		return []Player{}
	}
	
	// Position priority order
	positionOrder := map[string]int{
		"QB":  1,
		"RB":  2, 
		"WR":  3,
		"TE":  4,
		"K":   5,
		"DST": 6,
		"DEF": 6, // Alternative defense notation
	}
	
	sorted := make([]Player, len(ui.teamPlayers))
	copy(sorted, ui.teamPlayers)
	
	sort.Slice(sorted, func(i, j int) bool {
		posI := positionOrder[sorted[i].Pos]
		posJ := positionOrder[sorted[j].Pos]
		
		// If positions are different, sort by position priority
		if posI != posJ {
			return posI < posJ
		}
		
		// Within same position, sort by rank (lower rank number = better)
		return sorted[i].rankNum < sorted[j].rankNum
	})
	
	return sorted
}

// formatTeamPlayerForDisplay formats a team player for display in the list
func (ui *FantasyUI) formatTeamPlayerForDisplay(player Player) string {
	return fmt.Sprintf("%-4s  %-22s  %-4s", player.Pos, player.Name, player.Team)
}

// getTeamPlayerDisplayData returns formatted team data without position headers
func (ui *FantasyUI) getTeamPlayerDisplayData() []string {
	sortedPlayers := ui.sortTeamPlayersByPosition()
	if len(sortedPlayers) == 0 {
		return []string{"No players on your team yet"}
	}
	
	var displayData []string
	
	for _, player := range sortedPlayers {
		displayData = append(displayData, ui.formatTeamPlayerForDisplay(player))
	}
	
	return displayData
}

// toggleLLMCollapse toggles the LLM output panel collapsed state
func (ui *FantasyUI) toggleLLMCollapse() {
	ui.mutex.Lock()
	// Don't allow collapsing if team panel is already collapsed
	if ui.teamCollapsed && !ui.llmCollapsed {
		ui.mutex.Unlock()
		return
	}
	
	ui.llmCollapsed = !ui.llmCollapsed
	collapsed := ui.llmCollapsed
	
	// If we're collapsing LLM and team was collapsed, expand team
	if collapsed && ui.teamCollapsed {
		ui.teamCollapsed = false
	}
	ui.mutex.Unlock()
	
	ui.safeUIUpdate(func() {
		if collapsed {
			// Collapse LLM panel by setting offset to nearly 0 (give team panel most space)
			ui.rightVSplit.SetOffset(0.05)
			ui.llmCollapseBtn.SetText("  +  ")
			// Also ensure team panel is expanded
			ui.teamCollapseBtn.SetText("  −  ")
		} else {
			// Restore normal split
			ui.rightVSplit.SetOffset(0.6)
			ui.llmCollapseBtn.SetText("  −  ")
		}
	})
}

// toggleTeamCollapse toggles the team panel collapsed state  
func (ui *FantasyUI) toggleTeamCollapse() {
	ui.mutex.Lock()
	// Don't allow collapsing if LLM panel is already collapsed
	if ui.llmCollapsed && !ui.teamCollapsed {
		ui.mutex.Unlock()
		return
	}
	
	ui.teamCollapsed = !ui.teamCollapsed
	collapsed := ui.teamCollapsed
	
	// If we're collapsing team and LLM was collapsed, expand LLM
	if collapsed && ui.llmCollapsed {
		ui.llmCollapsed = false
	}
	ui.mutex.Unlock()
	
	ui.safeUIUpdate(func() {
		if collapsed {
			// Collapse team panel by setting offset to nearly 1 (give LLM panel most space)
			ui.rightVSplit.SetOffset(0.95)
			ui.teamCollapseBtn.SetText("  +  ")
			// Also ensure LLM panel is expanded
			ui.llmCollapseBtn.SetText("  −  ")
		} else {
			// Restore normal split
			ui.rightVSplit.SetOffset(0.6)
			ui.teamCollapseBtn.SetText("  −  ")
		}
	})
}

// loadTeamData loads the current team data from the file
func (ui *FantasyUI) loadTeamData() {
	teamPlayers, err := ui.dataLoader.LoadCurrentTeamPlayers()
	if err != nil {
		log.Printf("Warning: could not load team players: %v", err)
		teamPlayers = []Player{} // Use empty slice on error
	}
	
	ui.mutex.Lock()
	ui.teamPlayers = teamPlayers
	ui.mutex.Unlock()
	
	// Refresh team list
	ui.safeUIUpdate(func() {
		ui.teamList.Refresh()
	})
	
	log.Printf("Loaded %d team players", len(teamPlayers))
}

// showPlayerNote displays the full note content for a player in an overlay
func (ui *FantasyUI) showPlayerNote(playerName string) {
	// Load the note file content
	noteFile, err := ui.dataLoader.FindPlayerNoteFile(playerName)
	if err != nil {
		log.Printf("Could not find note file for %s: %v", playerName, err)
		return
	}
	
	content, err := os.ReadFile(noteFile)
	if err != nil {
		log.Printf("Could not read note file for %s: %v", playerName, err)
		return
	}
	
	// Update the note viewer
	ui.mutex.Lock()
	ui.currentViewedPlayer = playerName
	ui.noteViewerVisible = true
	ui.mutex.Unlock()
	
	// Update UI safely
	ui.safeUIUpdate(func() {
		// Create header with player name, draft status button, and close button
		headerContainer := container.NewBorder(
			nil, nil,
			widget.NewLabel(fmt.Sprintf("Analysis: %s", playerName)),
			container.NewHBox(ui.draftStatusButton, ui.closeNoteButton),
			nil,
		)
		
		// Update the note viewer container with the new header
		ui.noteViewerContainer = container.NewBorder(
			headerContainer,
			nil,
			nil,
			nil,
			container.NewScroll(ui.noteViewer),
		)
		
		// Set the note content
		ui.noteViewer.ParseMarkdown(string(content))
		
		// Replace the right panel content with note viewer
		ui.mainContainer.Trailing = ui.noteViewerContainer
		ui.mainContainer.Refresh()
	})
	
	// Selection is handled in OnSelected handler
}

// hidePlayerNote hides the note viewer and returns to normal view
func (ui *FantasyUI) hidePlayerNote() {
	ui.mutex.Lock()
	ui.noteViewerVisible = false
	ui.currentViewedPlayer = ""
	ui.mutex.Unlock()
	
	// Restore the original right panel
	ui.safeUIUpdate(func() {
		// Create right panel with buttons and status again
		buttonContainer := container.NewHBox(
			ui.queryButton,
			ui.refreshButton,
			widget.NewSeparator(),
			ui.settingsButton,
		)
		
		rightPanelWithControls := container.NewBorder(
			buttonContainer, // top
			ui.statusLabel,  // bottom
			nil,            // left
			nil,            // right
			ui.rightVSplit, // center
		)
		
		ui.mainContainer.Trailing = rightPanelWithControls
		ui.mainContainer.Refresh()
	})
}

// handleDraftStatusToggle toggles the draft status of the currently selected player
func (ui *FantasyUI) handleDraftStatusToggle() {
	ui.mutex.Lock()
	selectedIndex := ui.lastSelectedPlayerIndex  // Use last selected, not current (which might be -1 after unselect)
	if selectedIndex == -1 || selectedIndex >= len(ui.players) {
		ui.mutex.Unlock()
		return
	}
	
	player := &ui.players[selectedIndex]
	playerName := player.Name
	
	// Cycle through: "" -> "✅" -> "❌" -> ""
	switch player.DraftStatus {
	case "":
		player.DraftStatus = "✅"
	case "✅":
		player.DraftStatus = "❌"
	case "❌":
		player.DraftStatus = ""
	default:
		player.DraftStatus = "✅"
	}
	
	newStatus := player.DraftStatus
	ui.mutex.Unlock()
	
	// Update the note file
	if err := ui.dataLoader.WriteDraftStatusToNote(playerName, newStatus); err != nil {
		log.Printf("Error updating draft status for %s: %v", playerName, err)
	}
	
	// Refresh the UI
	ui.safeUIUpdate(func() {
		ui.playerList.Refresh()
	})
}

// loadDraftStatusForAllPlayers loads draft status from note files for all players
// Must be called with mutex held
func (ui *FantasyUI) loadDraftStatusForAllPlayers() {
	for i := range ui.players {
		ui.players[i].DraftStatus = ui.dataLoader.LoadDraftStatusFromNote(ui.players[i].Name)
	}
}
