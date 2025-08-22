package main

import (
	"log"
	"os"

	"fyne.io/fyne/v2/app"
	"github.com/joho/godotenv"
)

func main() {
	// --- Load Environment Variables ---
	err := godotenv.Load()
	if err != nil {
		log.Printf("Warning: Error loading .env file: %v", err)
	}

	// --- Logging Setup ---
	logFile, err := os.OpenFile("program-messages.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatal(err)
	}
	defer logFile.Close()
	log.SetOutput(logFile)
	log.Println("--- Application Starting ---")

	// --- Data Loading and Initialization ---

	// 1. Initialize the data loader.
	// Note: Updated paths - "analysis" for note files, "." for logs directory (where filtered files will be created)
	dataLoader := NewDataLoader("analysis", ".")

	// 2. Load player data from static players.csv file (not dynamic log files)
	// Try multiple possible player data file names
	playerDataFiles := []string{
		"players.csv",
		"combined_with_depth.csv",
		"go/combined_with_depth.csv", // fallback if running from root
	}

	var playerCSVPath string
	var players []Player

	for _, filename := range playerDataFiles {
		if _, err := os.Stat(filename); err == nil {
			playerCSVPath = filename
			players, err = LoadPlayers(playerCSVPath)
			if err == nil {
				log.Printf("Successfully loaded player data from: %s", playerCSVPath)
				break
			}
			log.Printf("Failed to load players from %s: %v", filename, err)
		}
	}

	if len(players) == 0 {
		log.Fatalf("Fatal error: Could not find or load player data from any of: %v", playerDataFiles)
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

	// 6. Create communication channel between HTTP server and UI
	playerUpdateChannel := make(chan PlayerUpdate, 1000)

	// 7. Start the HTTP server for browser extension communication
	statusDir := "status"
	httpPort := 8000
	httpServer := StartHTTPServerAsync(statusDir, httpPort, playerUpdateChannel)
	log.Printf("HTTP server started on port %d for browser extension communication", httpPort)
	_ = httpServer // Avoid unused variable warning

	// --- Start UI ---

	// 8. Initialize and run the Fyne UI, passing the loaded data and update channel.
	fyneApp := app.New()
	fyneApp.SetIcon(resourceLogoPng)
	
	// Set custom font for the app
	fyneApp.Settings().SetTheme(&customTheme{})
	ui := NewFantasyUI(fyneApp, players, dataLoader, llmManager, settings, playerUpdateChannel)
	ui.Show()
	fyneApp.Run()

	log.Println("--- Application Exiting ---")
}
