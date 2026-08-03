package main

import (
	"fmt"
	"os"
	"path/filepath"
)

// PromptManager handles loading and saving LLM prompts from files
type PromptManager struct {
	promptsDir string
}

// NewPromptManager creates a new prompt manager
func NewPromptManager() *PromptManager {
	return &PromptManager{
		promptsDir: "prompts",
	}
}

// ensurePromptsDir creates the prompts directory if it doesn't exist
func (pm *PromptManager) ensurePromptsDir() error {
	return os.MkdirAll(pm.promptsDir, 0755)
}

// LoadSystemPrompt loads the system prompt from file
func (pm *PromptManager) LoadSystemPrompt() (string, error) {
	return pm.loadPromptFromFile("system_prompt.md")
}

// LoadUserPrompt loads the user prompt template from file
func (pm *PromptManager) LoadUserPrompt() (string, error) {
	return pm.loadPromptFromFile("user_prompt.md")
}

// BuildFullUserPrompt constructs the complete user prompt with draft context
func (pm *PromptManager) BuildFullUserPrompt(currentPick int, pickedPlayersStr, currentTeam, allNotes string) (string, error) {
	userPromptCustom, err := pm.LoadUserPrompt()
	if err != nil {
		return "", err
	}
	
	// Build the full prompt with auto-generated context + user's custom instructions
	fullPrompt := fmt.Sprintf(
		"It is pick %d of a 2025 fantasy football draft. These players have been picked so far: %s. Current team info: %s. %s The notes for each player are separated by '---start playername---' and '---end playername---'.\n\nPlayer Notes:\n%s",
		currentPick, pickedPlayersStr, currentTeam, userPromptCustom, allNotes,
	)
	
	return fullPrompt, nil
}

// SaveSystemPrompt saves the system prompt to file
func (pm *PromptManager) SaveSystemPrompt(prompt string) error {
	return pm.savePromptToFile("system_prompt.md", prompt)
}

// SaveUserPrompt saves the user prompt template to file
func (pm *PromptManager) SaveUserPrompt(prompt string) error {
	return pm.savePromptToFile("user_prompt.md", prompt)
}

// loadPromptFromFile loads a prompt from the specified file
func (pm *PromptManager) loadPromptFromFile(filename string) (string, error) {
	filePath := filepath.Join(pm.promptsDir, filename)
	
	// If file doesn't exist, create default prompts
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		if err := pm.createDefaultPrompts(); err != nil {
			return "", fmt.Errorf("failed to create default prompts: %w", err)
		}
	}
	
	content, err := os.ReadFile(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to read prompt file %s: %w", filename, err)
	}
	
	return string(content), nil
}

// savePromptToFile saves a prompt to the specified file
func (pm *PromptManager) savePromptToFile(filename, prompt string) error {
	if err := pm.ensurePromptsDir(); err != nil {
		return fmt.Errorf("failed to create prompts directory: %w", err)
	}
	
	filePath := filepath.Join(pm.promptsDir, filename)
	err := os.WriteFile(filePath, []byte(prompt), 0644)
	if err != nil {
		return fmt.Errorf("failed to write prompt file %s: %w", filename, err)
	}
	
	return nil
}

// createDefaultPrompts creates the default prompt files if they don't exist
func (pm *PromptManager) createDefaultPrompts() error {
	if err := pm.ensurePromptsDir(); err != nil {
		return err
	}
	
	// Default system prompt
	systemPrompt := "You are a fantasy football expert. Give a summary of who to draft and why."
	if err := pm.SaveSystemPrompt(systemPrompt); err != nil {
		return fmt.Errorf("failed to create default system prompt: %w", err)
	}
	
	// Default user prompt template
	userPrompt := `Output the top several players you think could help me the most along with an explanation, considering their value, upside, and drawbacks. Give a summary of the most important players at the end once you are finished your explanations.`
	if err := pm.SaveUserPrompt(userPrompt); err != nil {
		return fmt.Errorf("failed to create default user prompt: %w", err)
	}
	
	return nil
}

// GetPromptsDir returns the prompts directory path
func (pm *PromptManager) GetPromptsDir() string {
	return pm.promptsDir
}
