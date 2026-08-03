package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Test helper to create a temporary CSV file
func createTestCSV(t *testing.T, content string) (string, func()) {
	t.Helper()

	tempDir, err := os.MkdirTemp("", "players_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	csvPath := filepath.Join(tempDir, "test_players.csv")
	err = os.WriteFile(csvPath, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test CSV: %v", err)
	}

	cleanup := func() {
		os.RemoveAll(tempDir)
	}

	return csvPath, cleanup
}

// Test helper to create a temporary analysis directory with note files
func createTestAnalysisDir(t *testing.T, players []string) (string, func()) {
	t.Helper()

	tempDir, err := os.MkdirTemp("", "analysis_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	analysisDir := filepath.Join(tempDir, "analysis")
	err = os.MkdirAll(analysisDir, 0755)
	if err != nil {
		t.Fatalf("Failed to create analysis dir: %v", err)
	}

	// Create note files for each player
	for _, playerName := range players {
		noteContent := `# ` + playerName + `

## Analysis
This is a test analysis for ` + playerName + `. The player shows great potential and could be a valuable addition to any fantasy team.

## Projection
Expected to perform well this season.
`
		notePath := filepath.Join(analysisDir, playerName+".md")
		err = os.WriteFile(notePath, []byte(noteContent), 0644)
		if err != nil {
			t.Fatalf("Failed to write note file for %s: %v", playerName, err)
		}
	}

	// Change to temp directory so analysis files can be found
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}

	err = os.Chdir(tempDir)
	if err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	cleanup := func() {
		os.Chdir(originalDir)
		os.RemoveAll(tempDir)
	}

	return analysisDir, cleanup
}

func TestLoadPlayers_ValidCSV(t *testing.T) {
	csvContent := `Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank
1.5,Patrick Mahomes,KC,10,QB,2,1
5.2,Travis Kelce,KC,10,TE,6,5
8.1,Tyreek Hill,MIA,12,WR,9,8`

	csvPath, cleanup := createTestCSV(t, csvContent)
	defer cleanup()

	players, err := LoadPlayers(csvPath)
	if err != nil {
		t.Fatalf("LoadPlayers failed: %v", err)
	}

	expectedCount := 3
	if len(players) != expectedCount {
		t.Errorf("Expected %d players, got %d", expectedCount, len(players))
	}

	// Test first player
	if players[0].Name != "Patrick Mahomes" {
		t.Errorf("Expected first player name 'Patrick Mahomes', got '%s'", players[0].Name)
	}

	if players[0].Team != "KC" {
		t.Errorf("Expected first player team 'KC', got '%s'", players[0].Team)
	}

	if players[0].Pos != "QB" {
		t.Errorf("Expected first player position 'QB', got '%s'", players[0].Pos)
	}

	if players[0].Rank != "1.5" {
		t.Errorf("Expected first player rank '1.5', got '%s'", players[0].Rank)
	}

	if players[0].Depth != "QB" {
		t.Errorf("Expected first player depth 'QB', got '%s'", players[0].Depth)
	}

	// Test sorting - players should be sorted by rank (Patrick Mahomes first with 1.5)
	if players[0].Name != "Patrick Mahomes" {
		t.Errorf("Expected first player to be Patrick Mahomes (lowest rank), got '%s'", players[0].Name)
	}

	if players[1].Name != "Travis Kelce" {
		t.Errorf("Expected second player to be Travis Kelce, got '%s'", players[1].Name)
	}

	if players[2].Name != "Tyreek Hill" {
		t.Errorf("Expected third player to be Tyreek Hill, got '%s'", players[2].Name)
	}
}

func TestLoadPlayers_FileNotFound(t *testing.T) {
	_, err := LoadPlayers("nonexistent.csv")
	if err == nil {
		t.Error("Expected error when loading nonexistent file")
	}
}

func TestLoadPlayers_InvalidCSV(t *testing.T) {
	csvContent := `Name,Team,Pos
Patrick Mahomes,KC`  // Missing columns

	csvPath, cleanup := createTestCSV(t, csvContent)
	defer cleanup()

	_, err := LoadPlayers(csvPath)
	if err == nil {
		t.Error("Expected error when loading CSV with insufficient columns")
	}
}

func TestLoadPlayers_EmptyFile(t *testing.T) {
	csvPath, cleanup := createTestCSV(t, "")
	defer cleanup()

	_, err := LoadPlayers(csvPath)
	if err == nil {
		t.Error("Expected error when loading empty CSV file")
	}
	
	// Verify it's the specific empty file error
	expectedError := "CSV file is empty"
	if !strings.Contains(err.Error(), expectedError) {
		t.Errorf("Expected error message to contain '%s', got: %v", expectedError, err)
	}
}

func TestLoadPlayers_HeaderOnly(t *testing.T) {
	csvContent := `Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank`

	csvPath, cleanup := createTestCSV(t, csvContent)
	defer cleanup()

	players, err := LoadPlayers(csvPath)
	if err != nil {
		t.Fatalf("LoadPlayers failed: %v", err)
	}

	if len(players) != 0 {
		t.Errorf("Expected 0 players from header-only file, got %d", len(players))
	}
}

func TestLoadTruncatedNote_FileExists(t *testing.T) {
	_, cleanup := createTestAnalysisDir(t, []string{"Patrick Mahomes"})
	defer cleanup()

	note := loadTruncatedNote("Patrick Mahomes")

	if note == "No note" || note == "Error loading" || note == "No content" {
		t.Errorf("Expected valid note content, got '%s'", note)
	}

	// Should contain "Expected to perform well this season" (the last line from our test file)
	if !strings.Contains(note, "Expected to perform well this season") {
		t.Errorf("Expected note to contain last line content, got '%s'", note)
	}

	// Should be around 40 characters or less
	if len(note) > 45 {
		t.Errorf("Expected note to be truncated to around 40 chars, got %d chars: '%s'", len(note), note)
	}
}

func TestLoadTruncatedNote_FileNotFound(t *testing.T) {
	note := loadTruncatedNote("Nonexistent Player")

	if note != "No note" {
		t.Errorf("Expected 'No note' for nonexistent player, got '%s'", note)
	}
}

func TestLoadTruncatedNote_NoAnalysisSection(t *testing.T) {
	// Create a note file without an Analysis section
	tempDir, err := os.MkdirTemp("", "note_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	analysisDir := filepath.Join(tempDir, "analysis")
	err = os.MkdirAll(analysisDir, 0755)
	if err != nil {
		t.Fatalf("Failed to create analysis dir: %v", err)
	}

	// Create a note file without Analysis section
	noteContent := `# Test Player

This is just a header without analysis section.
`
	notePath := filepath.Join(analysisDir, "Test Player.md")
	err = os.WriteFile(notePath, []byte(noteContent), 0644)
	if err != nil {
		t.Fatalf("Failed to write note file: %v", err)
	}

	// Change to temp directory
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}
	defer os.Chdir(originalDir)

	err = os.Chdir(tempDir)
	if err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	note := loadTruncatedNote("Test Player")

	// Now it should return the last meaningful line, not "No analysis"
	if !strings.Contains(note, "This is just a header without...") {
		t.Errorf("Expected note to contain last line content, got '%s'", note)
	}
}

func TestLoadTruncatedNote_ShortAnalysis(t *testing.T) {
	// Create a note file with short analysis that shouldn't be truncated
	tempDir, err := os.MkdirTemp("", "note_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	analysisDir := filepath.Join(tempDir, "analysis")
	err = os.MkdirAll(analysisDir, 0755)
	if err != nil {
		t.Fatalf("Failed to create analysis dir: %v", err)
	}

	// Create a note file with short analysis
	noteContent := `# Test Player

## Analysis
Short note.
`
	notePath := filepath.Join(analysisDir, "Test Player.md")
	err = os.WriteFile(notePath, []byte(noteContent), 0644)
	if err != nil {
		t.Fatalf("Failed to write note file: %v", err)
	}

	// Change to temp directory
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}
	defer os.Chdir(originalDir)

	err = os.Chdir(tempDir)
	if err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	note := loadTruncatedNote("Test Player")

	expected := "Short note."
	if note != expected {
		t.Errorf("Expected '%s' for short analysis, got '%s'", expected, note)
	}
}

func TestPlayerStruct(t *testing.T) {
	player := Player{
		Name:    "Test Player",
		Team:    "TST",
		Pos:     "QB",
		Depth:   "1",
		Rank:    "1.5",
		Note:    "Test note",
		rankNum: 1,
	}

	// Test all fields
	if player.Name != "Test Player" {
		t.Errorf("Expected Name 'Test Player', got '%s'", player.Name)
	}

	if player.Team != "TST" {
		t.Errorf("Expected Team 'TST', got '%s'", player.Team)
	}

	if player.Pos != "QB" {
		t.Errorf("Expected Pos 'QB', got '%s'", player.Pos)
	}

	if player.Depth != "1" {
		t.Errorf("Expected Depth '1', got '%s'", player.Depth)
	}

	if player.Rank != "1.5" {
		t.Errorf("Expected Rank '1.5', got '%s'", player.Rank)
	}

	if player.Note != "Test note" {
		t.Errorf("Expected Note 'Test note', got '%s'", player.Note)
	}

	if player.rankNum != 1 {
		t.Errorf("Expected rankNum 1, got %d", player.rankNum)
	}
}

func TestLoadPlayers_Sorting(t *testing.T) {
	csvContent := `Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank
8.1,Tyreek Hill,MIA,12,WR,9,8
1.5,Patrick Mahomes,KC,10,QB,2,1
5.2,Travis Kelce,KC,10,TE,6,5
3.8,Josh Allen,BUF,7,QB,4,3`

	csvPath, cleanup := createTestCSV(t, csvContent)
	defer cleanup()

	players, err := LoadPlayers(csvPath)
	if err != nil {
		t.Fatalf("LoadPlayers failed: %v", err)
	}

	// Verify sorting by rank (ascending)
	expectedOrder := []string{"Patrick Mahomes", "Josh Allen", "Travis Kelce", "Tyreek Hill"}
	expectedRanks := []string{"1.5", "3.8", "5.2", "8.1"}

	for i, expectedName := range expectedOrder {
		if players[i].Name != expectedName {
			t.Errorf("Expected player at index %d to be '%s', got '%s'", i, expectedName, players[i].Name)
		}

		if players[i].Rank != expectedRanks[i] {
			t.Errorf("Expected rank at index %d to be '%s', got '%s'", i, expectedRanks[i], players[i].Rank)
		}
	}
}

func TestLoadPlayers_NonNumericRank(t *testing.T) {
	csvContent := `Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank
invalid_rank,Patrick Mahomes,KC,10,QB,2,1
5.2,Travis Kelce,KC,10,TE,6,5`

	csvPath, cleanup := createTestCSV(t, csvContent)
	defer cleanup()

	players, err := LoadPlayers(csvPath)
	if err != nil {
		t.Fatalf("LoadPlayers failed: %v", err)
	}

	// Should still load players even with invalid rank
	if len(players) != 2 {
		t.Errorf("Expected 2 players, got %d", len(players))
	}

	// Player with invalid rank should have rankNum of 0 and be sorted first
	if players[0].Name != "Patrick Mahomes" {
		t.Errorf("Expected Patrick Mahomes (invalid rank) to be sorted first, got '%s'", players[0].Name)
	}

	if players[0].rankNum != 0 {
		t.Errorf("Expected rankNum to be 0 for invalid rank, got %d", players[0].rankNum)
	}
}
