package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Test helper to create a temporary status directory
func setupTempStatusDir(t *testing.T) (string, func()) {
	t.Helper()
	
	tempDir, err := os.MkdirTemp("", "http_server_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	
	cleanup := func() {
		os.RemoveAll(tempDir)
	}
	
	return tempDir, cleanup
}

func TestNewHTTPServer(t *testing.T) {
	statusDir := "test_status"
	updateChan := make(chan PlayerUpdate, 1)
	
	server := NewHTTPServer(statusDir, updateChan)
	
	if server.statusDir != statusDir {
		t.Errorf("Expected statusDir to be '%s', got '%s'", statusDir, server.statusDir)
	}
	
	if server.playerNames == nil {
		t.Error("Expected playerNames map to be initialized")
	}
	
	if server.updateChannel != updateChan {
		t.Error("Expected updateChannel to be set correctly")
	}
}

func TestSetupStatusDirectory(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 1)
	server := NewHTTPServer(tempDir, updateChan)
	
	err := server.setupStatusDirectory()
	if err != nil {
		t.Fatalf("setupStatusDirectory failed: %v", err)
	}
	
	// Check that status directory was created
	if _, err := os.Stat(tempDir); os.IsNotExist(err) {
		t.Error("Status directory was not created")
	}
	
	// Check that pick.txt was created with value "0"
	pickFile := filepath.Join(tempDir, "pick.txt")
	content, err := os.ReadFile(pickFile)
	if err != nil {
		t.Fatalf("Failed to read pick.txt: %v", err)
	}
	
	if string(content) != "0" {
		t.Errorf("Expected pick.txt content to be '0', got '%s'", string(content))
	}
}

func TestSendPlayerUpdate(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	// Setup status directory first
	err := server.setupStatusDirectory()
	if err != nil {
		t.Fatalf("setupStatusDirectory failed: %v", err)
	}
	
	playerNames := []string{"Patrick Mahomes", "Travis Kelce", "Tyreek Hill"}
	
	err = server.sendPlayerUpdate(playerNames)
	if err != nil {
		t.Fatalf("sendPlayerUpdate failed: %v", err)
	}
	
	// Check that pick.txt was updated correctly
	pickFile := filepath.Join(tempDir, "pick.txt")
	content, err := os.ReadFile(pickFile)
	if err != nil {
		t.Fatalf("Failed to read pick.txt: %v", err)
	}
	
	expectedPickNum := fmt.Sprintf("%d", len(playerNames))
	if string(content) != expectedPickNum {
		t.Errorf("Expected pick.txt content to be '%s', got '%s'", expectedPickNum, string(content))
	}
	
	// Check that update was sent via channel
	select {
	case update := <-updateChan:
		if len(update.PickedPlayers) != len(playerNames) {
			t.Errorf("Expected %d picked players, got %d", len(playerNames), len(update.PickedPlayers))
		}
		
		if update.PickNumber != len(playerNames) {
			t.Errorf("Expected pick number to be %d, got %d", len(playerNames), update.PickNumber)
		}
		
		// Check that all player names are included
		for i, expectedName := range playerNames {
			if update.PickedPlayers[i] != expectedName {
				t.Errorf("Expected player at index %d to be '%s', got '%s'", i, expectedName, update.PickedPlayers[i])
			}
		}
	case <-time.After(1 * time.Second):
		t.Error("Expected to receive update via channel, but none received")
	}
}

func TestHandlePlayerNames_ValidRequest(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	// Setup status directory
	err := server.setupStatusDirectory()
	if err != nil {
		t.Fatalf("setupStatusDirectory failed: %v", err)
	}
	
	// Create test request
	playerNames := []string{"Patrick Mahomes", "Travis Kelce"}
	requestData := PlayerNamesRequest{PlayerNames: playerNames}
	requestBody, err := json.Marshal(requestData)
	if err != nil {
		t.Fatalf("Failed to marshal request: %v", err)
	}
	
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(requestBody))
	req.Header.Set("Content-Type", "application/json")
	
	recorder := httptest.NewRecorder()
	server.handlePlayerNames(recorder, req)
	
	// Check response status
	if recorder.Code != http.StatusOK {
		t.Errorf("Expected status code %d, got %d", http.StatusOK, recorder.Code)
	}
	
	// Check response content type
	expectedContentType := "application/json"
	if contentType := recorder.Header().Get("Content-Type"); contentType != expectedContentType {
		t.Errorf("Expected Content-Type '%s', got '%s'", expectedContentType, contentType)
	}
	
	// Check CORS headers
	if origin := recorder.Header().Get("Access-Control-Allow-Origin"); origin != "*" {
		t.Errorf("Expected Access-Control-Allow-Origin '*', got '%s'", origin)
	}
	
	// Check response body
	var response map[string]string
	err = json.Unmarshal(recorder.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}
	
	if response["status"] != "success" {
		t.Errorf("Expected status 'success', got '%s'", response["status"])
	}
	
	// Verify update was sent via channel
	select {
	case update := <-updateChan:
		if len(update.PickedPlayers) != len(playerNames) {
			t.Errorf("Expected %d picked players, got %d", len(playerNames), len(update.PickedPlayers))
		}
	case <-time.After(1 * time.Second):
		t.Error("Expected to receive update via channel, but none received")
	}
}

func TestHandlePlayerNames_InvalidMethod(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	recorder := httptest.NewRecorder()
	
	server.handlePlayerNames(recorder, req)
	
	if recorder.Code != http.StatusMethodNotAllowed {
		t.Errorf("Expected status code %d, got %d", http.StatusMethodNotAllowed, recorder.Code)
	}
}

func TestHandlePlayerNames_InvalidJSON(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	// Send invalid JSON
	invalidJSON := []byte(`{"invalid": json}`)
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(invalidJSON))
	req.Header.Set("Content-Type", "application/json")
	
	recorder := httptest.NewRecorder()
	server.handlePlayerNames(recorder, req)
	
	if recorder.Code != http.StatusBadRequest {
		t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, recorder.Code)
	}
}

func TestHandlePlayerNames_EmptyBody(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer([]byte("")))
	req.Header.Set("Content-Type", "application/json")
	
	recorder := httptest.NewRecorder()
	server.handlePlayerNames(recorder, req)
	
	if recorder.Code != http.StatusBadRequest {
		t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, recorder.Code)
	}
}

func TestHandlePlayerNames_NoChanges(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	// Setup status directory
	err := server.setupStatusDirectory()
	if err != nil {
		t.Fatalf("setupStatusDirectory failed: %v", err)
	}
	
	playerNames := []string{"Patrick Mahomes", "Travis Kelce"}
	
	// First request - should trigger update
	requestData := PlayerNamesRequest{PlayerNames: playerNames}
	requestBody, err := json.Marshal(requestData)
	if err != nil {
		t.Fatalf("Failed to marshal request: %v", err)
	}
	
	req1 := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(requestBody))
	req1.Header.Set("Content-Type", "application/json")
	
	recorder1 := httptest.NewRecorder()
	server.handlePlayerNames(recorder1, req1)
	
	// Consume the first update
	<-updateChan
	
	// Second request with same data - should not trigger update
	req2 := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(requestBody))
	req2.Header.Set("Content-Type", "application/json")
	
	recorder2 := httptest.NewRecorder()
	server.handlePlayerNames(recorder2, req2)
	
	// Should still get success response
	if recorder2.Code != http.StatusOK {
		t.Errorf("Expected status code %d, got %d", http.StatusOK, recorder2.Code)
	}
	
	// But no update should be sent via channel
	select {
	case <-updateChan:
		t.Error("Expected no update to be sent for unchanged data")
	case <-time.After(100 * time.Millisecond):
		// Expected - no update should be sent
	}
}

func TestHandleOptions(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	req := httptest.NewRequest(http.MethodOptions, "/", nil)
	recorder := httptest.NewRecorder()
	
	server.handleOptions(recorder, req)
	
	if recorder.Code != http.StatusOK {
		t.Errorf("Expected status code %d, got %d", http.StatusOK, recorder.Code)
	}
	
	// Check CORS headers
	expectedHeaders := map[string]string{
		"Access-Control-Allow-Origin":  "*",
		"Access-Control-Allow-Methods": "POST, OPTIONS",
		"Access-Control-Allow-Headers": "Content-Type",
	}
	
	for header, expectedValue := range expectedHeaders {
		if actualValue := recorder.Header().Get(header); actualValue != expectedValue {
			t.Errorf("Expected header '%s' to be '%s', got '%s'", header, expectedValue, actualValue)
		}
	}
}

func TestHandlePlayerNames_ReadBodyError(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	updateChan := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChan)
	
	// Create a request with a body that will cause a read error
	req := httptest.NewRequest(http.MethodPost, "/", &errorReader{})
	req.Header.Set("Content-Type", "application/json")
	
	recorder := httptest.NewRecorder()
	server.handlePlayerNames(recorder, req)
	
	if recorder.Code != http.StatusBadRequest {
		t.Errorf("Expected status code %d, got %d", http.StatusBadRequest, recorder.Code)
	}
}

func TestSendPlayerUpdate_ChannelFull(t *testing.T) {
	tempDir, cleanup := setupTempStatusDir(t)
	defer cleanup()
	
	// Create a channel with buffer size 0 to simulate full channel
	updateChan := make(chan PlayerUpdate)
	server := NewHTTPServer(tempDir, updateChan)
	
	// Setup status directory
	err := server.setupStatusDirectory()
	if err != nil {
		t.Fatalf("setupStatusDirectory failed: %v", err)
	}
	
	playerNames := []string{"Patrick Mahomes"}
	
	// This should not block even though channel has no buffer
	err = server.sendPlayerUpdate(playerNames)
	if err != nil {
		t.Fatalf("sendPlayerUpdate should not fail even with full channel: %v", err)
	}
	
	// Verify pick.txt was still updated despite channel being full
	pickFile := filepath.Join(tempDir, "pick.txt")
	content, err := os.ReadFile(pickFile)
	if err != nil {
		t.Fatalf("Failed to read pick.txt: %v", err)
	}
	
	if string(content) != "1" {
		t.Errorf("Expected pick.txt content to be '1', got '%s'", string(content))
	}
}

// errorReader is a helper that always returns an error when reading
type errorReader struct{}

func (e *errorReader) Read(p []byte) (n int, err error) {
	return 0, fmt.Errorf("simulated read error")
}

func (e *errorReader) Close() error {
	return nil
}

func TestPlayerUpdate_Structure(t *testing.T) {
	// Test that PlayerUpdate struct has the expected fields
	update := PlayerUpdate{
		PickedPlayers: []string{"Player1", "Player2"},
		PickNumber:    2,
		TeamChanged:   false,
	}
	
	if len(update.PickedPlayers) != 2 {
		t.Errorf("Expected 2 picked players, got %d", len(update.PickedPlayers))
	}
	
	if update.PickNumber != 2 {
		t.Errorf("Expected pick number to be 2, got %d", update.PickNumber)
	}
}

func TestPlayerNamesRequest_Structure(t *testing.T) {
	// Test that PlayerNamesRequest can be marshaled/unmarshaled correctly
	original := PlayerNamesRequest{
		PlayerNames: []string{"Player1", "Player2", "Player3"},
	}
	
	// Marshal to JSON
	jsonData, err := json.Marshal(original)
	if err != nil {
		t.Fatalf("Failed to marshal PlayerNamesRequest: %v", err)
	}
	
	// Unmarshal back
	var unmarshaled PlayerNamesRequest
	err = json.Unmarshal(jsonData, &unmarshaled)
	if err != nil {
		t.Fatalf("Failed to unmarshal PlayerNamesRequest: %v", err)
	}
	
	// Compare
	if len(unmarshaled.PlayerNames) != len(original.PlayerNames) {
		t.Errorf("Expected %d player names, got %d", len(original.PlayerNames), len(unmarshaled.PlayerNames))
	}
	
	for i, name := range original.PlayerNames {
		if unmarshaled.PlayerNames[i] != name {
			t.Errorf("Expected player name at index %d to be '%s', got '%s'", i, name, unmarshaled.PlayerNames[i])
		}
	}
}

func TestUnifiedFormatHandling(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "http_server_test_unified_*")
	if err != nil {
		t.Fatalf("Failed to create temp directory: %v", err)
	}
	defer os.RemoveAll(tempDir)

	updateChannel := make(chan PlayerUpdate, 10)
	server := NewHTTPServer(tempDir, updateChannel)
	if err := server.setupStatusDirectory(); err != nil {
		t.Fatalf("Failed to setup status directory: %v", err)
	}

	// Test ESPN picked players format
	espnRequest := UnifiedDataRequest{
		Site:    "espn",
		Type:    "picked_players", 
		Players: []string{"Patrick Mahomes", "Travis Kelce"},
	}

	// Test roster players format (works for both sites)
	rosterRequest := UnifiedDataRequest{
		Site:    "espn",
		Type:    "roster_players",
		Players: []string{"Josh Allen", "Stefon Diggs"},
	}

	tests := []struct {
		name    string
		request UnifiedDataRequest
	}{
		{"ESPN picked players", espnRequest},
		{"Roster players", rosterRequest},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			jsonData, err := json.Marshal(tt.request)
			if err != nil {
				t.Fatalf("Failed to marshal request: %v", err)
			}

			req := httptest.NewRequest("POST", "/", bytes.NewReader(jsonData))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			server.handlePlayerNames(w, req)

			if w.Code != http.StatusOK {
				t.Errorf("Expected status 200, got %d", w.Code)
			}

			var response map[string]string
			if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil {
				t.Errorf("Failed to parse response: %v", err)
			}

			if response["status"] != "success" {
				t.Errorf("Expected success status, got %s", response["status"])
			}
		})
	}
}
