---
id: export-backup-state
title: Back up / move my prep to another browser
status: implemented
---

**As a user, I want to** export my draft prep to a file and import it
elsewhere — localStorage is per-browser, and draft day might happen on a
different machine.

## Steps
1. Settings (⚙) → "Export my data" downloads one JSON file.
2. Settings (⚙) → "Import my data…" on the other machine restores it.

## Expected
- Round-trips: target markers, manual picks, un-pick overrides, my team,
  rank overrides, edited notes, prompts, and scoring format.
- The API key is never exported (it's a secret); importing keeps the
  destination browser's key as-is.
- Import validates the file (JSON + an app marker) and asks for confirmation
  before replacing — a bad file never silently corrupts state.
- Live extension draft data is not part of the backup (it belongs to a
  specific draft, not to prep).

## Verify against
- `webapp/app.js` — `exportBackup()`, `importBackupFile()`
- `webapp/index.html` — backup buttons in `#settings-dialog`
