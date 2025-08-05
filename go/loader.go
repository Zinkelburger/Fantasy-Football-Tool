package main

import (
	"fmt"
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
	notesLoaded bool

	// playerNoteCache maps a cleaned name (from a file or a player) to a note file path.
	// It's pre-populated with all available notes and updated with lookup results.
	// NOTE: This implementation is not thread-safe.
	playerNoteCache map[string]string
}

// NewDataLoader creates a new DataLoader.
func NewDataLoader(notesDir, logsDir string) *DataLoader {
	// This regex finds and removes common suffixes (Jr., Sr., II, etc.) from player names.
	re := regexp.MustCompile(`\s+(?:Jr\.|Sr\.|II|III|IV|V)$`)

	return &DataLoader{
		notesDir:        notesDir,
		logsDir:         logsDir,
		nameCleaner:     re,
		playerNoteCache: make(map[string]string),
		notesLoaded:     false,
	}
}

// PreloadAvailableNotes scans for .md files and caches them for quick lookup.
func (d *DataLoader) PreloadAvailableNotes() error {
	mdFiles, err := filepath.Glob(filepath.Join(d.notesDir, "*.md"))
	if err != nil {
		return fmt.Errorf("cannot read note files: %w", err)
	}

	for _, file := range mdFiles {
		noteName := strings.TrimSuffix(filepath.Base(file), ".md")
		d.playerNoteCache[d.cleanName(noteName)] = file
	}

	d.notesLoaded = true
	log.Printf("Loaded %d player note files", len(d.playerNoteCache))
	return nil
}

// WarmUpCache pre-loads player notes for faster lookup during runtime.
func (d *DataLoader) WarmUpCache(players []Player) {
	foundCount := 0
	for _, player := range players {
		if _, err := d.FindPlayerNoteFile(player.Name); err == nil {
			foundCount++
		}
	}
	log.Printf("Found notes for %d/%d players", foundCount, len(players))
}

// cleanName removes suffixes and strips whitespace, preparing a name for matching.
func (d *DataLoader) cleanName(name string) string {
	cleaned := d.nameCleaner.ReplaceAllString(name, "")
	return strings.TrimSpace(cleaned)
}

// Returns the full path to the file with the highest (most recent) timestamp.
func (d *DataLoader) FindLatestLogFile() (string, error) {
	var latestTimestamp int64 = -1
	var latestFilteredFile string

	dirEntries, err := os.ReadDir(d.logsDir)
	if err != nil {
		return "", fmt.Errorf("could not read logs directory '%s': %w", d.logsDir, err)
	}

	for _, entry := range dirEntries {
		filename := entry.Name()
		if strings.HasPrefix(filename, "filtered_") && strings.HasSuffix(filename, ".csv") {
			timestampStr := strings.TrimSuffix(strings.TrimPrefix(filename, "filtered_"), ".csv")
			unixTimestamp, err := strconv.ParseInt(timestampStr, 10, 64)
			if err != nil {
				log.Printf("Warning: could not parse timestamp from '%s', skipping", filename)
				continue
			}

			if unixTimestamp > latestTimestamp {
				latestTimestamp = unixTimestamp
				latestFilteredFile = filename
			}
		}
	}

	if latestFilteredFile == "" {
		return "", fmt.Errorf("no filtered_<timestamp>.csv files found in '%s'", d.logsDir)
	}

	return filepath.Join(d.logsDir, latestFilteredFile), nil
}

// FindPlayerNoteFile finds a player's note file using exact matching
func (d *DataLoader) FindPlayerNoteFile(playerName string) (string, error) {
	if !d.notesLoaded {
		return "", fmt.Errorf("notes not loaded - call PreloadAvailableNotes() first")
	}

	cleanedPlayerName := d.cleanName(playerName)

	// 1. Check exact match in cache
	if path, exists := d.playerNoteCache[cleanedPlayerName]; exists {
		return path, nil
	}

	// 2. If not in cache, try a fuzzy search against the known note file names.
	// The keys of playerNoteCache initially contain all the cleaned file names.
	cleanedNoteNames := make([]string, 0, len(d.playerNoteCache))
	for name := range d.playerNoteCache {
		cleanedNoteNames = append(cleanedNoteNames, name)
	}

	matches := fuzzy.Find(cleanedPlayerName, cleanedNoteNames)
	if len(matches) > 0 && matches[0].Score <= maxFuzzyDistance {
		bestMatchName := matches[0].Str
		// The path is the value associated with the matched file name key.
		fullPath := d.playerNoteCache[bestMatchName]
		// Cache the result for this specific player name to speed up future lookups.
		d.playerNoteCache[cleanedPlayerName] = fullPath
		log.Printf("Fuzzy matched '%s' -> '%s' and cached result.", playerName, filepath.Base(fullPath))
		return fullPath, nil
		}

	// 3. If still not found, return an error.
	return "", fmt.Errorf("no note file found for '%s'", playerName)
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
		return 0, fmt.Errorf("could not read pick file '%s': %w", filePath, err)
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
