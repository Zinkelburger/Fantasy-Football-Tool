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
  (bundled from `engine/league-sim/data/market/findings_marks_2026.csv`).
  It is **green** when every directional mark is buy, **red** when every
  one is fade, and **gray** when they mix or are context-only.
- The ◆ tooltip reads like: `Findings that apply: buy (finding 16, 18) ·
  watch (finding 10) — open the note for the why.`
- The note pane shows a findings box between the toolbar and the note
  body: one row per mark, `Buy · finding 16` / `Fade · finding 9` /
  `Context · finding 15` in front of a plain-English sentence carrying
  the player's own numbers (e.g. touchdowns vs expected, targets per
  game, weeks listed Out).
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
