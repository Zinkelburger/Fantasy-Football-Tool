---
id: ask-ai
title: Ask the AI who to draft next
status: implemented
---

**As a user, I want to** press one key and get a streamed, ranked walkthrough
of the best available players across positions — each labelled by upside —
that already knows the draft state and keeps its opinion from one press to
the next.

## Steps
1. Press **Q** (or click "Ask AI" — its tooltip shows the shortcut).

## Expected
- **The slate spans positions.** Candidates are the best available at each
  position under per-position quotas (`AI_SLATE_QUOTAS`: 6 RB, 6 WR, 3 QB,
  3 TE, 18 in all, topped up evenly from RB/WR when a quota goes unfilled).
  A position I already start one of and cannot flex (QB, TE) keeps a single
  representative. This replaced "top 15 by board rank", which by round 6
  produced answers made of four quarterbacks. Kickers and defenses never
  make the slate. Twenty more names ride along as one-line context.
- **Every candidate carries the board's own numbers** above his note: rank,
  ADP and site ranks; his standing in his NFL team's position room and the
  gap in picks to the man behind him (the same room line the note pane
  shows) plus his own backup by name; whether he backs up one of my running
  backs; the 2025 usage read; the research marks in words; and what the
  pick simulation expects — gone before my next pick (and around which
  pick) or still there.
- **The prompt says what waiting costs** per position, from the same
  simulation the Draft Board suggestion runs on, and states my next pick
  and the one after it.
- **My roster is context, not a filter.** It is sent as a depth chart with
  each running back's handcuff status and the starting slots still open, and
  the prompt tells the model not to build the list around "needs": within
  its top 8 it must name at least three positions and never run four of one
  position in a row, saying in a few words when a player would ride my bench.
- **The answer shape is fixed** in `buildUserPrompt()`, not in the editable
  user prompt: walk the top 12–15 in the model's own order; label each
  **Upside play / Stable play / Balanced** with how much ceiling and how
  safe the floor; say who will probably be gone; finish with a numbered
  list under a "Ranking" heading. The editable prompts carry only voice
  and emphasis.
- **The ranking carries forward.** The final Ranking list is parsed from the
  answer (`parseRanking()`), stored, and sent with the next question as
  "your previous answer, at pick N, ranked …" with an instruction to keep
  the order unless a pick or the evidence changes it — so the advice stops
  reshuffling on every press. Reset draft state forgets it.
- Prompts saved by the old page (the previous defaults, including the
  "I NEED THE LIST" demand) upgrade to the new defaults on load; anything
  the user actually wrote is left alone (`upgradeLegacyPrompts()`).
- Asking switches the right panel to the permanent "AI Output" tab, where the
  answer streams in as rendered markdown.
- OpenAI models fall back down a chain if one fails; Ollama is used instead
  when enabled. Claude Code takes precedence when selected on the local server,
  uses the signed-in subscription with Sonnet, and streams into the same panel.
- The prompt includes the current season/date, scoring, league size, draft slot,
  next pick, lineup assumptions and current candidate rankings. The first overall
  pick is 1, not 0. Old Reddit notes are not presented as verified live facts.
- A failed or interrupted Claude request produces an error and re-enables Ask AI;
  it never silently switches to a paid API provider.
- If no LLM is configured, the panel explains exactly how to set one up —
  and the rest of the app still works without it.
- Queries are rate-limited (no accidental double-fire).
- A wrong API key produces a readable explanation, not a cryptic
  "Failed to fetch".

## Verify against
- `webapp/app.js` — `askLLM()`, `buildUserPrompt()`, `pickCandidates()`,
  `parseRanking()`, `upgradeLegacyPrompts()`, `streamOpenAI()`, `streamOllama()`
- `webapp/test_draft_connection.cjs`, `tests/e2e.cjs` (Claude advice scenario)
