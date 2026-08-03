---
id: keyboard-shortcuts
title: Drive the app from the keyboard
status: implemented
---

**As a user, I want to** run the whole draft without hunting for tiny
buttons — select a row and act on it with single keys, like the desktop
app's `d`/Space.

## Steps
1. Click any row (or press ↑/↓) to select it — highlighted with an accent bar.
2. **D** or **Space** → cycle the ✅/❌ target marker on the selected player.
3. **P** → toggle picked. **T** → toggle on/off my team (both work even with
   Manual mode off). **Enter** → open the note; **Ctrl+Enter** → open it in
   an additional tab; **E** → open the note and start editing it.
4. **Q** → Ask AI. **A** / **B** → jump to the AI Output / Draft Board tab.
   **/** → focus search. **R** → refresh. **?** → help dialog.
5. **X** → close the active note tab (same as clicking its ×).
6. **Esc** → cancel a note edit (asks first if the text changed), else close
   the active note tab; ends the guided tour when running.

## Expected
- ↑/↓ move through the rows currently visible (respecting filters/search)
  and scroll the selection into view.
- Marking the selected player picked moves the selection to the row that
  takes its place, so a rapid keyboard run keeps flowing.
- Shortcuts are ignored while typing in an input/textarea/select (Esc in the
  note editor being the one deliberate exception), while a dialog is open,
  or with Ctrl/Alt/Cmd held (except Ctrl+Enter).
- When a just-clicked button still has focus, Space/Enter activate that
  button only (the browser default) — they never also fire a row shortcut.
- The full shortcut list lives in the ? help dialog — the footer only hints
  "Press ? for help".
- Shortcuts are discoverable on hover: buttons carry their key in the title
  tooltip ("Ask AI" shows (Q), Edit shows (E), the tab × shows X / Esc,
  row action buttons show (D or Space) / (P) / (T)) instead of cluttering
  the visible label.

## Verify against
- `webapp/app.js` — `keydown` listener, `moveSelection()`, `keepSelectionNear()`,
  `startNoteEdit()`
- `webapp/index.html` — `.help-keys` table in `#help-dialog`
