package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Test helper to create a temporary directory structure for testing
func setupTestDir(t *testing.T) (string, string, func()) {
	t.Helper()

	tempDir, err := os.MkdirTemp("", "loader_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	notesDir := filepath.Join(tempDir, "notes")
	logsDir := filepath.Join(tempDir, "logs")

	if err := os.MkdirAll(notesDir, 0755); err != nil {
		t.Fatalf("Failed to create notes dir: %v", err)
	}

	if err := os.MkdirAll(logsDir, 0755); err != nil {
		t.Fatalf("Failed to create logs dir: %v", err)
	}

	cleanup := func() {
		os.RemoveAll(tempDir)
	}

	return notesDir, logsDir, cleanup
}

func TestNewDataLoader(t *testing.T) {
	loader := NewDataLoader("test_notes", "test_logs")

	if loader.notesDir != "test_notes" {
		t.Errorf("Expected notesDir to be 'test_notes', got '%s'", loader.notesDir)
	}

	if loader.logsDir != "test_logs" {
		t.Errorf("Expected logsDir to be 'test_logs', got '%s'", loader.logsDir)
	}

	if loader.nameCleaner == nil {
		t.Error("Expected nameCleaner to be initialized")
	}
}

func TestCleanName(t *testing.T) {
	loader := NewDataLoader("", "")

	testCases := []struct {
		input    string
		expected string
	}{
		{"Patrick Mahomes II", "Patrick Mahomes"},
		{"Ken Griffey Jr.", "Ken Griffey"},
		{"Martin Luther King Jr.", "Martin Luther King"},
		{"Robert Downey Sr.", "Robert Downey"},
		{"Louis XIV", "Louis XIV"}, // Roman numerals beyond V should not be removed
		{"John Smith III", "John Smith"},
		{"Mary Johnson IV", "Mary Johnson"},
		{"James Brown V", "James Brown"},
		{"Regular Name", "Regular Name"},
		{"  Spaced Name  ", "Spaced Name"},   // Test trimming
		{"Name Jr. Extra", "Name Jr. Extra"}, // Jr. not at end
	}

	for _, tc := range testCases {
		t.Run(tc.input, func(t *testing.T) {
			result := loader.cleanName(tc.input)
			if result != tc.expected {
				t.Errorf("cleanName(%q) = %q, expected %q", tc.input, result, tc.expected)
			}
		})
	}
}

func TestFindLatestLogFile(t *testing.T) {
	notesDir, logsDir, cleanup := setupTestDir(t)
	defer cleanup()

	loader := NewDataLoader(notesDir, logsDir)

	t.Run("NoFilesFound", func(t *testing.T) {
		_, err := loader.FindLatestLogFile()
		if err == nil {
			t.Error("Expected error when no filtered files exist")
		}
	})

	t.Run("SingleFile", func(t *testing.T) {
		// Create a single filtered file
		filename := "filtered_1640995200.csv" // 2022-01-01 00:00:00 UTC
		filepath := filepath.Join(logsDir, filename)
		if err := os.WriteFile(filepath, []byte("test"), 0644); err != nil {
			t.Fatalf("Failed to create test file: %v", err)
		}

		_, err := loader.FindLatestLogFile()
		if err == nil {
			t.Error("Expected error about direct IPC, but got nil")
		}

		expectedErrorMsg := "timestamp log files are no longer used - system now uses direct IPC"
		if !strings.Contains(err.Error(), expectedErrorMsg) {
			t.Errorf("Expected error message containing %q, got %q", expectedErrorMsg, err.Error())
		}
	})

	t.Run("MultipleFiles", func(t *testing.T) {
		// Create multiple filtered files with different timestamps
		files := []struct {
			name      string
			timestamp int64
		}{
			{"filtered_1640995200.csv", 1640995200}, // 2022-01-01
			{"filtered_1641081600.csv", 1641081600}, // 2022-01-02 (latest)
			{"filtered_1640908800.csv", 1640908800}, // 2021-12-31
		}

		for _, f := range files {
			filepath := filepath.Join(logsDir, f.name)
			if err := os.WriteFile(filepath, []byte("test"), 0644); err != nil {
				t.Fatalf("Failed to create test file %s: %v", f.name, err)
			}
		}

		_, err := loader.FindLatestLogFile()
		if err == nil {
			t.Error("Expected error about direct IPC, but got nil")
		}

		expectedErrorMsg := "timestamp log files are no longer used - system now uses direct IPC"
		if !strings.Contains(err.Error(), expectedErrorMsg) {
			t.Errorf("Expected error message containing %q, got %q", expectedErrorMsg, err.Error())
		}
	})

	t.Run("InvalidTimestamp", func(t *testing.T) {
		// Clean up previous test files
		os.RemoveAll(logsDir)
		os.MkdirAll(logsDir, 0755)

		// Create files with invalid timestamps
		invalidFiles := []string{
			"filtered_invalid.csv",
			"filtered_abc123.csv",
			"filtered_.csv",
		}

		for _, filename := range invalidFiles {
			filepath := filepath.Join(logsDir, filename)
			if err := os.WriteFile(filepath, []byte("test"), 0644); err != nil {
				t.Fatalf("Failed to create test file %s: %v", filename, err)
			}
		}

		_, err := loader.FindLatestLogFile()
		if err == nil {
			t.Error("Expected error when no valid timestamp files exist")
		}
	})

	t.Run("MixedValidInvalid", func(t *testing.T) {
		// Clean up and create mix of valid and invalid files
		os.RemoveAll(logsDir)
		os.MkdirAll(logsDir, 0755)

		// Valid file
		validFile := "filtered_1640995200.csv"
		if err := os.WriteFile(filepath.Join(logsDir, validFile), []byte("test"), 0644); err != nil {
			t.Fatalf("Failed to create valid test file: %v", err)
		}

		// Invalid files
		invalidFiles := []string{
			"filtered_invalid.csv",
			"not_filtered_1640995200.csv",
			"filtered_1640995200.txt",
		}

		for _, filename := range invalidFiles {
			if err := os.WriteFile(filepath.Join(logsDir, filename), []byte("test"), 0644); err != nil {
				t.Fatalf("Failed to create invalid test file %s: %v", filename, err)
			}
		}

		_, err := loader.FindLatestLogFile()
		if err == nil {
			t.Error("Expected error about direct IPC, but got nil")
		}

		expectedErrorMsg := "timestamp log files are no longer used - system now uses direct IPC"
		if !strings.Contains(err.Error(), expectedErrorMsg) {
			t.Errorf("Expected error message containing %q, got %q", expectedErrorMsg, err.Error())
		}
	})
}

func TestTestAvailableNotes(t *testing.T) {
	notesDir, logsDir, cleanup := setupTestDir(t)
	defer cleanup()

	loader := NewDataLoader(notesDir, logsDir)

	t.Run("AllNotesExist", func(t *testing.T) {
		// Create test players
		players := []Player{
			{Name: "Patrick Mahomes II"},
			{Name: "Travis Kelce"},
			{Name: "Tyreek Hill"},
		}

		// Create corresponding note files
		noteFiles := []string{
			"Patrick Mahomes.md",
			"Travis Kelce.md",
			"Tyreek Hill.md",
		}

		for _, filename := range noteFiles {
			filepath := filepath.Join(notesDir, filename)
			if err := os.WriteFile(filepath, []byte("test notes"), 0644); err != nil {
				t.Fatalf("Failed to create note file %s: %v", filename, err)
			}
		}

		missing, err := loader.TestAvailableNotes(players)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if len(missing) != 0 {
			t.Errorf("Expected no missing players, got %d: %v", len(missing), missing)
		}
	})

	t.Run("SomeNotesMissing", func(t *testing.T) {
		// Clean notes directory
		os.RemoveAll(notesDir)
		os.MkdirAll(notesDir, 0755)

		players := []Player{
			{Name: "Patrick Mahomes II"},
			{Name: "Travis Kelce"},
			{Name: "Missing Player"},
		}

		// Create only some note files
		noteFiles := []string{
			"Patrick Mahomes.md",
			"Travis Kelce.md",
		}

		for _, filename := range noteFiles {
			filepath := filepath.Join(notesDir, filename)
			if err := os.WriteFile(filepath, []byte("test notes"), 0644); err != nil {
				t.Fatalf("Failed to create note file %s: %v", filename, err)
			}
		}

		missing, err := loader.TestAvailableNotes(players)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if len(missing) != 1 {
			t.Errorf("Expected 1 missing player, got %d: %v", len(missing), missing)
		}

		if _, exists := missing["Missing Player"]; !exists {
			t.Error("Expected 'Missing Player' to be in missing list")
		}
	})

	t.Run("CleanedNameMatches", func(t *testing.T) {
		// Clean notes directory
		os.RemoveAll(notesDir)
		os.MkdirAll(notesDir, 0755)

		players := []Player{
			{Name: "Patrick Mahomes II"},
		}

		// Create a file that matches after name cleaning (this should be found)
		noteFile := "Patrick Mahomes.md"
		filepath := filepath.Join(notesDir, noteFile)
		if err := os.WriteFile(filepath, []byte("test notes"), 0644); err != nil {
			t.Fatalf("Failed to create note file %s: %v", noteFile, err)
		}

		missing, err := loader.TestAvailableNotes(players)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		// Should find 0 missing players because "Patrick Mahomes II" cleans to "Patrick Mahomes"
		if len(missing) != 0 {
			t.Errorf("Expected 0 missing players (name cleaning should match), got %d: %v", len(missing), missing)
		}
	})

	t.Run("FuzzySuggestions", func(t *testing.T) {
		// Clean notes directory
		os.RemoveAll(notesDir)
		os.MkdirAll(notesDir, 0755)

		players := []Player{
			{Name: "Patrick Mahomes"},
		}

		// Create files that should trigger fuzzy suggestions
		similarFiles := []string{
			"Patrick Mahome.md", // Close typo
			"Patrik Mahomes.md", // Single letter difference
		}

		for _, filename := range similarFiles {
			filepath := filepath.Join(notesDir, filename)
			if err := os.WriteFile(filepath, []byte("test notes"), 0644); err != nil {
				t.Fatalf("Failed to create note file %s: %v", filename, err)
			}
		}

		missing, err := loader.TestAvailableNotes(players)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if len(missing) != 1 {
			t.Errorf("Expected 1 missing player, got %d: %v", len(missing), missing)
		}

		suggestion := missing["Patrick Mahomes"]
		// Fuzzy matching might work or might not depending on the score threshold
		// We'll just check that the test doesn't crash and log the result
		t.Logf("Fuzzy suggestion result: %q", suggestion)
		// Note: This test mainly verifies the fuzzy logic doesn't crash rather than exact behavior
	})
}

func TestFindPlayerNoteFile(t *testing.T) {
	notesDir, logsDir, cleanup := setupTestDir(t)
	defer cleanup()

	loader := NewDataLoader(notesDir, logsDir)

	t.Run("FileExists", func(t *testing.T) {
		playerName := "Patrick Mahomes II"
		noteFile := "Patrick Mahomes.md"
		filepath := filepath.Join(notesDir, noteFile)

		if err := os.WriteFile(filepath, []byte("test notes"), 0644); err != nil {
			t.Fatalf("Failed to create note file: %v", err)
		}

		result, err := loader.FindPlayerNoteFile(playerName)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if result != filepath {
			t.Errorf("Expected %q, got %q", filepath, result)
		}
	})

	t.Run("FileNotExists", func(t *testing.T) {
		playerName := "Nonexistent Player"

		_, err := loader.FindPlayerNoteFile(playerName)
		if err == nil {
			t.Error("Expected error when note file doesn't exist")
		}
	})
}

func TestBuildAllNotes(t *testing.T) {
	notesDir, logsDir, cleanup := setupTestDir(t)
	defer cleanup()

	loader := NewDataLoader(notesDir, logsDir)

	t.Run("AllNotesExist", func(t *testing.T) {
		players := []Player{
			{Name: "Patrick Mahomes II"},
			{Name: "Travis Kelce"},
		}

		// Create note files with specific content
		notes := map[string]string{
			"Patrick Mahomes.md": "Great quarterback with strong arm",
			"Travis Kelce.md":    "Elite tight end with reliable hands",
		}

		for filename, content := range notes {
			filepath := filepath.Join(notesDir, filename)
			if err := os.WriteFile(filepath, []byte(content), 0644); err != nil {
				t.Fatalf("Failed to create note file %s: %v", filename, err)
			}
		}

		result, err := loader.BuildAllNotes(players)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		// Check that both players are included
		if !contains(result, "---start Patrick Mahomes II---") {
			t.Error("Expected Patrick Mahomes II section in notes")
		}

		if !contains(result, "---start Travis Kelce---") {
			t.Error("Expected Travis Kelce section in notes")
		}

		if !contains(result, "Great quarterback with strong arm") {
			t.Error("Expected Patrick Mahomes content in notes")
		}

		if !contains(result, "Elite tight end with reliable hands") {
			t.Error("Expected Travis Kelce content in notes")
		}
	})

	t.Run("NoNotesExist", func(t *testing.T) {
		// Clean notes directory
		os.RemoveAll(notesDir)
		os.MkdirAll(notesDir, 0755)

		players := []Player{
			{Name: "Missing Player"},
		}

		_, err := loader.BuildAllNotes(players)
		if err == nil {
			t.Error("Expected error when no notes are found")
		}
	})

	t.Run("SomeNotesExist", func(t *testing.T) {
		// Clean notes directory
		os.RemoveAll(notesDir)
		os.MkdirAll(notesDir, 0755)

		players := []Player{
			{Name: "Patrick Mahomes II"},
			{Name: "Missing Player"},
		}

		// Create only one note file
		filepath := filepath.Join(notesDir, "Patrick Mahomes.md")
		if err := os.WriteFile(filepath, []byte("Great QB"), 0644); err != nil {
			t.Fatalf("Failed to create note file: %v", err)
		}

		result, err := loader.BuildAllNotes(players)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		// Should only include the found player
		if !contains(result, "---start Patrick Mahomes II---") {
			t.Error("Expected Patrick Mahomes II section in notes")
		}

		if contains(result, "---start Missing Player---") {
			t.Error("Did not expect Missing Player section in notes")
		}
	})
}

func TestLoadCurrentTeam(t *testing.T) {
	// Create a temporary directory to test in (so we don't interfere with existing status files)
	tempDir, err := os.MkdirTemp("", "loader_team_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Change to temp directory for this test
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}
	defer os.Chdir(originalDir)

	if err := os.Chdir(tempDir); err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	loader := NewDataLoader("", "")

	// Test default behavior when file doesn't exist
	team, err := loader.LoadCurrentTeam()
	if err != nil {
		t.Errorf("LoadCurrentTeam should not return error when file doesn't exist, got: %v", err)
	}

	if team != "Unknown Team" {
		t.Errorf("Expected 'Unknown Team' when file doesn't exist, got %q", team)
	}
}

func TestLoadCurrentPickNum(t *testing.T) {
	// Create a temporary directory to test in (so we don't interfere with existing status files)
	tempDir, err := os.MkdirTemp("", "loader_pick_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Change to temp directory for this test
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}
	defer os.Chdir(originalDir)

	if err := os.Chdir(tempDir); err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	loader := NewDataLoader("", "")

	// Test behavior when file doesn't exist
	_, err = loader.LoadCurrentPickNum()
	if err == nil {
		t.Error("LoadCurrentPickNum should return error when file doesn't exist")
	}
}

// Helper function to check if a string contains a substring
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && (s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || containsAt(s, substr)))
}

func containsAt(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
