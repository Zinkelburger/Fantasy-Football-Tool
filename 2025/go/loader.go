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
	settings    *Settings
}

// NewDataLoader creates a new DataLoader.
func NewDataLoader(notesDir, logsDir string) *DataLoader {
	// This regex finds and removes common suffixes (Jr., Sr., II, etc.) from player names.
	re := regexp.MustCompile(`\s+(?:Jr\.|Sr\.|II|III|IV|V)$`)

	return &DataLoader{
		notesDir:    notesDir,
		logsDir:     logsDir,
		nameCleaner: re,
		settings:    nil, // Will be set later
	}
}

// SetSettings sets the settings for the data loader
func (d *DataLoader) SetSettings(settings *Settings) {
	d.settings = settings
}

// getPlayerDataFilename returns the appropriate CSV filename based on current settings
func (d *DataLoader) getPlayerDataFilename() string {
	if d.settings == nil {
		// Default fallback
		return "players.csv"
	}
	
	// Convert scoring format to filename format
	var formatStr string
	switch d.settings.ScoringFormat {
	case "STD":
		formatStr = "std"
	case "0.5PPR":
		formatStr = "0.5_ppr"
	case "PPR":
		formatStr = "ppr"
	default:
		formatStr = "std" // Default to standard
	}
	
	// Check if we have platform-specific files (JuiceBoxOne's rankings)
	var platformPrefix string
	switch d.settings.Platform {
	case "ESPN":
		platformPrefix = "ESPN "
	case "Sleeper":
		platformPrefix = "Sleeper "
	default:
		platformPrefix = "ESPN " // Default to ESPN
	}
	
	// Convert format for JuiceBoxOne's file naming convention
	var juiceBoxFormat string
	switch d.settings.ScoringFormat {
	case "STD":
		juiceBoxFormat = "Standard"
	case "0.5PPR":
		juiceBoxFormat = "Half PPR"
	case "PPR":
		juiceBoxFormat = "PPR"
	default:
		juiceBoxFormat = "Standard"
	}
	
	// Try platform-specific file first (JuiceBoxOne's rankings)
	platformFile := "JuiceBoxOne's 2025 Abusing Draft Rankings - " + platformPrefix + juiceBoxFormat + ".csv"
	
	// If platform-specific file exists, use it; otherwise fallback to depth files
	if _, err := os.Stat(getDataPath(platformFile)); err == nil {
		log.Printf("Using platform-specific file: %s", platformFile)
		return platformFile
	} else if _, err := os.Stat(platformFile); err == nil {
		log.Printf("Using platform-specific file: %s", platformFile)
		return platformFile
	}
	
	// Fallback to the original depth files
	fallbackFile := formatStr + "_with_depth.csv"
	log.Printf("Using fallback file: %s", fallbackFile)
	return fallbackFile
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
	content, err := os.ReadFile(getWritablePath("status/current_team.txt"))
	if err != nil {
		return "Unknown Team", nil // Default instead of error
	}

	if teamName := strings.TrimSpace(string(content)); teamName != "" {
		return teamName, nil
	}
	return "Unknown Team", nil
}

// LoadCurrentTeamPlayers reads the current team players from status/current_team.txt.
// Expects one player name per line. If the file contains just a team name, returns empty slice.
func (d *DataLoader) LoadCurrentTeamPlayers() ([]Player, error) {
	content, err := os.ReadFile(getWritablePath("status/current_team.txt"))
	if err != nil {
		return []Player{}, nil // Return empty slice instead of error
	}

	lines := strings.Split(string(content), "\n")
	var teamPlayers []Player
	
	// Load all available players first to match against
	primaryFile := d.getPlayerDataFilename()
	playerDataFiles := []string{
		getDataPath(primaryFile), // Settings-based file first
		primaryFile,              // Direct path
		getDataPath("players.csv"), // Legacy fallback
		"players.csv",              // Direct legacy fallback
		"go/players.csv",           // Explicit go directory fallback
	}
	
	var allPlayers []Player
	for _, filename := range playerDataFiles {
		if _, statErr := os.Stat(filename); statErr == nil {
			allPlayers, err = LoadPlayers(filename)
			if err == nil {
				break
			}
		}
	}
	
	if err != nil || len(allPlayers) == 0 {
		return []Player{}, fmt.Errorf("could not load player data: %w", err)
	}
	
	// Create a map for quick player lookup
	playerMap := make(map[string]Player)
	for _, player := range allPlayers {
		playerMap[strings.TrimSpace(player.Name)] = player
	}
	
	// Process each line from current_team.txt
	for _, line := range lines {
		playerName := strings.TrimSpace(line)
		if playerName == "" || playerName == "My Team" {
			continue // Skip empty lines and default team name
		}
		
		// Skip position headers (lines that start and end with "===")
		if strings.HasPrefix(playerName, "===") && strings.HasSuffix(playerName, "===") {
			continue
		}
		
		// Look up the player in our data
		if player, found := playerMap[playerName]; found {
			teamPlayers = append(teamPlayers, player)
		} else {
			// If not found, create a basic player entry
			teamPlayers = append(teamPlayers, Player{
				Name:  playerName,
				Team:  "Unknown",
				Pos:   "Unknown",
				Depth: "Unknown",
				Rank:  "Unknown",
				Note:  "Player not in database",
			})
		}
	}
	
	return teamPlayers, nil
}

// LoadCurrentTeamPlayersFromNames loads player data for the given player names
func (d *DataLoader) LoadCurrentTeamPlayersFromNames(playerNames []string) ([]Player, error) {
	// Load all available players first to match against
	primaryFile := d.getPlayerDataFilename()
	playerDataFiles := []string{
		getDataPath(primaryFile), // Settings-based file first
		primaryFile,              // Direct path
		getDataPath("players.csv"), // Legacy fallback
		"players.csv",              // Direct legacy fallback
		"go/players.csv",           // Explicit go directory fallback
	}
	
	var allPlayers []Player
	var err error
	for _, filename := range playerDataFiles {
		if _, statErr := os.Stat(filename); statErr == nil {
			allPlayers, err = LoadPlayers(filename)
			if err == nil {
				break
			}
		}
	}
	
	if err != nil || len(allPlayers) == 0 {
		return []Player{}, fmt.Errorf("could not load player data: %w", err)
	}
	
	// Create a map for quick player lookup
	playerMap := make(map[string]Player)
	for _, player := range allPlayers {
		playerMap[strings.TrimSpace(player.Name)] = player
	}
	
	// Find matching players
	var teamPlayers []Player
	for _, playerName := range playerNames {
		cleanName := strings.TrimSpace(playerName)
		if cleanName == "" {
			continue
		}
		
		if player, exists := playerMap[cleanName]; exists {
			teamPlayers = append(teamPlayers, player)
		}
	}
	
	return teamPlayers, nil
}

// LoadCurrentPickNum reads the pick number from status/pick.txt.
func (d *DataLoader) LoadCurrentPickNum() (int, error) {
	content, err := os.ReadFile(getWritablePath("status/pick.txt"))
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

// BuildAllNotes combines player notes into one string for GPT analysis.
// Typically called with the top 15 players to keep the prompt manageable.
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

	log.Printf("Built notes for %d players (limited to top players for optimal LLM performance)", notesFound)
	return notes.String(), nil
}

// WriteDraftStatusToNote writes the draft status to a player's note file
func (d *DataLoader) WriteDraftStatusToNote(playerName string, status string) error {
	noteFile, err := d.FindPlayerNoteFile(playerName)
	if err != nil {
		return fmt.Errorf("could not find note file for %s: %w", playerName, err)
	}

	content, err := os.ReadFile(noteFile)
	if err != nil {
		return fmt.Errorf("could not read note file for %s: %w", playerName, err)
	}

	contentStr := string(content)
	
	// Remove existing draft status line
	lines := strings.Split(contentStr, "\n")
	var filteredLines []string
	for _, line := range lines {
		if !strings.HasPrefix(line, "# To Draft:") {
			filteredLines = append(filteredLines, line)
		}
	}
	
	// Add new draft status if not empty
	if status != "" {
		// Remove trailing empty lines
		for len(filteredLines) > 0 && strings.TrimSpace(filteredLines[len(filteredLines)-1]) == "" {
			filteredLines = filteredLines[:len(filteredLines)-1]
		}
		filteredLines = append(filteredLines, "", fmt.Sprintf("# To Draft: %s", status))
	}
	
	newContent := strings.Join(filteredLines, "\n")
	return os.WriteFile(noteFile, []byte(newContent), 0644)
}

// LoadDraftStatusFromNote loads the draft status from a player's note file
func (d *DataLoader) LoadDraftStatusFromNote(playerName string) string {
	noteFile, err := d.FindPlayerNoteFile(playerName)
	if err != nil {
		return ""
	}

	content, err := os.ReadFile(noteFile)
	if err != nil {
		return ""
	}

	lines := strings.Split(string(content), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "# To Draft:") {
			// Extract the emoji after "# To Draft: "
			if len(line) > 12 {
				status := strings.TrimSpace(line[12:])
				if status == "✅" || status == "❌" {
					return status
				}
			}
		}
	}
	return ""
}

// LoadAllPlayers loads all players from the player data files
func (d *DataLoader) LoadAllPlayers() ([]Player, error) {
	// Try different player data file locations
	primaryFile := d.getPlayerDataFilename()
	playerDataFiles := []string{
		getDataPath(primaryFile), // Settings-based file first
		primaryFile,              // Direct path
		getDataPath("players.csv"), // Legacy fallback
		"players.csv",              // Direct legacy fallback
		"go/players.csv",           // Explicit go directory fallback
	}
	
	for _, filename := range playerDataFiles {
		if _, err := os.Stat(filename); err == nil {
			players, err := LoadPlayers(filename)
			if err == nil {
				return players, nil
			}
		}
	}
	
	return nil, fmt.Errorf("could not load player data from any available file")
}
