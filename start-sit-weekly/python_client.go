package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// PythonESPNClient handles ESPN API calls via Python subprocess
type PythonESPNClient struct {
	venvPath         string
	pythonPath       string
	scriptPath       string
	redditScriptPath string
	ffhoundScriptPath string
	cacheScriptPath  string
}

// LeagueInfo represents league connection information
type LeagueInfo struct {
	LeagueName string `json:"league_name"`
	Teams      []struct {
		ID    int    `json:"id"`
		Name  string `json:"name"`
		Owner string `json:"owner"`
	} `json:"teams"`
	Error string `json:"error,omitempty"`
}

// RosterInfo represents team roster information
type RosterInfo struct {
	TeamName string `json:"team_name"`
	Players  []struct {
		Name     string `json:"name"`
		Position string `json:"position"`
		Team     string `json:"team"`
		Status   string `json:"status"`
	} `json:"players"`
	Error string `json:"error,omitempty"`
}

// RedditScrapeResult represents the result of Reddit scraping for a team
type RedditScrapeResult struct {
	TeamID     int    `json:"team_id"`
	ScrapedAt  string `json:"scraped_at"`
	SinceDate  string `json:"since_date"`
	Players    []PlayerRedditData `json:"players"`
	Error      string `json:"error,omitempty"`
}

// PlayerRedditData represents Reddit data for a single player
type PlayerRedditData struct {
	Player     PlayerInfo `json:"player"`
	PostsFound int        `json:"posts_found"`
	Content    []RedditPost `json:"content"`
}

// PlayerInfo represents basic player information
type PlayerInfo struct {
	Name     string `json:"name"`
	Position string `json:"position"`
	Team     string `json:"team"`
}

// RedditPost represents a single Reddit post with relevant content
type RedditPost struct {
	Title    string   `json:"title"`
	URL      string   `json:"url"`
	Created  string   `json:"created"`
	Content  string   `json:"content"`
	Comments []string `json:"comments"`
}

// FFHoundScrapeResult represents the result of FF Hound scraping for a team
type FFHoundScrapeResult struct {
	TeamID     int    `json:"team_id"`
	ScrapedAt  string `json:"scraped_at"`
	SinceDate  string `json:"since_date"`
	Players    []PlayerFFHoundData `json:"players"`
	Error      string `json:"error,omitempty"`
}

// PlayerFFHoundData represents FF Hound data for a single player
type PlayerFFHoundData struct {
	Player     PlayerInfo `json:"player"`
	PostsFound int        `json:"posts_found"`
	Content    []FFHoundPost `json:"content"`
}

// FFHoundPost represents a single FF Hound post with relevant content
type FFHoundPost struct {
	URL          string   `json:"url"`
	SavedFile    string   `json:"saved_file"`
	DateScraped  string   `json:"date_scraped"`
	Mentions     []string `json:"mentions"`
	MentionCount int      `json:"mention_count"`
}

// NewPythonESPNClient creates a new Python ESPN client
func NewPythonESPNClient() *PythonESPNClient {
	workDir, _ := os.Getwd()
	venvPath := filepath.Join(workDir, "venv")
	pythonPath := filepath.Join(venvPath, "bin", "python")
	scriptPath := filepath.Join(workDir, "python", "espn_cli.py")
	redditScriptPath := filepath.Join(workDir, "python", "reddit_scraper.py")
	ffhoundScriptPath := filepath.Join(workDir, "python", "ffhound_scraper.py")
	cacheScriptPath := filepath.Join(workDir, "python", "espn_cache.py")

	return &PythonESPNClient{
		venvPath:          venvPath,
		pythonPath:        pythonPath,
		scriptPath:        scriptPath,
		redditScriptPath:  redditScriptPath,
		ffhoundScriptPath: ffhoundScriptPath,
		cacheScriptPath:   cacheScriptPath,
	}
}

// ensureVenv creates virtual environment and installs dependencies if needed
func (c *PythonESPNClient) ensureVenv() error {
	// Check if venv exists
	if _, err := os.Stat(c.venvPath); os.IsNotExist(err) {
		log.Println("Creating Python virtual environment...")
		cmd := exec.Command("python3", "-m", "venv", "venv")
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to create venv: %w", err)
		}
	}

	// Check if dependencies are installed by trying to import required modules
	cmd := exec.Command(c.pythonPath, "-c", "import espn_api, praw, dotenv, requests, bs4")
	if err := cmd.Run(); err != nil {
		log.Println("Installing Python dependencies...")
		reqPath := filepath.Join("python", "requirements.txt")
		cmd := exec.Command(c.pythonPath, "-m", "pip", "install", "-r", reqPath)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to install dependencies: %w", err)
		}
	}

	return nil
}

// ConnectToLeague connects to ESPN league via Python
func (c *PythonESPNClient) ConnectToLeague() (*LeagueInfo, error) {
	if err := c.ensureVenv(); err != nil {
		return nil, err
	}

	cmd := exec.Command(c.pythonPath, c.scriptPath, "connect")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("python command failed: %w", err)
	}

	var info LeagueInfo
	if err := json.Unmarshal(output, &info); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	if info.Error != "" {
		return nil, fmt.Errorf("ESPN API error: %s", info.Error)
	}

	return &info, nil
}

// GetTeamRoster gets roster for a specific team via Python
func (c *PythonESPNClient) GetTeamRoster(teamID int) (*RosterInfo, error) {
	if err := c.ensureVenv(); err != nil {
		return nil, err
	}

	cmd := exec.Command(c.pythonPath, c.scriptPath, "roster", fmt.Sprintf("%d", teamID))
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("python command failed: %w", err)
	}

	var info RosterInfo
	if err := json.Unmarshal(output, &info); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	if info.Error != "" {
		return nil, fmt.Errorf("ESPN API error: %s", info.Error)
	}

	return &info, nil
}

// ScrapeRedditForTeam scrapes Reddit for posts about all players on a team
func (c *PythonESPNClient) ScrapeRedditForTeam(teamID int) (*RedditScrapeResult, error) {
	if err := c.ensureVenv(); err != nil {
		return nil, err
	}

	// Check if Reddit credentials are available
	if !c.HasRedditCredentials() {
		return nil, fmt.Errorf("Reddit API credentials not found")
	}

	cmd := exec.Command(c.pythonPath, c.redditScriptPath, "scrape", fmt.Sprintf("%d", teamID))
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("reddit scraping command failed: %w", err)
	}

	var result RedditScrapeResult
	if err := json.Unmarshal(output, &result); err != nil {
		return nil, fmt.Errorf("failed to parse Reddit scrape JSON: %w", err)
	}

	if result.Error != "" {
		return nil, fmt.Errorf("Reddit scraping error: %s", result.Error)
	}

	return &result, nil
}

// ScrapeFFHoundForTeam scrapes FF Hound Substack for posts about all players on a team
func (c *PythonESPNClient) ScrapeFFHoundForTeam(teamID int) (*FFHoundScrapeResult, error) {
	if err := c.ensureVenv(); err != nil {
		return nil, err
	}

	cmd := exec.Command(c.pythonPath, c.ffhoundScriptPath, "scrape", fmt.Sprintf("%d", teamID))
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("FF Hound scraping command failed: %w", err)
	}

	var result FFHoundScrapeResult
	if err := json.Unmarshal(output, &result); err != nil {
		return nil, fmt.Errorf("failed to parse FF Hound scrape JSON: %w", err)
	}

	if result.Error != "" {
		return nil, fmt.Errorf("FF Hound scraping error: %s", result.Error)
	}

	return &result, nil
}

// CacheESPNData caches ESPN league and roster data to CSV files
func (c *PythonESPNClient) CacheESPNData() error {
	if err := c.ensureVenv(); err != nil {
		return err
	}

	cmd := exec.Command(c.pythonPath, c.cacheScriptPath, "cache")
	output, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("ESPN cache command failed: %w", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(output, &result); err != nil {
		return fmt.Errorf("failed to parse cache result JSON: %w", err)
	}

	if errorMsg, ok := result["error"]; ok {
		return fmt.Errorf("ESPN cache error: %s", errorMsg)
	}

	return nil
}

// ConnectToLeagueFromCache connects to ESPN league using cached data (faster)
func (c *PythonESPNClient) ConnectToLeagueFromCache() (*LeagueInfo, error) {
	if err := c.ensureVenv(); err != nil {
		return nil, err
	}

	cmd := exec.Command(c.pythonPath, c.cacheScriptPath, "load_teams")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("cached data load failed: %w", err)
	}

	var info LeagueInfo
	if err := json.Unmarshal(output, &info); err != nil {
		return nil, fmt.Errorf("failed to parse cached JSON: %w", err)
	}

	if info.Error != "" {
		return nil, fmt.Errorf("cached data error: %s", info.Error)
	}

	return &info, nil
}

// GetTeamRosterFromCache gets roster for a specific team from cached data (faster)
func (c *PythonESPNClient) GetTeamRosterFromCache(teamID int) (*RosterInfo, error) {
	if err := c.ensureVenv(); err != nil {
		return nil, err
	}

	cmd := exec.Command(c.pythonPath, c.cacheScriptPath, "load_roster", fmt.Sprintf("%d", teamID))
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("cached roster load failed: %w", err)
	}

	var info RosterInfo
	if err := json.Unmarshal(output, &info); err != nil {
		return nil, fmt.Errorf("failed to parse cached roster JSON: %w", err)
	}

	if info.Error != "" {
		return nil, fmt.Errorf("cached roster error: %s", info.Error)
	}

	return &info, nil
}

// IsCacheFresh checks if the cached data is fresh enough to use
func (c *PythonESPNClient) IsCacheFresh() bool {
	if err := c.ensureVenv(); err != nil {
		return false
	}

	cmd := exec.Command(c.pythonPath, c.cacheScriptPath, "check_cache")
	output, err := cmd.Output()
	if err != nil {
		return false
	}

	var result map[string]interface{}
	if err := json.Unmarshal(output, &result); err != nil {
		return false
	}

	fresh, ok := result["cache_fresh"].(bool)
	return ok && fresh
}

// CheckPythonDependencies checks if Python and required tools are available
func (c *PythonESPNClient) CheckPythonDependencies() error {
	// Check if python3 is available
	if _, err := exec.LookPath("python3"); err != nil {
		return fmt.Errorf("python3 not found: %w", err)
	}

	// Check if venv module is available
	cmd := exec.Command("python3", "-m", "venv", "--help")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("python3 venv module not available: %w", err)
	}

	return nil
}

// HasCredentials checks if ESPN credentials are available in environment
func (c *PythonESPNClient) HasCredentials() bool {
	leagueID := os.Getenv("ESPN_LEAGUE_ID")
	swid := os.Getenv("ESPN_SWID")
	espnS2 := os.Getenv("ESPN_S2")

	return leagueID != "" && swid != "" && espnS2 != ""
}

// HasRedditCredentials checks if Reddit API credentials are available in environment
func (c *PythonESPNClient) HasRedditCredentials() bool {
	clientID := os.Getenv("CLIENT_ID")
	clientSecret := os.Getenv("CLIENT_SECRET")
	userAgent := os.Getenv("USER_AGENT")

	return clientID != "" && clientSecret != "" && userAgent != ""
}

// GetStatus returns status information about the Python client
func (c *PythonESPNClient) GetStatus() string {
	var status []string

	// Check Python
	if err := c.CheckPythonDependencies(); err != nil {
		return fmt.Sprintf("Python not available: %v", err)
	}
	status = append(status, "Python: ✓")

	// Check venv
	if _, err := os.Stat(c.venvPath); err == nil {
		status = append(status, "Venv: ✓")
	} else {
		status = append(status, "Venv: ✗")
	}

	// Check ESPN credentials
	if c.HasCredentials() {
		status = append(status, "ESPN: ✓")
	} else {
		status = append(status, "ESPN: ✗")
	}

	// Check Reddit credentials
	if c.HasRedditCredentials() {
		status = append(status, "Reddit: ✓")
	} else {
		status = append(status, "Reddit: ✗")
	}

	return strings.Join(status, " | ")
}