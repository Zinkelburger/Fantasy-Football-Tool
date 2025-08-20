package main

import (
	"fmt"
	"log"
	"sync"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/widget"
)

// FantasyUI holds the Fyne UI components and application state
type FantasyUI struct {
	app        fyne.App
	window     fyne.Window
	
	// Data
	players     []Player
	dataLoader  *DataLoader
	gpt         *GPT
	
	// UI Components
	playerList  *widget.List
	outputText  *widget.RichText
	statusLabel *widget.Label
	queryButton *widget.Button
	refreshButton *widget.Button
	
	// State
	querying    bool
	refreshing  bool
	lastQuery   time.Time
	lastRefresh time.Time
	notice      string
	
	// Concurrency
	mutex       sync.RWMutex
	autoRefreshTicker *time.Ticker
	stopChan    chan bool
	uiUpdateChan chan func()  // Channel for safe UI updates
}

// NewFantasyUI creates and initializes the Fyne UI
func NewFantasyUI(app fyne.App, players []Player, loader *DataLoader, gpt *GPT) *FantasyUI {
	window := app.NewWindow("Fantasy Football Tool")
	window.Resize(fyne.NewSize(1200, 800))
	
	ui := &FantasyUI{
		app:         app,
		window:      window,
		players:     players,
		dataLoader:  loader,
		gpt:         gpt,
		lastQuery:   time.Now().Add(-5 * time.Second),
		lastRefresh: time.Now(),
		stopChan:    make(chan bool, 1),  // Buffered to prevent blocking
		uiUpdateChan: make(chan func(), 10),  // Buffered channel for UI updates
	}
	
	ui.setupUI()
	ui.startUIUpdateHandler()
	ui.startAutoRefresh()
	
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
			return widget.NewLabel("template")
		},
		func(id widget.ListItemID, item fyne.CanvasObject) {
			ui.mutex.RLock()
			defer ui.mutex.RUnlock()
			
			if id < len(ui.players) {
				p := ui.players[id]
				label := item.(*widget.Label)
				label.SetText(fmt.Sprintf("%-4s %-20s %-5s %-3s", p.Rank, p.Name, p.Depth, p.Team))
			}
		},
	)
	
	// Create output text area
	ui.outputText = widget.NewRichText()
	ui.outputText.Scroll = container.ScrollBoth
	ui.outputText.Wrapping = fyne.TextWrapWord
	
	// Create status label
	ui.statusLabel = widget.NewLabel("Ready - Auto-refresh enabled")
	
	// Create buttons
	ui.queryButton = widget.NewButton("Query ChatGPT (q)", ui.handleChatGPTQuery)
	ui.refreshButton = widget.NewButton("Manual Refresh (r)", ui.handleManualRefresh)
	
	// Create button container
	buttonContainer := container.NewHBox(
		ui.queryButton,
		ui.refreshButton,
	)
	
	// Create header for player list
	headerLabel := widget.NewLabel(fmt.Sprintf("%-4s %-20s %-5s %-3s", "Rank", "Name", "Depth", "Team"))
	headerLabel.TextStyle = fyne.TextStyle{Bold: true}
	
	// Create left panel (player list)
	leftPanel := container.NewBorder(
		headerLabel, // top
		nil,         // bottom
		nil,         // left
		nil,         // right
		ui.playerList, // center
	)
	
	// Create right panel (output and controls)
	rightPanel := container.NewBorder(
		buttonContainer, // top
		ui.statusLabel,  // bottom
		nil,            // left
		nil,            // right
		container.NewScroll(ui.outputText), // center
	)
	
	// Create main split container
	content := container.NewHSplit(leftPanel, rightPanel)
	content.SetOffset(0.5) // 50/50 split
	
	ui.window.SetContent(content)
	
	// Set up keyboard shortcuts
	ui.window.Canvas().SetOnTypedKey(ui.handleKeyPress)
	
	// Handle window close
	ui.window.SetCloseIntercept(func() {
		ui.stopAutoRefresh()
		ui.window.Close()
	})
}

// handleKeyPress handles keyboard shortcuts
func (ui *FantasyUI) handleKeyPress(key *fyne.KeyEvent) {
	switch key.Name {
	case fyne.KeyQ:
		ui.handleChatGPTQuery()
	case fyne.KeyR:
		ui.handleManualRefresh()
	case fyne.KeyEscape:
		ui.stopAutoRefresh()
		ui.window.Close()
	}
}

// handleChatGPTQuery handles ChatGPT query requests
func (ui *FantasyUI) handleChatGPTQuery() {
	ui.mutex.Lock()
	defer ui.mutex.Unlock()
	
	if ui.querying || ui.refreshing {
		return
	}
	
	if time.Since(ui.lastQuery) < 5*time.Second {
		ui.notice = "Wait 5 seconds between ChatGPT queries"
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
	
	go ui.performChatGPTQuery()
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
	
	go ui.performRefresh(true)
}

// performChatGPTQuery runs the ChatGPT query in a goroutine
func (ui *FantasyUI) performChatGPTQuery() {
	// First refresh player data
	ui.performRefreshInternal()
	
	// Build the notes string using the updated players
	ui.mutex.RLock()
	currentPlayers := make([]Player, len(ui.players))  // Create safe copy
	copy(currentPlayers, ui.players)
	ui.mutex.RUnlock()
	
	allNotes, err := ui.dataLoader.BuildAllNotes(currentPlayers)
	if err != nil {
		ui.handleError(fmt.Errorf("failed to build notes: %w", err))
		return
	}
	
	// Get current context
	pickNum, err := ui.dataLoader.LoadCurrentPickNum()
	if err != nil {
		log.Printf("Warning: could not load current pick number: %v", err)
		pickNum = 0
	}
	
	currentTeam, err := ui.dataLoader.LoadCurrentTeam()
	if err != nil {
		log.Printf("Warning: could not load current team: %v", err)
		currentTeam = "[Team not available]"
	}
	
	// Construct the prompt
	prompt := fmt.Sprintf(
		"It is pick %d of a 2025 fantasy football draft. "+
			"This is my current team: %s. "+
			"Output the top several players you think could help me the most along with an explanation, considering their value, upside, and drawbacks. "+
			"Give a summary of the most important players at the end once you are finished your explanations. "+
			"The notes for each player are separated by '---start playername---' and '---end playername---'.\n\n"+
			"Player Notes:\n%s",
		pickNum, currentTeam, allNotes,
	)
	
	// Ask ChatGPT and return the answer
	answer, err := ui.gpt.Ask(prompt)
	if err != nil {
		log.Printf("Error from GPT API: %v", err)
		ui.handleError(fmt.Errorf("ChatGPT error: %w", err))
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

// performRefreshInternal does the actual refresh work
func (ui *FantasyUI) performRefreshInternal() {
	// Try to find the latest filtered log file
	latestLogFile, err := ui.dataLoader.FindLatestLogFile()
	if err != nil {
		// No filtered files found - this is normal at the start
		log.Printf("No filtered log file found, keeping current data: %v", err)
		return
	}
	
	// Load players from the latest filtered file
	updatedPlayers, err := LoadPlayers(latestLogFile)
	if err != nil {
		log.Printf("Failed to load players from %s: %v", latestLogFile, err)
		return
	}
	
	log.Printf("Refreshed player data from %s, loaded %d players", latestLogFile, len(updatedPlayers))
	
	ui.mutex.Lock()
	// Only update if the data actually changed
	shouldUpdate := len(updatedPlayers) != len(ui.players)
	if !shouldUpdate && len(updatedPlayers) > 0 && len(ui.players) > 0 {
		shouldUpdate = updatedPlayers[0].Name != ui.players[0].Name
	}
	
	if shouldUpdate {
		ui.players = updatedPlayers
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
		status = "Querying ChatGPT..."
	default:
		status = "Ready - Auto-refresh enabled (q: ChatGPT, r: Refresh, Esc: Quit)"
	}
	
	ui.safeUIUpdate(func() {
		ui.statusLabel.SetText(status)
	})
}

// startAutoRefresh starts the automatic refresh timer
func (ui *FantasyUI) startAutoRefresh() {
	ui.autoRefreshTicker = time.NewTicker(3 * time.Second)
	
	go func() {
		defer ui.autoRefreshTicker.Stop()  // Ensure cleanup
		
		for {
			select {
			case <-ui.autoRefreshTicker.C:
				ui.mutex.Lock()
				canRefresh := !ui.refreshing && !ui.querying
				if canRefresh {
					ui.refreshing = true
				}
				ui.mutex.Unlock()
				
				if canRefresh {
					go ui.performRefresh(false)
				}
			case <-ui.stopChan:
				return
			}
		}
	}()
}

// stopAutoRefresh stops the automatic refresh timer
func (ui *FantasyUI) stopAutoRefresh() {
	if ui.autoRefreshTicker != nil {
		ui.autoRefreshTicker.Stop()
	}
	
	// Non-blocking send to stop channel
	select {
	case ui.stopChan <- true:
	case <-time.After(100 * time.Millisecond):
		// If we can't send within 100ms, the goroutines are probably already stopped
	}
}

// Show displays the UI window
func (ui *FantasyUI) Show() {
	ui.window.Show()
}
