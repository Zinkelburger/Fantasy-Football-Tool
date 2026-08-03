---
id: live-draft-sync
title: Picks flow in live from the ESPN/Sleeper draft room
status: implemented
---

**As a user, I want to** put the draft room and this app side by side and have
picks disappear from my board automatically.

## Steps
1. Install the Chrome extension (`chrome-extension/`), open the ESPN or
   Sleeper draft page, and open this app in another window.

## Expected
- The header shows "Extension: connected" with a timestamp once data flows.
- ESPN picks accumulate (append-only): a short scrape never un-picks the
  board. Sleeper's full available-list snapshot is recomputed instead.
- My roster fills in from the draft room's "my team" area.
- Updates arrive while this tab is in the background — no tab switching.
- Scraped names are fuzzy-matched to board names; a bad match is fixable
  with Undo (see mark-picked-and-undo).
- Without the extension, everything still works by clicking "Picked" by hand.

## Verify against
- `webapp/app.js` — `message` listener, `mergeExtPicked()`, `computePickedFromAvailable()`
- `chrome-extension/bridge.js`, `chrome-extension/content.js`
