package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// PlayerNamesRequest represents the JSON payload from the browser extension
type PlayerNamesRequest struct {
	PlayerNames []string `json:"playerNames"`
}

// HTTPServer handles incoming requests from the browser extension
type HTTPServer struct {
	logDir      string
	playerNames map[string]bool
	latestFile  string
}

// NewHTTPServer creates a new HTTP server instance
func NewHTTPServer(logDir string) *HTTPServer {
	return &HTTPServer{
		logDir:      logDir,
		playerNames: make(map[string]bool),
		latestFile:  "",
	}
}

// setupLogDirectory creates the log directory and initializes files
func (s *HTTPServer) setupLogDirectory() error {
	// Create log directory if it doesn't exist
	if err := os.MkdirAll(s.logDir, 0755); err != nil {
		return fmt.Errorf("failed to create log directory: %w", err)
	}

	// Delete all existing .txt files initially
	files, err := os.ReadDir(s.logDir)
	if err != nil {
		return fmt.Errorf("failed to read log directory: %w", err)
	}

	for _, file := range files {
		if strings.HasSuffix(file.Name(), ".txt") {
			filePath := filepath.Join(s.logDir, file.Name())
			if err := os.Remove(filePath); err != nil {
				log.Printf("Error deleting file %s: %v", file.Name(), err)
			}
		}
	}

	// Delete the existing draft_script.log file if it exists
	logFile := filepath.Join(s.logDir, "draft_script.log")
	if _, err := os.Stat(logFile); err == nil {
		if err := os.Remove(logFile); err != nil {
			log.Printf("Error deleting log file %s: %v", logFile, err)
		}
	}

	// Initialize pick.txt with 0
	pickFile := filepath.Join(s.logDir, "pick.txt")
	if err := os.WriteFile(pickFile, []byte("0"), 0644); err != nil {
		return fmt.Errorf("failed to initialize pick.txt: %w", err)
	}

	log.Println("Initialized pick.txt with value 0")
	return nil
}

// saveNewPlayerFile saves new player names to a timestamped file
func (s *HTTPServer) saveNewPlayerFile(newNames []string) error {
	if len(newNames) == 0 {
		return nil
	}

	var newFile string
	
	// If we don't have a latest file yet, create a new one
	if s.latestFile == "" {
		// Generate a new filename with the current timestamp (with microseconds for uniqueness)
		timestamp := time.Now().Format("20060102-150405.000000")
		newFile = filepath.Join(s.logDir, fmt.Sprintf("players_%s.txt", timestamp))
		s.latestFile = newFile
	} else {
		// Use the existing latest file
		newFile = s.latestFile
	}

	// Append new player names to the new file
	file, err := os.OpenFile(newFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open new player file: %w", err)
	}
	defer file.Close()

	for _, name := range newNames {
		if _, err := file.WriteString(fmt.Sprintf("%s\n", name)); err != nil {
			return fmt.Errorf("failed to write player name: %w", err)
		}
	}

	log.Printf("Appended new player names to %s", newFile)

	// Update pick.txt with the length of the new file
	content, err := os.ReadFile(newFile)
	if err != nil {
		return fmt.Errorf("failed to read new player file: %w", err)
	}

	lines := strings.Split(strings.TrimSpace(string(content)), "\n")
	playerCount := len(lines)
	if len(lines) == 1 && lines[0] == "" {
		playerCount = 0
	}

	pickFile := filepath.Join(s.logDir, "pick.txt")
	if err := os.WriteFile(pickFile, []byte(fmt.Sprintf("%d", playerCount)), 0644); err != nil {
		return fmt.Errorf("failed to update pick.txt: %w", err)
	}

	log.Printf("Updated pick.txt with player count: %d", playerCount)

	// Update latest_file reference
	s.latestFile = newFile

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

	// Process player names
	var newEntries []string
	for _, playerName := range request.PlayerNames {
		if !s.playerNames[playerName] {
			s.playerNames[playerName] = true
			newEntries = append(newEntries, playerName)
			log.Printf("Added player: %s", playerName)
		}
	}

	// Save new players if any
	if len(newEntries) > 0 {
		if err := s.saveNewPlayerFile(newEntries); err != nil {
			log.Printf("Error saving player file: %v", err)
			http.Error(w, "Failed to save players", http.StatusInternalServerError)
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
	// Setup log directory
	if err := s.setupLogDirectory(); err != nil {
		log.Fatalf("Failed to setup log directory: %v", err)
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
func StartHTTPServerAsync(logDir string, port int) *HTTPServer {
	server := NewHTTPServer(logDir)
	
	go func() {
		server.StartHTTPServer(port)
	}()
	
	return server
}

// copyFile copies a file from src to dst
func copyFile(src, dst string) error {
	srcFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer srcFile.Close()

	dstFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer dstFile.Close()

	_, err = io.Copy(dstFile, srcFile)
	return err
}
