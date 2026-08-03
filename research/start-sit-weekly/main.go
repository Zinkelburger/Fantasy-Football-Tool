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

	// Initialize ESPN client
	espnClient := NewESPNClient()

	// Create UI
	ui := NewESPNUI(fyneApp, espnClient)
	ui.Show()
	fyneApp.Run()

	log.Println("Application exiting")
}