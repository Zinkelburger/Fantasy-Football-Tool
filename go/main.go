package main

import (
	"log"
	"os"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/widget"
)

func main() {
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
		// Show error dialog instead of console output
		fyneApp := app.New()
		w := fyneApp.NewWindow("Fantasy Football Tool - Error")
		
		errorText := "ERROR: Missing note files for players:\n\n"
		for playerName, suggestion := range missingPlayers {
			if suggestion != "" {
				errorText += "Couldn't find " + playerName + ".md. Found " + suggestion + ". Do you want to rename it?\n"
				log.Printf("Missing note file for '%s', suggested: %s", playerName, suggestion)
			} else {
				errorText += "Couldn't find " + playerName + ".md. No similar files found.\n"
				log.Printf("Missing note file for '%s', no suggestions", playerName)
			}
		}
		errorText += "\nPlease ensure all player note files exist in the analysis directory before running the program."
		
		errorLabel := widget.NewLabel(errorText)
		w.SetContent(errorLabel)
		w.Resize(fyne.NewSize(800, 400))
		
		// Show dialog and wait for user to close it
		w.ShowAndRun()
		log.Printf("Application stopped due to %d missing player note files", len(missingPlayers))
		return
	}

	log.Printf("All %d players have corresponding note files.", len(players))

	// 5. Initialize the GPT client.
	gpt, err := NewGPT()
	if err != nil {
		log.Fatalf("Fatal error initializing GPT client: %v", err)
	}

	// 6. Start the HTTP server for browser extension communication
	logDir := "log"
	httpPort := 8000
	httpServer := StartHTTPServerAsync(logDir, httpPort)
	log.Printf("HTTP server started on port %d for browser extension communication", httpPort)
	_ = httpServer // Avoid unused variable warning

	// --- Start UI ---

	// 7. Initialize and run the Fyne UI, passing the loaded data.
	fyneApp := app.New()
	ui := NewFantasyUI(fyneApp, players, dataLoader, gpt)
	ui.Show()
	fyneApp.Run()

	log.Println("--- Application Exiting ---")
}
