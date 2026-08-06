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
- Each rule is named the way people already say it, never by number —
  `TD regression`, `Targets vs. points`, `Injury history`,
  `Hot/cold finish`, `Bounce-back discount`, `Receiver age`, `Top
  receiver on a bad team` (`FM_TOPIC` in app.js). A finding with no
  entry falls back to its write-up title from the slug, never to a
  bare "finding 21".
- A **Model marks** checkbox sits in the toolbar next to Show picked
  (default on, persisted). Unchecking it hides everything the models
  add — the name-cell tooltip's model lines, the note-pane findings box
  and expected-points read — leaving the user's own marks, notes, and
  rankings untouched.
- The name-cell tooltip shows the marks themselves, one per line —
  `Fade — TD regression: 18 TDs on chances worth 11.` — no click
  needed, alongside the 2025 opportunity read.
- The note pane shows a findings box between the toolbar and the note
  body: one row per mark. The row starts with a chip that is a link —
  `Buy · TD regression ↗` — opening that finding's write-up on
  foss.football in a new tab (`target="_blank" rel="noopener"`), so
  draft state is never navigated away from. The chip is not colored by
  direction; "Buy"/"Fade"/"Context" already says it.
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
- The ✅/❌/★ flags are unchanged; the fixed-width flag slot fits them.

## Verify against
- `webapp/app.js` — `fmarksFor()`, `FM_TOPIC`/`fmTopic()`, `fmTip()`,
  name cell in `renderTable()`, findings box in `renderNotePane()`
- `webapp/build_data.py` — `load_findings_marks()`, `fmarks` bundle key
- `webapp/index.html` — `#note-findings`
- `webapp/style.css` — `#note-findings`
- `engine/league-sim/analysis/findings_marks.py` — the rules, and
  `--grade` for how the 2024-flagged names actually did in 2025
