# MCP usability pass for smaller models

The design goal is to reduce decisions the caller must make correctly before
it can answer the football question. A tool should state what it establishes,
what is unknown, and the next useful action or stopping point. More prompting
does not compensate for ambiguous identities, missing data or unsafe execution.

This pass follows the [initial correctness review](MCP-REVIEW-2026-09-30.md)
and the receiving-opportunity/injury improvements. It covers discovery,
arguments, returned evidence, error recovery, source expansion and action
previews across weekly, Reddit, weather and YouTube. Existing working-tree
changes were preserved. No ESPN move, paid model call or live Luna benchmark
was performed.

## Where a caller would get confused

| Situation | Trap | Implemented change |
|---|---|---|
| Start an ordinary question | Two full guides before deciding which tools matter | Short default guides; eight task-specific paths with explicit stop rules; full documentation remains opt-in |
| Ask whether a receiver's injury helps a teammate | Historical vacancy, current injury and candidate ranking look interchangeable | `receiving_opportunity` declares decision status, candidate ordering and next step; percentage fields use 0–100 units |
| Read an injury result | Pending, failed, unlisted and healthy are easy to conflate | Explicit status plus next_step; current status precedes history; compact output includes the news source needed to verify the quoted claim |
| Check whether a player is available | The tool unnecessarily requires projections; surname matching silently picks one player | Named checks use live rosters/pool directly, reject ambiguous matches, and retain UNKNOWN for missing results |
| Read a depth chart | Not found on a fantasy roster is presented as available | Unowned-looking rows now say availability is unverified and point to the named availability check |
| Read a lineup or waiver recommendation | A mechanical optimizer result looks like completed research | Prominent DRAFT / MODEL SHORTLIST labels and the specific injury/role/drop-cost checks still needed |
| Supply an invalid argument | SDK masks ordinary ValueError as a generic crash | Expected argument failures use the SDK's public ToolError type; unexpected failures stay masked |
| Mistype an NFL team | Empty results suggest refreshing the whole data bundle | Team validation explains that refreshing cannot fix an invalid abbreviation |
| Paste a Reddit link | Caller must extract the ID or may choose the full corpus scraper | Bounded thread reader accepts full comments permalinks and redd.it links, canonicalizes the cache key, and rejects unrelated/opaque URLs |
| Read a video | Default transcript may occupy 40,000 characters with no useful continuation | Default page 6,000, maximum 12,000, explicit offset/next_offset; upload date and source limits accompany the text |
| Ask weather for coordinates | Missing timezone crashes after a successful forecast | UTC fallback; schema bounds/provider enum; unknown NFL team is an argument error, not a bye |
| Preview an ESPN move | Raw authenticated request appears in context and the approval question omits the bid | Public preview is an allowlist of action fields; bid appears in the approval question; no authenticated body is serialized |

All 36 weekly tools now carry behavior annotations. External writes are marked
destructive/non-idempotent; local proposal generation is not misrepresented as
a pure read. Annotations inform callers; they do not enforce authorization.

## The intended short paths

- Injury: `injury_check` -> read status/summary/next_step -> answer or wait.
- Receiving beneficiary: `injury_check` -> `receiving_opportunity` -> conditional
  shortlist. Add `my_roster` only if making an actual pickup recommendation.
- Named availability: `free_agents(names=..., week=...)` -> answer. No projection
  model, injury research or broad waiver scan is needed for that narrow question.
- Lineup: established scope/settings/roster -> injury check -> optimizer draft
  -> resolve material conflicts -> final starters with kickoff flexibility.
- Reddit: brief -> linked primary source -> at most the relevant bounded thread
  reads. Empty/failed retrieval is a stopping condition, not a reason to sweep.
- Video: dated player/video search -> relevant transcript page(s) -> summarize
  as creator analysis, not official clearance.
- Transaction: user requests the move -> exact public preview -> explicit
  approval -> execution with the matching token. Research alone stops earlier.

## Verification

Default weekly guides decreased from approximately **25,948 to 2,017 characters**,
a **92% reduction**. The receiving-task guide is 1,038 characters. This measures
tool text, not model tokens or total context loaded by a particular client.

Actual stdio discovery/calls ran against all four launchers: weekly 36 tools,
Reddit 33, weather 3, YouTube 6. The live Waller availability read returned a
129-character answer with the season/week, scoring, checked time, NFL team,
ESPN ID and waiver status. It did not load the projection pipeline.

All **223 tests passed**: weekly 171, Reddit 28, weather 20 and YouTube 4.
Offline tests cover the earlier correctness cases plus guide argument names,
response limits, ambiguous/unmatched availability, projection independence,
public preview fields and synthetic-secret exclusion, public MCP error text,
permalink cache reuse, coordinate weather, and lossless transcript pagination.
No real add/drop or lineup apply was used for validation.

## What remains

There are still **78 tools** in discovery. Corpus/adjudication/publication tools
remain available alongside everyday research tools. A smaller default tool
profile could reduce selection errors further, but it needs a clear advanced
access path and client/reconnect testing; hiding tools without that path can
make legitimate work harder.

The current tool surface still mixes text and structured outputs and has
different time/argument conventions in older tools. Continue migrating common
workflows toward explicit units, IDs, coverage, decision status and next steps,
using compatibility tests rather than a blanket rewrite.

Official game-day inactives and IR activation are not an automated authoritative
feed. Pending reports remain pending. Whole-game target growth cannot establish
post-injury causation or a calibrated points adjustment. Those are evidence and
model limitations, not wording problems.

The initial review's SQL isolation, token replay/account binding, historical
points ownership/cache isolation, and interrupted-venv recovery findings are
still separate correctness work. The public-preview credential exposure is
addressed here; clearer instructions do not resolve the other boundaries.

To measure smaller-model performance, run a fixed set of realistic questions on
the exact target model/version: Monday pickup versus remaining-game lineup,
partial-game injury, unlisted IR player, duplicate surname, unavailable data,
missing odds, receiving beneficiary, D/ST ordering, pasted Reddit link and an
unapproved move. Score wrong tool/arguments/week, unsupported certainty,
unnecessary calls, premature writes, answer correctness, context size and
latency. Include synthetic/no-write execution tools. Repeated deterministic
contract tests are useful, but they do not establish Luna's actual error rate.
