---
id: search-players
title: Search players by name or team
status: implemented
---

**As a user, I want to** type a few letters and find a player instantly,
because during a live draft I have seconds to react.

## Steps
1. Type in the "Search players..." box.

## Expected
- The table narrows live on every keystroke (matches name or team,
  case-insensitive).
- Clearing the box restores the board.

## Verify against
- `webapp/app.js` — `search-box` input listener, `searchText` in `renderTable()`
