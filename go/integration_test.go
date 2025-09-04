package main

import (
	"testing"
)

func TestRealCSVWithPlatformSwitching(t *testing.T) {
	// Create CSV with actual ranking data
	csvContent := `Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank
1.0,Ja'Marr Chase,CIN,10.0,WR1,5,3
2.0,Bijan Robinson,ATL,5.0,RB1,8,4
3.0,Saquon Barkley,PHI,9.0,RB2,12,7
4.0,Jahmyr Gibbs,DET,8.0,RB3,15,9
5.0,Justin Jefferson,MIN,6.0,WR2,2,1`

	csvPath, cleanup := createTestCSV(t, csvContent)
	defer cleanup()

	// Test loading players
	players, err := LoadPlayers(csvPath)
	if err != nil {
		t.Fatalf("Failed to load players: %v", err)
	}

	if len(players) != 5 {
		t.Fatalf("Expected 5 players, got %d", len(players))
	}

	// Verify ESPN ranks are loaded
	expectedESPN := []string{"5", "8", "12", "15", "2"}
	for i, player := range players {
		if player.ESPNRank != expectedESPN[i] {
			t.Errorf("Player %s: expected ESPN rank %s, got %s", 
				player.Name, expectedESPN[i], player.ESPNRank)
		}
	}

	// Verify Sleeper ranks are loaded  
	expectedSleeper := []string{"3", "4", "7", "9", "1"}
	for i, player := range players {
		if player.SleeperRank != expectedSleeper[i] {
			t.Errorf("Player %s: expected Sleeper rank %s, got %s", 
				player.Name, expectedSleeper[i], player.SleeperRank)
		}
	}

	// Test UI rank selection logic
	testCases := []struct {
		platform     string
		expectedRank string // For first player (Ja'Marr Chase)
	}{
		{"ESPN", "5"},
		{"Sleeper", "3"},
		{"", "5"}, // Default to ESPN
	}

	for _, tc := range testCases {
		t.Run("Platform_"+tc.platform, func(t *testing.T) {
			settings := &Settings{Platform: tc.platform}
			
			// Simulate the UI logic
			player := players[0] // Ja'Marr Chase
			platformRank := player.ESPNRank
			if settings != nil && settings.Platform == "Sleeper" {
				platformRank = player.SleeperRank
			}

			if platformRank != tc.expectedRank {
				t.Errorf("Platform %s: expected rank %s, got %s", 
					tc.platform, tc.expectedRank, platformRank)
			}
		})
	}
}

func TestFileFormatDetection(t *testing.T) {
	loader := NewDataLoader("analysis", "logs")

	testCases := []struct {
		name          string
		scoringFormat string
		platform      string
		expectedFile  string
	}{
		{
			name:          "STD ESPN",
			scoringFormat: "STD",
			platform:      "ESPN",
			expectedFile:  "std_with_depth.csv",
		},
		{
			name:          "Half PPR Sleeper",
			scoringFormat: "0.5PPR", 
			platform:      "Sleeper",
			expectedFile:  "0.5_ppr_with_depth.csv",
		},
		{
			name:          "PPR ESPN",
			scoringFormat: "PPR",
			platform:      "ESPN", 
			expectedFile:  "ppr_with_depth.csv",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			settings := &Settings{
				ScoringFormat: tc.scoringFormat,
				Platform:      tc.platform,
			}
			loader.SetSettings(settings)

			filename := loader.getPlayerDataFilename()
			if filename != tc.expectedFile {
				t.Errorf("Expected %s, got %s", tc.expectedFile, filename)
			}
		})
	}
}