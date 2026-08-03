---
id: filter-by-position
title: Filter the board by position
status: implemented
---

**As a user, I want to** show only one position (e.g. RB) so I can compare
players at the spot I'm drafting next.

## Steps
1. Click a position button (All / QB / RB / WR / TE / …) in the filter bar.

## Expected
- The table shows only that position; the active button is highlighted.
- The filter combines with search and the show-picked toggle.
- "All" restores the full board.

## Verify against
- `webapp/app.js` — `renderPosFilters()`, `posFilter` in `renderTable()`
