# 2026 scraper redesign — corpus sweep + guarded matching + cheap-LLM filter

Verdicts from live experiments (Aug 2026, see git history for scripts):

- A "do not draft" megathread contained full-name discussion of 97/335
  players; 0 were findable via Reddit search (search never indexes comments).
- "Achane is getting slept on" thread: ~5,000 chars of pure draft insight,
  all surname-only. Full-name-only matching caught 32 chars of it.
- Surname-only matching is safe iff the surname is (a) not an English
  word and (b) unique across ALL name tokens in the player pool.
  Violations produced Chase Bisontis (for Ja'Marr), Zac Robinson the OC
  (for Bijan), Chase Brown (for A.J. Brown).
- Token cost is a non-issue: ~1M input tokens for all 335 players ≈ cents
  on the cheapest OpenAI model, half via Batch API. Recall is the
  constraint, not cost. Final disambiguation is the LLM's job — the
  prompt already warns about same-name players.

## Architecture

```
TRACK 1 (new): corpus sweep          TRACK 2 (existing, trimmed): per-player search
  top(month) + hot + new posts         full name + nickname (+ safe surname) queries
  comments expanded, capped            finds dedicated threads ("Achane slept on")
        │                                   │
        └────────────► corpus/comments.jsonl ◄──────────┘
                       (one line per comment: post_id, title, score, body;
                        deduped by comment id; gitignored — Reddit ToS)
                                │
                       match_players.py  (offline, zero API calls, re-runnable)
                                │
                       filtered_data/<slug>_reddit_discussion.txt
                                │
                       ff-hound + combine steps (unchanged)
                                │
                       live_process.py / submit_batch.py (unchanged)
```

## Comment scraping mechanics (track 1)

- `subreddit.top(time_filter='month')` + `.hot(limit≈150)` + `.new(limit≈300)`,
  dedupe by post id, drop posts older than the 60-day window and posts with
  score < 5 (junk filter).
- Per post: `submission.comment_sort = 'top'`, then
  `submission.comments.replace_more(limit=20)` — each replace_more call is
  one API request returning up to ~100 comments, so a cap of 20 gets the
  top ~2,000 comments of a megathread and bounds cost. `.list()` flattens.
- Budget: ~300 posts × 2–5 requests ≈ 15–30 min at the free tier's
  100 requests/min. PRAW self-throttles.
- Append-only JSONL cache keyed by comment id → sweep is resumable and
  re-matching later costs zero API calls.

## Matching rules (offline)

Alias table per player, built once per season:
1. Full-name variants — existing punctuation/initials logic (A.J./AJ/a j).
2. Initialisms, auto-generated, ≥3 letters (CMC, JSN, ARSB, MHJ, BTJ).
3. Nicknames + misspellings: CSV column, topped up by one cheap LLM batch
   call ("common Reddit aliases and misspellings for these players").
4. Surname-only / first-name-only ONLY if the token passes ALL of:
   not in the English dictionary (/usr/share/dict/words), unique across
   every token of every player name in the pool, length ≥ 4.
   (Nacua, Achane, Bijan, Kupp pass; Chase, Hill, Brown, Josh fail.)

Match at sentence level (split paragraphs — stops one giant post body
matching as a single "line"). Tag every hit with match type + thread title
+ comment score.

## Garbage controls (the "too much fake/irrelevant data" problem)

- Skip comments with score < 1 — downvoted means the community already
  flagged it.
- Dedupe identical lines (ranking tables get reposted constantly).
- Reply context: when a reply matches, include its parent comment once
  (bounded — not the whole chain).
- Per-player cap ≈ 8k chars, prioritized: exact match > alias > surname,
  then comment score, then recency.
- Surname-only snippets go in a separate labeled section the prompt tells
  the model to treat skeptically.

## The "most players won't match" problem

Expected and fine. Mention count is itself a signal: the assembly header
includes it, and the prompt instructs the model to say "low discussion
volume" honestly instead of padding. The corpus sweep raises the floor a
lot (97 players in one thread); the deep bench getting thin notes is
truthful output, not failure.

## Assembly format fed to the LLM (per player)

```
PLAYER: De'Von Achane (MIA, RB1) — ADP 12.4 — 31 mentions found

== FULL-NAME / ALIAS MENTIONS ==
[thread: "Rank my keepers", score 45] <sentence>
...

== SURNAME-ONLY MENTIONS (verify these refer to the player) ==
[thread: "Achane is getting slept on", score 210] <sentence>
...
```

Model is whatever's cheapest at run time — it's just `OPENAI_MODEL` /
`OPENAI_BATCH_MODEL` in `.env`; the design doesn't care.

## Build list

1. `fetch_corpus.py` — track-1 sweep + track-2 search into the JSONL cache.
2. `match_players.py` — alias table + guarded matching + assembly; writes
   `filtered_data/*_reddit_discussion.txt` (replaces the Reddit half of
   `main_scrape_reddit_api.py`; ff-hound/combine/summarize stay as-is).
3. `gen_aliases.py` — one-off LLM batch call to fill the nickname column.
4. Smoke run on ~12 players before a full 335-player pass.
