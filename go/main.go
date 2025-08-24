package main

import (
	"fmt"
	"log"
	"os"
	"strings"

	"fyne.io/fyne/v2/app"
	"github.com/joho/godotenv"
)

func main() {
	// --- Load Environment Variables ---
	// Only log warning if .env exists but can't be read
	// Note: We check the current directory first, then fall back to godotenv.Load() for compatibility
	if _, err := os.Stat(".env"); err == nil {
		// .env file exists, try to load it
		if err := godotenv.Load(); err != nil {
			log.Printf("Warning: Error loading existing .env file: %v", err)
		} else {
			log.Printf("Info: Loaded configuration from .env file")
		}
	} else {
		// .env file doesn't exist, that's fine - we'll use defaults and environment variables
		log.Printf("Info: No .env file found, using default settings and environment variables")
	}

	// --- Logging Setup ---
	logFile, err := os.OpenFile(getWritablePath("program-messages.log"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatal(err)
	}
	defer logFile.Close()
	log.SetOutput(logFile)
	log.Println("--- Application Starting ---")

	// --- Data Loading and Initialization ---

	// 1. Initialize the data loader.
	// Note: Updated paths - "analysis" for note files, "." for logs directory (where filtered files will be created)
	dataLoader := NewDataLoader(getDataPath("analysis"), ".")

	// 2. Load player data from static players.csv file (not dynamic log files)
	// Prioritize go/players.csv over other files to avoid loading incorrect data
	playerDataFiles := []string{
		getDataPath("players.csv"), // Should resolve to go/players.csv with updated getAppDir()
		getDataPath("combined_with_depth.csv"), // Fallback
		"players.csv", // Direct path fallback
		"go/players.csv", // Explicit go directory fallback
		"go/combined_with_depth.csv", // Final fallback
	}

	var playerCSVPath string
	var players []Player
	var loadErrors []string

	for _, filename := range playerDataFiles {
		if _, err := os.Stat(filename); err == nil {
			playerCSVPath = filename
			players, err = LoadPlayers(playerCSVPath)
			if err == nil {
				log.Printf("Successfully loaded player data from: %s", playerCSVPath)
				break
			}
			loadErrors = append(loadErrors, fmt.Sprintf("Failed to load %s: %v", filename, err))
		} else {
			loadErrors = append(loadErrors, fmt.Sprintf("File not found: %s", filename))
		}
	}

	if len(players) == 0 {
		log.Fatalf("Fatal error: Could not find or load player data from any of: %v\nErrors encountered:\n%s", 
			playerDataFiles, strings.Join(loadErrors, "\n"))
	}

	log.Printf("Successfully loaded %d players from %s.", len(players), playerCSVPath)

	// 3. Test that all players have corresponding note files.
	missingPlayers, err := dataLoader.TestAvailableNotes(players)
	if err != nil {
		log.Fatalf("Fatal error testing note files: %v", err)
	}

	// 4. Report any missing player files and stop if any are found.
	if len(missingPlayers) > 0 {
		log.Printf("ERROR: Missing note files for %d players:", len(missingPlayers))
		for playerName, suggestion := range missingPlayers {
			if suggestion != "" {
				log.Printf("Missing note file for '%s', suggested: %s", playerName, suggestion)
			} else {
				log.Printf("Missing note file for '%s', no suggestions", playerName)
			}
		}
		log.Fatalf("Application stopped due to %d missing player note files. Please ensure all player note files exist in the analysis directory.", len(missingPlayers))
	}

	log.Printf("All %d players have corresponding note files.", len(players))

	// 5. Load settings and initialize LLM.
	settings, err := LoadSettings()
	if err != nil {
		log.Fatalf("Fatal error loading settings: %v", err)
	}

	// Initialize LLM manager - allow it to fail gracefully if not configured
	llmManager, err := NewLLMManager(settings)
	if err != nil {
		log.Printf("Warning: LLM manager initialization failed: %v", err)
		log.Printf("Application will start without LLM functionality")
		// Create a nil LLM manager to indicate no LLM is available
		llmManager = &LLMManager{
			settings: settings,
			provider: nil,
		}
	}

	// 6. Initialize status directory and files if they don't exist
	statusDir := getWritablePath("status")
	if err := os.MkdirAll(statusDir, 0755); err != nil {
		log.Fatalf("Failed to create status directory: %v", err)
	}
	
	// Initialize status files with defaults if they don't exist
	pickFile := statusDir + "/pick.txt"
	if _, err := os.Stat(pickFile); os.IsNotExist(err) {
		if err := os.WriteFile(pickFile, []byte("0"), 0644); err != nil {
			log.Fatalf("Failed to create pick.txt: %v", err)
		}
		log.Printf("Created default %s", pickFile)
	}
	
	teamFile := statusDir + "/current_team.txt"
	if _, err := os.Stat(teamFile); os.IsNotExist(err) {
		if err := os.WriteFile(teamFile, []byte(""), 0644); err != nil {
			log.Fatalf("Failed to create current_team.txt: %v", err)
		}
		log.Printf("Created default %s", teamFile)
	}

	// 7. Create communication channel between HTTP server and UI
	playerUpdateChannel := make(chan PlayerUpdate, 1000)

	// 8. Start the HTTP server for browser extension communication
	httpPort := 8000
	httpServer := StartHTTPServerAsync(statusDir, httpPort, playerUpdateChannel)
	log.Printf("HTTP server started on port %d for browser extension communication", httpPort)
	_ = httpServer // Avoid unused variable warning

	// --- Start UI ---

	// 9. Initialize and run the Fyne UI, passing the loaded data and update channel.
	fyneApp := app.New()
	fyneApp.SetIcon(resourceLogoPng)
	
	// Set custom font for the app
	fyneApp.Settings().SetTheme(&customTheme{})
	ui := NewFantasyUI(fyneApp, players, dataLoader, llmManager, settings, playerUpdateChannel)
	ui.Show()
	fyneApp.Run()

	log.Println("--- Application Exiting ---")
}
