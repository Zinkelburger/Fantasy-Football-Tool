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
1. Hover a player's name on the board for the reads that apply to him,
   written out.
2. Open the player's note: a findings box sits above the note text,
   one line per rule with the player's own numbers.

## Expected
- **No glyph or color coding on the row.** The reads are words, not a
  red/green symbol the user has to learn: a colored ◆ carried less
  information than the sentence behind it, so the row keeps only the
  user's own flags (✅/❌/★).
- Each rule is named the way you would say it out loud at a draft
  table, never by number and never in jargon — `Touchdown luck`,
  `How often he got the ball`, `Games he missed`, `How he finished the
  year`, `Cheap after a bad year`, `Age`, `Best receiver on a bad
  team`, `Backup running back`, `When to take a quarterback`, `When to
  take a tight end`, `How good his offense is` (`FM_TOPIC` in app.js).
  Terms you have to already know — "TD regression", "hot/cold finish",
  "bounce-back discount" — are the thing this label exists to avoid.
  A finding with no entry falls back to its write-up title from the
  slug, never to a bare "finding 21".
- A **Model marks** checkbox sits in the toolbar next to Show picked
  (default on, persisted). Unchecking it hides everything the models
  add — the name-cell tooltip's model lines, the note-pane findings box
  and expected-points read — leaving the user's own marks, notes, and
  rankings untouched.
- The name-cell tooltip shows the marks themselves, one per line —
  `Fade — Touchdown luck: 18 TDs on chances worth 11.` — no click
  needed, alongside the 2025 opportunity read.
- The note pane shows a findings box between the toolbar and the note
  body: one row per mark. The row starts with a chip that is a link —
  `Buy · Touchdown luck ↗` — opening that finding's write-up on
  foss.football in a new tab (`target="_blank" rel="noopener"`), so
  draft state is never navigated away from. The chip is not colored by
  direction; "Buy"/"Fade"/"Context" already says it.
- After the chip comes one concise reason with the player's own
  numbers — "30 years old — lower ceiling at this price", "18 TDs on
  chances worth 11" — **never an explanation of the finding itself.**
  The chip is a link; that is what carries the research. A note is a
  fragment naming the player's situation, not the argument for it.
  Enforced, not merely documented: `mark()` in `findings_marks.py`
  raises above `MAX_NOTE` (90 chars), because prose kept creeping back
  in every time the rules were edited.
- Rows are ordered buys, then fades, then context.
- Nothing is said twice. The meta line's "scored above/below them" tag
  is suppressed when a touchdown-luck row is present, because for most
  flagged players the whole gap *is* the extra scores — same fact, two
  units, two lines apart. The room line no longer opens "He's DET's
  RB1 on the draft board" when the meta directly above already reads
  "DET RB, rank 1"; it states his standing only when he is *not* top of
  his room, and otherwise goes straight to who is next and how far
  back. And a topic chip never repeats the first words of its own note.
- The marks come from the rules the findings actually tested — WR age
  (finding 10), TD luck (16), target excess (17), the injury-prone
  label (18) — plus three price-band rules that report which tested
  band the player falls in: the handcuff (13), QB timing (14) and TE
  timing (33). Findings that are strategy advice with no per-player
  hook (bench shape, waiver policy) are not marked.
- **A mark has to change what you do.** A row that reports a real
  number and then explains it means nothing is not neutral: it costs
  attention on the clock, and a reader fairly assumes anything shown is
  meant to be acted on. Findings **08, 09, 15 and 30 are deliberately
  not marked** for that reason — all four came back null at the player
  level (08's mid-round edge is price mix; 09 shows no penalty at any
  price; 15's own title is "a hot finish predicts nothing"; 30's
  close-ADP pairs show the better offense winning nothing once the
  board has charged for it). Their retractions belong in the write-ups,
  not on the draft clock. A null result is a reason to remove a row,
  never to soften one into context — if the only honest way to end a
  sentence is "and this is not a reason to move him", delete the row.
- Finding 10 fires at **every** price, not the old 36–120 ADP band —
  it is the one WR archetype that survived the board-wide re-test
  (`wr_archetypes.py --full`). A mark must never claim more than the
  price it fires at was tested for.
- Players with no marks render exactly as before; a missing marks CSV
  only prints a build warning and drops the feature.
- The ✅/❌/★ flags are unchanged; the fixed-width flag slot fits them.

## Verify against
- `webapp/app.js` — `fmarksFor()`, `FM_TOPIC`/`fmTopic()`, `fmTip()`,
  name cell in `renderTable()`, findings box in `renderNotePane()`
- `webapp/build_data.py` — `load_findings_marks()`, `fmarks` bundle key
- `webapp/index.html` — `#note-findings`
- `webapp/style.css` — `#note-findings`
- `engine/league-sim/analysis/findings_marks.py` — the rules, and
  `--grade` for how the 2024-flagged names actually did in 2025
