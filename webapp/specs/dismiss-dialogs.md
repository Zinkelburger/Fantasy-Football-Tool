---
id: dismiss-dialogs
title: Close the Help or Settings dialog without saving
status: implemented
---

**As a user, I want to** dismiss the Help or Settings dialog once I'm done
looking, without being forced through a save.

## Steps
1. Open Help (**?** button or the **?** key) or Settings (⚙ button).
2. Click the **×** in the dialog's top corner — or press **Esc**.

## Expected
- The dialog closes immediately; both the × button and Esc (native
  `<dialog>` behavior) work on either dialog.
- Closing Settings this way discards any unsaved form changes silently —
  no confirmation prompt. Save is the only path that persists; reopening
  the dialog repopulates every field from the saved settings. (Deliberate:
  unlike a hand-written player note, settings fields are cheap to retype,
  so an "are you sure?" here would be noise.)
- Nothing else changes: closing a dialog never mutates draft state, tabs,
  or the table. While a dialog is open, the app's keyboard shortcuts are
  suppressed — Esc closes the dialog only, never the active note tab.

## Verify against
- `webapp/index.html` — `.dialog-close` buttons in `#help-dialog` and
  `#settings-dialog`
- `webapp/app.js` — the `.dialog-close` click wiring; `openSettings()`
  (field repopulation) and the save handler (`settings-dialog` close on
  save)
