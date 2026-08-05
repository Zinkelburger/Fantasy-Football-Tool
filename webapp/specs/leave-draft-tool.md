---
id: leave-draft-tool
title: Leave the draft tool and get back to foss.football
status: implemented
---

**As a user, I want to** leave the full-screen draft tool and get back
to the main site without fighting the browser back button.

## Steps
1. Click the house icon at the left end of the header.

## Expected
- The house icon links to `../` with `target="_top"`, so it escapes the
  site's Draft Tool iframe and lands on the foss.football home page —
  not a nested copy of the site inside the frame.
- The icon has a tooltip: "Leave the draft tool — back to foss.football".
- When the tool is opened directly (no iframe), the same link resolves
  to the site root one level up.

## Verify against
- `webapp/index.html` — `#home-link`
- `webapp/style.css` — `#home-link` hover styling
