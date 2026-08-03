---
id: switch-scoring-format
title: Switch between STD / 0.5 PPR / PPR rankings
status: implemented
---

**As a user, I want to** switch the board between scoring formats because my
leagues score differently.

## Steps
1. Use the "Scoring" dropdown in the header.

## Expected
- The board re-sorts to that format's rankings immediately.
- The choice persists across page reloads (localStorage).
- Picked/team/target state carries over — it is keyed by player name, not
  by format.

## Verify against
- `webapp/app.js` — `allPlayers()`, `scoring-format` change listener
