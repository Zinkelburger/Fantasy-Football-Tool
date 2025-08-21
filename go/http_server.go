package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sync"
)

// PlayerNamesRequest represents the JSON payload from the browser extension
type PlayerNamesRequest struct {
	PlayerNames []string `json:"playerNames"`
}

// PlayerUpdate represents the data sent to the UI
type PlayerUpdate struct {
	PickedPlayers []string
	PickNumber    int
}

// HTTPServer handles incoming requests from the browser extension
type HTTPServer struct {
	statusDir     string
	playerNames   map[string]bool
	updateChannel chan<- PlayerUpdate
	mutex         sync.RWMutex
}

// NewHTTPServer creates a new HTTP server instance
func NewHTTPServer(statusDir string, updateChannel chan<- PlayerUpdate) *HTTPServer {
	return &HTTPServer{
		statusDir:     statusDir,
		playerNames:   make(map[string]bool),
		updateChannel: updateChannel,
	}
}

// setupStatusDirectory creates the status directory and initializes files
func (s *HTTPServer) setupStatusDirectory() error {
	// Create status directory if it doesn't exist
	if err := os.MkdirAll(s.statusDir, 0755); err != nil {
		return fmt.Errorf("failed to create status directory: %w", err)
	}

	// Initialize pick.txt with 0
	pickFile := fmt.Sprintf("%s/pick.txt", s.statusDir)
	if err := os.WriteFile(pickFile, []byte("0"), 0644); err != nil {
		return fmt.Errorf("failed to initialize pick.txt: %w", err)
	}

	log.Println("Initialized pick.txt with value 0")
	return nil
}

// sendPlayerUpdate sends player data to the UI via channel
func (s *HTTPServer) sendPlayerUpdate(allPlayerNames []string) error {
	pickNumber := len(allPlayerNames)
	
	// Update pick.txt file for backwards compatibility
	pickFile := fmt.Sprintf("%s/pick.txt", s.statusDir)
	if err := os.WriteFile(pickFile, []byte(fmt.Sprintf("%d", pickNumber)), 0644); err != nil {
		return fmt.Errorf("failed to update pick.txt: %w", err)
	}

	// Send update via channel (non-blocking)
	update := PlayerUpdate{
		PickedPlayers: allPlayerNames,
		PickNumber:    pickNumber,
	}

	select {
	case s.updateChannel <- update:
		log.Printf("Sent player update via channel: %d players", len(allPlayerNames))
	default:
		log.Printf("Warning: Update channel full, skipping update")
	}

	return nil
}

// handlePlayerNames handles POST requests with player names from the browser extension
func (s *HTTPServer) handlePlayerNames(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Read the request body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		log.Printf("Error reading request body: %v", err)
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Parse JSON data
	var request PlayerNamesRequest
	if err := json.Unmarshal(body, &request); err != nil {
		log.Printf("Error parsing JSON: %v", err)
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Thread-safe processing of player names
	s.mutex.Lock()
	
	// Check if the complete list has changed
	hasChanges := false
	if len(request.PlayerNames) != len(s.playerNames) {
		hasChanges = true
	} else {
		for _, playerName := range request.PlayerNames {
			if !s.playerNames[playerName] {
				hasChanges = true
				break
			}
		}
	}

	// Update our internal map to match the current state
	s.playerNames = make(map[string]bool)
	for _, playerName := range request.PlayerNames {
		s.playerNames[playerName] = true
	}
	
	allPlayerNames := make([]string, len(request.PlayerNames))
	copy(allPlayerNames, request.PlayerNames)
	s.mutex.Unlock()

	// Send update if there were changes
	if hasChanges {
		log.Printf("Player list changed, sending update with %d players", len(allPlayerNames))
		if err := s.sendPlayerUpdate(allPlayerNames); err != nil {
			log.Printf("Error sending player update: %v", err)
			http.Error(w, "Failed to process players", http.StatusInternalServerError)
			return
		}
	}

	// Send success response
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

	response := map[string]string{"status": "success"}
	if err := json.NewEncoder(w).Encode(response); err != nil {
		log.Printf("Error encoding response: %v", err)
	}
}

// handleOptions handles preflight OPTIONS requests for CORS
func (s *HTTPServer) handleOptions(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	w.WriteHeader(http.StatusOK)
}

// StartHTTPServer starts the HTTP server in a goroutine
func (s *HTTPServer) StartHTTPServer(port int) {
	// Setup status directory
	if err := s.setupStatusDirectory(); err != nil {
		log.Fatalf("Failed to setup status directory: %v", err)
	}

	// Setup routes
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodOptions {
			s.handleOptions(w, r)
		} else {
			s.handlePlayerNames(w, r)
		}
	})

	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: nil,
	}

	log.Printf("Starting HTTP server on port %d...", port)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Printf("HTTP server error: %v", err)
	}
}

// StartHTTPServerAsync starts the HTTP server as a goroutine
func StartHTTPServerAsync(statusDir string, port int, updateChannel chan<- PlayerUpdate) *HTTPServer {
	server := NewHTTPServer(statusDir, updateChannel)
	
	go func() {
		server.StartHTTPServer(port)
	}()
	
	return server
}
