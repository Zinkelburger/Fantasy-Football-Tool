---
id: reset-draft-state
title: Reset everything between drafts
status: implemented
---

**As a user, I want to** wipe all draft state in one click so my second draft
starts clean.

## Steps
1. Settings (⚙) → Debug tab → "Reset draft state" → confirm.
2. In Manual/debug mode there's also a red **Reset draft** button right in the
   header, for quick repeated resets while testing.

## Expected
- Clears: picked players, my team, target markers, un-pick overrides, and the
  extension's stored draft data (a clear message is sent to the bridge).
- Does NOT clear: API key, model, prompts, scoring format.
- Asks for confirmation before wiping.

- The header button only appears when Manual mode is on.

## Verify against
- `webapp/app.js` — `resetDraftState()`, `#btn-reset-top` toggle in `renderAll()`
