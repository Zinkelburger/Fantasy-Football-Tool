---
id: opportunity-flags
title: See whether a player's 2025 scoring outran his chances
status: implemented
---

**As a user, I want to** see, right on the board, which players scored well
above or below what their 2025 usage was worth, so I fade touchdown luck and
buy suppressed usage without leaving the draft tool.

## Steps
1. Hover any veteran's name on the player board.
2. Read the tooltip — it says whether he scored above or below what his
   chances were worth, and what that means, in words; there is no glyph
   or color code on the row.
3. Open the player's note and read the line under the tab bar.

## Expected
- Hovering the **name cell** of any player with 2025 data shows a tooltip:
  `2025: <actual> PPG on <expected> expected from his chances (<n> games).`
  Expected PPG is usage-based expected points — what a typical player would
  have scored from the same targets, carries and field position — bundled per
  scoring format (STD/0.5PPR/PPR follow the format switcher).
- A flagged season (8+ games and actual-minus-expected at least 1.5
  (STD) / 1.9 (0.5PPR) / 2.25 (PPR) points per game past the typical
  player at his position) adds a sentence to that tooltip saying he
  scored above or below his chances and by how much. It is written out
  — "He scored 3.4 a game more than a typical RB does with the same
  targets and carries" — never as "ran hot"/"ran cold", which is a
  term you have to already know to read.
- Direction counts **only for WR and TE**, per the 2017–25 backtest
  (`engine/league-sim/analysis/gap_regression_check.py`): the gap
  predicted the next season in 8 of 8 year-pairs there. **RB and QB
  gaps are context only**, and their tooltips say the gap is context,
  not a verdict (goal-line roles are sticky). WR/TE tooltips say how
  much and why it matters (TD luck named when it explains the gap).
- The read adds no glyph, no color, and no new column — row layout is
  unchanged. Unchecking **Model marks** in the toolbar hides the
  tooltip line and the note-pane read.
- The note pane meta line carries the read:
  `TEAM POS, rank N · 2025: 13.9 PPG, 11.2 from his chances — scored
  above them`. The trailing verdict is **only ever shown at WR and
  TE**, the two positions where the backtest above found the gap
  predicts anything; RB and QB get the bare stat and no verdict,
  because telling a drafter his running back "scored above his
  chances" is a judgement the engine's own tooltip then walks back.
  It is **also dropped when the player has a touchdown-luck row** in
  the findings box below: for most flagged players the whole gap *is*
  the extra scores, so the two would state one finding twice, in
  different units, two lines apart. The row wins — it carries the
  number and the link.
- Players without 2025 data (2026 rookies, injury redshirts) show no flag, no
  tooltip line, and render exactly as before.

## Verify against
- `webapp/app.js` — `oppRead()`, `OPP_GAP_FLAG`, name cell in
  `renderTable()`, `renderNotePane()`
- `webapp/build_data.py` — `load_opportunity()`, `xfp/ppg25/gapc/tdl/g25`
  fields
- `engine/league-sim/analysis/export_opportunity.py` — the numbers' source
