package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// RamalamaClient handles ramalama operations
type RamalamaClient struct {
	installed   bool
	defaultModel string
}

// RamalamaSummary represents a summary result
type RamalamaSummary struct {
	PlayerName string `json:"player_name"`
	Summary    string `json:"summary"`
	Model      string `json:"model"`
	Error      string `json:"error,omitempty"`
}

// NewRamalamaClient creates a new ramalama client
func NewRamalamaClient() *RamalamaClient {
	return &RamalamaClient{
		defaultModel: "llama3.2:3b", // Default model
	}
}

// CheckInstallation checks if ramalama is installed
func (r *RamalamaClient) CheckInstallation() bool {
	if _, err := exec.LookPath("ramalama"); err == nil {
		r.installed = true
		return true
	}
	r.installed = false
	return false
}

// InstallRamalama installs ramalama using curl
func (r *RamalamaClient) InstallRamalama(progressCallback func(string)) error {
	if r.CheckInstallation() {
		return nil // Already installed
	}

	progressCallback("Installing ramalama...")

	// Check if curl is available
	if _, err := exec.LookPath("curl"); err != nil {
		return fmt.Errorf("curl is required to install ramalama: %w", err)
	}

	// Install ramalama using the official script
	installScript := `curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | bash`

	cmd := exec.Command("bash", "-c", installScript)
	cmd.Env = append(os.Environ(), "INSTALL_PREFIX="+os.Getenv("HOME")+"/.local")

	// Capture output for progress
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	stderr, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start ramalama installation: %w", err)
	}

	// Read output and send progress updates
	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			progressCallback("Installing: " + scanner.Text())
		}
	}()

	go func() {
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			progressCallback("Install: " + scanner.Text())
		}
	}()

	if err := cmd.Wait(); err != nil {
		return fmt.Errorf("ramalama installation failed: %w", err)
	}

	progressCallback("Ramalama installation completed!")

	// Update PATH to include ~/.local/bin
	localBin := filepath.Join(os.Getenv("HOME"), ".local", "bin")
	currentPath := os.Getenv("PATH")
	if !strings.Contains(currentPath, localBin) {
		os.Setenv("PATH", localBin+":"+currentPath)
	}

	r.installed = r.CheckInstallation()
	if !r.installed {
		return fmt.Errorf("installation completed but ramalama not found in PATH")
	}

	return nil
}

// PullModel pulls a model with progress updates
func (r *RamalamaClient) PullModel(model string, progressCallback func(string)) error {
	if !r.installed {
		return fmt.Errorf("ramalama is not installed")
	}

	progressCallback(fmt.Sprintf("Pulling model %s...", model))

	cmd := exec.Command("ramalama", "pull", model)

	// Capture output for progress
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	stderr, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start model pull: %w", err)
	}

	// Read output and send progress updates
	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.Contains(line, "downloading") || strings.Contains(line, "pulling") {
				progressCallback("Downloading: " + line)
			} else if strings.TrimSpace(line) != "" {
				progressCallback("Pull: " + line)
			}
		}
	}()

	go func() {
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.TrimSpace(line) != "" {
				progressCallback("Pull: " + line)
			}
		}
	}()

	if err := cmd.Wait(); err != nil {
		return fmt.Errorf("model pull failed: %w", err)
	}

	progressCallback(fmt.Sprintf("Model %s pulled successfully!", model))
	return nil
}

// IsModelAvailable checks if a model is available locally
func (r *RamalamaClient) IsModelAvailable(model string) bool {
	if !r.installed {
		return false
	}

	cmd := exec.Command("ramalama", "list")
	output, err := cmd.Output()
	if err != nil {
		return false
	}

	return strings.Contains(string(output), model)
}

// SummarizeText summarizes text using ramalama
func (r *RamalamaClient) SummarizeText(text, model string) (string, error) {
	if !r.installed {
		return "", fmt.Errorf("ramalama is not installed")
	}

	if model == "" {
		model = r.defaultModel
	}

	// Create a prompt for summarization
	prompt := fmt.Sprintf(`You are a fantasy football expert. Please provide a concise summary of the following Reddit discussion about this player. Focus on:

1. Key fantasy football insights (injuries, usage, matchups, trends)
2. Community sentiment (positive/negative outlook)
3. Start/sit recommendations if mentioned
4. Any breaking news or important updates

Keep the summary under 200 words and focus on actionable fantasy football information.

Reddit Discussion:
%s

Summary:`, text)

	// Use ramalama to generate the summary
	cmd := exec.Command("ramalama", "run", model, "--prompt", prompt)

	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to generate summary: %w", err)
	}

	summary := strings.TrimSpace(string(output))
	if summary == "" {
		return "", fmt.Errorf("received empty summary from model")
	}

	return summary, nil
}

// SetDefaultModel sets the default model to use
func (r *RamalamaClient) SetDefaultModel(model string) {
	r.defaultModel = model
}

// GetDefaultModel returns the current default model
func (r *RamalamaClient) GetDefaultModel() string {
	return r.defaultModel
}

// GetStatus returns the status of ramalama
func (r *RamalamaClient) GetStatus() string {
	if r.CheckInstallation() {
		return "Ramalama: ✓"
	}
	return "Ramalama: ✗"
}

// SaveSummaryToFile saves a summary to a file
func (r *RamalamaClient) SaveSummaryToFile(playerName, summary, outputDir string) error {
	// Create output directory if it doesn't exist
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}

	// Create a safe filename
	safePlayerName := strings.ReplaceAll(strings.ToLower(playerName), " ", "_")
	safePlayerName = strings.ReplaceAll(safePlayerName, ".", "")

	filename := filepath.Join(outputDir, fmt.Sprintf("%s_summary.md", safePlayerName))

	content := fmt.Sprintf(`# Fantasy Football Summary: %s

Generated on: %s
Model: %s

## Summary

%s

---
*Generated by ramalama AI summarization*
`, playerName,
	   fmt.Sprintf("%s", strings.Split(fmt.Sprintf("%v", os.Getenv("TZ")), " ")[0]),
	   r.defaultModel,
	   summary)

	if err := os.WriteFile(filename, []byte(content), 0644); err != nil {
		return fmt.Errorf("failed to write summary file: %w", err)
	}

	log.Printf("Summary saved to: %s", filename)
	return nil
}