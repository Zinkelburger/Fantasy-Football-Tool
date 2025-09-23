package main

import (
	"os"
	"path/filepath"
	"runtime"
)

// getAppDir returns the directory where the application's data files are located
// This handles different deployment scenarios: development, .deb package, macOS bundle, etc.
func getAppDir() string {
	// List of potential data directories to check, in order of preference
	candidateDirs := []string{}
	
	// FIRST PRIORITY: Always check go/ directory first (for development and most deployments)
	candidateDirs = append(candidateDirs, "go")
	candidateDirs = append(candidateDirs, "./go")
	
	// On Linux, check if we're running from a system installation (.deb/.rpm package)
	if runtime.GOOS == "linux" {
		candidateDirs = append(candidateDirs, "/usr/share/fantasy-football-tool")
	}
	
	// On macOS, if we're in an app bundle, the data files are in the Resources directory
	if runtime.GOOS == "darwin" {
		if execPath, err := os.Executable(); err == nil {
			// If we're in a .app bundle: /path/to/MyApp.app/Contents/MacOS/MyApp
			// Data files are in: /path/to/MyApp.app/Contents/Resources/
			appPath := filepath.Dir(execPath)                    // Contents/MacOS
			contentsPath := filepath.Dir(appPath)                // Contents
			resourcesPath := filepath.Join(contentsPath, "Resources")
			candidateDirs = append(candidateDirs, resourcesPath)
			
			// Also check parent of the .app bundle for backward compatibility
			bundlePath := filepath.Dir(contentsPath)             // MyApp.app
			parentPath := filepath.Dir(bundlePath)               // parent directory
			candidateDirs = append(candidateDirs, parentPath)
		}
	}
	
	// Always check current working directory last (for development/extracted packages)
	candidateDirs = append(candidateDirs, ".")
	
	// Return the first directory that contains our key data files
	for _, dir := range candidateDirs {
		if _, err := os.Stat(filepath.Join(dir, "players.csv")); err == nil {
			if _, err := os.Stat(filepath.Join(dir, "analysis")); err == nil {
				return dir
			}
		}
	}
	
	// Fallback to current directory
	return "."
}

// getDataPath returns the full path to a data file or directory
func getDataPath(relativePath string) string {
	return filepath.Join(getAppDir(), relativePath)
}

// getWritableDir returns a directory where the app can write files (logs, status, etc.)
func getWritableDir() string {
	// On Linux, if we're installed as a system package, use user's home directory
	if runtime.GOOS == "linux" {
		if execPath, _ := os.Executable(); execPath == "/usr/bin/fantasy-football-tool" {
			// We're running from system installation, use user data directory
			if homeDir, err := os.UserHomeDir(); err == nil {
				userDataDir := filepath.Join(homeDir, ".local", "share", "fantasy-football-tool")
				// Create the directory if it doesn't exist
				if err := os.MkdirAll(userDataDir, 0755); err == nil {
					return userDataDir
				}
			}
		}
	}
	
	// Default: current working directory (for development/extracted packages)
	return "."
}

// getWritablePath returns the full path to a writable file or directory
func getWritablePath(relativePath string) string {
	return filepath.Join(getWritableDir(), relativePath)
}
