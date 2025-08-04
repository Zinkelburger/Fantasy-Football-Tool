package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/sahilm/fuzzy"
)

// A reasonable value for fuzzy matching distance; adjust as needed.
const maxFuzzyDistance = 5

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

// PreloadAvailableNotes scans the notes directory and indexes existing files into the cache.
// This is a prerequisite for any file finding operations.
func (d *DataLoader) PreloadAvailableNotes() error {
	log.Println("Scanning for available note files...")
	mdFiles, err := filepath.Glob(filepath.Join(d.notesDir, "*.md"))
	if err != nil {
		return fmt.Errorf("cannot read player note files: %w", err)
	}

	for _, file := range mdFiles {
		base := filepath.Base(file)
		noteName := strings.TrimSuffix(base, ".md")
		cleanedName := d.cleanName(noteName)
		d.playerNoteCache[cleanedName] = file
	}

	d.notesLoaded = true
	log.Printf("Finished scanning. Indexed %d available note files into the cache.", len(d.playerNoteCache))
	return nil
}

// WarmUpCache proactively populates the cache for a given list of players.
func (d *DataLoader) WarmUpCache(players []Player) {
	log.Printf("Warming up cache for %d players...", len(players))
	var foundCount int
	for _, player := range players {
		if _, err := d.FindPlayerNoteFile(player.Name); err == nil {
			foundCount++
		}
	}
	log.Printf("Finished warming up cache. Found notes for %d of %d players.", foundCount, len(players))
}

// cleanName removes suffixes and strips whitespace, preparing a name for matching.
func (d *DataLoader) cleanName(name string) string {
	cleaned := d.nameCleaner.ReplaceAllString(name, "")
	return strings.TrimSpace(cleaned)
}

// FindLatestLogFile scans the logs directory and returns the path to the most recent file.
func (d *DataLoader) FindLatestLogFile() (string, error) {
	var latestTime int64 = -1
	var latestFile string

	files, err := os.ReadDir(d.logsDir)
	if err != nil {
		return "", fmt.Errorf("could not read logs directory '%s': %w", d.logsDir, err)
	}

	for _, file := range files {
		filename := file.Name()
		if strings.HasPrefix(filename, "filtered_") && strings.HasSuffix(filename, ".csv") {
			tsString := strings.TrimSuffix(strings.TrimPrefix(filename, "filtered_"), ".csv")
			unixTime, err := strconv.ParseInt(tsString, 10, 64)
			if err != nil {
				log.Printf("Warning: could not parse timestamp from '%s', skipping", filename)
				continue
			}

			if unixTime > latestTime {
				latestTime = unixTime
				latestFile = filename
			}
		}
	}

	if latestFile == "" {
		return "", fmt.Errorf("no filtered log files found in '%s'", d.logsDir)
	}

	return filepath.Join(d.logsDir, latestFile), nil
}

// FindPlayerNoteFile finds a player's note file, using a cache to speed up lookups.
// If a player isn't in the cache, it performs a search and updates the cache.
func (d *DataLoader) FindPlayerNoteFile(playerName string) (string, error) {
	if !d.notesLoaded {
		return "", fmt.Errorf("error: available notes not loaded. Call PreloadAvailableNotes() first")
	}

	cleanedPlayerName := d.cleanName(playerName)

	// 1. Check the cache. This finds players who have already been looked up,
	// as well as players whose names are an exact match to a cleaned file name.
	if path, ok := d.playerNoteCache[cleanedPlayerName]; ok {
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

// LoadCurrentTeam reads the current team name from status/current_team.txt.
func (d *DataLoader) LoadCurrentTeam() (string, error) {
	filePath := "status/current_team.txt"
	content, err := os.ReadFile(filePath)
	if err != nil {
		return "", fmt.Errorf("could not read team file '%s': %w", filePath, err)
	}

	teamName := strings.TrimSpace(string(content))
	if teamName == "" {
		return "", fmt.Errorf("team file '%s' is empty", filePath)
	}

	return teamName, nil
}

Of course. Here is the modified Go code with the two new functions, LoadCurrentPick and LoadCurrentTeam, added to the DataLoader.

These functions read an integer from current_status/pick.txt and a string from status/current_team.txt, respectively. They include error handling for file access and content parsing.
Go

package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/sahilm/fuzzy"
)

// A reasonable value for fuzzy matching distance; adjust as needed.
const maxFuzzyDistance = 5

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

// PreloadAvailableNotes scans the notes directory and indexes existing files into the cache.
// This is a prerequisite for any file finding operations.
func (d *DataLoader) PreloadAvailableNotes() error {
	log.Println("Scanning for available note files...")
	mdFiles, err := filepath.Glob(filepath.Join(d.notesDir, "*.md"))
	if err != nil {
		return fmt.Errorf("cannot read player note files: %w", err)
	}

	for _, file := range mdFiles {
		base := filepath.Base(file)
		noteName := strings.TrimSuffix(base, ".md")
		cleanedName := d.cleanName(noteName)
		d.playerNoteCache[cleanedName] = file
	}

	d.notesLoaded = true
	log.Printf("Finished scanning. Indexed %d available note files into the cache.", len(d.playerNoteCache))
	return nil
}

// WarmUpCache proactively populates the cache for a given list of players.
func (d *DataLoader) WarmUpCache(players []Player) {
	log.Printf("Warming up cache for %d players...", len(players))
	var foundCount int
	for _, player := range players {
		if _, err := d.FindPlayerNoteFile(player.Name); err == nil {
			foundCount++
		}
	}
	log.Printf("Finished warming up cache. Found notes for %d of %d players.", foundCount, len(players))
}

// cleanName removes suffixes and strips whitespace, preparing a name for matching.
func (d *DataLoader) cleanName(name string) string {
	cleaned := d.nameCleaner.ReplaceAllString(name, "")
	return strings.TrimSpace(cleaned)
}

// FindLatestLogFile scans the logs directory and returns the path to the most recent file.
func (d *DataLoader) FindLatestLogFile() (string, error) {
	var latestTime int64 = -1
	var latestFile string

	files, err := os.ReadDir(d.logsDir)
	if err != nil {
		return "", fmt.Errorf("could not read logs directory '%s': %w", d.logsDir, err)
	}

	for _, file := range files {
		filename := file.Name()
		if strings.HasPrefix(filename, "filtered_") && strings.HasSuffix(filename, ".csv") {
			tsString := strings.TrimSuffix(strings.TrimPrefix(filename, "filtered_"), ".csv")
			unixTime, err := strconv.ParseInt(tsString, 10, 64)
			if err != nil {
				log.Printf("Warning: could not parse timestamp from '%s', skipping", filename)
				continue
			}

			if unixTime > latestTime {
				latestTime = unixTime
				latestFile = filename
			}
		}
	}

	if latestFile == "" {
		return "", fmt.Errorf("no filtered log files found in '%s'", d.logsDir)
	}

	return filepath.Join(d.logsDir, latestFile), nil
}

// LoadCurrentTeam reads the current team name from status/current_team.txt.
func (d *DataLoader) LoadCurrentTeam() (string, error) {
	filePath := "status/current_team.txt"
	content, err := os.ReadFile(filePath)
	if err != nil {
		return "", fmt.Errorf("could not read team file '%s': %w", filePath, err)
	}

	teamName := strings.TrimSpace(string(content))
	if teamName == "" {
		return "", fmt.Errorf("team file '%s' is empty", filePath)
	}

	return teamName, nil
}

// LoadCurrentPick reads the current pick number from current_status/pick.txt.
func (d *DataLoader) LoadCurrentPickNum() (int, error) {
	filePath := "current_status/pick.txt"
	content, err := os.ReadFile(filePath)
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

// BuildAllNotes finds the note file for each player, reads the content,
// and concatenates them into a single string with demarcations.
func (d *DataLoader) BuildAllNotes(players []Player) (string, error) {
	var allNotesBuilder strings.Builder

	for _, player := range players {
		noteFile, err := d.FindPlayerNoteFile(player.Name)
		if err != nil {
			log.Printf("Skipping player %s: could not find note file: %v", player.Name, err)
			continue
		}

		noteContent, err := os.ReadFile(noteFile)
		if err != nil {
			log.Printf("Skipping player %s: could not read note file: %v", player.Name, err)
			continue
		}

		// Use demarcations to separate notes for the prompt context.
		allNotesBuilder.WriteString(fmt.Sprintf("---start %s---\n", player.Name))
		allNotesBuilder.WriteString(string(noteContent))
		allNotesBuilder.WriteString(fmt.Sprintf("\n---end %s---\n\n", player.Name))
	}

	allNotes := allNotesBuilder.String()
	if allNotes == "" {
		return "", fmt.Errorf("no player notes could be found or read")
	}

	return allNotes, nil
}