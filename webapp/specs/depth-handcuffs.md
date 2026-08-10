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
2. Draft a running back to your team, then scan the board for his
   backup — the row finds you.

## Expected
- The Pos cell tooltip lists the team's top depth entries at that
  position, ranked, each with "n behind" the top player (never a
  signed number). More than four entries collapses to "…n more".
- The Pos cell shows the player's depth slot (e.g. `RB2`) after the
  position.
- **The whole row is highlighted** — green tint, green bar down the
  first cell — when an available player is the direct backup to a
  **running back** on your roster. The handcuff is usually 100+ ranks
  down the board (Pacheco is rank 151 behind Gibbs at 1), so a mark
  inside one cell loses to the scan; the row is the thing that finds
  it. His Pos cell also turns green, and the tooltip leads with "Backs
  up your <name>". Your own players read "← yours" in the depth list.
- **Running backs only.** Handcuffing is an RB idea: finding 13 tested
  "should you draft your starting RB's backup", and what it prices is
  a workload transferring whole when the starter sits. Nothing like
  that happens at receiver — your WR1 missing time does not hand his
  targets to one named man — so the WR behind yours is not a handcuff
  and is not flagged. This previously fired at every position.
- The row treatment is deliberate here even though findings marks are
  forbidden one: this is a fact about *your* roster, not a model
  opinion, so it belongs with the ★ "on your team" flag rather than
  with buy/fade. It is rare by construction — at most one row per
  running back you roster.
- Highlights **stack with** the predicted-gone row: an orange
  background (the deadline) keeps priority while the green bar keeps
  the first cell, and the tooltip carries both reasons on their own
  lines. "Your handcuff, and he may not last" is exactly the row you
  act on. Selection still overrides both backgrounds.
- Picked players are not highlighted; the row is already struck out.
- No glyph. The ⛓ that used to sit in the Pos cell is gone — a symbol
  you have to learn said less than the highlight does.
- The Pos column header tooltip advertises the hover.

## Verify against
- `webapp/app.js` — `depthInfo()`, `depthListByName`/`depthByName`,
  the `handcuff` row class and Pos cell in `renderTable()`
- `webapp/style.css` — `tr.handcuff`, `.pos-cell.is-handcuff`
- `webapp/index.html` — Pos column header title
