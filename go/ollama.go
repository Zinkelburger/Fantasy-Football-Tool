package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

// OllamaClient handles communication with Ollama
type OllamaClient struct {
	endpoint string
	model    string
}

// NewOllamaClient creates a new Ollama client
func NewOllamaClient(endpoint, model string) *OllamaClient {
	return &OllamaClient{
		endpoint: endpoint,
		model:    model,
	}
}

// OllamaRequest represents a request to Ollama
type OllamaRequest struct {
	Model    string `json:"model"`
	Prompt   string `json:"prompt"`
	Stream   bool   `json:"stream"`
	Format   string `json:"format,omitempty"`
	Options  map[string]interface{} `json:"options,omitempty"`
}

// OllamaResponse represents a response from Ollama
type OllamaResponse struct {
	Model      string `json:"model"`
	Response   string `json:"response"`
	Done       bool   `json:"done"`
	Context    []int  `json:"context,omitempty"`
	TotalTime  int64  `json:"total_duration,omitempty"`
	LoadTime   int64  `json:"load_duration,omitempty"`
	PromptTime int64  `json:"prompt_eval_duration,omitempty"`
	EvalTime   int64  `json:"eval_duration,omitempty"`
}

// Ask sends a prompt to Ollama and returns the response
func (c *OllamaClient) Ask(prompt string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	
	request := OllamaRequest{
		Model:  c.model,
		Prompt: prompt,
		Stream: false,
		Options: map[string]interface{}{
			"temperature": 0.7,
			"top_p":       0.9,
		},
	}
	
	jsonData, err := json.Marshal(request)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}
	
	req, err := http.NewRequestWithContext(ctx, "POST", c.endpoint+"/api/generate", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}
	
	req.Header.Set("Content-Type", "application/json")
	
	client := &http.Client{
		Timeout: 120 * time.Second,
	}
	
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("ollama request failed with status %d: %s", resp.StatusCode, string(body))
	}
	
	var response OllamaResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}
	
	return response.Response, nil
}

// IsOllamaRunning checks if Ollama service is running
func IsOllamaRunning(endpoint string) bool {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	req, err := http.NewRequestWithContext(ctx, "GET", endpoint+"/api/tags", nil)
	if err != nil {
		return false
	}
	
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	
	return resp.StatusCode == http.StatusOK
}

// InstallOllama installs Ollama on the system
func InstallOllama() error {
	switch runtime.GOOS {
	case "linux":
		return installOllamaLinux()
	case "darwin":
		return installOllamaMacOS()
	case "windows":
		return installOllamaWindows()
	default:
		return fmt.Errorf("unsupported operating system: %s", runtime.GOOS)
	}
}

// installOllamaLinux installs Ollama on Linux
func installOllamaLinux() error {
	// Check if curl is available
	if _, err := exec.LookPath("curl"); err != nil {
		return fmt.Errorf("curl is required but not found in PATH")
	}
	
	// Download and run Ollama install script
	cmd := exec.Command("curl", "-fsSL", "https://ollama.com/install.sh")
	installScript, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("failed to download Ollama install script: %w", err)
	}
	
	// Run the install script
	cmd = exec.Command("sh", "-c", string(installScript))
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to install Ollama: %w", err)
	}
	
	return nil
}

// installOllamaMacOS installs Ollama on macOS
func installOllamaMacOS() error {
	// Check if brew is available
	if _, err := exec.LookPath("brew"); err != nil {
		return fmt.Errorf("Homebrew is required but not found. Please install Homebrew first or download Ollama manually from https://ollama.com")
	}
	
	// Install using Homebrew
	cmd := exec.Command("brew", "install", "ollama")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to install Ollama via Homebrew: %w", err)
	}
	
	return nil
}

// installOllamaWindows provides instructions for Windows installation
func installOllamaWindows() error {
	return fmt.Errorf("please download and install Ollama manually from https://ollama.com/download/windows")
}

// StartOllama starts the Ollama service
func StartOllama() error {
	switch runtime.GOOS {
	case "linux", "darwin":
		// Try to start Ollama service
		cmd := exec.Command("ollama", "serve")
		if err := cmd.Start(); err != nil {
			return fmt.Errorf("failed to start Ollama service: %w", err)
		}
		
		// Wait a moment for service to start
		time.Sleep(2 * time.Second)
		return nil
		
	case "windows":
		// On Windows, Ollama is typically installed as a service
		return nil
		
	default:
		return fmt.Errorf("unsupported operating system: %s", runtime.GOOS)
	}
}

// PullModel downloads a model to Ollama
func PullModel(model string) error {
	cmd := exec.Command("ollama", "pull", model)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to pull model %s: %w", model, err)
	}
	
	return nil
}

// ListModels lists available models in Ollama
func ListModels(endpoint string) ([]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	req, err := http.NewRequestWithContext(ctx, "GET", endpoint+"/api/tags", nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("request failed with status %d", resp.StatusCode)
	}
	
	var result struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}
	
	var models []string
	for _, model := range result.Models {
		models = append(models, model.Name)
	}
	
	return models, nil
}

// TestModel tests if a model is available and working
func TestModel(endpoint, model string) error {
	client := NewOllamaClient(endpoint, model)
	
	response, err := client.Ask("Hello! Please respond with 'OK' if you can understand this message.")
	if err != nil {
		return fmt.Errorf("failed to test model: %w", err)
	}
	
	if !strings.Contains(strings.ToUpper(response), "OK") {
		return fmt.Errorf("model test failed - unexpected response: %s", response)
	}
	
	return nil
}
