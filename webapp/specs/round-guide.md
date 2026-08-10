---
id: round-guide
title: Get the findings' advice for the round I'm actually in
status: implemented
---

**As a user, I want to** see what the research says to do in the
current round, right in the draft room, without reading 29 write-ups.

## Steps
1. Look at the line under the filter bar while drafting.
2. Click **all rounds** to open the full round-by-round guide.
3. Click any link in the line or the dialog.

## Expected
- The line shows the current round (`R<n>`, from picks made ÷
  `numTeams`, capped at 15) and the guide text for its round band
  (1-2, 3-5, 6-8, 9-11, 12-15) — one to three sentences of tested
  advice with the key numbers (e.g. rounds 9-11: QB/TE still hit
  41%/43%, RB/WR are 12%/17% lotteries, go young at WR/TE).
- **The rounds 3-5 and 6-8 bands must warn off the tight-end dead
  zone** (finding 33: top-6 odds fall 53% → 30% → 16% after round 4,
  and a rounds 5-9 TE misses top-12 more than half the time). This is
  the one band where the guide previously pointed the wrong way: it
  quoted finding 29's ~50% "startable" rate for mid TEs, which is
  top-12 at a 12-team position — the artifact finding 29 itself warns
  about — and so recommended exactly the pick findings 05 and 33 call
  the trap, contradicting the tool's own per-player mark
  (`f33_te_timing` marks rounds 5-9 TEs `fade — the tight end dead
  zone`). Guide text and player marks must not disagree.
- Rounds 9-11 keeping "TE still hits 43%" is correct and not the same
  error: that is finding 33's **wait door**, where the price is cheap
  enough for those odds to be good value.
- Claims in the text link to their findings on foss.football, opening
  in a new tab (`target="_blank" rel="noopener"`).
- **all rounds** opens a dialog with every band plus a bench section
  (findings 19/20/22), same link behavior; it closes via × or Esc
  like other dialogs.
- The dialog notes the structure holds in 0.5PPR and full PPR
  (finding 29).
- Unchecking **Model marks** hides the guide line (it is model
  advice); the dialog stays reachable only through the line, so it
  effectively goes too.
- With no picks logged the line reads R1; it updates as picks come in
  (manual or extension).

## Verify against
- `webapp/app.js` — `GUIDE`, `renderRoundGuide()`, `guide-body` fill,
  `btn-round-guide` wiring, `renderAll()`
- `webapp/index.html` — `#round-guide`, `#guide-dialog`
- `webapp/style.css` — `#round-guide`, `#guide-scroll`
- `engine/league-sim/analysis/round_profile.py` — the numbers
