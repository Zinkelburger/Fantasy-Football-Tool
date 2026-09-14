# Weekly research review — 2026-09-14

The main problem was retrieval policy and tool ambiguity. The agent already had
roster, usage, injury and lineup tools, but its checklist encouraged per-player
Reddit searches and discussion-thread reading without a shared budget or stop
condition. The scheduled GitHub job refreshes data; it does not itself run a
personalized research agent or deliver a weekly report.

| Finding | Implemented change |
|---|---|
| Search loaded comments for every selected post, including when the caller requested zero comments. | Discovery and detail reads are separate. Existing search helpers default to zero comments; explicit compatibility reads stop at two threads. |
| Latest listings could scan 1,000 posts for every selected subreddit. | A single combined listing is capped at 100 posts and reports incomplete coverage. |
| Broad advice/dynasty defaults encouraged unrelated questions and long-horizon takes during weekly work. | Weekly discovery defaults to player-scoped queries in fantasyfootball + nfl; team and specialist rooms are explicit follow-ups. |
| Repeated or concurrent tool calls repeated retrievals. | Shared SQLite TTL cache, reservations, negative caching, and rolling retrieval limits. |
| Results mixed popularity, information relevance and factual support. | Transparent player/signal filtering, identifiable story deduplication, dates/links, and explicit unverified evidence labels; votes do not rank the shortlist. |
| Long roundups could attach another player's injury to the requested player or truncate away the useful paragraph. | Match injury/usage language within relevant paragraphs and return those excerpts. |
| Draft sweeps, live-game tools and weekly research appeared interchangeable. | MCP server instructions, purpose-specific tool descriptions, and one canonical weekly runbook returned by `weekly_checklist()`. Removed an accidentally exposed private age-formatting tool. |
| Week status compared only the week number, accepting last season's same week. | Compare season and week together. |

## Design and boundaries

`engine/reddit-scraper/research.py` contains the retrieval/cache and shortlist
logic. Thin MCP wrappers handle player resolution and tool responses. The
existing draft pipeline and team-source catalogue remain available; this work
builds on the source-catalogue changes already present in the working tree.
No new runtime dependencies, alternative Reddit scraper, or model-based
classification service were introduced.

Recommended per-pass workflow: one batch of up to six decision-relevant players,
one targeted follow-up if needed, at most two detail reads, then deliver the
supported action and evidence gaps. These are workflow instructions. Code
separately enforces a shared 24-operation rolling hourly ceiling, at most eight
detail reads, candidate/source limits and no reply expansion. Counts represent
retrieval operations; PRAW's HTTP authentication, pagination and retries are
not an exact one-to-one mapping. Corpus and live-game tools are outside this
budget and the runbook explicitly excludes them from routine weekly work.

Discovery cache: 15 minutes. Detail cache: 5 minutes. Errors: 60 seconds, reported
as unavailable rather than empty success. Expired data is never returned as
current. Source text stays in the ignored local corpus cache. Original reports
are verified using the agent's existing web reader; no new source-fetching
service is needed. All source text is treated as data rather than instructions.

The live test exposed a useful relevance issue: a multi-team data roundup
mentioned the requested player's usage and a different player's injury in
separate paragraphs. The added paragraph regression ensures that a usage lead
is not misclassified as that player's injury update.

## Validation

- 22 offline Reddit tests: retrieval bounds, no hidden comment reads, cache reuse
  across instances, expiry, cached empty results/errors, concurrent reservations,
  budgets, duplicates, relevant excerpts, missing coverage, real name-pool
  matching, tool schemas and an actual MCP structured-output invocation.
- 13 existing weekly-engine tests plus two new weekly workflow/status tests.
- One live batched discovery for two players inspected 20 candidate posts with
  zero comment reads. Repeating the same query returned a cache hit with zero
  additional retrieval operations. This checks live integration and cache
  behavior, not season-long precision/recall or recommendation quality.

Run from the repository root:

```bash
.venv-reddit-scraper/bin/python -m unittest discover -s engine/reddit-scraper -p test_research.py
.venv-league-sim/bin/python -m unittest discover -s engine/weekly -p 'test_*.py'
```

Load the updated code by reconnecting/restarting the ff-reddit and ff-weekly MCP
servers. An already-running process can still expose the old tools. No new
recurring schedule or roster transaction was created by this review.

## Remaining limits

This is a bounded relevance heuristic, not proof of truth or exhaustive search.
News can arrive after a cached read; titles can omit a player's name; the
preseason pool can omit current players; and a source can report something
incorrectly. Full-name fallback handles players absent from the pool. Original
report verification, current official availability checks and explicit coverage
gaps remain essential. Repost deduplication cannot establish independent
corroboration across different publishers. Per-player precision and useful
recommendation rates need evaluation across actual weekly reports before
claiming improvement in fantasy results.

References: [PRAW comment extraction](https://praw.readthedocs.io/en/stable/tutorials/comments.html),
[PRAW submission comment limits](https://praw.readthedocs.io/en/stable/code_overview/models/submission.html),
and [MCP tool descriptions and structured output](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
