package main

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type Player struct {
	Name        string
	Team        string
	Pos         string
	Depth       string
	Rank        string
	Note        string
	DraftStatus string // "✅", "❌", or "" (empty)
	rankNum     int    // internal field for sorting
	ESPNRank    string // ESPN ranking from JuiceBoxOne data
}

func LoadPlayers(path string) ([]Player, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	rows, err := csv.NewReader(f).ReadAll()
	if err != nil {
		return nil, err
	}

	var ps []Player
	for i, r := range rows {
		if i == 0 { // Skip header
			continue
		}

		// Validate we have enough columns
		if len(r) < 6 {
			return nil, fmt.Errorf("CSV row %d has %d columns, expected at least 6", i, len(r))
		}

		// Parse Average_ADP for sorting (4th column)
		rankNum, _ := strconv.ParseFloat(r[3], 64)

		// Load truncated note from analysis file
		note := loadTruncatedNote(r[0])

		ps = append(ps, Player{
			Name:        r[0], // Name (1st column)
			Team:        r[1], // Team (2nd column)
			Pos:         r[2], // Pos (3rd column)
			Depth:       r[4], // Depth (5th column)
			Rank:        r[3], // Average_ADP (4th column)
			Note:        note,
			DraftStatus: "", // Will be loaded by UI
			rankNum:     int(rankNum),
			ESPNRank:    r[5], // ESPN_Rank column
		})
	}

	// Sort by rank number
	sort.Slice(ps, func(i, j int) bool {
		return ps[i].rankNum < ps[j].rankNum
	})

	return ps, nil
}

// loadTruncatedNote loads a truncated note from a player's analysis file
// Prefers content after "# Analysis" header if present, otherwise uses the last meaningful line
func loadTruncatedNote(playerName string) string {
	// Clean the player name for file lookup
	cleanedName := strings.TrimSpace(playerName)

	// Try to find the analysis file
	analysisPath := filepath.Join("analysis", cleanedName+".md")
	if _, err := os.Stat(analysisPath); os.IsNotExist(err) {
		return "No note"
	}

	content, err := os.ReadFile(analysisPath)
	if err != nil {
		return "Error loading"
	}

	lines := strings.Split(string(content), "\n")

	// First, try to find content after "# Analysis" header
	analysisStarted := false
	var analysisLines []string

	for _, line := range lines {
		if strings.HasPrefix(strings.TrimSpace(line), "# Analysis") {
			analysisStarted = true
			continue
		}
		if analysisStarted && strings.TrimSpace(line) != "" {
			analysisLines = append(analysisLines, line)
		}
	}

	var textToTruncate string

	if len(analysisLines) > 0 {
		// Use analysis section content
		textToTruncate = strings.Join(analysisLines, " ")
	} else {
		// Fall back to last meaningful line
		for i := len(lines) - 1; i >= 0; i-- {
			line := strings.TrimSpace(lines[i])
			if line != "" && !strings.HasPrefix(line, "#") {
				textToTruncate = line
				break
			}
		}
	}

	if textToTruncate == "" {
		return "No content"
	}

	// Clean up markdown and formatting
	textToTruncate = strings.ReplaceAll(textToTruncate, "**", "")
	textToTruncate = strings.ReplaceAll(textToTruncate, "*", "")
	textToTruncate = strings.ReplaceAll(textToTruncate, "- ", "")
	textToTruncate = strings.TrimSpace(textToTruncate)

	// Truncate to about 40 characters
	if len(textToTruncate) <= 40 {
		return textToTruncate
	}

	// Find a good breaking point near 40 characters
	words := strings.Fields(textToTruncate)
	truncated := ""
	for _, word := range words {
		if len(truncated)+len(word)+1 > 37 { // Leave room for "..."
			break
		}
		if truncated != "" {
			truncated += " "
		}
		truncated += word
	}

	return truncated + "..."
}
