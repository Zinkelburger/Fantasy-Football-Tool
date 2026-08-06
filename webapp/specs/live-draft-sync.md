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

## Prep survives the browser (extension installed)
- Your **prep** — player ratings, note edits, imported ranks — is mirrored
  into `chrome.storage.local` (`ffda_prep`) on every change. The reason is
  that localStorage is the wrong place for the only copy: "clear browsing
  data" wipes it, and it doesn't cross origins, so a local copy of the tool
  and foss.football can't see each other's work.
- localStorage stays the working copy: synchronous, always present, and
  completely unchanged when no extension is installed.
- Conflicts are settled by timestamp, whole-blob, by the page: it adopts
  the extension's copy only when `prep.savedAt` is newer than its own, and
  pushes its own up when the extension's is older or absent. Merging two
  edit histories per-player would invent a third state neither browser had.
- The page never adopts a remote copy while a note is open for editing.
- The bridge drops the storage-change echo of a prep write made by this
  same page (it remembers the last blob it pushed), so rating a player
  doesn't re-render the board or claim "draft data received". A prep change
  from a *different* tab is still relayed, which is how two open copies of
  the tool stay level.
- An older extension that doesn't know `save-prep` is harmless: the message
  is ignored, no prep comes back, and the page runs on localStorage alone.
- "Reset draft state" clears ratings and pushes the cleared copy; edited
  notes and custom ranks are kept.

## Verify against
- `webapp/app.js` — `message` listener, `mergeExtPicked()`,
  `computePickedFromAvailable()`, `savePrep()`, `mirrorPrep()`, `adoptPrep()`
- `chrome-extension/bridge.js` (`PREP_KEY`, `save-prep`, `lastPrepPushed`),
  `chrome-extension/content.js`
