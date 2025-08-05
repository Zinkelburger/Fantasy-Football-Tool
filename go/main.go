package main

import (
	"fmt"
	"log"
	"os"

	tea "github.com/charmbracelet/bubbletea"
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
	dataLoader := NewDataLoader("players", "filtered_logs")

	// 2. Use the loader to find the most recent player data CSV file.
	playerCSVPath, err := dataLoader.FindLatestLogFile()
	if err != nil {
		log.Fatalf("Fatal error finding latest log file: %v", err)
	}
	log.Printf("Located latest player data file: %s", playerCSVPath)

	// 3. Load the player data from the discovered file.
	players, err := LoadPlayers(playerCSVPath)
	if err != nil {
		log.Fatalf("Fatal error loading players from %s: %v", playerCSVPath, err)
	}
	log.Printf("Successfully loaded %d players.", len(players))

	// 4. Test that all players have corresponding note files.
	missingPlayers, err := dataLoader.TestAvailableNotes(players)
	if err != nil {
		log.Fatalf("Fatal error testing note files: %v", err)
	}

	// 5. Report any missing player files and stop if any are found.
	if len(missingPlayers) > 0 {
		fmt.Printf("ERROR: Missing note files for %d players:\n\n", len(missingPlayers))
		
		for playerName, suggestion := range missingPlayers {
			if suggestion != "" {
				fmt.Printf("Couldn't find %s.md. Found %s. Do you want to rename it?\n", playerName, suggestion)
				log.Printf("Missing note file for '%s', suggested: %s", playerName, suggestion)
			} else {
				fmt.Printf("Couldn't find %s.md. No similar files found.\n", playerName)
				log.Printf("Missing note file for '%s', no suggestions", playerName)
			}
		}
		
		fmt.Printf("\nPlease ensure all player note files exist in the analysis directory before running the program.\n")
		log.Fatalf("Application stopped due to %d missing player note files", len(missingPlayers))
	}

	log.Printf("All %d players have corresponding note files.", len(players))

	// 6. Initialize the GPT client.
	gpt, err := NewGPT()
	if err != nil {
		log.Fatalf("Fatal error initializing GPT client: %v", err)
	}

	// --- Start UI ---

	// 7. Initialize and run the Bubble Tea UI, passing the loaded data.
	m := newModel(players, dataLoader, gpt)
	p := tea.NewProgram(m, tea.WithAltScreen())

	if _, err := p.Run(); err != nil {
		log.Fatalf("Error running program: %v", err)
	}

	log.Println("--- Application Exiting ---")
}
