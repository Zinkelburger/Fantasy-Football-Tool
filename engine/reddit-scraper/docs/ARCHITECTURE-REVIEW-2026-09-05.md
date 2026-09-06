**Architecture review — September 5, 2026**

The thread → typed claims → player note architecture is worth keeping. Its main
weakness is that it preserves an agent's assertion more reliably than the evidence
supporting that assertion. Source fidelity, real-world verification and draft
judgment currently blur together. Better prompts alone will not close that gap.

This is a review and proposed implementation plan, not a deployed redesign. No
scraper code, corpus records or published player notes were changed. The review
used the local source, runbooks, recent commit descriptions, corpus aggregates,
sample source-to-claim comparisons, and isolated behavioral checks. There is no
complete saved record proving which digest pages each agent read or why it omitted
a particular claim. Descriptions of individual runs in git history are evidence
of reported workflow, not substitutes for execution logs.

**How decisions are made today**

| Stage | Code/tool | What actually decides |
|---|---|---|
| Collect | `sweep_subreddit`, `fetch_thread` | Listing limits, age, comment thresholds and optional title relevance select posts. Comments are expanded with a cap and sorted by score for collection. |
| Prioritize | `_mention_index`, `_thread_priority`, `next_threads` | Name matching estimates relevance. A hand-built score favors attributed news, concentration on a few draftable players and recency; long threads and AMAs are penalized. |
| Present | `thread_digest`, `distill_thread` | A reply tree is paginated; low-score comments and short nameless leaves are pruned unless they have retained descendants. The agent is instructed to read every page. |
| Extract | Agent plus `submit_claims` | The agent chooses assertions, players, claim types, authority labels and conditions. The server checks shape and allowed values, not factual support. |
| Synthesize | `player_claims` plus note-writing agent | Claims are grouped by type and date. A second agent reconstructs credibility, current status and disagreements from short summaries, following the note brief. |
| Publish | `write_note`, `note_queue` | Arbitrary Markdown is accepted. Freshness is approximated using note dates and the count of claims present when the note was saved. |

`.mcp.json` registers this server, but `docs/FULL-PASS.md` tells workers to import
the Python module directly to avoid a stale MCP process. The tool functions and
the briefs both matter; revising only a tool description will not consistently
change future runs. `adjudicate.py` resolves player identities, not whether a
football assertion is true.

**Findings, in order of importance**

1. **A stored claim is not a verified fact.** `claims.py:validate` accepts a
   `team_official` assertion without an evidence reference. A supplied comment ID
   is not checked for existence or membership in the thread; dates are not
   validated either. The existing corpus's supplied comment IDs did resolve to
   the right threads in the previous audit, so this is a missing safeguard, not
   evidence that those IDs were fabricated. An isolated check confirmed that a
   nonexistent comment and an invalid date both pass validation.

   `basis` also bundles different things: who supposedly originated a statement,
   whether the Redditor heard it secondhand, and whether it is an observation or
   forecast. Sample `team_official` claims combine a relayed coach quote with fan
   expectations. The Stevenson age example from the preceding audit demonstrates
   the downstream failure: a commenter's assertion was correctly attributed in a
   claim, then asserted without that qualification in the note.

2. **The note-writing handoff discards evidence and explicit corrections.**
   `mcp_server.py:player_claims` prints claim text, date, basis, condition and
   thread ID. It omits the supporting comment ID and the `supersedes` field. There
   are 44 populated `supersedes` fields in this snapshot. An isolated check
   confirmed that neither the correction target nor the supporting comment ID
   reaches the writer. The source is retrievable manually, but the ordinary
   writing loop does not require that retrieval.

   `write_note` then accepts unsupported, undated prose; the missing-date warning
   happens after writing. The last-line instruction to make the draft take decide
   something encourages a stronger conclusion than thin evidence sometimes allows.

3. **“Finished” and “current” are stronger claims than the tools can establish.**
   `claims.py:distilled_threads` treats any thread with one claim as complete. No
   separate completion record identifies pages delivered, source revision, omitted
   topics or extraction scope. Submitting one batch releases the lease, even if
   the reader intended another batch. `release_thread` permanently retires a
   thread; it is not an ordinary abandon-work operation.

   `write_note` records the total claim count at write time, not the actual input
   snapshot or claim IDs used. This can mark unseen claims as consumed if new
   claims arrive while a writer is working. Replacing or correcting a claim without
   increasing the count can also evade freshness detection. An isolated check
   confirmed that arbitrary prose is logged as using all stored claims.

   There is a concrete queue bug at `mcp_server.py:1380`: sorting
   `not status.startswith("current")` ascending puts current notes first. A
   fixture with one current and one stale note and `limit=1` returned only the
   current note, contrary to the printed instructions.

4. **Evidence can age without being revisited.** A normal sweep skips cached
   posts. Explicit `fetch_thread` adds new comment IDs but does not update an
   existing post or edited comment. Neither path records retrieval time, external
   submission URL or author identity in the current schema. New comments on an
   explicitly refreshed thread also do not invalidate its per-post mention cache
   or its completed status.

   Claims default to the thread's date, even when the source is a later reply.
   In this snapshot 765 claims have a date earlier than their referenced comment's
   UTC date. This does not prove the football event was misdated: an event can
   precede a comment. It does show why event date, publication time and retrieval
   time must be distinct. An old practice absence should trigger a follow-up check,
   not remain a current injury merely because nothing newer was extracted.

5. **Thread selection optimizes an imperfect proxy for useful information.**
   A title and the number of player mentions cannot determine whether a long
   discussion contains valuable statistics or relayed reporting. Commit `672b4ee`
   explicitly reports that reading discussion threads recovered material missed
   by the earlier news-first pass, but the scorer and runbook still retain the
   earlier broad size/AMA rationale. That commit's raw claim totals also do not
   establish quality per unit of effort; they use the same unreliable basis labels.

   Downvotes are useful for presentation but are not a truth test. Pruning can
   hide a correct dissenting reply. Counting names in nomination slots also does
   not establish endorsement, although the tool warns about this. Do not turn
   those tallies into a measured consensus without reading stance and context.

6. **The briefs overstate what the backtest established.** The note brief and
   full-pass runbook say injury and role facts are what the 2025 study found useful.
   `research/reddit-notes-study/METHODOLOGY.md` explicitly says the study tested
   tone and says nothing about the value of specific facts. Prioritizing recent
   role/availability evidence is a sensible design hypothesis, not a demonstrated
   result from that study. The silent-player template similarly treats absence of
   extracted discussion as a football signal; it should describe limited coverage.

**Proposed tool contracts**

These are proposed changes, not callable tools added by this review. Extend the
existing server in stages rather than replace the resolver or add more writers.

| Contract | Required behavior |
|---|---|
| `fetch_thread(..., refresh=True)` | Upsert current post/comment records; preserve permitted local revision metadata, fetch time, original linked URL and source identity where available. Invalidate only affected indexes and mark completed work outdated when the source changes. |
| `distill_thread` | Return a source revision and read-session ID, page identifiers, direct source links and the ability to retrieve unpruned replies. Record pages delivered; this proves delivery, not comprehension. |
| `submit_claims` | Store drafts without retiring the thread. Require stable claim IDs and evidence references for factual assertions. Validate reference membership, dates and supplied evidence spans. Keep one assertion per claim. |
| `finish_thread` | Explicitly close a source revision after required pages were delivered; record the scope, exclusions and whether any issues remain. Separate this from `abandon_thread`, which returns a lease to the queue. |
| `review_claim` | Record whether the source actually supports the assertion and, separately, whether it was checked against an original/authoritative source. Keep the verification source, date, outcome and a concise explanation. |
| `player_claims` | Return an immutable snapshot ID, claim IDs, evidence links/excerpts, verification state, conditions, correction relationships, conflicts and follow-up needs. Preserve attributed opinion as attributed opinion. |
| `write_note` | Require the input snapshot and supporting claim IDs for factual bullets. Record recommendations separately with their evidence and conditions. Reject broken references; stage unsupported factual assertions for correction. Detect newer material before publication. Render readable Markdown with source links. |
| `note_queue` | Put work-needed notes first. Compare source/claim revisions and verification freshness, not just counts. Expose unknown, thin, conflicting and stale evidence states. |

The minimum new claim metadata should separate:

- **Assertion:** one statement, player ID, and whether it is an observation,
  relayed report, opinion or prediction.
- **Evidence:** one or more post/comment references and local supporting spans;
  originating source URL/name where known; direct versus relayed attribution.
- **Verification:** unchecked, source-supported, independently corroborated,
  contradicted or unresolved, with the check's evidence and timestamp. These are
  records of checks performed, not a model's invented confidence percentage.
- **Time and scope:** event date when known, source publication/retrieval times,
  season, scoring/league context for market claims, and next-check requirements.
- **Relationships:** stable IDs for superseded claims and prerequisite player
  statuses. Link repeated versions of the same originating report so ten Reddit
  reposts do not become ten independent confirmations.

Checking that an evidence span exists cannot prove the claim is true. A semantic
review still has to determine whether it supports the assertion; a separate
external check is needed to establish real-world facts. An unavailable original
source must remain visibly unverified. Do not silently upgrade old records when
migrating them into this schema.

For example, a practice absence on August 11 should remain a supported observation
about that date. If no later evidence is available, the September note should say
current participation is unknown and needs checking. It should not infer an
ongoing absence. A coach's forecast can be verified as a real quote while still
remaining a forecast rather than a confirmed role.

**Implementation order and acceptance checks**

1. Repair the immediate defects: queue order; missing comment/correction fields
   in writer input; reference/date validation; inaccurate backtest language;
   silent-player and draft-take instructions. These are bounded changes that do
   not require re-extracting the whole corpus.
2. Add source revisions, explicit thread completion and note input snapshots.
   Preserve old claims as legacy/unverified records and queue them for review
   when they affect a decision. Separate lease abandonment from permanent skip.
3. Add verification and structured note support. Review current availability,
   roster changes and decision-changing usage/statistical claims first. A second
   model agreeing with the first without looking at evidence is not verification.
4. Improve discovery with player-specific coverage gaps and follow-up queries,
   plus a bounded sample of lower-ranked discussion threads. Measure missed
   useful evidence and correction retrieval before tuning the ranking again.

Before another full pass, replay a small fixed set of source threads containing:
an incorrect statistic, a relayed coach quote, a corrected injury report, a
temporary role contingent on another player, a valuable long discussion, a
downvoted correction, and a player with little evidence. Include tests for a
partial multi-page read, changed source text, a mid-write new claim and two notes
whose claim counts are equal but contents differ.

Measure source-to-claim support, false factual assertions, preserved conditions,
recognized corrections, freshness, and how many useful facts a human review finds
that the pipeline missed. Track opinions separately from verified observations.
Keep extraction quality separate from a future test of whether the resulting
draft decisions outperform current rankings.

The isolated checks in this review reproduced seven current behaviors: invalid
reference/date acceptance; omitted correction target; omitted comment ID;
current-before-stale queue ordering; unsupported/undated note publication;
unearned claim-consumption logging; and one-claim thread completion. They used the
actual function bodies with temporary fixtures and mocked surrounding I/O; no
Reddit request, real corpus write or deployment was performed.
