package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Settings holds the application configuration
type Settings struct {
	OpenAIAPIKey   string `json:"openai_api_key"`
	UseLocalLLM    bool   `json:"use_local_llm"`
	OllamaModel    string `json:"ollama_model"`
	OllamaEndpoint string `json:"ollama_endpoint"`
}

// DefaultSettings returns default settings configuration
func DefaultSettings() *Settings {
	return &Settings{
		OpenAIAPIKey:   "",
		UseLocalLLM:    false,
		OllamaModel:    "microsoft/Phi-3-mini-128k-instruct",
		OllamaEndpoint: "http://localhost:11434",
	}
}

// LoadSettings loads settings from .env file
func LoadSettings() (*Settings, error) {
	settings := DefaultSettings()
	
	// Try to read .env file
	envPath := ".env"
	if _, err := os.Stat(envPath); os.IsNotExist(err) {
		// .env doesn't exist, return defaults
		return settings, nil
	}
	
	file, err := os.Open(envPath)
	if err != nil {
		return settings, fmt.Errorf("failed to open .env file: %w", err)
	}
	defer file.Close()
	
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])
		
		// Remove quotes if present
		if len(value) >= 2 && ((value[0] == '"' && value[len(value)-1] == '"') || 
			(value[0] == '\'' && value[len(value)-1] == '\'')) {
			value = value[1 : len(value)-1]
		}
		
		switch key {
		case "OPENAI_API_KEY":
			settings.OpenAIAPIKey = value
		case "USE_LOCAL_LLM":
			lowerValue := strings.ToLower(value)
			settings.UseLocalLLM = lowerValue == "true" || lowerValue == "1"
		case "OLLAMA_MODEL":
			settings.OllamaModel = value
		case "OLLAMA_ENDPOINT":
			settings.OllamaEndpoint = value
		}
	}
	
	return settings, scanner.Err()
}

// SaveSettings saves settings to .env file
func (s *Settings) SaveSettings() error {
	envPath := ".env"
	
	// Read existing .env content to preserve other variables
	var existingLines []string
	settingsKeys := map[string]bool{
		"OPENAI_API_KEY": true,
		"USE_LOCAL_LLM":  true,
		"OLLAMA_MODEL":   true,
		"OLLAMA_ENDPOINT": true,
	}
	
	if file, err := os.Open(envPath); err == nil {
		scanner := bufio.NewScanner(file)
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if line == "" || strings.HasPrefix(line, "#") {
				existingLines = append(existingLines, line)
				continue
			}
			
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				if !settingsKeys[key] {
					existingLines = append(existingLines, line)
				}
			} else {
				existingLines = append(existingLines, line)
			}
		}
		file.Close()
	}
	
	// Create new .env content
	var newContent strings.Builder
	
	// Add existing non-settings lines
	for _, line := range existingLines {
		newContent.WriteString(line + "\n")
	}
	
	// Add settings
	if s.OpenAIAPIKey != "" {
		newContent.WriteString(fmt.Sprintf("OPENAI_API_KEY=%s\n", s.OpenAIAPIKey))
	}
	newContent.WriteString(fmt.Sprintf("USE_LOCAL_LLM=%t\n", s.UseLocalLLM))
	if s.OllamaModel != "" {
		newContent.WriteString(fmt.Sprintf("OLLAMA_MODEL=%s\n", s.OllamaModel))
	}
	if s.OllamaEndpoint != "" {
		newContent.WriteString(fmt.Sprintf("OLLAMA_ENDPOINT=%s\n", s.OllamaEndpoint))
	}
	
	// Write to file
	return os.WriteFile(envPath, []byte(newContent.String()), 0644)
}

// HasValidConfig returns true if settings have a valid configuration
func (s *Settings) HasValidConfig() bool {
	if s.UseLocalLLM {
		return s.OllamaModel != "" && s.OllamaEndpoint != ""
	}
	return s.OpenAIAPIKey != ""
}

// GetWorkingDirectory returns the current working directory for settings operations
func GetWorkingDirectory() string {
	if wd, err := os.Getwd(); err == nil {
		return wd
	}
	// Fallback to executable directory
	if ex, err := os.Executable(); err == nil {
		return filepath.Dir(ex)
	}
	return "."
}
