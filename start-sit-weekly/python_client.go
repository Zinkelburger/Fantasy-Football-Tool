package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// ESPNClient handles ESPN data with automatic caching
type ESPNClient struct {
	venvPath     string
	pythonPath   string
	cacheScript  string
	cache        *Cache
	initialized  bool
}

// NewESPNClient creates a new ESPN client
func NewESPNClient() *ESPNClient {
	workDir, _ := os.Getwd()
	venvPath := filepath.Join(workDir, "venv")

	client := &ESPNClient{
		venvPath:    venvPath,
		pythonPath:  filepath.Join(venvPath, "bin", "python3"),
		cacheScript: filepath.Join(workDir, "python", "espn_cache.py"),
		cache:       NewCache("espn_cache", 24*time.Hour), // 24 hour cache
	}

	return client
}

// Initialize sets up the client and ensures fresh data
func (c *ESPNClient) Initialize() error {
	if c.initialized {
		return nil
	}

	// Ensure venv exists
	if err := c.ensureVenv(); err != nil {
		return fmt.Errorf("venv setup failed: %w", err)
	}

	// Check if cache needs refresh
	if c.cache.IsStale() {
		if err := c.refreshCache(); err != nil {
			return fmt.Errorf("cache refresh failed: %w", err)
		}
	}

	c.initialized = true
	return nil
}

// GetLeagueInfo gets league information (always from cache after initialization)
func (c *ESPNClient) GetLeagueInfo() (*LeagueInfo, error) {
	if err := c.Initialize(); err != nil {
		return nil, err
	}
	return c.cache.GetLeagueInfo()
}

// GetTeamRoster gets team roster (always from cache after initialization)
func (c *ESPNClient) GetTeamRoster(teamID int) (*RosterInfo, error) {
	if err := c.Initialize(); err != nil {
		return nil, err
	}
	return c.cache.GetTeamRoster(teamID)
}

// GetFreeAgents gets free agents (always from cache after initialization)
func (c *ESPNClient) GetFreeAgents(position string, size int) (*FreeAgentsResult, error) {
	if err := c.Initialize(); err != nil {
		return nil, err
	}
	return c.cache.GetFreeAgents(position, size)
}

// RefreshCache forces a cache refresh
func (c *ESPNClient) RefreshCache() error {
	return c.refreshCache()
}

// refreshCache calls Python to refresh all ESPN data
func (c *ESPNClient) refreshCache() error {
	if err := c.ensureVenv(); err != nil {
		return err
	}

	// Call Python cache script to refresh all data
	cmd := exec.Command(c.pythonPath, c.cacheScript, "cache")
	cmd.Dir = filepath.Dir(c.cacheScript)
	cmd.Env = append(os.Environ(), "PYTHONPATH="+filepath.Dir(c.cacheScript))

	output, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("cache refresh failed: %w, output: %s", err, output)
	}

	// Update timestamp to mark cache as fresh
	return c.cache.UpdateTimestamp()
}

// ensureVenv sets up Python virtual environment if needed
func (c *ESPNClient) ensureVenv() error {
	// Check if venv already exists
	if _, err := os.Stat(c.pythonPath); err == nil {
		return nil
	}

	// Create venv
	cmd := exec.Command("python3", "-m", "venv", c.venvPath)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to create venv: %w", err)
	}

	// Install dependencies
	pipPath := filepath.Join(c.venvPath, "bin", "pip")
	deps := []string{"espn-api", "python-dotenv", "requests", "beautifulsoup4", "selenium"}

	for _, dep := range deps {
		cmd := exec.Command(pipPath, "install", dep)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to install %s: %w", dep, err)
		}
	}

	return nil
}

// HasCredentials checks if ESPN credentials are available
func (c *ESPNClient) HasCredentials() bool {
	required := []string{"ESPN_LEAGUE_ID", "ESPN_SWID", "ESPN_S2"}
	for _, env := range required {
		if os.Getenv(env) == "" {
			return false
		}
	}
	return true
}

// HasRedditCredentials checks if Reddit credentials are available
func (c *ESPNClient) HasRedditCredentials() bool {
	required := []string{"CLIENT_ID", "CLIENT_SECRET", "USER_AGENT"}
	for _, env := range required {
		if os.Getenv(env) == "" {
			return false
		}
	}
	return true
}

// GetStatus returns client status
func (c *ESPNClient) GetStatus() string {
	if !c.HasCredentials() {
		return "ESPN credentials not configured"
	}
	if c.cache.IsStale() {
		return "Cache is stale, will refresh on next operation"
	}
	return "Ready - cache is fresh"
}

// Legacy methods for Reddit/FFHound (keep for compatibility)
func (c *ESPNClient) ScrapeRedditForTeam(teamID int) (*RedditScrapeResult, error) {
	// Implementation would go here - keeping interface for now
	return nil, fmt.Errorf("not implemented in simplified client")
}

func (c *ESPNClient) ScrapeFFHoundForTeam(teamID int) (*FFHoundScrapeResult, error) {
	// Implementation would go here - keeping interface for now
	return nil, fmt.Errorf("not implemented in simplified client")
}