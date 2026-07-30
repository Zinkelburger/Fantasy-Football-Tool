# Note-tone scoring rubric (LLM step)

Every one of the 599 note files was read and scored by a Claude Sonnet
subagent (13 agents, ~47 files each, one pass, July 2026). Scores are
keyed by (year, filename) — 198 players have files in BOTH years and the
two files are scored independently. Output: `data/sentiment_scores.csv`.

The exact instruction given to each agent:

---

You are scoring the tone of fantasy football draft-prep note files
(scraped Reddit comments/summaries about one player per file).

Read the file list at <batch file> (one absolute path per line). Read
EVERY file in the list.

For each file, judge the overall tone of the notes toward drafting that
player this season, on this scale:

- +2 = strongly bullish (league-winner/smash-pick framing, enthusiasm clearly dominates)
- +1 = lean positive (more upside talk than concerns)
- 0 = neutral, mixed, or purely informational (no directional lean)
- -1 = lean negative (concerns/risks dominate)
- -2 = clearly bearish (bust/avoid/fade framing)

Judge the whole file. Balanced upside-and-risk with no clear lean = 0.
Hype quotes plus serious unresolved concerns = 0 or -1 depending on
balance.

Also record has_negative: true if the file contains ANY substantive
negative/risk point about the player (injury risk, crowded backfield,
bad QB play, "going too high", bust concern, etc.), else false.

Write results as a JSON array to <output file>, one object per file:
{"file": "<basename without .md>", "s": <int -2..2>, "has_negative": <bool>}.
Include every file from the list, even if a file is empty (score it 0).

---

Known limitations of this step:

- One scorer pass per file; no inter-rater agreement measured. Tone
  scoring of short hype-y text is subjective at the +/-1 boundary.
- The scorer saw only the note text, never the player's ADP or results
  (no hindsight leak), but the notes themselves sometimes quote ADP.
- 2025 files are LLM-condensed summaries and score much more neutral
  (60% zero) than 2024's raw pastes (31% zero) — tone compression by
  the summarizer, not necessarily milder opinions.
