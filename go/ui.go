package main

import (
	"fmt"
	"log"
	"time"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

/* --------------------------- list item ----------------------------------- */

// This struct defines an item in our list.
type playerItem struct{ title string }

func (p playerItem) Title() string       { return p.title }
func (p playerItem) Description() string { return "" }
func (p playerItem) FilterValue() string { return p.title }

/* --------------------------- model --------------------------------------- */

const rightWidth = 50 // Increased width for better summary display

// The model holds the application's state.
// We've added dataLoader and players so the UI knows about our data.
type model struct {
	list         list.Model
	gpt          *GPT
	dataLoader   *DataLoader
	players      []Player // The original slice of player data
	output       string   // Holds the response from ChatGPT
	querying     bool
	refreshing   bool     // tracks if we're refreshing player data
	lastQuery    time.Time
	lastRefresh  time.Time // tracks when we last refreshed player data
	notice       string
}

func newModel(players []Player, loader *DataLoader, g *GPT) model {
	items := make([]list.Item, len(players))
	for i, p := range players {
		items[i] = playerItem{fmt.Sprintf("%-4s %-20s %-5s %-3s",
			p.Rank, p.Name, p.Depth, p.Team)}
	}

	delegate := list.NewDefaultDelegate()
	delegate.ShowDescription = false
	delegate.SetSpacing(0)

	l := list.New(items, delegate, 0, 0)
	l.DisableQuitKeybindings()
	l.Title = fmt.Sprintf("%-4s %-20s %-5s %-3s", "Rank", "Name", "Depth", "Team")
	l.SetShowStatusBar(false)
	l.SetShowPagination(false)
	l.SetShowHelp(false)
	l.SetShowFilter(false)
	l.SetFilteringEnabled(false)

	return model{
		list:        l,
		gpt:         g,
		dataLoader:  loader,
		players:     players,
		lastQuery:   time.Now().Add(-5 * time.Second),
		lastRefresh: time.Now(), // Initialize refresh time
	}
}

// autoRefreshCmd returns a command that triggers automatic refresh
func autoRefreshCmd() tea.Cmd {
	return tea.Tick(3*time.Second, func(t time.Time) tea.Msg {
		return autoRefreshMsg(t)
	})
}

// refreshPlayerData is a helper function to refresh player data
func (m model) refreshPlayerData() tea.Cmd {
	return func() tea.Msg {
		// Try to find the latest filtered log file
		latestLogFile, err := m.dataLoader.FindLatestLogFile()
		if err != nil {
			// No filtered files found - this is normal at the start
			log.Printf("No filtered log file found, keeping current data: %v", err)
			return refreshMsg(m.players) // Return current players unchanged
		}
		
		// Load players from the latest filtered file
		updatedPlayers, err := LoadPlayers(latestLogFile)
		if err != nil {
			log.Printf("Failed to load players from %s: %v", latestLogFile, err)
			return refreshMsg(m.players) // Return current players unchanged on error
		}
		
		log.Printf("Refreshed player data from %s, loaded %d players", latestLogFile, len(updatedPlayers))
		return refreshMsg(updatedPlayers)
	}
}

/* --------------------------- Bubble Tea ---------------------------------- */

type chatMsg string                    // A successful response from ChatGPT
type refreshMsg []Player               // successful refresh of player data
type autoRefreshMsg time.Time          // automatic refresh trigger
type errMsg struct{ err error }        // An error that occurred during the process

func (e errMsg) Error() string { return e.err.Error() }

func (m model) Init() tea.Cmd { 
	// Start the automatic refresh timer
	return autoRefreshCmd()
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.list.SetSize(msg.Width-rightWidth, msg.Height)
		return m, nil

	case autoRefreshMsg:
		// Automatic refresh every 3 seconds (only if not already refreshing/querying)
		if !m.refreshing && !m.querying {
			m.refreshing = true
			m.lastRefresh = time.Time(msg)
			return m, tea.Batch(m.refreshPlayerData(), autoRefreshCmd())
		}
		// If busy, just set up next refresh
		return m, autoRefreshCmd()

	case tea.KeyMsg:
		switch msg.String() {
		case "r":
			// Manual refresh - still useful for immediate refresh
			if m.refreshing || m.querying {
				break
			}
			m.notice, m.refreshing = "", true
			m.output = "" // Clear previous output
			m.lastRefresh = time.Now()
			
			return m, m.refreshPlayerData()
			
		case "q":
			if m.querying || m.refreshing {
				break
			}
			if time.Since(m.lastQuery) < 5*time.Second {
				m.notice = "Wait 5 seconds between ChatGPT queries"
				return m, nil
			}
			m.notice, m.querying, m.lastQuery = "", true, time.Now()
			m.output = "" // Clear previous output before new query

			// Always refresh player data before ChatGPT query
			return m, func() tea.Msg {
				// First, refresh player data
				latestLogFile, err := m.dataLoader.FindLatestLogFile()
				if err == nil {
					if updatedPlayers, err := LoadPlayers(latestLogFile); err == nil {
						log.Printf("Pre-query refresh: loaded %d players from %s", len(updatedPlayers), latestLogFile)
						// Update the model's players for the ChatGPT query
						return struct {
							players []Player
							msg     string
						}{updatedPlayers, "refresh_and_query"}
					}
				}
				
				// If refresh failed, proceed with current players
				log.Printf("Pre-query refresh failed, using current players")
				return struct {
					players []Player
					msg     string
				}{m.players, "refresh_and_query"}
			}

		case "esc", "ctrl+c":
			return m, tea.Quit
		}

	// Handle the refresh-and-query message
	case struct {
		players []Player
		msg     string
	}:
		if msg.msg == "refresh_and_query" {
			// Update players and continue with ChatGPT query
			m.players = msg.players
			
			// Rebuild the list items with updated player data
			items := make([]list.Item, len(m.players))
			for i, p := range m.players {
				items[i] = playerItem{fmt.Sprintf("%-4s %-20s %-5s %-3s",
					p.Rank, p.Name, p.Depth, p.Team)}
			}
			m.list.SetItems(items)
			
			// Now proceed with ChatGPT query using updated players
			return m, func() tea.Msg {
				// Build the notes string using the updated players
				allNotes, err := m.dataLoader.BuildAllNotes(m.players)
				if err != nil {
					return errMsg{err}
				}

				// Get current context
				pickNum, err := m.dataLoader.LoadCurrentPickNum()
				if err != nil {
					log.Printf("Warning: could not load current pick number: %v", err)
					pickNum = 0
				}

				currentTeam, err := m.dataLoader.LoadCurrentTeam()
				if err != nil {
					log.Printf("Warning: could not load current team: %v", err)
					currentTeam = "[Team not available]"
				}

				// Construct the prompt
				prompt := fmt.Sprintf(
					"It is pick %d of a 2025 fantasy football draft. "+
						"This is my current team: %s. "+
						"Output the top several players you think could help me the most along with an explanation, considering their value, upside, and drawbacks. "+
						"Give a summary of the most important players at the end once you are finished your explanations. "+
						"The notes for each player are separated by '---start playername---' and '---end playername---'.\n\n"+
						"Player Notes:\n%s",
					pickNum, currentTeam, allNotes,
				)

				// Ask ChatGPT and return the answer
				ans, err := m.gpt.Ask(prompt)
				if err != nil {
					log.Printf("Error from GPT API for field summary: %v", err)
					return errMsg{err}
				}
				return chatMsg(ans)
			}
		}

	// This handles the successful refresh of player data
	case refreshMsg:
		m.refreshing = false
		
		// Only update if the data actually changed
		if len([]Player(msg)) != len(m.players) || (len(msg) > 0 && msg[0].Name != m.players[0].Name) {
			m.players = []Player(msg) // Update the players slice
			
			// Rebuild the list items with updated player data
			items := make([]list.Item, len(m.players))
			for i, p := range m.players {
				items[i] = playerItem{fmt.Sprintf("%-4s %-20s %-5s %-3s",
					p.Rank, p.Name, p.Depth, p.Team)}
			}
			m.list.SetItems(items)
			
			// Only show refresh message if it's a manual refresh
			if time.Since(m.lastRefresh) < 1*time.Second {
				m.output = fmt.Sprintf("Refreshed: %d players (updated %s)", 
					len(m.players), time.Now().Format("15:04:05"))
			}
		}
		return m, nil

	// This handles the successful response from ChatGPT.
	case chatMsg:
		m.querying, m.output = false, string(msg)
		return m, nil

	// This handles any errors that occurred in our background function.
	case errMsg:
		m.querying, m.refreshing = false, false
		m.output = lipgloss.NewStyle().Foreground(lipgloss.Color("9")).Render("Error: " + msg.Error())
		return m, nil
	}

	var cmd tea.Cmd
	m.list, cmd = m.list.Update(msg)
	return m, cmd
}

func (m model) View() string {
	// Styles for the right-hand panel.
	headerStyle := lipgloss.NewStyle().
		Width(rightWidth).
		Foreground(lipgloss.Color("#fff")).
		Background(lipgloss.Color("#5d3fd3")).
		Padding(0, 1)

	bodyStyle := lipgloss.NewStyle().
		Width(rightWidth-2). // Adjust for padding.
		Height(m.list.Height()-2).
		Border(lipgloss.NormalBorder()).
		BorderForeground(lipgloss.Color("#5d3fd3")).
		Padding(0, 1)

	rightHeader := headerStyle.Render("Auto-refresh ON   q → ChatGPT   Esc → quit")

	var body string
	switch {
	case m.notice != "":
		body = lipgloss.NewStyle().Foreground(lipgloss.Color("#ff0000")).Render(m.notice)
	case m.refreshing:
		body = "Refreshing player data…"
	case m.querying:
		body = "Querying ChatGPT…"
	default:
		body = m.output
	}

	right := lipgloss.JoinVertical(lipgloss.Left, rightHeader, bodyStyle.Render(body))

	return lipgloss.JoinHorizontal(lipgloss.Top, m.list.View(), right)
}
