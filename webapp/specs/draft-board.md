---
id: draft-board
title: Snake draft board with deterministic pick prediction
status: implemented
---

**As a user, I want** a Sleeper-style draft board — every team's picks laid
out on the snake — plus a "Who should I take?" simulation, so I can answer "will
this player make it back to me?" and "should I take a QB now?" with
evidence instead of vibes.

## Steps
1. Open the **Draft Board** tab (or press **B**).
2. Click my column header — or let the slot auto-detect from my first pick.
   (Teams / Slot / Rounds controls only appear in Debug mode; normally the
   toolbar shows a read-only "12 teams · 15 rounds · your slot: N" summary.)
3. Click **Who should I take?** — predict mode stays on, re-simulating after
   every real pick; **Return to live** removes the simulation.

## Expected
- A grid, one column per team, one row per round, snake numbering
  (1.01 … 1.12, then 2.12 back to 2.01). Filled cells show the player's
  short name (first-initial abbreviation) on a position color (QB/RB/WR/TE/
  K/DST each get a color); pick number, position, and full name live in the
  cell tooltip. Names stay on one line, ellipsized if they still don't fit —
  with 12+ columns horizontal space is the premium, and wrapping would
  reserve a second name line in every cell of the board.
- **The whole grid fits the panel** — columns shrink to the available width
  (no minimum), so a 12-team × 15-round board never needs horizontal
  scrolling; empty future cells show just the tiny pick label.
- Real picks keep their position color, only slightly muted — the board
  stays readable as a record of the draft; the attention contrast comes
  from simulated cells' dashed orange borders and the pink next-pick
  highlight. Off-board picks (K/DST) still occupy their slot.
- My column is outlined; my next pick's cell is highlighted pink, and the
  main player table shows a matching pink "Your next pick — #N (x picks
  away)" line at the same depth.
- Team headers show the team name plus drafted-position counts (RB2 WR1 …;
  positions with none drafted are omitted). The needs detail lives in the
  header tooltip: "needs QB, TE" (or "starters ✓"), escalating to "REALLY
  needs RB" when the team is deep in the draft with none of them (no RB/WR
  by round 4, no QB by round 10, no TE by round 12). The Your Team panel
  bolds badly-needed positions in its "Still need" line using the same
  thresholds. Clicking a header sets/unsets my slot.
- **Who should I take?** deterministically simulates only the picks between now
  and my next turn — the decision-relevant window. By default opponents
  draft by their own site's rankings (ESPN or Sleeper, whichever the draft
  is on; falls back to board rank), adjusted for each team's needs (no
  early second QB/TE, positional caps, forced starter-filling late). No AI
  involved. It requires a known slot; on the clock it simulates nothing
  (there are no picks before mine) but still shows the outlook and
  suggested pick.
- A toolbar button next to **Return to live** always states which ranking
  the bots are using ("Bots: ESPN ADP") and opens a popover holding the two
  controls: **Bots follow** picks the ranking they draft by — site ADP
  (auto), ESPN ADP, Sleeper rank, or my board rank (edits included) — and
  **Bot style** switches between need-aware (the wouldDraft filter above)
  and pure best available (strictly the next name in the ranking). Changing
  either re-simulates immediately when predict mode is on. The label is
  never hidden behind the gear: it is the assumption every surprising
  prediction traces back to, so it stays on screen.
- Simulated cells are colored with a dashed orange border; on the main
  table, players predicted gone before my next pick get an orange tint.
- An outlook answers the meta-game question per position: best available
  **now** vs **Yours at <pick>**, how many are **taken before you**, who
  I get **if I pass** until my *following* pick, and how far the position
  **falls** — the board spots lost by waiting, which is exactly the row's
  "if you pass" rank minus its "yours at" rank. A cost of 0 renders as
  "same" rather than a bare 0.
- Every name in the outlook carries **two** numbers: my board rank (what
  "falls" is measured in) and the ranking the bots sort on (what decides
  who actually disappears), with a legend naming both. Showing only the
  first makes any player my board rates well above the site's look like a
  broken simulation — the ESPN-36 / board-18 gap is the explanation.
- The headline answers first and justifies second, in two lines: "Your pick
  now — **Brock Bowers** TE · your #25" over "TE falls 24 spots by pick 28
  — pass and it's Colston Loveland 49". Off the clock the first line reads
  "At your pick 21" instead. It names the single best pick for MY roster:
  among positions I'd reasonably draft (same wouldDraft rules), the one
  with the steepest wait cost — i.e. naive two-pick-lookahead pick value
  with ranks as the value scale. Naming the fallback is required — the cost
  is stated as a concrete choice between two players, never a bare number,
  because a rank delta with no name attached is unreadable mid-draft. The
  extended simulation past my pick is internal only; the grid still shows
  nothing beyond my next pick.
- **Predict and live coexist**: predict mode persists, and every new real
  pick (or slot / league-shape change) re-simulates the window instead of
  leaving a stale overlay — the outlook is marked "live". While the mode is
  on, the toolbar swaps the button for **Return to live**, which drops
  the simulated picks (real picks always render as they arrive either way).
- Teams / slot / rounds persist (defaults 12 / auto / 15), as do the bot
  ranking/style selects (defaults site ADP / need-aware); predict mode
  persists too and is cleared by Reset draft state.

## Verify against
- `webapp/app.js` — `renderBoard()`, `renderOutlook()`, `computePrediction()`,
  `runPrediction()`, `predictDraft()`, `wouldDraft()`, `snakeTeamForPick()`,
  `nextPickForTeam()`, `pickLogEntries()`, `effectiveSlot()`, `yourNextPick()`,
  `renderAll()` (auto re-simulation), `BADLY_NEEDED_BY_ROUND`
- `webapp/index.html` — `#board-view`
