package main

import (
	"log"

	tea "github.com/charmbracelet/bubbletea"
)

func main() {
	players, err := LoadPlayers("combined_with_depth.csv")
	if err != nil {
		log.Fatal(err)
	}

	gpt, err := NewGPT()
	if err != nil {
		log.Fatal(err)
	}

	if err := tea.NewProgram(
		newModel(players, gpt),
		tea.WithAltScreen(),
	).Start(); err != nil {
		log.Fatal(err)
	}
}
