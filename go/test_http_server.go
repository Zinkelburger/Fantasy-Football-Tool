package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// testHTTPServer sends a test request to the HTTP server
func testHTTPServer() {
	// Wait a moment for the server to start
	time.Sleep(2 * time.Second)

	// Create test data
	testData := PlayerNamesRequest{
		PlayerNames: []string{"Josh Allen", "Saquon Barkley", "Ja'Marr Chase"},
	}

	// Convert to JSON
	jsonData, err := json.Marshal(testData)
	if err != nil {
		fmt.Printf("Error marshaling JSON: %v\n", err)
		return
	}

	// Send POST request
	resp, err := http.Post("http://localhost:8000", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		fmt.Printf("Error sending request: %v\n", err)
		return
	}
	defer resp.Body.Close()

	// Check response
	if resp.StatusCode == http.StatusOK {
		fmt.Println("✓ HTTP server test successful!")
		fmt.Printf("Response status: %s\n", resp.Status)
	} else {
		fmt.Printf("✗ HTTP server test failed with status: %s\n", resp.Status)
	}

	// Send another request with one new player and one duplicate
	testData2 := PlayerNamesRequest{
		PlayerNames: []string{"Josh Allen", "CeeDee Lamb"}, // Josh Allen is duplicate
	}

	jsonData2, err := json.Marshal(testData2)
	if err != nil {
		fmt.Printf("Error marshaling JSON: %v\n", err)
		return
	}

	resp2, err := http.Post("http://localhost:8000", "application/json", bytes.NewBuffer(jsonData2))
	if err != nil {
		fmt.Printf("Error sending second request: %v\n", err)
		return
	}
	defer resp2.Body.Close()

	if resp2.StatusCode == http.StatusOK {
		fmt.Println("✓ Second HTTP server test successful!")
		fmt.Printf("Response status: %s\n", resp2.Status)
	} else {
		fmt.Printf("✗ Second HTTP server test failed with status: %s\n", resp2.Status)
	}
}

func main() {
	fmt.Println("Testing HTTP server functionality...")
	
	// Start the HTTP server
	logDir := "test_log"
	httpPort := 8000
	server := StartHTTPServerAsync(logDir, httpPort)
	fmt.Printf("Started test HTTP server on port %d\n", httpPort)
	_ = server

	// Test the server
	testHTTPServer()
	
	fmt.Println("Test complete. Check the test_log directory for generated files.")
}
