package main

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"fyne.io/fyne/v2/test"
)

// Test helper to create a minimal FantasyUI for testing
func createTestUI(t *testing.T) (*FantasyUI, chan PlayerUpdate, func()) {
	t.Helper()

	// Create test app and data
	testApp := test.NewApp()
	players := []Player{
		{Name: "Patrick Mahomes", Team: "KC", Pos: "QB", Depth: "1", Rank: "1", Note: "Great QB"},
		{Name: "Travis Kelce", Team: "KC", Pos: "TE", Depth: "1", Rank: "5", Note: "Elite TE"},
		{Name: "Tyreek Hill", Team: "MIA", Pos: "WR", Depth: "1", Rank: "8", Note: "Fast WR"},
	}

	// Create mock data loader
	dataLoader := NewDataLoader("test", "test")

	// Create mock settings and LLM manager
	settings := DefaultSettings()
	llmManager, _ := NewLLMManager(settings)

	// Create player update channel
	playerUpdateChan := make(chan PlayerUpdate, 100)

	// Create mock HTTP server
	mockHTTPServer := NewHTTPServer("test", playerUpdateChan)

	// Create UI
	ui := NewFantasyUI(testApp, players, dataLoader, llmManager, settings, playerUpdateChan, mockHTTPServer)

	cleanup := func() {
		ui.stop()
	}

	return ui, playerUpdateChan, cleanup
}

func TestNewFantasyUI(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Test basic initialization
	if ui.app == nil {
		t.Error("Expected app to be initialized")
	}

	if ui.window == nil {
		t.Error("Expected window to be initialized")
	}

	if len(ui.players) != 3 {
		t.Errorf("Expected 3 players, got %d", len(ui.players))
	}

	if ui.dataLoader == nil {
		t.Error("Expected dataLoader to be initialized")
	}

	if ui.llmManager == nil {
		t.Error("Expected llmManager to be initialized")
	}

	if ui.settings == nil {
		t.Error("Expected settings to be initialized")
	}

	// Test UI components
	if ui.playerList == nil {
		t.Error("Expected playerList to be initialized")
	}

	if ui.outputText == nil {
		t.Error("Expected outputText to be initialized")
	}

	if ui.statusLabel == nil {
		t.Error("Expected statusLabel to be initialized")
	}

	if ui.queryButton == nil {
		t.Error("Expected queryButton to be initialized")
	}

	if ui.refreshButton == nil {
		t.Error("Expected refreshButton to be initialized")
	}

	// Test initial state
	if ui.querying {
		t.Error("Expected querying to be false initially")
	}

	if ui.refreshing {
		t.Error("Expected refreshing to be false initially")
	}

	if ui.currentPick != 0 {
		t.Errorf("Expected currentPick to be 0, got %d", ui.currentPick)
	}

	if len(ui.pickedPlayers) != 0 {
		t.Errorf("Expected no picked players initially, got %d", len(ui.pickedPlayers))
	}
}

func TestSafeUIUpdate(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Test that safeUIUpdate doesn't block
	updateFunc := func() {
		// Update function for testing
	}

	ui.safeUIUpdate(updateFunc)

	// Give some time for the update to process
	time.Sleep(100 * time.Millisecond)

	// Note: Since we can't easily test Fyne UI updates in unit tests,
	// we'll just verify the function doesn't panic or block
}

func TestUpdateStatus(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Test initial status
	ui.updateStatus()

	// Test status during querying
	ui.mutex.Lock()
	ui.querying = true
	ui.mutex.Unlock()

	ui.updateStatus()

	// Test status during refreshing
	ui.mutex.Lock()
	ui.querying = false
	ui.refreshing = true
	ui.mutex.Unlock()

	ui.updateStatus()

	// Test notice status
	ui.mutex.Lock()
	ui.refreshing = false
	ui.notice = "Test notice"
	ui.mutex.Unlock()

	ui.updateStatus()

	// Verify notice is cleared after updating
	ui.mutex.RLock()
	if ui.notice != "" {
		t.Error("Expected notice to be cleared after updating status")
	}
	ui.mutex.RUnlock()
}

func TestPlayerUpdateListener(t *testing.T) {
	ui, playerUpdateChan, cleanup := createTestUI(t)
	defer cleanup()

	// Send a player update
	update := PlayerUpdate{
		PickedPlayers: []string{"Patrick Mahomes", "Travis Kelce"},
		PickNumber:    2,
		TeamChanged:   false,
	}

	playerUpdateChan <- update

	// Give some time for the update to be processed
	time.Sleep(200 * time.Millisecond)

	// Check that the UI state was updated
	ui.mutex.RLock()
	if len(ui.pickedPlayers) != 2 {
		t.Errorf("Expected 2 picked players, got %d", len(ui.pickedPlayers))
	}

	if ui.currentPick != 2 {
		t.Errorf("Expected current pick to be 2, got %d", ui.currentPick)
	}

	expectedPlayers := []string{"Patrick Mahomes", "Travis Kelce"}
	for i, expected := range expectedPlayers {
		if i >= len(ui.pickedPlayers) || ui.pickedPlayers[i] != expected {
			t.Errorf("Expected picked player at index %d to be '%s', got '%s'", i, expected, ui.pickedPlayers[i])
		}
	}
	ui.mutex.RUnlock()
}

func TestHandleLLMQueryRateLimit(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Set last query to recent time to trigger rate limit
	ui.mutex.Lock()
	ui.lastQuery = time.Now()
	ui.mutex.Unlock()

	// Try to query - should be rate limited
	ui.handleLLMQuery()

	// Check that notice was set
	ui.mutex.RLock()
	// Note: The notice might have been cleared by updateStatus, so we can't reliably test it
	// But we can verify that querying didn't start
	if ui.querying {
		t.Error("Expected query to be rate limited")
	}
	ui.mutex.RUnlock()
}

func TestHandleLLMQueryWhenBusy(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Set UI as already querying
	ui.mutex.Lock()
	ui.querying = true
	ui.mutex.Unlock()

	// Try to query - should be ignored
	ui.handleLLMQuery()

	// Should still be querying (no state change)
	ui.mutex.RLock()
	if !ui.querying {
		t.Error("Expected querying state to remain true")
	}
	ui.mutex.RUnlock()

	// Test when refreshing
	ui.mutex.Lock()
	ui.querying = false
	ui.refreshing = true
	ui.mutex.Unlock()

	ui.handleLLMQuery()

	ui.mutex.RLock()
	if ui.querying {
		t.Error("Expected query to be ignored when refreshing")
	}
	ui.mutex.RUnlock()
}

func TestHandleManualRefreshWhenBusy(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Set UI as already refreshing
	ui.mutex.Lock()
	ui.refreshing = true
	ui.mutex.Unlock()

	// Try to refresh - should be ignored
	ui.handleManualRefresh()

	// Should still be refreshing (no state change)
	ui.mutex.RLock()
	if !ui.refreshing {
		t.Error("Expected refreshing state to remain true")
	}
	ui.mutex.RUnlock()

	// Test when querying
	ui.mutex.Lock()
	ui.refreshing = false
	ui.querying = true
	ui.mutex.Unlock()

	ui.handleManualRefresh()

	ui.mutex.RLock()
	if ui.refreshing {
		t.Error("Expected refresh to be ignored when querying")
	}
	ui.mutex.RUnlock()
}

func TestPerformRefreshInternal(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	initialPlayerCount := len(ui.players)

	// Test refresh without picked players
	ui.performRefreshInternal()

	ui.mutex.RLock()
	playerCountAfterRefresh := len(ui.players)
	ui.mutex.RUnlock()

	// Since we don't have a real CSV file, the player count might change
	// We'll just verify the function doesn't panic
	t.Logf("Initial players: %d, After refresh: %d", initialPlayerCount, playerCountAfterRefresh)
}

func TestPerformRefreshInternalWithPickedPlayers(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Set some picked players
	ui.mutex.Lock()
	ui.pickedPlayers = []string{"Patrick Mahomes"}
	ui.mutex.Unlock()

	ui.performRefreshInternal()

	// Verify the function completes without error
	// Note: Since we don't have real CSV files in the test environment,
	// we can't test the actual filtering logic, but we can ensure it doesn't crash
}

func TestHandleError(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Set UI as busy
	ui.mutex.Lock()
	ui.querying = true
	ui.refreshing = true
	ui.mutex.Unlock()

	testError := "test error message"
	ui.handleError(fmt.Errorf(testError))

	// Check that busy states were cleared
	ui.mutex.RLock()
	if ui.querying {
		t.Error("Expected querying to be false after error")
	}

	if ui.refreshing {
		t.Error("Expected refreshing to be false after error")
	}
	ui.mutex.RUnlock()
}

func TestHandleSettingsUpdate(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Create new settings with OpenAI (doesn't require external service)
	newSettings := &Settings{
		OpenAIAPIKey:   "test-key",
		UseLocalLLM:    false,
		OllamaModel:    "",
		OllamaEndpoint: "",
	}

	err := ui.handleSettingsUpdate(newSettings)
	if err != nil {
		t.Errorf("Expected no error from handleSettingsUpdate, got: %v", err)
	}

	// Verify settings were updated
	if ui.settings != newSettings {
		t.Error("Expected settings reference to be updated")
	}
}

func TestStop(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Test that stop doesn't block
	ui.stop()

	// Call stop again to ensure it's safe to call multiple times
	ui.stop()
}

func TestConcurrentAccess(t *testing.T) {
	ui, playerUpdateChan, cleanup := createTestUI(t)
	defer cleanup()

	// Test concurrent access to UI state
	var wg sync.WaitGroup
	numGoroutines := 10

	// Simulate concurrent status updates
	for i := 0; i < numGoroutines; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ui.updateStatus()
		}()
	}

	// Simulate concurrent player updates
	for i := 0; i < numGoroutines; i++ {
		wg.Add(1)
		go func(index int) {
			defer wg.Done()
			update := PlayerUpdate{
				PickedPlayers: []string{fmt.Sprintf("Player%d", index)},
				PickNumber:    index,
				TeamChanged:   false,
			}
			select {
			case playerUpdateChan <- update:
			case <-time.After(100 * time.Millisecond):
				// Timeout is OK for this test
			}
		}(i)
	}

	// Wait for all goroutines to complete
	done := make(chan bool, 1)
	go func() {
		wg.Wait()
		done <- true
	}()

	select {
	case <-done:
		// Success
	case <-time.After(5 * time.Second):
		t.Error("Concurrent access test timed out")
	}
}

func TestUIUpdateChannelFull(t *testing.T) {
	ui, _, cleanup := createTestUI(t)
	defer cleanup()

	// Fill up the UI update channel by sending more updates than buffer size
	for i := 0; i < 20; i++ { // More than the buffer size of 10
		ui.safeUIUpdate(func() {
			// Do nothing - just fill the channel
		})
	}

	// This should not block even though channel is full
	ui.safeUIUpdate(func() {
		// This update should be skipped
	})
}

// Test the Player struct used in UI (UI-specific test)
func TestPlayerStructUI(t *testing.T) {
	player := Player{
		Name:  "Test Player",
		Team:  "TST",
		Pos:   "QB",
		Depth: "1",
		Rank:  "1.5",
		Note:  "Test note",
	}

	if player.Name != "Test Player" {
		t.Errorf("Expected Name 'Test Player', got '%s'", player.Name)
	}

	if player.Team != "TST" {
		t.Errorf("Expected Team 'TST', got '%s'", player.Team)
	}

	if player.Pos != "QB" {
		t.Errorf("Expected Pos 'QB', got '%s'", player.Pos)
	}

	if player.Depth != "1" {
		t.Errorf("Expected Depth '1', got '%s'", player.Depth)
	}

	if player.Rank != "1.5" {
		t.Errorf("Expected Rank '1.5', got '%s'", player.Rank)
	}

	if player.Note != "Test note" {
		t.Errorf("Expected Note 'Test note', got '%s'", player.Note)
	}
}
