---
id: import-custom-rankings
title: Import or adjust my own rankings in the browser
status: implemented
---

**As a user, I want to** bring my own rankings list (or reorder the bundled
one) without re-running `build_data.py` — spreadsheets are how people
actually manage rankings.

## Steps
1. Settings (⚙) → "Download rankings (CSV)" to get the current board as a
   spreadsheet.
2. Reorder the rows in Excel/Sheets (no need to renumber — or edit the Rank
   column directly).
3. Settings (⚙) → "Import rankings (CSV)…" and pick the file.

## Expected
- Accepts: a CSV with Player/Name (+ optional Rank) columns, headerless
  `rank,name` rows, or a plain pasted-style list of names — numbered
  ("12. Justin Jefferson") or bare (rank = line order).
- The board re-sorts immediately; overridden ranks show in accent color with
  the bundled rank in the tooltip.
- Overrides apply to the current scoring format and persist in localStorage
  as an overlay — the bundled data file is untouched.
- Names are fuzzy-matched to the board; unmatched names are reported in a
  summary, not silently dropped.
- The Ask AI top-15 uses the custom order.
- "Revert to bundled rankings" (with confirm) clears the current format's
  overrides.
- The downloaded CSV re-numbers Rank 1..N in board order so the
  download → reorder → import round-trip needs no manual renumbering.

## Verify against
- `webapp/app.js` — `parseRankingsText()`, `buildRankingsCsv()`,
  `importRankingsFile()`, `boardPlayers()`, `rankOverrideFor()`
- `webapp/index.html` — "Rankings & your data" fieldset in `#settings-dialog`
