---
id: target-markers
title: Mark players as targets or avoids
status: implemented
---

**As a user, I want to** flag players I love (✅) or refuse to draft (❌) while
preparing, so my opinions are visible on the board on draft day.

## Steps
1. Click the marker button on a row: it cycles ○ → ✅ → ❌ → ○.

## Expected
- The column is headed **Target** (**Actions** in Manual mode, where it also
  carries the Picked / +Team buttons), and its tooltip spells the states out —
  ✅ want him, ❌ avoid him, ○ no opinion — plus the fact that drafting itself
  happens on the league site. The header is never labelled with something that
  isn't a control ("pick on site" read as an instruction to click).
- The marker shows on the button and next to the player's name.
- An unset marker is a faint hollow ring on no button chrome — it's on every
  row, so it must not read as 600 raised buttons demanding attention — and
  grows a real button's background and border on hover, where it's clickable.
  A set ✅/❌ stays fully lit in green/red.
- Each state's tooltip says what a click will do next, not just what the
  button is.
- Cycling a marker never shifts the row's layout — the marker button and the
  name-side flag slot have fixed widths, so nothing jumps while you mark.
- Markers persist across reloads and survive picks.
- Markers are cleared by "Reset draft state".

## Verify against
- `webapp/app.js` — `cycleToDraft()`, `toDraft` store, `renderTable()`
  (`markLabel`, `th-actions`)
- `webapp/style.css` — `.row-actions .act-mark`, `#player-table th.actions-col`
