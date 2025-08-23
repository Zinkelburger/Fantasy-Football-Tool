package main

import (
	"os"
	"path/filepath"
	"runtime"
)

// getAppDir returns the directory where the application's data files are located
// This handles the case where on macOS, the working directory might not be the same
// as the directory containing the .app bundle
func getAppDir() string {
	// On macOS, if we're in an app bundle, the data files are in the same directory
	// as the .app bundle, not inside it
	if runtime.GOOS == "darwin" {
		if execPath, err := os.Executable(); err == nil {
			// If we're in a .app bundle: /path/to/MyApp.app/Contents/MacOS/MyApp
			// We want to go up to: /path/to/ (parent of MyApp.app)
			appPath := filepath.Dir(execPath)                    // Contents/MacOS
			contentsPath := filepath.Dir(appPath)                // Contents
			bundlePath := filepath.Dir(contentsPath)             // MyApp.app
			parentPath := filepath.Dir(bundlePath)               // parent directory
			
			// Check if data files exist in the parent directory
			if _, err := os.Stat(filepath.Join(parentPath, "players.csv")); err == nil {
				return parentPath
			}
		}
	}
	
	// Default: current working directory
	return "."
}

// getDataPath returns the full path to a data file or directory
func getDataPath(relativePath string) string {
	return filepath.Join(getAppDir(), relativePath)
}
