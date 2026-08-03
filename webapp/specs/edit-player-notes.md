---
id: edit-player-notes
title: Edit a player's note in the browser
status: implemented
---

**As a user, I want to** add my own thoughts to a player's note (or fix a
stale one) right where I read it.

## Steps
1. Open a player's note (click their row, or select it and press Enter) — it
   opens in a tab on the right.
2. Click "Edit" in the note tab (or just press **E** on the selected row),
   change the markdown, "Save". **Esc** (or Cancel) abandons the edit —
   asking first if the text was changed.

## Expected
- The edited note persists in localStorage as an overlay; the bundled note is
  untouched. "Revert to bundled" (with confirm) restores it.
- The note's meta line shows "edited" and the table's note preview gets a ✎
  marker when a note is overridden.
- An in-progress draft survives switching tabs and comes back untouched;
  closing or replacing the tab with unsaved changes asks for confirmation
  first — edits are never silently lost.
- The table preview and the Ask AI prompt use the edited version.
- Players with no bundled note can get a brand-new note the same way.
- Saving text identical to the bundled note clears the override instead of
  storing a pointless copy.
- Settings → "Download edited notes" exports all overridden notes as one
  markdown file with `----- Player.md -----` separators, ready to merge back
  into `go/analysis/`. Edits are also included in the "Export my data" backup.

## Verify against
- `webapp/app.js` — `noteFor()`, `noteOverrides`, `renderNotePane()`,
  `confirmDiscardEdit()`, note-editing button wiring
- `webapp/index.html` — `#note-editor` in `#note-view`
