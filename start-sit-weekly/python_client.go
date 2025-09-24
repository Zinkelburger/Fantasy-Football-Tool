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
	venvPath   string
	pythonPath string
	scriptPath string
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

// NewPythonESPNClient creates a new Python ESPN client
func NewPythonESPNClient() *PythonESPNClient {
	workDir, _ := os.Getwd()
	venvPath := filepath.Join(workDir, "venv")
	pythonPath := filepath.Join(venvPath, "bin", "python")
	scriptPath := filepath.Join(workDir, "python", "espn_cli.py")

	return &PythonESPNClient{
		venvPath:   venvPath,
		pythonPath: pythonPath,
		scriptPath: scriptPath,
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

	// Check if dependencies are installed by trying to import espn_api
	cmd := exec.Command(c.pythonPath, "-c", "import espn_api")
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

	// Check credentials
	if c.HasCredentials() {
		status = append(status, "Credentials: ✓")
	} else {
		status = append(status, "Credentials: ✗")
	}

	return strings.Join(status, " | ")
}