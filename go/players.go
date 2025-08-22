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
	Name  string
	Team  string
	Pos   string
	Depth string
	Rank  string
	Note  string
	rankNum int // internal field for sorting
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
		if i == 0 {  // Skip header
			continue
		}
		
		// Validate we have enough columns
		if len(r) < 7 {
			return nil, fmt.Errorf("CSV row %d has %d columns, expected at least 7", i, len(r))
		}
		
		// Parse Average_ADP for sorting (4th column)
		rankNum, _ := strconv.ParseFloat(r[3], 64)
		
		// Load truncated note from analysis file
		note := loadTruncatedNote(r[0])
		
		ps = append(ps, Player{
			Name:    r[0],                    // Name (1st column)
			Team:    r[1],                    // Team (2nd column)  
			Pos:     r[2],                    // Pos (3rd column)
			Depth:   r[4],                    // Depth (5th column)
			Rank:    r[3],                    // Average_ADP (4th column)
			Note:    note,
			rankNum: int(rankNum),
		})
	}
	
	// Sort by rank number
	sort.Slice(ps, func(i, j int) bool {
		return ps[i].rankNum < ps[j].rankNum
	})
	
	return ps, nil
}

// loadTruncatedNote loads the first few words from a player's analysis file
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
	
	// Extract just the analysis content (skip the header)
	lines := strings.Split(string(content), "\n")
	analysisStarted := false
	var analysisLines []string
	
	for _, line := range lines {
		if strings.HasPrefix(line, "## Analysis") {
			analysisStarted = true
			continue
		}
		if analysisStarted && strings.TrimSpace(line) != "" {
			analysisLines = append(analysisLines, line)
		}
	}
	
	if len(analysisLines) == 0 {
		return "No analysis"
	}
	
	// Join and truncate to about 40 characters
	analysisText := strings.Join(analysisLines, " ")
	words := strings.Fields(analysisText)
	
	if len(words) == 0 {
		return "No analysis"
	}
	
	// Take first 6-8 words or until we hit ~40 chars
	truncated := ""
	for i, word := range words {
		if i > 7 || len(truncated)+len(word)+1 > 40 {
			break
		}
		if i > 0 {
			truncated += " "
		}
		truncated += word
	}
	
	if len(truncated) < len(analysisText) {
		truncated += "..."
	}
	
	return truncated
}
