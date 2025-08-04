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
	list       list.Model
	gpt        *GPT
	dataLoader *DataLoader
	players    []Player // The original slice of player data
	output     string   // Holds the response from ChatGPT
	querying   bool
	lastQuery  time.Time
	notice     string
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
		list:       l,
		gpt:        g,
		dataLoader: loader,
		players:    players,
		lastQuery:  time.Now().Add(-5 * time.Second),
	}
}

/* --------------------------- Bubble Tea ---------------------------------- */

type chatMsg string             // A successful response from ChatGPT
type errMsg struct{ err error } // An error that occurred during the process

func (e errMsg) Error() string { return e.err.Error() }

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.list.SetSize(msg.Width-rightWidth, msg.Height)
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "q":
			if m.querying {
				break
			}
			if time.Since(m.lastQuery) < 5*time.Second {
				m.notice = "Wait 5 seconds between ChatGPT queries"
				return m, nil
			}
			m.notice, m.querying, m.lastQuery = "", true, time.Now()
			m.output = "" // Clear previous output before new query

			// This function now runs in the background to process ALL players.
			return m, func() tea.Msg {
				// 1. Build the notes string using the new DataLoader method.
				allNotes, err := m.dataLoader.BuildAllNotes(m.players)
				if err != nil {
					return errMsg{err}
				}

				// 3. This is the new prompt for a field-wide summary.
				pickNum, err := m.dataLoader.LoadCurrentPickNum()
				if err != nil {
					log.Printf("Warning: could not load current pick number: %v", err)
					pickNum = 0
				}

				// Load the current team, handling any potential error.
				currentTeam, err := m.dataLoader.LoadCurrentTeam()
				if err != nil {
					log.Printf("Warning: could not load current team: %v", err)
					currentTeam = "[Team not available]"
				}

				// Now that we have the values in variables, we can safely construct the prompt.
				// I've also added spaces between the concatenated parts for better formatting.
				prompt := fmt.Sprintf(
					"It is pick %d of a 2025 fantasy football draft. "+
						"This is my current team: %s. "+
						"Output the top several players you think could help me the most along with an explanation, considering their value, upside, and drawbacks. "+
						"Give a summary of the most important players at the end once you are finished your explanations. "+
						"The notes for each player are separated by '---start playername---' and '---end playername---'.\n\n"+
						"Player Notes:\n%s",
					pickNum, currentTeam, allNotes,
				)

				// 4. Ask ChatGPT and return the answer.
				ans, err := m.gpt.Ask(prompt)
				if err != nil {
					log.Printf("Error from GPT API for field summary: %v", err)
					return errMsg{err}
				}
				return chatMsg(ans)
			}

		case "esc", "ctrl+c":
			return m, tea.Quit
		}

	// This handles the successful response from ChatGPT.
	case chatMsg:
		m.querying, m.output = false, string(msg)
		return m, nil

	// This handles any errors that occurred in our background function.
	case errMsg:
		m.querying = false
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

	rightHeader := headerStyle.Render("q → ChatGPT   Esc → quit")

	var body string
	switch {
	case m.notice != "":
		body = lipgloss.NewStyle().Foreground(lipgloss.Color("#ff0000")).Render(m.notice)
	case m.querying:
		body = "Querying ChatGPT…"
	default:
		body = m.output
	}

	right := lipgloss.JoinVertical(lipgloss.Left, rightHeader, bodyStyle.Render(body))

	return lipgloss.JoinHorizontal(lipgloss.Top, m.list.View(), right)
}
