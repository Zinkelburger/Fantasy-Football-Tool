---
id: resize-panels
title: Resize the board / right-panel split
status: implemented
---

**As a user, I want to** drag the border between the player board and the
right panel, so I can give whichever side I'm using more room.

## Steps
1. Drag the vertical divider between the two panels left or right.
2. Double-click the divider to reset to the default split.

## Expected
- The divider shows a col-resize cursor and highlights on hover/drag.
- Dragging resizes live; the split is clamped (left panel 25–80% of the
  window) so neither side can be dragged away entirely.
- The default split is 40% board / 60% right panel.
- The chosen split persists across reloads; double-click clears it back to
  the default ratio.
- On narrow screens (stacked layout) the divider disappears.

## Verify against
- `webapp/app.js` — `applySplit()`, `#panel-divider` mousedown/dblclick
- `webapp/style.css` — `#panel-divider`, `body.dragging`
