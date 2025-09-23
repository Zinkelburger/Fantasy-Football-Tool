package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Test helper to create a temporary .env file
func createTestEnvFile(t *testing.T, content string) (string, func()) {
	t.Helper()

	tempDir, err := os.MkdirTemp("", "settings_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	envPath := filepath.Join(tempDir, ".env")
	err = os.WriteFile(envPath, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test .env file: %v", err)
	}

	// Change to temp directory so .env file can be found
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}

	err = os.Chdir(tempDir)
	if err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	cleanup := func() {
		os.Chdir(originalDir)
		os.RemoveAll(tempDir)
	}

	return envPath, cleanup
}

func TestDefaultSettings(t *testing.T) {
	settings := DefaultSettings()

	if settings.OpenAIAPIKey != "" {
		t.Errorf("Expected OpenAIAPIKey to be empty, got '%s'", settings.OpenAIAPIKey)
	}

	if settings.UseLocalLLM != false {
		t.Errorf("Expected UseLocalLLM to be false, got %t", settings.UseLocalLLM)
	}

	expectedModel := "microsoft/Phi-3-mini-128k-instruct"
	if settings.OllamaModel != expectedModel {
		t.Errorf("Expected OllamaModel to be '%s', got '%s'", expectedModel, settings.OllamaModel)
	}

	expectedEndpoint := "http://localhost:11434"
	if settings.OllamaEndpoint != expectedEndpoint {
		t.Errorf("Expected OllamaEndpoint to be '%s', got '%s'", expectedEndpoint, settings.OllamaEndpoint)
	}
}

func TestLoadSettings_NoEnvFile(t *testing.T) {
	// Create a temporary directory without .env file
	tempDir, err := os.MkdirTemp("", "settings_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Change to temp directory
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}
	defer os.Chdir(originalDir)

	err = os.Chdir(tempDir)
	if err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	settings, err := LoadSettings()
	if err != nil {
		t.Fatalf("LoadSettings failed when no .env file exists: %v", err)
	}

	// Should return default settings
	defaultSettings := DefaultSettings()
	if settings.OpenAIAPIKey != defaultSettings.OpenAIAPIKey {
		t.Errorf("Expected OpenAIAPIKey to match default, got '%s'", settings.OpenAIAPIKey)
	}

	if settings.UseLocalLLM != defaultSettings.UseLocalLLM {
		t.Errorf("Expected UseLocalLLM to match default, got %t", settings.UseLocalLLM)
	}

	if settings.OllamaModel != defaultSettings.OllamaModel {
		t.Errorf("Expected OllamaModel to match default, got '%s'", settings.OllamaModel)
	}

	if settings.OllamaEndpoint != defaultSettings.OllamaEndpoint {
		t.Errorf("Expected OllamaEndpoint to match default, got '%s'", settings.OllamaEndpoint)
	}
}

func TestLoadSettings_ValidEnvFile(t *testing.T) {
	envContent := `OPENAI_API_KEY=test-api-key-123
USE_LOCAL_LLM=true
OLLAMA_MODEL=custom/model:latest
OLLAMA_ENDPOINT=http://custom:8080`

	_, cleanup := createTestEnvFile(t, envContent)
	defer cleanup()

	settings, err := LoadSettings()
	if err != nil {
		t.Fatalf("LoadSettings failed: %v", err)
	}

	if settings.OpenAIAPIKey != "test-api-key-123" {
		t.Errorf("Expected OpenAIAPIKey 'test-api-key-123', got '%s'", settings.OpenAIAPIKey)
	}

	if settings.UseLocalLLM != true {
		t.Errorf("Expected UseLocalLLM true, got %t", settings.UseLocalLLM)
	}

	if settings.OllamaModel != "custom/model:latest" {
		t.Errorf("Expected OllamaModel 'custom/model:latest', got '%s'", settings.OllamaModel)
	}

	if settings.OllamaEndpoint != "http://custom:8080" {
		t.Errorf("Expected OllamaEndpoint 'http://custom:8080', got '%s'", settings.OllamaEndpoint)
	}
}

func TestLoadSettings_PartialEnvFile(t *testing.T) {
	envContent := `OPENAI_API_KEY=partial-test-key
# USE_LOCAL_LLM is commented out
OLLAMA_MODEL=partial/model`

	_, cleanup := createTestEnvFile(t, envContent)
	defer cleanup()

	settings, err := LoadSettings()
	if err != nil {
		t.Fatalf("LoadSettings failed: %v", err)
	}

	if settings.OpenAIAPIKey != "partial-test-key" {
		t.Errorf("Expected OpenAIAPIKey 'partial-test-key', got '%s'", settings.OpenAIAPIKey)
	}

	// Should use default for unspecified values
	defaultSettings := DefaultSettings()
	if settings.UseLocalLLM != defaultSettings.UseLocalLLM {
		t.Errorf("Expected UseLocalLLM to use default %t, got %t", defaultSettings.UseLocalLLM, settings.UseLocalLLM)
	}

	if settings.OllamaModel != "partial/model" {
		t.Errorf("Expected OllamaModel 'partial/model', got '%s'", settings.OllamaModel)
	}

	if settings.OllamaEndpoint != defaultSettings.OllamaEndpoint {
		t.Errorf("Expected OllamaEndpoint to use default '%s', got '%s'", defaultSettings.OllamaEndpoint, settings.OllamaEndpoint)
	}
}

func TestLoadSettings_WithComments(t *testing.T) {
	envContent := `# This is a comment
OPENAI_API_KEY=test-key-with-comments

# Another comment
USE_LOCAL_LLM=false

# Model configuration
OLLAMA_MODEL=commented/model:tag
OLLAMA_ENDPOINT=http://localhost:11434`

	_, cleanup := createTestEnvFile(t, envContent)
	defer cleanup()

	settings, err := LoadSettings()
	if err != nil {
		t.Fatalf("LoadSettings failed: %v", err)
	}

	if settings.OpenAIAPIKey != "test-key-with-comments" {
		t.Errorf("Expected OpenAIAPIKey 'test-key-with-comments', got '%s'", settings.OpenAIAPIKey)
	}

	if settings.UseLocalLLM != false {
		t.Errorf("Expected UseLocalLLM false, got %t", settings.UseLocalLLM)
	}

	if settings.OllamaModel != "commented/model:tag" {
		t.Errorf("Expected OllamaModel 'commented/model:tag', got '%s'", settings.OllamaModel)
	}

	if settings.OllamaEndpoint != "http://localhost:11434" {
		t.Errorf("Expected OllamaEndpoint 'http://localhost:11434', got '%s'", settings.OllamaEndpoint)
	}
}

func TestLoadSettings_EmptyValues(t *testing.T) {
	envContent := `OPENAI_API_KEY=
USE_LOCAL_LLM=
OLLAMA_MODEL=
OLLAMA_ENDPOINT=`

	_, cleanup := createTestEnvFile(t, envContent)
	defer cleanup()

	settings, err := LoadSettings()
	if err != nil {
		t.Fatalf("LoadSettings failed: %v", err)
	}

	// Empty values should remain empty (not fall back to defaults)
	if settings.OpenAIAPIKey != "" {
		t.Errorf("Expected OpenAIAPIKey to be empty, got '%s'", settings.OpenAIAPIKey)
	}

	if settings.UseLocalLLM != false {
		t.Errorf("Expected UseLocalLLM false (empty string parsed as false), got %t", settings.UseLocalLLM)
	}

	if settings.OllamaModel != "" {
		t.Errorf("Expected OllamaModel to be empty, got '%s'", settings.OllamaModel)
	}

	if settings.OllamaEndpoint != "" {
		t.Errorf("Expected OllamaEndpoint to be empty, got '%s'", settings.OllamaEndpoint)
	}
}

func TestLoadSettings_BooleanParsing(t *testing.T) {
	testCases := []struct {
		value    string
		expected bool
	}{
		{"true", true},
		{"TRUE", true},
		{"True", true},
		{"1", true},
		{"false", false},
		{"FALSE", false},
		{"False", false},
		{"0", false},
		{"", false},
		{"invalid", false},
	}

	for _, tc := range testCases {
		envContent := "USE_LOCAL_LLM=" + tc.value

		_, cleanup := createTestEnvFile(t, envContent)

		settings, err := LoadSettings()
		if err != nil {
			t.Fatalf("LoadSettings failed for value '%s': %v", tc.value, err)
		}

		if settings.UseLocalLLM != tc.expected {
			t.Errorf("For value '%s', expected UseLocalLLM %t, got %t", tc.value, tc.expected, settings.UseLocalLLM)
		}

		cleanup()
	}
}

func TestLoadSettings_WhitespaceHandling(t *testing.T) {
	envContent := `  OPENAI_API_KEY  =  test-key-with-spaces  
	USE_LOCAL_LLM=true   
OLLAMA_MODEL=   model-with-spaces   
OLLAMA_ENDPOINT=http://localhost:11434`

	_, cleanup := createTestEnvFile(t, envContent)
	defer cleanup()

	settings, err := LoadSettings()
	if err != nil {
		t.Fatalf("LoadSettings failed: %v", err)
	}

	if settings.OpenAIAPIKey != "test-key-with-spaces" {
		t.Errorf("Expected OpenAIAPIKey 'test-key-with-spaces', got '%s'", settings.OpenAIAPIKey)
	}

	if settings.UseLocalLLM != true {
		t.Errorf("Expected UseLocalLLM true, got %t", settings.UseLocalLLM)
	}

	if settings.OllamaModel != "model-with-spaces" {
		t.Errorf("Expected OllamaModel 'model-with-spaces', got '%s'", settings.OllamaModel)
	}
}

func TestLoadSettings_InvalidEqualsSign(t *testing.T) {
	envContent := `OPENAI_API_KEY=valid-key
INVALID_LINE_NO_EQUALS
USE_LOCAL_LLM=true`

	_, cleanup := createTestEnvFile(t, envContent)
	defer cleanup()

	settings, err := LoadSettings()
	if err != nil {
		t.Fatalf("LoadSettings failed: %v", err)
	}

	// Should skip invalid lines and continue
	if settings.OpenAIAPIKey != "valid-key" {
		t.Errorf("Expected OpenAIAPIKey 'valid-key', got '%s'", settings.OpenAIAPIKey)
	}

	if settings.UseLocalLLM != true {
		t.Errorf("Expected UseLocalLLM true, got %t", settings.UseLocalLLM)
	}
}

func TestHasValidConfig(t *testing.T) {
	testCases := []struct {
		name     string
		settings *Settings
		expected bool
	}{
		{
			name: "OpenAI API Key only",
			settings: &Settings{
				OpenAIAPIKey:   "test-key",
				UseLocalLLM:    false,
				OllamaModel:    "",
				OllamaEndpoint: "",
			},
			expected: true,
		},
		{
			name: "Local LLM only",
			settings: &Settings{
				OpenAIAPIKey:   "",
				UseLocalLLM:    true,
				OllamaModel:    "test-model",
				OllamaEndpoint: "http://localhost:11434",
			},
			expected: true,
		},
		{
			name: "Both configured",
			settings: &Settings{
				OpenAIAPIKey:   "test-key",
				UseLocalLLM:    true,
				OllamaModel:    "test-model",
				OllamaEndpoint: "http://localhost:11434",
			},
			expected: true,
		},
		{
			name: "No configuration",
			settings: &Settings{
				OpenAIAPIKey:   "",
				UseLocalLLM:    false,
				OllamaModel:    "",
				OllamaEndpoint: "",
			},
			expected: false,
		},
		{
			name: "Local LLM enabled but missing model",
			settings: &Settings{
				OpenAIAPIKey:   "",
				UseLocalLLM:    true,
				OllamaModel:    "",
				OllamaEndpoint: "http://localhost:11434",
			},
			expected: false,
		},
		{
			name: "Local LLM enabled but missing endpoint",
			settings: &Settings{
				OpenAIAPIKey:   "",
				UseLocalLLM:    true,
				OllamaModel:    "test-model",
				OllamaEndpoint: "",
			},
			expected: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			result := tc.settings.HasValidConfig()
			if result != tc.expected {
				t.Errorf("Expected HasValidConfig() to return %t, got %t", tc.expected, result)
			}
		})
	}
}

func TestSaveSettings(t *testing.T) {
	// Create a temporary directory
	tempDir, err := os.MkdirTemp("", "settings_save_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	// Change to temp directory
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}
	defer os.Chdir(originalDir)

	err = os.Chdir(tempDir)
	if err != nil {
		t.Fatalf("Failed to change to temp directory: %v", err)
	}

	// Create settings to save
	settings := &Settings{
		OpenAIAPIKey:   "test-save-key",
		UseLocalLLM:    true,
		OllamaModel:    "test/save:model",
		OllamaEndpoint: "http://test:11434",
	}

	err = settings.SaveSettings()
	if err != nil {
		t.Fatalf("SaveSettings failed: %v", err)
	}

	// Verify .env file was created and contains correct content
	envContent, err := os.ReadFile(".env")
	if err != nil {
		t.Fatalf("Failed to read saved .env file: %v", err)
	}

	content := string(envContent)

	expectedLines := []string{
		"OPENAI_API_KEY=test-save-key",
		"USE_LOCAL_LLM=true",
		"OLLAMA_MODEL=test/save:model",
		"OLLAMA_ENDPOINT=http://test:11434",
	}

	for _, line := range expectedLines {
		if !strings.Contains(content, line) {
			t.Errorf("Expected .env file to contain '%s', but it didn't. Content:\n%s", line, content)
		}
	}

	// Test loading the saved settings
	loadedSettings, err := LoadSettings()
	if err != nil {
		t.Fatalf("Failed to load saved settings: %v", err)
	}

	if loadedSettings.OpenAIAPIKey != settings.OpenAIAPIKey {
		t.Errorf("Expected loaded OpenAIAPIKey '%s', got '%s'", settings.OpenAIAPIKey, loadedSettings.OpenAIAPIKey)
	}

	if loadedSettings.UseLocalLLM != settings.UseLocalLLM {
		t.Errorf("Expected loaded UseLocalLLM %t, got %t", settings.UseLocalLLM, loadedSettings.UseLocalLLM)
	}

	if loadedSettings.OllamaModel != settings.OllamaModel {
		t.Errorf("Expected loaded OllamaModel '%s', got '%s'", settings.OllamaModel, loadedSettings.OllamaModel)
	}

	if loadedSettings.OllamaEndpoint != settings.OllamaEndpoint {
		t.Errorf("Expected loaded OllamaEndpoint '%s', got '%s'", settings.OllamaEndpoint, loadedSettings.OllamaEndpoint)
	}
}
