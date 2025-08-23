package main

import (
	"fmt"
	"log"
	"strings"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"
)

// SettingsUI manages the settings interface
type SettingsUI struct {
	parent     fyne.Window
	settings   *Settings
	llmManager *LLMManager
	onUpdate   func(*Settings) error
}

// NewSettingsUI creates a new settings UI manager
func NewSettingsUI(parent fyne.Window, settings *Settings, llmManager *LLMManager, onUpdate func(*Settings) error) *SettingsUI {
	return &SettingsUI{
		parent:     parent,
		settings:   settings,
		llmManager: llmManager,
		onUpdate:   onUpdate,
	}
}

// CreateSettingsButton creates a gear icon button for opening settings
func (s *SettingsUI) CreateSettingsButton() *widget.Button {
	btn := widget.NewButtonWithIcon("", theme.SettingsIcon(), func() {
		s.ShowSettingsDialog()
	})
	btn.Resize(fyne.NewSize(30, 30))
	return btn
}

// ShowSettingsDialog displays the settings configuration dialog
func (s *SettingsUI) ShowSettingsDialog() {
	// Create form entries
	apiKeyEntry := widget.NewPasswordEntry()
	apiKeyEntry.SetText(s.settings.OpenAIAPIKey)
	apiKeyEntry.SetPlaceHolder("Enter your OpenAI API key")

	useLocalLLMCheck := widget.NewCheck("Use local LLM (Ollama)", nil)
	useLocalLLMCheck.SetChecked(s.settings.UseLocalLLM)

	ollamaModelEntry := widget.NewEntry()
	ollamaModelEntry.SetText(s.settings.OllamaModel)
	ollamaModelEntry.SetPlaceHolder("e.g., microsoft/Phi-3-mini-128k-instruct")

	ollamaEndpointEntry := widget.NewEntry()
	ollamaEndpointEntry.SetText(s.settings.OllamaEndpoint)
	ollamaEndpointEntry.SetPlaceHolder("e.g., http://localhost:11434")

	// Load current user prompt (no system prompt editing)
	userPrompt, _ := s.llmManager.GetUserPrompt()

	// Create larger text area for user prompt editing
	userPromptEntry := widget.NewMultiLineEntry()
	userPromptEntry.SetText(userPrompt)
	userPromptEntry.Wrapping = fyne.TextWrapWord
	userPromptEntry.Resize(fyne.NewSize(550, 200))
	userPromptEntry.SetPlaceHolder("Look for high upside players with good matchups...")

	// Helper text with examples
	userPromptHelp := widget.NewLabel("You can customize the analysis instructions. E.g. 'Look for high upside players'")
	userPromptHelp.Wrapping = fyne.TextWrapWord

	// Status label
	statusLabel := widget.NewLabel("")
	s.updateStatusLabel(statusLabel)

	// Setup Ollama button
	setupOllamaBtn := widget.NewButton("Setup Ollama", func() {
		s.handleOllamaSetup(statusLabel)
	})

	// Test connection button
	testBtn := widget.NewButton("Test Connection", func() {
		s.handleTestConnection(apiKeyEntry.Text, useLocalLLMCheck.Checked,
			ollamaModelEntry.Text, ollamaEndpointEntry.Text, statusLabel)
	})

	// Update UI based on local LLM checkbox
	updateUI := func() {
		if useLocalLLMCheck.Checked {
			ollamaModelEntry.Enable()
			ollamaEndpointEntry.Enable()
			setupOllamaBtn.Enable()
			apiKeyEntry.Disable()
		} else {
			ollamaModelEntry.Disable()
			ollamaEndpointEntry.Disable()
			setupOllamaBtn.Disable()
			apiKeyEntry.Enable()
		}
	}

	useLocalLLMCheck.OnChanged = func(checked bool) {
		updateUI()
		s.updateStatusLabel(statusLabel)
	}

	// Initial UI state
	updateUI()

	// Create form with scrollable content
	form := &widget.Form{
		Items: []*widget.FormItem{
			{Text: "OpenAI API Key:", Widget: apiKeyEntry},
			{Text: "", Widget: useLocalLLMCheck},
			{Text: "Ollama Model:", Widget: ollamaModelEntry},
			{Text: "Ollama Endpoint:", Widget: ollamaEndpointEntry},
			{Text: "", Widget: widget.NewSeparator()},
			{Text: "Analysis Instructions:", Widget: container.NewVBox(
				userPromptEntry,
				userPromptHelp,
			)},
		},
	}

	// Buttons container
	buttonsContainer := container.NewHBox(
		setupOllamaBtn,
		testBtn,
	)

	// Main content
	content := container.NewVBox(
		widget.NewLabel("LLM Configuration"),
		widget.NewSeparator(),
		form,
		buttonsContainer,
		widget.NewSeparator(),
		statusLabel,
	)

	// Create dialog
	settingsDialog := dialog.NewCustom("Settings", "Close", content, s.parent)
	settingsDialog.Resize(fyne.NewSize(500, 400))

	// Note: Save functionality is handled by the custom dialog confirm button

	// Add save button to dialog
	settingsDialog.SetOnClosed(func() {
		// Dialog closed
	})

	// Create dialog with custom buttons
	customDialog := dialog.NewCustomConfirm("Settings", "Save", "Cancel", content,
		func(save bool) {
			if save {
				if err := s.handleSave(apiKeyEntry.Text, useLocalLLMCheck.Checked,
					ollamaModelEntry.Text, ollamaEndpointEntry.Text,
					userPromptEntry.Text); err != nil {
					dialog.ShowError(err, s.parent)
					// Don't close dialog on error
					s.ShowSettingsDialog()
				}
			}
		}, s.parent)

	customDialog.Resize(fyne.NewSize(650, 600))
	customDialog.Show()
}

// updateStatusLabel updates the status label with current configuration status
func (s *SettingsUI) updateStatusLabel(label *widget.Label) {
	if s.settings.UseLocalLLM {
		if IsOllamaRunning(s.settings.OllamaEndpoint) {
			label.SetText("✓ Status: Ollama is running")
			label.Importance = widget.SuccessImportance
		} else {
			label.SetText("⚠ Status: Ollama is not running")
			label.Importance = widget.WarningImportance
		}
	} else {
		if s.settings.OpenAIAPIKey != "" {
			label.SetText("✓ Status: OpenAI API key configured")
			label.Importance = widget.SuccessImportance
		} else {
			label.SetText("⚠ Status: OpenAI API key not configured")
			label.Importance = widget.WarningImportance
		}
	}
}

// handleSave saves the settings and updates the LLM manager
func (s *SettingsUI) handleSave(apiKey string, useLocal bool, model, endpoint, userPrompt string) error {
	// Update settings
	newSettings := &Settings{
		OpenAIAPIKey:   strings.TrimSpace(apiKey),
		UseLocalLLM:    useLocal,
		OllamaModel:    strings.TrimSpace(model),
		OllamaEndpoint: strings.TrimSpace(endpoint),
	}

	// Validate settings
	if !newSettings.HasValidConfig() {
		if newSettings.UseLocalLLM {
			return fmt.Errorf("Ollama configuration is incomplete. Please provide model and endpoint.")
		} else {
			return fmt.Errorf("OpenAI API key is required when not using local LLM.")
		}
	}

	// Save user prompt only (system prompt is hardcoded)
	if err := s.llmManager.SetUserPrompt(strings.TrimSpace(userPrompt)); err != nil {
		return fmt.Errorf("failed to save user prompt: %w", err)
	}

	// Save to .env file
	if err := newSettings.SaveSettings(); err != nil {
		return fmt.Errorf("failed to save settings: %w", err)
	}

	// Update current settings
	s.settings.OpenAIAPIKey = newSettings.OpenAIAPIKey
	s.settings.UseLocalLLM = newSettings.UseLocalLLM
	s.settings.OllamaModel = newSettings.OllamaModel
	s.settings.OllamaEndpoint = newSettings.OllamaEndpoint

	// Notify parent of update
	if s.onUpdate != nil {
		if err := s.onUpdate(s.settings); err != nil {
			return fmt.Errorf("failed to update LLM configuration: %w", err)
		}
	}

	log.Printf("Settings saved successfully. Using %s",
		map[bool]string{true: "Ollama", false: "OpenAI"}[s.settings.UseLocalLLM])

	return nil
}

// handleTestConnection tests the current configuration
func (s *SettingsUI) handleTestConnection(apiKey string, useLocal bool, model, endpoint string, statusLabel *widget.Label) {
	statusLabel.SetText("Testing connection...")
	statusLabel.Importance = widget.MediumImportance

	go func() {
		var err error
		if useLocal {
			// Test Ollama
			if !IsOllamaRunning(endpoint) {
				err = fmt.Errorf("Ollama is not running at %s", endpoint)
			} else {
				err = TestModel(endpoint, model)
			}
		} else {
			// Test OpenAI
			if apiKey == "" {
				err = fmt.Errorf("API key is required")
			} else {
				gpt, gptErr := NewGPT(apiKey, "You are a helpful assistant.")
				if gptErr != nil {
					err = gptErr
				} else {
					_, err = gpt.Ask("Hello")
				}
			}
		}

		// Update UI on main thread
		if err != nil {
			statusLabel.SetText(fmt.Sprintf("✗ Test failed: %s", err.Error()))
			statusLabel.Importance = widget.DangerImportance
		} else {
			provider := map[bool]string{true: "Ollama", false: "OpenAI"}[useLocal]
			statusLabel.SetText(fmt.Sprintf("✓ Test passed: %s is working", provider))
			statusLabel.Importance = widget.SuccessImportance
		}
	}()
}

// handleOllamaSetup handles Ollama installation and setup
func (s *SettingsUI) handleOllamaSetup(statusLabel *widget.Label) {
	statusLabel.SetText("Setting up Ollama...")
	statusLabel.Importance = widget.MediumImportance

	go func() {
		var err error

		// Check if Ollama is running first
		if !IsOllamaRunning(s.settings.OllamaEndpoint) {
			// Try to start Ollama
			if startErr := StartOllama(); startErr != nil {
				// If starting fails, try to install
				if installErr := InstallOllama(); installErr != nil {
					err = fmt.Errorf("failed to install Ollama: %w", installErr)
				} else {
					// Try to start after installation
					if startErr2 := StartOllama(); startErr2 != nil {
						err = fmt.Errorf("Ollama installed but failed to start: %w", startErr2)
					}
				}
			}
		}

		// If no error so far, try to pull the model
		if err == nil {
			if pullErr := PullModel(s.settings.OllamaModel); pullErr != nil {
				err = fmt.Errorf("failed to pull model: %w", pullErr)
			}
		}

		// Update UI on main thread
		if err != nil {
			statusLabel.SetText(fmt.Sprintf("✗ Setup failed: %s", err.Error()))
			statusLabel.Importance = widget.DangerImportance
		} else {
			statusLabel.SetText("✓ Ollama setup completed successfully")
			statusLabel.Importance = widget.SuccessImportance
		}
	}()
}
