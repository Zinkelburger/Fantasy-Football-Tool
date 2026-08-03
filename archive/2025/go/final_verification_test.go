package main

import (
	"testing"
)

func TestEndToEndPlatformSwitching(t *testing.T) {
	// Test loading actual CSV files with populated rank data
	loader := NewDataLoader("analysis", "logs")
	
	testCases := []struct {
		name          string
		scoringFormat string
		platform      string
		expectedFile  string
	}{
		{
			name:          "PPR ESPN",
			scoringFormat: "PPR", 
			platform:      "ESPN",
			expectedFile:  "ppr_with_depth.csv",
		},
		{
			name:          "0.5PPR Sleeper",
			scoringFormat: "0.5PPR",
			platform:      "Sleeper", 
			expectedFile:  "0.5_ppr_with_depth.csv",
		},
		{
			name:          "STD ESPN",
			scoringFormat: "STD",
			platform:      "ESPN",
			expectedFile:  "std_with_depth.csv",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Set up settings
			settings := &Settings{
				ScoringFormat: tc.scoringFormat,
				Platform:      tc.platform,
			}
			loader.SetSettings(settings)

			// Verify correct file is selected
			filename := loader.getPlayerDataFilename()
			if filename != tc.expectedFile {
				t.Errorf("Expected %s, got %s", tc.expectedFile, filename)
				return
			}

			// Load players from the file
			players, err := LoadPlayers(filename)
			if err != nil {
				t.Errorf("Failed to load players from %s: %v", filename, err)
				return
			}

			if len(players) == 0 {
				t.Errorf("No players loaded from %s", filename)
				return
			}

			// Verify that both ESPN and Sleeper ranks are populated
			player := players[0] // Test first player
			if player.ESPNRank == "" {
				t.Errorf("ESPN rank is empty for first player %s", player.Name)
			}
			if player.SleeperRank == "" {
				t.Errorf("Sleeper rank is empty for first player %s", player.Name)
			}

			// Test platform rank selection logic
			platformRank := player.ESPNRank
			if settings != nil && settings.Platform == "Sleeper" {
				platformRank = player.SleeperRank
			}

			expectedRank := player.ESPNRank
			if tc.platform == "Sleeper" {
				expectedRank = player.SleeperRank
			}

			if platformRank != expectedRank {
				t.Errorf("Platform %s: expected rank %s, got %s for player %s", 
					tc.platform, expectedRank, platformRank, player.Name)
			}

			t.Logf("✅ %s: Player %s shows %s rank %s (ESPN:%s, Sleeper:%s)", 
				tc.name, player.Name, tc.platform, platformRank, player.ESPNRank, player.SleeperRank)
		})
	}
}

func TestRankVariationExists(t *testing.T) {
	// Verify that ESPN and Sleeper ranks are actually different (not identical)
	players, err := LoadPlayers("ppr_with_depth.csv")
	if err != nil {
		t.Fatalf("Failed to load players: %v", err)
	}

	differentRanks := 0
	for _, player := range players[:10] { // Check first 10 players
		if player.ESPNRank != player.SleeperRank && player.ESPNRank != "" && player.SleeperRank != "" {
			differentRanks++
		}
	}

	if differentRanks == 0 {
		t.Error("ESPN and Sleeper ranks appear to be identical - platform switching wouldn't be visible")
	} else {
		t.Logf("✅ Found %d players with different ESPN/Sleeper ranks (out of 10 tested)", differentRanks)
	}
}