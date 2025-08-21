package main

import (
	"fmt"
	"github.com/sahilm/fuzzy"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// DataLoader handles finding draft-related files.
type DataLoader struct {
	notesDir    string
	logsDir     string
	nameCleaner *regexp.Regexp
}

// NewDataLoader creates a new DataLoader.
func NewDataLoader(notesDir, logsDir string) *DataLoader {
	// This regex finds and removes common suffixes (Jr., Sr., II, etc.) from player names.
	re := regexp.MustCompile(`\s+(?:Jr\.|Sr\.|II|III|IV|V)$`)

	return &DataLoader{
		notesDir:    notesDir,
		logsDir:     logsDir,
		nameCleaner: re,
	}
}

// TestAvailableNotes validates that all players have corresponding note files.
// Returns map of missing players and suggestions for potential matches.
func (d *DataLoader) TestAvailableNotes(players []Player) (map[string]string, error) {
	missingPlayers := make(map[string]string)

	// Get all available note files
	mdFiles, err := filepath.Glob(filepath.Join(d.notesDir, "*.md"))
	if err != nil {
		return nil, fmt.Errorf("cannot read note files: %w", err)
	}

	// Create a map of available note file names (cleaned)
	availableNotes := make([]string, 0, len(mdFiles))
	noteFileMap := make(map[string]string) // cleaned name -> full path

	for _, file := range mdFiles {
		noteName := strings.TrimSuffix(filepath.Base(file), ".md")
		cleanedName := d.cleanName(noteName)
		availableNotes = append(availableNotes, cleanedName)
		noteFileMap[cleanedName] = file
	}

	log.Printf("Found %d note files in %s", len(mdFiles), d.notesDir)

	// Check each player
	for _, player := range players {
		cleanedPlayerName := d.cleanName(player.Name)

		// Check for exact match first
		if _, exists := noteFileMap[cleanedPlayerName]; !exists {
			// No exact match, try fuzzy matching for suggestions
			matches := fuzzy.Find(cleanedPlayerName, availableNotes)
			suggestion := ""
			if len(matches) > 0 && matches[0].Score <= 10 { // reasonable fuzzy distance
				bestMatch := matches[0].Str
				if fullPath, exists := noteFileMap[bestMatch]; exists {
					suggestion = filepath.Base(fullPath)
				}
			}
			missingPlayers[player.Name] = suggestion
		}
	}

	return missingPlayers, nil
}

// cleanName removes suffixes and strips whitespace, preparing a name for matching.
func (d *DataLoader) cleanName(name string) string {
	cleaned := d.nameCleaner.ReplaceAllString(name, "")
	return strings.TrimSpace(cleaned)
}

// FindLatestLogFile is deprecated - keeping for backwards compatibility
// The new system uses direct channel communication instead of file polling
func (d *DataLoader) FindLatestLogFile() (string, error) {
	return "", fmt.Errorf("timestamp log files are no longer used - system now uses direct IPC")
}

// FindPlayerNoteFile finds a player's note file using direct file system access.
// This is much simpler since we only need exact matches.
func (d *DataLoader) FindPlayerNoteFile(playerName string) (string, error) {
	cleanedPlayerName := d.cleanName(playerName)
	noteFilePath := filepath.Join(d.notesDir, cleanedPlayerName+".md")

	if _, err := os.Stat(noteFilePath); os.IsNotExist(err) {
		return "", fmt.Errorf("no note file found for '%s' at %s", playerName, noteFilePath)
	}

	return noteFilePath, nil
}

// LoadCurrentTeam reads the team's players from status/current_team.txt.
func (d *DataLoader) LoadCurrentTeam() (string, error) {
	content, err := os.ReadFile("status/current_team.txt")
	if err != nil {
		return "Unknown Team", nil // Default instead of error
	}

	if teamName := strings.TrimSpace(string(content)); teamName != "" {
		return teamName, nil
	}
	return "Unknown Team", nil
}

// LoadCurrentPickNum reads the pick number from status/pick.txt.
func (d *DataLoader) LoadCurrentPickNum() (int, error) {
	content, err := os.ReadFile("status/pick.txt")
	if err != nil {
		return 0, fmt.Errorf("could not read pick file: %w", err)
	}

	pickStr := strings.TrimSpace(string(content))
	pick, err := strconv.Atoi(pickStr)
	if err != nil {
		return 0, fmt.Errorf("could not parse pick number from '%s': %w", pickStr, err)
	}

	return pick, nil
}

// BuildAllNotes combines all player notes into one string for GPT analysis.
func (d *DataLoader) BuildAllNotes(players []Player) (string, error) {
	var notes strings.Builder
	notesFound := 0

	for _, player := range players {
		if noteFile, err := d.FindPlayerNoteFile(player.Name); err == nil {
			if content, err := os.ReadFile(noteFile); err == nil {
				notes.WriteString(fmt.Sprintf("---start %s---\n%s\n---end %s---\n\n",
					player.Name, string(content), player.Name))
				notesFound++
			}
		}
	}

	if notesFound == 0 {
		return "", fmt.Errorf("no player notes found")
	}

	log.Printf("Built notes for %d players", notesFound)
	return notes.String(), nil
}
