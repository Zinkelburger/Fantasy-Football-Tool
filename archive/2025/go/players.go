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
	SleeperRank string // Sleeper ranking from JuiceBoxOne data
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
	
	if len(rows) == 0 {
		return nil, fmt.Errorf("CSV file is empty: %s", path)
	}

	// Parse header to determine CSV format
	header := rows[0]
	columnMap := make(map[string]int)
	
	// Map column names to their indices
	for i, colName := range header {
		columnMap[colName] = i
	}
	
	// Verify we have the expected unified format: Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank
	expectedColumns := []string{"Rank", "Player", "Team", "Bye", "POS", "ESPN_Rank", "Sleeper_Rank"}
	
	// Check if all required columns exist
	for _, col := range expectedColumns {
		if _, exists := columnMap[col]; !exists {
			return nil, fmt.Errorf("missing required column '%s' in CSV file %s. Expected format: Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank", col, path)
		}
	}
	
	// Get column indices for the unified format
	rankCol := columnMap["Rank"]
	playerCol := columnMap["Player"] 
	teamCol := columnMap["Team"]
	posCol := columnMap["POS"]
	espnCol := columnMap["ESPN_Rank"]
	sleeperCol := columnMap["Sleeper_Rank"]
	
	fmt.Printf("Loading unified CSV format from %s\n", filepath.Base(path))

	var ps []Player
	for i, r := range rows {
		if i == 0 { // Skip header
			continue
		}

		// Validate we have enough columns (need at least 7 for our unified format)
		if len(r) < 7 {
			return nil, fmt.Errorf("CSV row %d has %d columns, expected at least 7 for unified format", i+1, len(r))
		}

		// Skip rows with empty player names
		playerName := strings.TrimSpace(r[playerCol])
		if playerName == "" {
			continue
		}

		// Parse ranking for sorting
		rankValue := r[rankCol]
		rankNum, _ := strconv.ParseFloat(rankValue, 64)

		// Load truncated note from analysis file
		note := loadTruncatedNote(playerName)

		// Get ESPN rank
		espnRank := r[espnCol]

		// Get Sleeper rank
		sleeperRank := r[sleeperCol]

		// Use position as depth (the JuiceBoxOne data doesn't have separate depth info)
		depth := r[posCol]

		ps = append(ps, Player{
			Name:        playerName,
			Team:        r[teamCol],
			Pos:         r[posCol],
			Depth:       depth,
			Rank:        rankValue,
			Note:        note,
			DraftStatus: "", // Will be loaded by UI
			rankNum:     int(rankNum),
			ESPNRank:    espnRank,
			SleeperRank: sleeperRank,
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
