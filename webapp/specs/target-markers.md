---
id: target-markers
title: Mark players as targets or avoids
status: implemented
---

**As a user, I want to** flag players I love (✅) or refuse to draft (❌) while
preparing, so my opinions are visible on the board on draft day.

## Steps
1. Click the marker button on a row: it cycles – → ✅ → ❌ → –.

## Expected
- The marker shows on the button and next to the player's name.
- Cycling a marker never shifts the row's layout — the marker button and the
  name-side flag slot have fixed widths, so nothing jumps while you mark.
- Markers persist across reloads and survive picks.
- Markers are cleared by "Reset draft state".

## Verify against
- `webapp/app.js` — `cycleToDraft()`, `toDraft` store
