---
id: depth-handcuffs
title: See a player's depth chart and spot your handcuffs
status: implemented
---

**As a user, I want to** see where a player sits on his NFL team's
depth chart at his position, and get flagged when he is the direct
backup to someone I already drafted — the handcuff worth a late pick
(finding 13).

## Steps
1. Hover any player's Pos cell on the board.
2. Draft a running back to your team, then look at his direct backup's
   row.

## Expected
- The Pos cell tooltip lists the team's top depth entries at that
  position, ranked, each with "n behind" the top player (never a
  signed number). More than four entries collapses to "…n more".
- The Pos cell shows the player's depth slot (e.g. `RB2`) after the
  position.
- When the player directly behind one of *your* players, a ⛓ appears
  in his Pos cell and the tooltip leads with "Handcuff to your <name>".
  Your own players are marked "← yours" in the tooltip list.
- The Pos column header tooltip advertises the hover.

## Verify against
- `webapp/app.js` — `depthInfo()`, `depthListByName`/`depthByName`,
  Pos cell in `renderTable()`
- `webapp/style.css` — `.hc-mark`, `.pos-cell`
- `webapp/index.html` — Pos column header title
