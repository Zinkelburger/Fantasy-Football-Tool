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
2. Look for a small ▾ (red) or ▴ (green) after the name flags.
3. Open the player's note and read the line under the tab bar.

## Expected
- Hovering the **name cell** of any player with 2025 data shows a tooltip:
  `2025: <actual> PPG on <expected> expected from his chances (<n> games).`
  Expected PPG is usage-based expected points — what a typical player would
  have scored from the same targets, carries and field position — bundled per
  scoring format (STD/0.5PPR/PPR follow the format switcher).
- A **▾** appears in the name-flag slot when the player *ran hot*: 8+
  games and actual-minus-expected at least 1.5 (STD) / 1.9 (0.5PPR) /
  2.25 (PPR) points per game above the typical player at his position. A
  **▴** marks the mirror-image *ran cold* case.
- Flag color states the evidence (2017–25 backtest,
  `engine/league-sim/analysis/gap_regression_check.py`): **red ▾ / green ▴
  only for WR and TE**, where the gap predicted the next season in 8 of 8
  year-pairs; **RB and QB flags render gray**, and their tooltips say the
  gap is context, not a verdict (no incremental signal there — goal-line
  roles are sticky). WR/TE tooltips say how much and why it matters (TD
  luck named when it explains the gap).
- The ▾/▴ never displaces the ✅/❌/★ flags and adds no new column — row
  layout is unchanged for unflagged players.
- The note pane meta line repeats the read:
  `TEAM POS, rank N · 2025: 13.9 PPG on 11.2 expected (ran hot)`.
- Players without 2025 data (2026 rookies, injury redshirts) show no flag, no
  tooltip line, and render exactly as before.

## Verify against
- `webapp/app.js` — `oppRead()`, `OPP_GAP_FLAG`, name cell in
  `renderTable()`, `renderNotePane()`
- `webapp/build_data.py` — `load_opportunity()`, `xfp/ppg25/gapc/tdl/g25`
  fields
- `webapp/style.css` — `.opp-flag`
- `engine/league-sim/analysis/export_opportunity.py` — the numbers' source
