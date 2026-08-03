---
id: show-picked-toggle
title: Show or hide already-picked players
status: implemented
---

**As a user, I want to** hide picked players by default (so the board is only
who's left) but be able to reveal them to review the draft so far.

## Steps
1. Check/uncheck "Show picked" in the filter bar.

## Expected
- Unchecked (default): picked players disappear from the table.
- Checked: they reappear, struck through and dimmed, with an Undo button.

## Verify against
- `webapp/app.js` — `showPicked` in `renderTable()`
