---
id: ask-ai
title: Ask the AI who to draft next
status: implemented
---

**As a user, I want to** press one key and get a streamed recommendation that
already knows the draft state — pick number, who's gone, my roster, and the
full notes of the best available players.

## Steps
1. Press **Q** (or click "Ask AI" — its tooltip shows the shortcut).

## Expected
- The prompt includes: current pick number, all picked players, my roster
  grouped by position, my custom instructions, and the full notes of the
  top-15 available players.
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
- `webapp/app.js` — `askLLM()`, `buildUserPrompt()`, `streamOpenAI()`, `streamOllama()`
