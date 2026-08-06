---
id: browse-on-a-phone
title: Browse the draft tool on a phone
status: implemented
---

**As a user, I want to** open the tool on my phone and actually read the
board, a player's note and the draft grid — not a desktop layout squeezed
into 390px with two panels fighting over 600px of height.

The phone layout is for reading and light use. A live draft still wants a
laptop: the Chrome extension that syncs picks is desktop-only, so on a phone
you are either browsing or running a draft by hand in Manual mode.

## Steps
1. Open the tool on a phone (or any window under 620px wide).
2. Tap between **Players**, **Board**, **Note** and **Team** in the bar at
   the bottom.
3. Tap any player row.

## Expected
- One pane fills the screen at a time; the bar at the bottom switches between
  them and highlights the current one.
- Tapping a player row jumps to **Note** with that player's note open.
- Tapping a note tab or the Draft Board tab brings its view along, so a tab
  never changes behind the pane you are looking at.
- **Players**: Team and the note-preview column are dropped, so rank, name,
  position, site rank and the target marker fit without sideways scrolling.
  In Manual mode the site-rank column is dropped too, to make room for the
  Picked and +Team buttons.
- **Board**: team columns stop shrinking at 64px and the grid pans sideways
  with the round numbers pinned to the left edge. The tab scrolls as one
  page, so the grid gets full height under the outlook rather than a
  one-round strip.
- **Team**: fills the screen; the desktop collapse control is hidden.
- Help, Settings and the round-by-round guide open as full-screen sheets, and
  the help dialog's key table reflows into stacked pairs instead of running
  off the side.
- Nothing on any view scrolls the page horizontally.
- Rotating into landscape crosses back to the stacked two-pane layout and
  back again without stranding you on a hidden pane.

## Verify against
- `webapp/style.css` — the `@media (max-width: 860px)` and
  `@media (max-width: 620px)` blocks, and `@media (hover: none)`
- `webapp/app.js` — `onPhone()`, `showMobileView()`, the `#mobile-nav`
  handlers, `activateTab()`, `openNote()`, `BD_MIN_COL` / `boardColWidth()`
- `webapp/index.html` — `#mobile-nav`
