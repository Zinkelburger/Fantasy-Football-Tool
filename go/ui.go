package main

import (
	"fmt"
	"time"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

/* --------------------------- list item ----------------------------------- */

type playerItem struct{ title string }

func (p playerItem) Title() string       { return p.title }
func (p playerItem) Description() string { return "" }
func (p playerItem) FilterValue() string { return p.title }

/* --------------------------- model --------------------------------------- */

const rightWidth = 40

type model struct {
	list      list.Model
	gpt       *GPT
	output    string
	querying  bool
	lastQuery time.Time
	notice    string
}

func newModel(players []Player, g *GPT) model {
	items := make([]list.Item, len(players))
	for i, p := range players {
		items[i] = playerItem{fmt.Sprintf("%4s %-20s %-5s %-3s",
			p.Rank, p.Name, p.Depth, p.Team)}
	}

	delegate := list.NewDefaultDelegate()
	delegate.ShowDescription = false
	delegate.SetSpacing(0)

	l := list.New(items, delegate, 0, 0)
	l.DisableQuitKeybindings()
	l.Title = fmt.Sprintf("%4s %-20s %-5s %-3s", "Rank", "Name", "Depth", "Team")
	l.SetShowStatusBar(false)
	l.SetShowPagination(false)
	l.SetShowHelp(false)
	l.SetShowFilter(false)
	l.SetFilteringEnabled(false)

	return model{list: l, gpt: g, lastQuery: time.Now().Add(-5 * time.Second)}
}

/* --------------------------- Bubble Tea ---------------------------------- */

type chatMsg string

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
				m.notice = "wait 5 seconds between successive ChatGPT queries"
				return m, nil
			}
			m.notice, m.querying, m.lastQuery = "", true, time.Now()
			return m, func() tea.Msg {
				ans, err := m.gpt.Ask("Who should I pick next?")
				if err != nil {
					return chatMsg(err.Error())
				}
				return chatMsg(ans)
			}
		case "esc", "ctrl+c":
			return m, tea.Quit
		}

	case chatMsg:
		m.querying, m.output = false, string(msg)
		return m, nil
	}

	var cmd tea.Cmd
	m.list, cmd = m.list.Update(msg)
	return m, cmd
}

func (m model) View() string {
	headerStyle := lipgloss.NewStyle().
		Width(rightWidth).
		Foreground(lipgloss.Color("#fff")).
		Background(lipgloss.Color("#5d3fd3")).
		Padding(0, 1)
	bodyStyle := lipgloss.NewStyle().
		Width(rightWidth).
		Background(lipgloss.Color("#5d3fd3")).
		Padding(0, 1)

	right := headerStyle.Render("q → ChatGPT   Esc → quit")

	var body string
	switch {
	case m.notice != "":
		body = lipgloss.NewStyle().Foreground(lipgloss.Color("#ff0000")).Render(m.notice)
	case m.querying:
		body = "querying ChatGPT…"
	default:
		body = m.output
	}
	if body != "" {
		right = lipgloss.JoinVertical(lipgloss.Left, right, bodyStyle.Render(body))
	}
	return lipgloss.JoinHorizontal(lipgloss.Top, m.list.View(), right)
}
