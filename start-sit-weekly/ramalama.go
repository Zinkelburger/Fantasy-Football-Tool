package main

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// RamalamaClient handles ramalama operations
type RamalamaClient struct {
	installed    bool
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
	// FIX: Use a correct default model name that exists in the registry.
	return &RamalamaClient{
		defaultModel: "llama3.2",
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

// PullModel pulls a model with real-time progress updates.
func (r *RamalamaClient) PullModel(model string, progressCallback func(string)) error {
	if !r.installed {
		return fmt.Errorf("ramalama is not installed")
	}

	progressCallback(fmt.Sprintf("Pulling model %s...", model))

	cmd := exec.Command("ramalama", "pull", model)

	// FIX: Use pipes to stream output for real-time progress instead of waiting for the command to finish.
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to get stdout pipe: %w", err)
	}
	cmd.Stderr = cmd.Stdout // Combine stdout and stderr for simplicity

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start model pull: %w", err)
	}

	// Read the output line by line
	scanner := bufio.NewScanner(stdout)
	for scanner.Scan() {
		line := scanner.Text()
		progressCallback(line)
	}

	// Wait for the command to finish and check for errors.
	if err := cmd.Wait(); err != nil {
		return fmt.Errorf("model pull command failed: %w", err)
	}

	progressCallback(fmt.Sprintf("Model %s pulled successfully!", model))
	return nil
}

// IsModelAvailable checks if a model is available locally in a robust way.
func (r *RamalamaClient) IsModelAvailable(model string) bool {
	if !r.installed {
		return false
	}

	cmd := exec.Command("ramalama", "list")
	output, err := cmd.Output()
	if err != nil {
		return false
	}

	// FIX: Parse the output properly instead of a simple string contains check.
	// This prevents false positives (e.g., checking for "llama" when only "llama3" exists).
	lines := strings.Split(string(output), "\n")
	for _, line := range lines {
		fields := strings.Fields(line) // Split line by whitespace
		if len(fields) > 0 && fields[0] == model {
			return true
		}
	}
	return false
}

// SummarizeText summarizes text using the correct non-interactive command.
func (r *RamalamaClient) SummarizeText(text, model string) (string, error) {
	if !r.installed {
		return "", fmt.Errorf("ramalama is not installed")
	}

	if model == "" {
		model = r.defaultModel
	}

	prompt := fmt.Sprintf(`You are a fantasy football expert. Please provide a concise summary of the following Reddit discussion about this player. Focus on:

1. Key fantasy football insights (injuries, usage, matchups, trends)
2. Community sentiment (positive/negative outlook)
3. Start/sit recommendations if mentioned
4. Any breaking news or important updates

Keep the summary under 200 words and focus on actionable fantasy football information.

Reddit Discussion:
%s

Summary:`, text)

	// FIX: Use 'generate' for single-shot tasks and pass the prompt via standard input.
	// The 'run' command is for interactive chat sessions.
	cmd := exec.Command("ramalama", "generate", model)

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return "", fmt.Errorf("failed to get stdin pipe: %w", err)
	}

	// Write the prompt to stdin in a background goroutine.
	go func() {
		defer stdin.Close()
		io.WriteString(stdin, prompt)
	}()

	// Run the command and capture the combined output to see any errors.
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to generate summary: %s", string(output))
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
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}

	safePlayerName := strings.ReplaceAll(strings.ToLower(playerName), " ", "_")
	safePlayerName = strings.ReplaceAll(safePlayerName, ".", "")

	filename := filepath.Join(outputDir, fmt.Sprintf("%s_summary.md", safePlayerName))

	// FIX: Use the standard 'time' package for reliable timestamps.
	content := fmt.Sprintf(`# Fantasy Football Summary: %s

Generated on: %s
Model: %s

## Summary

%s

---
*Generated by ramalama AI summarization*
`, playerName,
		time.Now().Format("2006-01-02 15:04:05"),
		r.defaultModel,
		summary)

	if err := os.WriteFile(filename, []byte(content), 0644); err != nil {
		return fmt.Errorf("failed to write summary file: %w", err)
	}

	log.Printf("Summary saved to: %s", filename)
	return nil
}

// SaveRamalamaAnalysisToFile saves raw ramalama analysis output to ramalama_analysis/ directory
func (r *RamalamaClient) SaveRamalamaAnalysisToFile(playerName, analysis string) error {
	outputDir := "ramalama_analysis"
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("failed to create ramalama analysis directory: %w", err)
	}

	safePlayerName := strings.ReplaceAll(strings.ToLower(playerName), " ", "_")
	safePlayerName = strings.ReplaceAll(safePlayerName, ".", "")

	filename := filepath.Join(outputDir, fmt.Sprintf("%s_ramalama_analysis.txt", safePlayerName))

	content := fmt.Sprintf(`Fantasy Football Analysis for %s
Generated on: %s
Model: %s

%s
`, playerName, time.Now().Format("2006-01-02 15:04:05"), r.defaultModel, analysis)

	if err := os.WriteFile(filename, []byte(content), 0644); err != nil {
		return fmt.Errorf("failed to write ramalama analysis file: %w", err)
	}

	log.Printf("Ramalama analysis saved to: %s", filename)
	return nil
}
