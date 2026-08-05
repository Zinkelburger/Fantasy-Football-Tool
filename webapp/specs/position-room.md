---
id: position-room
title: See who else is in a player's position room before I draft him
status: implemented
---

**As a user, I want to** know, without leaving the note panel, whether
a player is his team's clear starter at his position or is stacked
behind someone — and whether his team just drafted a rookie to take his
job.

## Steps
1. Open any player's tab (click him on the board or in search).
2. Read the line under the player meta, above the findings marks.

## Expected
- One plain sentence naming his rank in his own team's position room on
  the draft board, e.g. *"He's CIN's WR1 on the draft board — 31 picks
  ahead of their WR2 (Tee Higgins)."*
- The gap to the man ahead of him and/or the man behind him is given in
  picks. A gap of 0 reads *"priced level with <name>"*; anything at or
  past the 200-pick cap reads *"200+ picks"* rather than a fake exact
  number.
- If his team spent a pick inside the top 100 at his position this
  year, that is named — either inline when the rookie IS the man next
  to him (*"…their QB2 (Ty Simpson, this year's pick 13)"*) or as its
  own sentence (*"NYG spent pick 74 on a WR (Malachi Fields)."*).
  Picks after 100 are not mentioned; a 7th-rounder is not competition.
- Team codes match the rest of the tool (`DET`, `SF`), not nicknames.
- The line is **descriptive context, not a model opinion**: it gets no
  row glyph on the board and is *not* hidden by the **Model marks**
  switch. The room order is read off ADP, so it is not a disagreement
  with the market — finding 25 measured it adding nothing on top of
  ADP.
- Players with no room data (rookies, and anyone not on the returning-
  player projection board) simply show no line — the panel renders
  normally without it.
- The room follows the active scoring format: switching STD / 0.5PPR /
  PPR can change the ordering and the gaps.

## Data
`engine/league-sim/analysis/player_model.py` (`room_standing`) writes
the room columns into `data/market/model_board_2026{,_half,_ppr}.csv`;
`webapp/build_data.py` (`load_rooms`) bundles them per format.
