package main

import (
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

	// 2. Pre-scan and cache all available note files. This is a required step.
	if err := dataLoader.PreloadAvailableNotes(); err != nil {
		log.Fatalf("Fatal error pre-loading note files: %v", err)
	}

	// 3. Use the loader to find the most recent player data CSV file.
	playerCSVPath, err := dataLoader.FindLatestLogFile()
	if err != nil {
		log.Fatalf("Fatal error finding latest log file: %v", err)
	}
	log.Printf("Located latest player data file: %s", playerCSVPath)

	// 4. Load the player data from the discovered file.
	// We are assuming LoadPlayers(path) and the Player struct are defined elsewhere.
	players, err := LoadPlayers(playerCSVPath)
	if err != nil {
		log.Fatalf("Fatal error loading players from %s: %v", playerCSVPath, err)
	}
	log.Printf("Successfully loaded %d players.", len(players))

	// 5. Proactively find and cache notes for all loaded players to speed up UI operations.
	dataLoader.WarmUpCache(players)

	// 6. Initialize the GPT client.
	// We are assuming NewGPT() is defined elsewhere.
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
