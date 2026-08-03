---
id: read-player-note
title: Read player notes in tabs beside the AI output
status: implemented
---

**As a user, I want** one click on a player to show their full analysis note
in a tab on the right — like Obsidian — so I can keep a few open and compare,
without popups covering the board.

## Steps
1. Click anywhere on a player's row (or select it and press Enter) → the
   note opens in a tab next to "AI Output" / "Draft Board" and replaces the
   current note tab. Clicks on the row's buttons don't count.
2. **Ctrl+click** the row (or **Ctrl+Enter**) → the note opens in an
   additional tab instead of replacing.
3. Click a tab to switch; click its **×** to close it. Players in the Team
   panel open notes the same way.

## Expected
- "AI Output" and "Draft Board" are permanent tabs: never replaced, never
  closable.
- A plain open replaces the most recently used note tab (or opens the first
  one); Ctrl adds a new tab; opening an already-open player just activates
  its tab. **Esc** or **X** closes the active note tab.
- Ctrl+click is advertised, not secret: every player row's tooltip says
  "Click / Enter: open the note · Ctrl+click / Ctrl+Enter: open in an extra
  tab" (Team-panel rows similarly), and the × has a generous hitbox with a
  "Close (X / Esc)" tooltip.
- Closing the active tab activates its neighbor, falling back to AI Output.
- Player names are not styled as links (no underline on hover) — the whole
  row is the click target.
- The note renders as formatted markdown with a meta line (team, position,
  rank); players without a note get an explicit message pointing at Edit.
- Long names are truncated in the tab with an ellipsis.
- The Note column in the table shows a truncated preview of the same note.
- Notes are editable in place — see edit-player-notes.

## Verify against
- `webapp/app.js` — `openNote()`, `closeNote()`, `renderTabs()`, `renderNotePane()`,
  row click handler in `renderTable()`
- `webapp/index.html` — `#tab-bar`, `#note-view`
