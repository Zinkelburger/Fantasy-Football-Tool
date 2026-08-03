---
id: build-your-team
title: Track my own roster during the draft
status: implemented
---

**As a user, I want to** see my roster as a depth chart so I know exactly
which spots I still need to fill.

## Steps
1. Let the extension detect my roster (automatic during a live draft) — or,
   with **Manual mode** on in Settings, click "+Team" on a row / press **T**.
2. Click a player in the Team panel → their note opens in a tab.
3. Click a position header (▾ RB · 2) to collapse/expand that group.

## Expected
- Each player renders as a row with a depth chip (QB1, RB1, RB2, WR1 …
  numbered by rank within the position), name, NFL team, "Bye n", and
  overall rank — real columns, not raw text. The name column is capped so
  team/bye/rank sit next to the name instead of at the panel's far edge.
- Chips in this panel are quiet (outlined, dim) — the loud position colors
  live on the Draft Board only.
- A "Still need: …" line under the panel header lists unfilled starting
  slots (QB, RB×2, WR×2, TE, K, DST); it flips to "All starting spots
  filled ✓" when done. A position I've hit its badly-needed round with zero
  of (no RB/WR by round 4, QB by 10, TE by 12) is bolded red; K/DST are
  never bolded — off-board picks can't be counted, so they'd cry wolf.
- Rostered players get a ★ on the board.
- The × remove button appears only in Manual mode and only on
  manually-added players; extension-detected roster players merge in
  without duplicates; manual additions persist across reloads.
- Collapsed position groups persist across reloads.
- The » chevron sits on the **left** of the panel header and collapses the
  whole panel to its title bar (giving the note/AI tabs the space); that
  state persists too.

## Verify against
- `webapp/app.js` — `renderTeam()`, `toggleTeam()`, `teamNames()`, `STARTER_SLOTS`
- `webapp/style.css` — `.team-row`, `.pos-chip`, `#team-needs`
