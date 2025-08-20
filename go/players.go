package main

import (
	"encoding/csv"
	"fmt"
	"os"
)

type Player struct {
	Name  string
	Team  string
	Pos   string
	Depth string
	Rank  string
}

func LoadPlayers(path string) ([]Player, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	rows, err := csv.NewReader(f).ReadAll()
	if err != nil {
		return nil, err
	}

	var ps []Player
	for i, r := range rows {
		if i == 0 {  // Skip header
			continue
		}
		
		// Validate we have enough columns
		if len(r) < 10 {
			return nil, fmt.Errorf("CSV row %d has %d columns, expected at least 10", i, len(r))
		}
		
		ps = append(ps, Player{
			Name:  r[0],
			Team:  r[1],
			Pos:   r[5],
			Depth: r[9],
			Rank:  r[2],
		})
	}
	return ps, nil
}
