---
id: guided-tour
title: Help dialog and guided tour
status: implemented
---

**As a user, I want** a ? button that explains the app — a keyboard
reference, a glossary, and a step-by-step spotlight tour — instead of a
cluttered always-on legend in the footer.

## Steps
1. Click the **?** button in the header (or press **?**).
2. Read the help dialog: keyboard shortcuts table, "what things mean"
   glossary (columns, markers, orange rows), Manual-mode note, and the
   player-data-generated stamp.
3. Click **▶ Start the guided tour**; **Next** advances, **Skip tour** /
   **×** / Esc ends it.

## Expected
- The footer holds only the status line and a "Press ? for help" hint — no
  permanent keyboard legend or data stamp.
- Each tour step spotlights one component (dimmed page, accent border) with
  an explainer card positioned near the target and clamped to the viewport.
- A step counter shows progress; the last step's button reads "Done".
- Steps cover at least: the board, filters, search, opening notes, target
  markers, tabs, the Draft Board, Ask AI, Your Team, extension sync, help,
  and Settings.
- Steps whose target isn't currently on the page are skipped, not broken.
- While the tour is open, clicks on the app underneath and other keyboard
  shortcuts are blocked; Esc exits.

## Verify against
- `webapp/app.js` — `openHelp()`, `TOUR_STEPS`, `startTour()`, `showTourStep()`
- `webapp/index.html` — `#help-dialog`, `#tour-overlay`, `#btn-help`
