---
id: mark-picked-and-undo
title: Mark players picked, and undo bad picks
status: implemented
---

**As a user, I want** picked players to leave the board — automatically via
the extension during a real draft, by hand otherwise — and to be able to
correct any mistake.

## Steps
1. In a live draft: do nothing — the extension marks picks as they happen.
2. Drafting by hand: enable **Manual mode** in Settings (⚙) → Debug → a
   "Picked" button appears on every row (the **P** key works regardless).
3. Enable "Show picked", click "Undo" on a picked player → they return.

## Expected
- With Manual mode off (the default), rows show no Picked/+Team buttons —
  the draft is driven by the extension and the board stays clean.
- "Undo" still appears on picked rows even with Manual mode off: it is the
  fix when the extension fuzzy-matches the wrong player, and the override
  is remembered so a later scrape of the same name does not re-pick them.
- Manual picks persist across reloads (localStorage).
- The header pick counter reflects the total number of picks.

## Verify against
- `webapp/app.js` — `togglePicked()`, `pickedSet()`, `unpicked` set,
  `settings.manualMode` in `renderTable()`
