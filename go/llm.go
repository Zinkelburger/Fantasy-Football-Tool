package main

import (
	"fmt"
)

// LLMProvider interface for different LLM implementations
type LLMProvider interface {
	Ask(prompt string) (string, error)
}

// LLMManager manages the current LLM provider
type LLMManager struct {
	provider LLMProvider
	settings *Settings
}

// NewLLMManager creates a new LLM manager
func NewLLMManager(settings *Settings) (*LLMManager, error) {
	manager := &LLMManager{
		settings: settings,
	}
	
	if err := manager.InitializeProvider(); err != nil {
		return nil, err
	}
	
	return manager, nil
}

// InitializeProvider initializes the LLM provider based on settings
func (m *LLMManager) InitializeProvider() error {
	if m.settings.UseLocalLLM {
		return m.initializeOllama()
	}
	return m.initializeOpenAI()
}

// initializeOpenAI sets up OpenAI as the provider
func (m *LLMManager) initializeOpenAI() error {
	if m.settings.OpenAIAPIKey == "" {
		return fmt.Errorf("OpenAI API key is not configured")
	}
	
	gpt, err := NewGPT(m.settings.OpenAIAPIKey)
	if err != nil {
		return fmt.Errorf("failed to initialize OpenAI client: %w", err)
	}
	
	m.provider = gpt
	return nil
}

// initializeOllama sets up Ollama as the provider
func (m *LLMManager) initializeOllama() error {
	if m.settings.OllamaModel == "" || m.settings.OllamaEndpoint == "" {
		return fmt.Errorf("Ollama configuration is incomplete")
	}
	
	// Check if Ollama is running
	if !IsOllamaRunning(m.settings.OllamaEndpoint) {
		return fmt.Errorf("Ollama service is not running at %s", m.settings.OllamaEndpoint)
	}
	
	// Check if model is available
	models, err := ListModels(m.settings.OllamaEndpoint)
	if err != nil {
		return fmt.Errorf("failed to list Ollama models: %w", err)
	}
	
	modelFound := false
	for _, model := range models {
		if model == m.settings.OllamaModel {
			modelFound = true
			break
		}
	}
	
	if !modelFound {
		return fmt.Errorf("model %s is not available in Ollama. Available models: %v", m.settings.OllamaModel, models)
	}
	
	// Test the model
	if err := TestModel(m.settings.OllamaEndpoint, m.settings.OllamaModel); err != nil {
		return fmt.Errorf("model test failed: %w", err)
	}
	
	m.provider = NewOllamaClient(m.settings.OllamaEndpoint, m.settings.OllamaModel)
	return nil
}

// Ask delegates to the current provider
func (m *LLMManager) Ask(prompt string) (string, error) {
	if m.provider == nil {
		return "", fmt.Errorf("no LLM provider initialized")
	}
	return m.provider.Ask(prompt)
}

// GetProviderType returns the current provider type
func (m *LLMManager) GetProviderType() string {
	if m.settings.UseLocalLLM {
		return "Ollama"
	}
	return "OpenAI"
}

// UpdateSettings updates the manager's settings and reinitializes provider
func (m *LLMManager) UpdateSettings(settings *Settings) error {
	m.settings = settings
	return m.InitializeProvider()
}

// SetupOllamaIfNeeded sets up Ollama if it's not available
func (m *LLMManager) SetupOllamaIfNeeded() error {
	if !m.settings.UseLocalLLM {
		return nil
	}
	
	// Check if Ollama is running
	if !IsOllamaRunning(m.settings.OllamaEndpoint) {
		// Try to start Ollama
		if err := StartOllama(); err != nil {
			return fmt.Errorf("failed to start Ollama: %w", err)
		}
		
		// Wait and check again
		if !IsOllamaRunning(m.settings.OllamaEndpoint) {
			return fmt.Errorf("Ollama service failed to start")
		}
	}
	
	// Check if model is available
	models, err := ListModels(m.settings.OllamaEndpoint)
	if err != nil {
		return fmt.Errorf("failed to list models: %w", err)
	}
	
	modelFound := false
	for _, model := range models {
		if model == m.settings.OllamaModel {
			modelFound = true
			break
		}
	}
	
	// Pull model if not found
	if !modelFound {
		if err := PullModel(m.settings.OllamaModel); err != nil {
			return fmt.Errorf("failed to pull model: %w", err)
		}
	}
	
	return nil
}

// IsConfigured returns true if the LLM is properly configured
func (m *LLMManager) IsConfigured() bool {
	if m.settings.UseLocalLLM {
		return m.settings.OllamaModel != "" && m.settings.OllamaEndpoint != "" && IsOllamaRunning(m.settings.OllamaEndpoint)
	}
	return m.settings.OpenAIAPIKey != ""
}
