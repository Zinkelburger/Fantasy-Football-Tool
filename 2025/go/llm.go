package main

import (
	"fmt"
)

// LLMProvider interface for different LLM implementations
type LLMProvider interface {
	Ask(prompt string) (string, error)
	AskStream(prompt string, callback func(string)) error
}

// LLMManager manages the current LLM provider
type LLMManager struct {
	provider      LLMProvider
	settings      *Settings
	promptManager *PromptManager
}

// NewLLMManager creates a new LLM manager
func NewLLMManager(settings *Settings) (*LLMManager, error) {
	manager := &LLMManager{
		settings:      settings,
		promptManager: NewPromptManager(),
	}
	
	// If no valid config, don't initialize provider but still return manager
	if !settings.HasValidConfig() {
		return manager, nil
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
	
	// Load system prompt
	systemPrompt, err := m.promptManager.LoadSystemPrompt()
	if err != nil {
		return fmt.Errorf("failed to load system prompt: %w", err)
	}
	
	gpt, err := NewGPT(m.settings.OpenAIAPIKey, systemPrompt)
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
	
	// Load system prompt
	systemPrompt, err := m.promptManager.LoadSystemPrompt()
	if err != nil {
		return fmt.Errorf("failed to load system prompt: %w", err)
	}
	
	m.provider = NewOllamaClient(m.settings.OllamaEndpoint, m.settings.OllamaModel, systemPrompt)
	return nil
}

// Ask delegates to the current provider
func (m *LLMManager) Ask(prompt string) (string, error) {
	if m.provider == nil {
		return "", fmt.Errorf("no LLM provider configured - please configure OpenAI or Ollama in settings")
	}
	return m.provider.Ask(prompt)
}

// AskStream delegates to the current provider's streaming method
func (m *LLMManager) AskStream(prompt string, callback func(string)) error {
	if m.provider == nil {
		return fmt.Errorf("no LLM provider configured - please configure OpenAI or Ollama in settings")
	}
	return m.provider.AskStream(prompt, callback)
}

// GetProviderType returns the current provider type
func (m *LLMManager) GetProviderType() string {
	if m.provider == nil {
		return "None"
	}
	if m.settings.UseLocalLLM {
		return "Ollama"
	}
	return "OpenAI"
}

// UpdateSettings updates the manager's settings and reinitializes provider
func (m *LLMManager) UpdateSettings(settings *Settings) error {
	m.settings = settings
	
	// Clear provider first
	m.provider = nil
	
	// If no valid config, leave provider as nil
	if !settings.HasValidConfig() {
		return nil
	}
	
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
	return m.provider != nil
}

// HasValidSettings returns true if the settings have valid configuration (but provider may not be initialized)
func (m *LLMManager) HasValidSettings() bool {
	return m.settings.HasValidConfig()
}

// GetSystemPrompt returns the current system prompt
func (m *LLMManager) GetSystemPrompt() (string, error) {
	return m.promptManager.LoadSystemPrompt()
}

// GetUserPrompt returns the current user prompt template
func (m *LLMManager) GetUserPrompt() (string, error) {
	return m.promptManager.LoadUserPrompt()
}

// SetSystemPrompt saves a new system prompt
func (m *LLMManager) SetSystemPrompt(prompt string) error {
	return m.promptManager.SaveSystemPrompt(prompt)
}

// SetUserPrompt saves a new user prompt template
func (m *LLMManager) SetUserPrompt(prompt string) error {
	return m.promptManager.SaveUserPrompt(prompt)
}

// BuildUserPrompt constructs the full user prompt with draft context
func (m *LLMManager) BuildUserPrompt(currentPick int, pickedPlayersStr, currentTeam, allNotes string) (string, error) {
	return m.promptManager.BuildFullUserPrompt(currentPick, pickedPlayersStr, currentTeam, allNotes)
}
