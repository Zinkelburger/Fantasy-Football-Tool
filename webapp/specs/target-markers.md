---
id: target-markers
title: Rate players on a five-step scale
status: implemented
---

**As a user, I want to** rate every player from "really good" to "really
bad" while preparing, so that on draft day I can scan the board for my own
opinion instead of re-reading it.

## Steps
1. Click the rating button on a row. A picker opens listing all five steps
   in words; click the one you mean.
2. Or, with a row selected, press **1**–**5** — the picker shows which
   number is which, so it teaches the shortcut the first time you open it.

## Expected
- Five steps, defined once in `MARK_SCALE` — the picker, the button, the
  name-side flag, the column tooltip and the legend all read from it, in
  that one order, so no two of them can disagree about what a glyph means.
- Stored values are `'love' | 'yes' | 'no' | 'hate'` with the marker
  absent for "no opinion". **The middle two keep the names the
  three-state version used**, so prep saved before the scale existed —
  including exported backup files — still loads and still means the same
  thing.
- **Nothing cycles.** Click-to-advance would need four clicks to say
  "really bad" and only reveals that a scale exists if you keep clicking;
  the picker shows the whole scale, in words, the first time you open it.
- The picker is a menu of the five steps, best first, each row a glyph, a
  plain-English word, and its number key. The rating currently set is
  marked with a filled left edge, so the row you'd click to undo is the
  one lit up.
- The picker opens anchored under the button and is pulled back inside
  the window, so rows at the bottom or the right edge never open
  off-screen.
- Scrolling the board moves the picker with its row rather than closing
  it; it closes on Esc, on a click outside, on a second click of its own
  button, on a pick, or when its row scrolls out of view. It must not
  close merely because some re-render fired a scroll event.
- Keyboard: **1**–**5** set a rating from the board or from inside the
  picker; **D**/**Space** opens it on the selected row; **↑**/**↓** move
  within it (and must not move the board selection while it is open);
  **Enter** takes the focused step; **Esc** closes it.
- On touch devices the number hints are hidden (nothing to press) and the
  rows grow to finger size.
- One shape family carries direction (tick = yes, cross = no) and weight
  carries strength: ✔/✘ are plain glyphs colored green/red, ✅/❌ are the
  bold emoji, so a strong opinion pops out of a screen of mild ones.
- The column is headed **Rating** (**Actions** in Manual mode, where it
  also carries the Picked / +Team buttons), and its tooltip spells out
  every step plus the fact that drafting itself happens on the league site.
  The header is never labelled with something that isn't a control ("pick
  on site" read as an instruction to click).
- The rating shows on the button and next to the player's name; the
  name-side glyph has its own tooltip naming the step in words.
- An unset marker is a faint hollow ring on no button chrome — it's on
  every row, so it must not read as 600 raised buttons demanding attention
  — and grows a real button's background and border on hover, where it's
  clickable. Any set rating stays fully lit.
- The button's tooltip names the rating in words and lists the whole
  scale, so the meaning is available without opening anything.
- Rating never shifts the row's layout — the marker button and the
  name-side flag slot have fixed widths, so nothing jumps while you rate.
- Ratings persist across reloads, survive picks, and are mirrored to the
  extension when it is installed (see live-draft-sync spec).
- Ratings are cleared by "Reset draft state" (which also pushes the
  cleared copy to the extension, so it doesn't come back).

## Verify against
- `webapp/app.js` — `MARK_SCALE`, `markStep()`, `setMark()`,
  `openRatingMenu()`/`closeRatingMenu()`/`positionRatingMenu()`,
  `savePrep()`, `renderTable()` (`step`, `th-actions`), keydown handler
- `webapp/index.html` — `#rating-menu`
- `webapp/style.css` — `#rating-menu`, `.rating-opt`, `.row-actions
  .act-mark`, `.mark-yes/.mark-love/.mark-no/.mark-hate`,
  `#player-table th.actions-col`
