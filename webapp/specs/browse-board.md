---
id: browse-board
title: Browse the ranked player board
status: implemented
---

**As a user, I want to** see every draftable player in one ranked table so I
always know who the best available players are — without columns I don't
need or jargon I have to guess at.

## Steps
1. Open `index.html`.
2. Hover any column header for a plain-language explanation.
3. Click the Rank / ESPN / Sleeper headers to sort by that column.

## Expected
- A table sorted by overall rank with columns: Rank, Player, Team, Bye, Pos,
  **one** site-rank column, a truncated note preview, and the marker button.
- The Pos column includes NFL-team depth: **WR2** = that team's 2nd-ranked
  WR (bundled ranks, so imported ranks don't reshuffle other teams' depth).
- The site-rank column auto-matches where the draft is happening: ESPN by
  default, Sleeper once the extension reports a Sleeper draft. Settings can
  pin it to ESPN, Sleeper, or show both.
- Site ranks show the delta vs board rank, signed by how the site *feels*
  about the player: **(+n)** = the site is n spots higher on them (goes
  earlier there), **(−n)** = n spots lower (may fall to you); no delta when
  they agree. The delta is rendered quietly (dim, small) — context, not
  alarm — with the full explanation in the cell tooltip.
- Clicking a sortable header re-sorts the view (↓ marks the active sort);
  sorting never changes the real board order used by the AI prompt,
  predictions, or the pick marker (the marker only shows in rank order).
- Every column header has a tooltip explaining what it means (what "Bye"
  is, whose ranking "ESPN" is, etc.).
- A count line shows how many players are shown / available / picked.
- Picked players are struck through and dimmed (hidden by default).
- Players on my team are marked with a ★.
- A pink "Your next pick" line shows where my pick lands (see draft-board);
  orange rows are players predicted gone by then after "Predict picks".
- The data-generated stamp lives in the ? help dialog, so I can tell if my
  rankings are stale.

## Verify against
- `webapp/app.js` — `renderTable()`, `siteColumns()`, `draftSite()`
- `webapp/index.html` — `#player-table` header tooltips
