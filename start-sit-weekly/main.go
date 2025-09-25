package main

import (
	"log"
	"os"

	"fyne.io/fyne/v2/app"
	"github.com/joho/godotenv"
)

func main() {
	// Load environment variables
	if _, err := os.Stat(".env"); err == nil {
		if err := godotenv.Load(); err != nil {
			log.Printf("Warning: Error loading .env file: %v", err)
		} else {
			log.Printf("Info: Loaded configuration from .env file")
		}
	} else {
		log.Printf("Info: No .env file found, will try browser extension")
	}

	// Create Fyne app
	fyneApp := app.New()
	fyneApp.SetIcon(resourceLogoPng)
	fyneApp.Settings().SetTheme(&customTheme{})

	// Initialize Python ESPN client
	pythonClient := NewPythonESPNClient()

	// Check Python dependencies
	if err := pythonClient.CheckPythonDependencies(); err != nil {
		log.Printf("Warning: Python dependencies not available: %v", err)
	}

	// Create UI
	ui := NewESPNUI(fyneApp, pythonClient)
	ui.Show()
	fyneApp.Run()

	log.Println("Application exiting")
}