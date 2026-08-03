package main

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// Cache handles all ESPN data caching with timestamp-based freshness
type Cache struct {
	cacheDir    string
	timestampFile string
	maxAge      time.Duration
}

// NewCache creates a new cache instance
func NewCache(cacheDir string, maxAge time.Duration) *Cache {
	return &Cache{
		cacheDir:    cacheDir,
		timestampFile: filepath.Join(cacheDir, "timestamp.txt"),
		maxAge:      maxAge,
	}
}

// IsStale checks if cache needs refreshing
func (c *Cache) IsStale() bool {
	if _, err := os.Stat(c.timestampFile); os.IsNotExist(err) {
		return true
	}

	data, err := os.ReadFile(c.timestampFile)
	if err != nil {
		return true
	}

	timestamp, err := time.Parse(time.RFC3339, strings.TrimSpace(string(data)))
	if err != nil {
		return true
	}

	return time.Since(timestamp) > c.maxAge
}

// UpdateTimestamp marks cache as fresh
func (c *Cache) UpdateTimestamp() error {
	if err := os.MkdirAll(c.cacheDir, 0755); err != nil {
		return err
	}
	return os.WriteFile(c.timestampFile, []byte(time.Now().Format(time.RFC3339)), 0644)
}

// GetLeagueInfo reads league info from cache
func (c *Cache) GetLeagueInfo() (*LeagueInfo, error) {
	file := filepath.Join(c.cacheDir, "league_info.csv")
	f, err := os.Open(file)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	reader := csv.NewReader(f)
	records, err := reader.ReadAll()
	if err != nil || len(records) < 2 {
		return nil, fmt.Errorf("invalid league_info.csv")
	}

	// Skip header, read data row
	row := records[1]
	leagueName := row[1]

	// Read teams
	teams, err := c.GetTeams()
	if err != nil {
		return nil, err
	}

	return &LeagueInfo{
		LeagueName: leagueName,
		Teams:      teams,
	}, nil
}

// GetTeams reads teams from cache
func (c *Cache) GetTeams() ([]Team, error) {
	file := filepath.Join(c.cacheDir, "teams.csv")
	f, err := os.Open(file)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	reader := csv.NewReader(f)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}

	var teams []Team

	for i, row := range records {
		if i == 0 { // Skip header
			continue
		}
		if len(row) < 3 {
			continue
		}

		id, err := strconv.Atoi(row[0])
		if err != nil {
			continue
		}

		teams = append(teams, Team{
			ID:    id,
			Name:  row[1],
			Owner: row[2],
		})
	}

	return teams, nil
}

// GetTeamRoster reads roster for specific team from cache
func (c *Cache) GetTeamRoster(teamID int) (*RosterInfo, error) {
	file := filepath.Join(c.cacheDir, "rosters.csv")
	f, err := os.Open(file)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	reader := csv.NewReader(f)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}

	var players []Player
	var teamName string

	for i, row := range records {
		if i == 0 { // Skip header
			continue
		}
		if len(row) < 6 {
			continue
		}

		rowTeamID, err := strconv.Atoi(row[0])
		if err != nil || rowTeamID != teamID {
			continue
		}

		if teamName == "" {
			teamName = row[1]
		}

		players = append(players, Player{
			Name:            row[2],
			Position:        row[3],
			TeamName:        row[4],
			Status:          row[5],
			WeeklyOppScore:  "N/A",
			AvgOppScore:     "N/A",
		})
	}

	return &RosterInfo{
		TeamName: teamName,
		Players:  players,
	}, nil
}

// GetFreeAgents reads free agents from cache
func (c *Cache) GetFreeAgents(position string, size int) (*FreeAgentsResult, error) {
	file := filepath.Join(c.cacheDir, "free_agents.csv")
	f, err := os.Open(file)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	reader := csv.NewReader(f)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}

	var players []FreeAgentPlayer
	count := 0

	for i, row := range records {
		if i == 0 { // Skip header
			continue
		}
		if len(row) < 7 {
			continue
		}

		// Apply position filter
		if position != "" && strings.ToUpper(row[2]) != strings.ToUpper(position) {
			continue
		}

		// Apply size limit
		if size > 0 && count >= size {
			break
		}

		playerID := 0
		if row[0] != "" && row[0] != "None" {
			playerID, _ = strconv.Atoi(row[0])
		}

		percentOwned, _ := strconv.ParseFloat(row[5], 64)
		percentStarted, _ := strconv.ParseFloat(row[6], 64)

		players = append(players, FreeAgentPlayer{
			PlayerID:       playerID,
			Name:           row[1],
			Position:       row[2],
			Team:           row[3],
			Status:         row[4],
			PercentOwned:   percentOwned,
			PercentStarted: percentStarted,
		})
		count++
	}

	return &FreeAgentsResult{
		Players:        players,
		Count:          len(players),
		PositionFilter: position,
	}, nil
}