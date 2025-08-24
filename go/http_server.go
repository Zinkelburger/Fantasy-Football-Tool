package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sort"
	"sync"
)

// PlayerNamesRequest represents the JSON payload from the browser extension (legacy format)
type PlayerNamesRequest struct {
	PlayerNames []string `json:"playerNames"`
}

// UnifiedDataRequest represents the new unified data format from the browser extension
type UnifiedDataRequest struct {
	Type    string   `json:"type"`    // "picked_players" or "roster_players"
	Players []string `json:"players"`
}

// PlayerUpdate represents the data sent to the UI
type PlayerUpdate struct {
	PickedPlayers []string
	PickNumber    int
	TeamChanged   bool // Indicates if roster/team data was updated
}

// HTTPServer handles incoming requests from the browser extension
type HTTPServer struct {
	statusDir     string
	playerNames   map[string]bool // picked players
	rosterPlayers map[string]bool // roster/team players
	updateChannel chan<- PlayerUpdate
	mutex         sync.RWMutex
}

// NewHTTPServer creates a new HTTP server instance
func NewHTTPServer(statusDir string, updateChannel chan<- PlayerUpdate) *HTTPServer {
	return &HTTPServer{
		statusDir:     statusDir,
		playerNames:   make(map[string]bool),
		rosterPlayers: make(map[string]bool),
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

	// Initialize/clear current_team.txt
	teamFile := fmt.Sprintf("%s/current_team.txt", s.statusDir)
	if err := os.WriteFile(teamFile, []byte(""), 0644); err != nil {
		return fmt.Errorf("failed to initialize current_team.txt: %w", err)
	}

	log.Println("Initialized pick.txt with value 0 and cleared current_team.txt")
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

// saveRosterPlayers saves roster players to current_team.txt grouped by position
func (s *HTTPServer) saveRosterPlayers(rosterPlayers []string) error {
	teamFile := fmt.Sprintf("%s/current_team.txt", s.statusDir)
	
	// Load player data to get position information for sorting
	loader := NewDataLoader("analysis", "status")
	teamPlayers, err := loader.LoadCurrentTeamPlayersFromNames(rosterPlayers)
	if err != nil {
		// Fallback: save without grouping if we can't load player data
		content := ""
		for _, playerName := range rosterPlayers {
			if playerName != "" {
				content += playerName + "\n"
			}
		}
		if err := os.WriteFile(teamFile, []byte(content), 0644); err != nil {
			return fmt.Errorf("failed to update current_team.txt: %w", err)
		}
		log.Printf("Updated current_team.txt with %d players (ungrouped fallback)", len(rosterPlayers))
		return nil
	}
	
	// Sort players by position
	sortedPlayers := s.sortPlayersByPosition(teamPlayers)
	
	// Group by position and format output
	content := ""
	var currentPosition string
	
	for _, player := range sortedPlayers {
		// Add position header when position changes
		if player.Pos != currentPosition {
			currentPosition = player.Pos
			// Add spacing before position header (except for first)
			if content != "" {
				content += "\n"
			}
			content += fmt.Sprintf("=== %s ===\n", currentPosition)
		}
		content += player.Name + "\n"
	}
	
	if err := os.WriteFile(teamFile, []byte(content), 0644); err != nil {
		return fmt.Errorf("failed to update current_team.txt: %w", err)
	}
	
	log.Printf("Updated current_team.txt with %d players (grouped by position)", len(rosterPlayers))
	return nil
}

// sortPlayersByPosition sorts players by position groups and within each position
func (s *HTTPServer) sortPlayersByPosition(players []Player) []Player {
	if len(players) == 0 {
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
	
	sorted := make([]Player, len(players))
	copy(sorted, players)
	
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

	// Try to parse as unified data format first
	var unifiedRequest UnifiedDataRequest
	if err := json.Unmarshal(body, &unifiedRequest); err == nil && unifiedRequest.Type != "" {
		// Handle unified format
		log.Printf("HTTP: Received %s with %d players: %v", unifiedRequest.Type, len(unifiedRequest.Players), unifiedRequest.Players)
		
		switch unifiedRequest.Type {
		case "picked_players":
			s.handlePickedPlayers(unifiedRequest.Players, w)
		case "roster_players":
			s.handleRosterPlayers(unifiedRequest.Players, w)
		default:
			log.Printf("Unknown data type: %s", unifiedRequest.Type)
			http.Error(w, "Unknown data type", http.StatusBadRequest)
			return
		}
		return
	}
	
	// Fall back to legacy format
	var request PlayerNamesRequest
	if err := json.Unmarshal(body, &request); err != nil {
		log.Printf("Error parsing JSON: %v", err)
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Log all received player names (legacy format)
	log.Printf("HTTP: Received %d players (legacy): %v", len(request.PlayerNames), request.PlayerNames)
	
	// Handle legacy format as picked players
	s.handlePickedPlayers(request.PlayerNames, w)

}

// handlePickedPlayers processes picked players data
func (s *HTTPServer) handlePickedPlayers(playerNames []string, w http.ResponseWriter) {
	// Thread-safe processing of picked player names
	s.mutex.Lock()
	
	// Check if the complete list has changed
	hasChanges := false
	if len(playerNames) != len(s.playerNames) {
		hasChanges = true
	} else {
		for _, playerName := range playerNames {
			if !s.playerNames[playerName] {
				hasChanges = true
				break
			}
		}
	}

	// Update our internal map to match the current state
	s.playerNames = make(map[string]bool)
	for _, playerName := range playerNames {
		s.playerNames[playerName] = true
	}
	
	allPlayerNames := make([]string, len(playerNames))
	copy(allPlayerNames, playerNames)
	s.mutex.Unlock()

	// Send update if there were changes
	if hasChanges {
		log.Printf("Picked player list changed, sending update with %d players", len(allPlayerNames))
		if err := s.sendPlayerUpdate(allPlayerNames); err != nil {
			log.Printf("Error sending player update: %v", err)
			http.Error(w, "Failed to process players", http.StatusInternalServerError)
			return
		}
	}

	s.sendSuccessResponse(w)
}

// handleRosterPlayers processes roster/team players data
func (s *HTTPServer) handleRosterPlayers(playerNames []string, w http.ResponseWriter) {
	// Thread-safe processing of roster players
	s.mutex.Lock()
	
	// Check if the roster has changed
	hasChanges := false
	if len(playerNames) != len(s.rosterPlayers) {
		hasChanges = true
	} else {
		for _, playerName := range playerNames {
			if !s.rosterPlayers[playerName] {
				hasChanges = true
				break
			}
		}
	}

	// Update our internal roster map
	s.rosterPlayers = make(map[string]bool)
	for _, playerName := range playerNames {
		s.rosterPlayers[playerName] = true
	}
	
	rosterPlayerNames := make([]string, len(playerNames))
	copy(rosterPlayerNames, playerNames)
	s.mutex.Unlock()

	// Save to current_team.txt if there were changes
	if hasChanges {
		log.Printf("Roster changed, saving %d players to current_team.txt", len(rosterPlayerNames))
		if err := s.saveRosterPlayers(rosterPlayerNames); err != nil {
			log.Printf("Error saving roster players: %v", err)
			http.Error(w, "Failed to save roster", http.StatusInternalServerError)
			return
		}
		
		// Send UI update notification for team changes
		teamUpdate := PlayerUpdate{
			PickedPlayers: make([]string, 0), // Empty for team updates
			PickNumber:    0,                 // Not relevant for team updates
			TeamChanged:   true,
		}
		
		select {
		case s.updateChannel <- teamUpdate:
			log.Printf("Sent team update notification via channel")
		default:
			log.Printf("Warning: Update channel full, skipping team update notification")
		}
	}

	s.sendSuccessResponse(w)
}

// sendSuccessResponse sends a standardized success response
func (s *HTTPServer) sendSuccessResponse(w http.ResponseWriter) {
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
