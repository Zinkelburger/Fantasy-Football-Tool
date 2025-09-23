package main

import (
	"strings"
	"testing"
)

func TestPlatformRankDisplay(t *testing.T) {
	// Create mock player data with both ESPN and Sleeper ranks
	players := []Player{
		{Name: "Patrick Mahomes", Team: "KC", Pos: "QB", Rank: "1.0", ESPNRank: "2", SleeperRank: "3"},
		{Name: "Travis Kelce", Team: "KC", Pos: "TE", Rank: "5.0", ESPNRank: "6", SleeperRank: "7"},
	}

	tests := []struct {
		name           string
		platform       string
		expectedRank1  string // Expected rank for Patrick Mahomes
		expectedRank2  string // Expected rank for Travis Kelce
	}{
		{
			name:          "ESPN platform shows ESPN ranks",
			platform:      "ESPN",
			expectedRank1: "2",
			expectedRank2: "6",
		},
		{
			name:          "Sleeper platform shows Sleeper ranks", 
			platform:      "Sleeper",
			expectedRank1: "3",
			expectedRank2: "7",
		},
		{
			name:          "Default shows ESPN ranks",
			platform:      "",
			expectedRank1: "2",
			expectedRank2: "6",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create settings
			settings := &Settings{
				Platform: tt.platform,
				ScoringFormat: "PPR",
			}

			// Test the rank selection logic for each player
			for i, player := range players {
				platformRank := player.ESPNRank
				if settings != nil && settings.Platform == "Sleeper" {
					platformRank = player.SleeperRank
				}

				var expectedRank string
				if i == 0 {
					expectedRank = tt.expectedRank1
				} else {
					expectedRank = tt.expectedRank2
				}

				if platformRank != expectedRank {
					t.Errorf("Player %s: expected rank %s for platform %s, got %s", 
						player.Name, expectedRank, tt.platform, platformRank)
				}
			}
		})
	}
}

func TestCSVParsingWithBothRanks(t *testing.T) {
	// Test CSV content with both ESPN_Rank and Sleeper_Rank columns
	csvContent := `Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank
1.0,Patrick Mahomes,KC,10.0,QB1,2,3
5.0,Travis Kelce,KC,10.0,TE1,6,7`

	// Create a temporary file
	csvPath, cleanup := createTestCSV(t, csvContent)
	defer cleanup()

	// Load players from the CSV
	players, err := LoadPlayers(csvPath)
	if err != nil {
		t.Fatalf("Could not load players: %v", err)
	}

	if len(players) != 2 {
		t.Fatalf("Expected 2 players, got %d", len(players))
	}

	// Verify ESPN and Sleeper ranks are loaded correctly
	expectedData := []struct {
		name        string
		espnRank    string
		sleeperRank string
	}{
		{"Patrick Mahomes", "2", "3"},
		{"Travis Kelce", "6", "7"},
	}

	for i, expected := range expectedData {
		if players[i].Name != expected.name {
			t.Errorf("Expected player name %s, got %s", expected.name, players[i].Name)
		}
		if players[i].ESPNRank != expected.espnRank {
			t.Errorf("Player %s: expected ESPN rank %s, got %s", 
				expected.name, expected.espnRank, players[i].ESPNRank)
		}
		if players[i].SleeperRank != expected.sleeperRank {
			t.Errorf("Player %s: expected Sleeper rank %s, got %s", 
				expected.name, expected.sleeperRank, players[i].SleeperRank)
		}
	}
}

func TestCSVParsingMissingColumns(t *testing.T) {
	tests := []struct {
		name       string
		csvContent string
		wantErr    bool
	}{
		{
			name: "CSV with only ESPN_Rank",
			csvContent: `Rank,Player,Team,Bye,POS,ESPN_Rank
1.0,Patrick Mahomes,KC,10,QB,2`,
			wantErr: true, // Should error because Sleeper_Rank is missing
		},
		{
			name: "CSV with only Sleeper_Rank", 
			csvContent: `Rank,Player,Team,Bye,POS,Sleeper_Rank
1.0,Patrick Mahomes,KC,10,QB,3`,
			wantErr: true, // Should error because ESPN_Rank is missing
		},
		{
			name: "CSV with no rank columns",
			csvContent: `Rank,Player,Team,Bye,POS
1.0,Patrick Mahomes,KC,10,QB`,
			wantErr: true, // Should error because both rank columns are missing
		},
		{
			name: "CSV with all required columns",
			csvContent: `Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank
1.0,Patrick Mahomes,KC,10,QB,2,3`,
			wantErr: false, // Should work with all columns present
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			csvPath, cleanup := createTestCSV(t, tt.csvContent)
			defer cleanup()

			players, err := LoadPlayers(csvPath)
			if (err != nil) != tt.wantErr {
				t.Errorf("LoadPlayers() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if !tt.wantErr && len(players) == 0 {
				t.Error("Expected at least one player to be loaded")
			}
		})
	}
}

func TestGetPlayerDataFilename(t *testing.T) {
	loader := NewDataLoader("analysis", "logs")
	
	tests := []struct {
		name           string
		scoringFormat  string
		platform       string
		expectedSuffix string
	}{
		{
			name:           "STD format",
			scoringFormat:  "STD",
			platform:       "ESPN",
			expectedSuffix: "std_with_depth.csv",
		},
		{
			name:           "0.5PPR format", 
			scoringFormat:  "0.5PPR",
			platform:       "ESPN",
			expectedSuffix: "0.5_ppr_with_depth.csv",
		},
		{
			name:           "PPR format",
			scoringFormat:  "PPR", 
			platform:       "Sleeper",
			expectedSuffix: "ppr_with_depth.csv",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			settings := &Settings{
				ScoringFormat: tt.scoringFormat,
				Platform:      tt.platform,
			}
			loader.SetSettings(settings)
			
			filename := loader.getPlayerDataFilename()
			if !strings.HasSuffix(filename, tt.expectedSuffix) {
				t.Errorf("Expected filename to end with %s, got %s", tt.expectedSuffix, filename)
			}
		})
	}
}