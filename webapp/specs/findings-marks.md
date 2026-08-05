---
id: findings-marks
title: See which research findings apply to a player, with his numbers
status: implemented
---

**As a user, I want to** see, on the board and in a player's note, which
of our tested findings apply to him — buy, fade, or just context — so
the research actually reaches me on draft day instead of living in blog
posts.

## Steps
1. Look for a small ◆ after a player's name flags on the board.
2. Hover the ◆ for a one-line summary of which findings apply.
3. Open the player's note: a findings box sits above the note text,
   one line per rule with the player's own numbers.

## Expected
- The ◆ appears only for players with at least one findings mark
  (bundled from `engine/league-sim/data/market/findings_marks_2026.csv`)
  or a flagged 2025 hot/cold season (opportunity-flags spec). One glyph
  carries the net of both: **green** when the directional signals all
  say buy, **red** when they all say fade, **gray** when they conflict
  or are context-only. A direction beats gray (red + gray = red).
- A **Model marks** checkbox sits in the toolbar next to Show picked
  (default on, persisted). Unchecking it hides everything the models
  add — the ◆, its tooltips, the note-pane findings box and
  expected-points read — leaving the user's own marks, notes, and
  rankings untouched.
- The ◆ tooltip shows the marks themselves, one per line — `Buy
  (finding 16): 18 TDs on chances worth 11 — TD luck doesn't carry
  over.` — no click needed. The name-cell tooltip shows the 2025
  opportunity read and the marks together, so hovering anywhere on the
  name works.
- The note pane shows a findings box between the toolbar and the note
  body: one row per mark. The row starts with a chip that is a link —
  `Buy · finding 16 ↗` — opening that finding's write-up on
  foss.football in a new tab (`target="_blank" rel="noopener"`), so
  draft state is never navigated away from.
- After the chip comes one concise reason with the player's own
  numbers — "18 TDs on chances worth 11 — TD luck doesn't carry
  over." — not a paragraph; the why lives in the linked finding.
- Rows are ordered buys, then fades, then context.
- The marks come from the rules the findings actually tested — mid-round
  WR archetypes (findings 08/09/10), hot/cold finishes (15), TD luck
  (16), target excess (17), the injury-prone label (18) — with
  thresholds unchanged from the backtests. Findings that are strategy
  advice rather than per-player rules (rounds, positions, benches) are
  not marked.
- Players with no marks render exactly as before; a missing marks CSV
  only prints a build warning and drops the feature.
- The ✅/❌/★ and ▾/▴ flags are unchanged; the flag slot fits all four.

## Verify against
- `webapp/app.js` — `fmarksFor()`, `fmGlyph()`, name cell in
  `renderTable()`, findings box in `renderNotePane()`
- `webapp/build_data.py` — `load_findings_marks()`, `fmarks` bundle key
- `webapp/index.html` — `#note-findings`
- `webapp/style.css` — `.fm-flag`, `#note-findings`
- `engine/league-sim/analysis/findings_marks.py` — the rules, and
  `--grade` for how the 2024-flagged names actually did in 2025
