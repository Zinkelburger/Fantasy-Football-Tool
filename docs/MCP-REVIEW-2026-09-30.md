# MCP correctness and LLM usability review

This is the initial review snapshot. Subsequent receiving/injury changes and
the implemented usability pass are documented in
[MCP agent usability](MCP-AGENT-USABILITY-2026-09-30.md), which also identifies
the initial findings that remain open.

Reviewed September 30, 2026, at commit `af5c3b8`, focusing on the September 28
tool expansion (`779381a`) and launcher change (`af5c3b8`), with a broader pass
through all four MCP servers and the separate model integrations.

The recent direction is good: tools answer recognizable questions, return
smaller responses, and distinguish evidence from judgment. The next priority
is enforcing those promises in code. I reproduced defects in SQL isolation,
credential redaction, transaction replay, cache correctness, startup recovery,
and several input paths. Better prompting alone cannot fix these.

This is a review and implementation proposal. Production code is unchanged.
The existing edits to `docs/TEAM-QUESTIONS.md` and `engine/weekly/RESEARCH.md`
were preserved. No real ESPN write or paid model evaluation was performed.

## Verification results

| Server | Tools | Warm initialization | Checks performed |
| --- | ---: | ---: | --- |
| ff-weekly | 35 | 0.50 s | Actual stdio discovery and calls; saved SQL, schedule and target-share reads; confirmation refusal; live NFL state and ESPN settings; 135 tests passed |
| ff-reddit | 33 | 1.08 s | Actual stdio discovery and source catalogue; live discovery through the connected MCP; 27 tests passed |
| ff-youtube | 6 | 0.62 s | Actual stdio discovery and watched channels; live one-video listing with upload metadata |
| ff-weather | 3 | 0.48 s | Actual stdio discovery and stadium lookup; live one-hour NWS forecast; 18 tests passed |

All 180 existing weekly/Reddit/weather tests passed. The read-only live checks
succeeded around 14:48 UTC. Reddit discovery used one retrieval operation and
fetched no comments; raw source text is not included in this document. NWS
returned a fresh forecast, and YouTube returned a dated upload. These checks
establish connectivity and basic retrieval, not the correctness of every source
parser or football recommendation. YouTube transcript retrieval was not tested.

All four local servers negotiated MCP `2025-11-25`. The weekly environment has
MCP 2.2.0 and Polars 1.43.1. The current published MCP revision resolves to
`2026-07-28`; using a mutually supported older revision is not itself a defect.
Protocol upgrades should be compatibility-tested rather than combined with
these application fixes. See the specification's
[backward compatibility guidance](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports).

Discovery measurements:

- 77 tools, with **zero behavior annotations**.
- 218 input properties, with **zero property descriptions**, one enum, and no
  numeric bounds encoded in the generated schemas. Some limits are enforced
  correctly inside the implementations, particularly Reddit research.
- 74 tools have output schemas, but most are automatically generated
  `{result: string}` wrappers. The three weekly tools returning bare `dict`
  have no output schema. Open-ended dictionaries are not precise contracts.
- Serialized tool definitions total approximately 72,620 characters. This is
  an inventory measurement, not a claim about tokens loaded by every client;
  clients can defer discovery or tool loading.
- A malformed SQL query returned `isError=false` over real MCP transport.
- The flagged-team target-share response was 3,066 characters: the compact
  format is working and should be retained.

## Confirmed findings

P1 means fix before relying on the affected boundary. P2 means a correctness
or reliability defect to include in the next hardening pass. Reproductions used
temporary files and mocks where needed; they did not read real credentials or
send transactions.

### P1 SQL can read outside the registered tables

Introduced in `779381a`.
[datastore.py](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/datastore.py:219)
checks that the query starts with SELECT/WITH and contains a known table name,
then delegates to Polars SQL. Polars also accepts file-reading table functions.

With a harmless one-row temporary CSV, this succeeded:

```sql
SELECT * FROM read_csv('/tmp/<temporary-directory>/outside.csv') AS usage
```

The registered-table check sees the alias `usage`, yet the result contains the
temporary file's contents. No join to a real weekly table is necessary. The
tool's promised boundary of saved weekly tables is therefore not enforced.
This matters especially because the same process can access credential files.
Only local-file access was reproduced; external URL access was not tested.

**Fix:** validate a parsed query tree against permitted statement types,
registered relations, and allowed operations. Reject external table functions
and file/URL sources, including nested queries and CTEs. Add process-level
execution limits for expensive queries: a returned-row cap does not bound the
work required by a sort or join. Do not treat another regular expression as a
complete SQL security boundary.

### P1 The transaction preview returns a cookie value

Predates these commits, from the original weekly write path.
[propose_transaction](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/mcp_server.py:1637)
serializes the entire dry-run body.
[League.transaction](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/espn_league.py:300)
puts `self.swid` in `memberId`. The preview therefore exposes the ESPN SWID
cookie value in model-visible output, contrary to the repository instruction.
A synthetic sentinel supplied as SWID appeared in the returned preview.

**Fix:** construct a public preview from an explicit allowlist of player IDs,
names, add/drop actions, bid, week, league and team identifiers. Keep member
credentials inside the transport layer. Test previews, errors and execution
receipts with synthetic secrets and assert that none reaches returned content.

### P1 Proposal tokens permit repeated writes and lack account scope

Predates these commits.
[proposal storage](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/mcp_server.py:247)
records only kind, payload, week and timestamp.
[execution](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/mcp_server.py:1649)
does not consume the token and resolves the current league/season again.
Calling the same confirmed token twice produced two mock external write
attempts. Actual duplicate acceptance by ESPN was not tested and should not be
relied upon as the safeguard. A changed league/team configuration can also
redirect execution away from the scope originally previewed.

**Fix:** keep the existing explicit user-confirmation workflow, and bind each
proposal to season, league, team, exact action and relevant roster state.
Use an atomic store with pending/executing/succeeded/failed/unknown states and
an execution receipt. A replay should return the receipt or require resolution,
not send again. After a timeout with an uncertain ESPN outcome, reconcile before
retrying. Recheck locks, ownership and the approved scope immediately before
the write. `confirmed=True` remains a caller assertion, not independent proof
of human consent.

### P2 Historical points reuse stale ownership as current availability

Introduced in `779381a`.
[league_points.py](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/league_points.py:26)
caches player ownership/status alongside completed-week points for 12 hours.
The `available_only` filter then uses that cached status. After a fixture player
was picked up, the second call still listed him as a free agent and did not
read updated ownership. No retrieval timestamp warns the caller.

**Fix:** cache historical scores independently, then join current availability
by ESPN player ID. Return separate timestamps for scores and ownership. If
current ownership cannot be verified, return unknown availability instead of
placing the player in an available-only result.

### P2 League points are cached without league identity

Introduced in `779381a`.
[the cache key](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/league_points.py:20)
contains season, week and position, but not league ID or scoring settings.
Two mock leagues sharing a cache returned the first league's 5.3 points for
the second league, whose reader would have returned 99; the second reader was
never called. This is conditional on switching/sharing league configuration,
but contradicts the promise of exact points in THIS league.

**Fix:** namespace scores by league and season, and invalidate when the scoring
rules change. Treat team-specific context separately where needed.

### P2 Interrupted virtual environment creation can remain broken forever

Introduced in `af5c3b8`.
[the launcher](/home/anbernal/Projects/Fantasy-Football-Tool/engine/mcp_launch.sh:58)
treats an executable `bin/python` as evidence that venv creation completed.
If interrupted after Python exists but before pip is installed, subsequent
attempts call the missing `bin/pip`. The build marker is written only after
`python3 -m venv` completes.

A disposable copy of the launcher with a venv created using `--without-pip`
reproduced that partial state. Two successive setup attempts exited 127; neither
repaired it. This tests the recovery state, not an actual timed interruption.

**Fix:** under the existing lock, validate Python and pip independently. Repair
pip using ensurepip or recreate only the incomplete environment; use
`python -m pip` after validation. Add tests for missing Python, missing pip,
interrupted dependency installation, concurrent weekly/weather startup and
requirements changes. Preserve the existing stderr-only bootstrap behavior.

### P2 Injury timing mistakes missing odds for a bye

Introduced in `779381a`.
[next_game](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/injury_check.py:40)
searches the lines file and adds a bye whenever the team has no row. But
[the lines producer](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/lines.py:30)
omits schedule rows without totals. An absent line is not evidence of a bye.
A fixture with missing Week 4 odds and a Week 5 row reported Week 4 as a bye
and selected Week 5 for injury timing.

**Fix:** determine opponents, byes and kickoffs from the full schedule, then
attach odds when available. A missing schedule must remain unknown. Use the
same schedule service for injury, weather, roster locks and lineup timing.

### P2 Coordinate weather requests crash after a successful fetch

Existing weather implementation.
[weather](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weather/mcp_server.py:64)
uses `datetime.timezone.utc` when raw coordinates have no timezone, then reads
`tz.key`, which exists on `ZoneInfo` but not that UTC object. The documented
`weather("44.50,-88.06")` input raised `AttributeError` with a successful mocked
provider response.

**Fix:** use a consistent timezone representation and explicitly state the
timezone for raw coordinates. Add a wrapper test, not just provider tests.

### P2 Availability silently selects an ambiguous player

Introduced in `779381a`.
[_availability](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/mcp_server.py:1507)
selects the first substring match. A query for `Brown` with A.J. Brown and
Chase Brown on a fixture roster returned only A.J. Brown, with no ambiguity
warning. The transaction resolver already handles ambiguity better.

**Fix:** share one resolver across lookup, injury and transaction tools. Prefer
canonical IDs and exact normalized names; return candidates when a partial
name has multiple matches. Do not infer availability from the first match.

### P2 Partial scores can crash the schedule response

Introduced in `779381a`.
[team_weeks](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/schedule_view.py:93)
constructs a score tuple when only the requested team's score is present.
The formatter compares that number with a potentially null opposing score.
A `(24, None)` fixture raised `TypeError`. Related completion helpers check
only the home score, so they can also classify incomplete data as final.

**Fix:** require both scores and a reliable final-state signal where available;
otherwise display pending/partial data without a W/L result. Use one completion
predicate across schedule, usage freshness and league-points cache selection.

### P2 Query errors are reported as successful tool calls

Introduced with the new SQL tool.
[datastore.query](/home/anbernal/Projects/Fantasy-Football-Tool/engine/weekly/datastore.py:238)
returns an error sentence as an ordinary string. An actual MCP call requesting
a nonexistent column returned `isError=false` and a success-shaped structured
result. Other wrappers similarly encode unavailable/error states inconsistently.

**Fix:** map invalid input and execution failures to sanitized MCP tool errors,
with a stable code and useful recovery instruction. Keep a legitimate empty
result distinct from a failed retrieval. Planned partial coverage can be an
explicit typed domain state. Both the tested protocol and the
[current tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
distinguish tool execution errors from protocol errors.

## Make the tools easier for an LLM to use correctly

These are proposed design changes, not measured improvements yet.

**Use a small shared contract layer.** Keep football calculations and source
adapters in their existing modules. Put parameter validation, identity/scope,
freshness, error conversion and output models in a shared layer, with thin MCP
wrappers. Split the large weekly server by domain when touching it, without
renaming every public tool at once.

Start typed responses with `week_status`, named-player availability,
`injury_check`, lineup proposals and execution receipts. Return a concise
summary alongside inspectable fields for season, decision week, observed
weeks, player IDs, league scope, source timestamps, cache state, coverage and
warnings. Add an explicit distinction between observed points, usage-based
expected points, model projections and narrative judgment. Do not attach every
field to every trivial utility tool.

**Make inputs explicit and bounded.** Put enum values and constraints into the
schema: scoring format, position, response detail, name-list length, output
limit and forecast horizon. Use descriptions for the meaning of each field.
Separate decision week from observed game week in both parameter names and
results. Add explicit season/week control to workflows that currently depend
on implicit state, especially the opponent injury path. Retain automatic
next-game selection as a clearly named mode.

**Resolve players independently of whether they have usage.** Injury checks
currently start from opportunity rows, even in roster mode. Kickers and players
who have not recorded usage can therefore fail to resolve despite being on the
live roster. Start with current ESPN roster identities and the player crosswalk,
using historical usage as evidence rather than the identity catalogue. Return
an explicit unresolved state when sources disagree about a team assignment.

**Describe and annotate actual behavior.** Distinguish reads, cache refreshes,
local proposal creation, corpus editing/publication, and ESPN writes. Annotate
destructive effects, repeat-call behavior and external access accurately;
annotations supplement server checks. Retain the useful user-oriented tool
descriptions. OpenAI's [tool contract guidance](https://developers.openai.com/plugins/plan/tools)
specifically calls for explicit scope, structured outputs, failure behavior,
stable identifiers and secret-free results.

**Separate routine research from corpus maintenance.** The 33 Reddit tools mix
bounded weekly discovery with sweeps, adjudication, claims, note publication and
live-game collection. Offer an optional weekly profile exposing the research
brief, targeted search, cached lookup and selected-thread reader, while keeping
maintenance tools in an explicit profile/server. Keep ESPN execution tools in
an optional write surface if the host supports it. Avoid a large mandatory
"answer everything" tool that hides unrelated retrieval and writes.

**Preserve the recent output reductions.** Keep compact default summaries and
optional detail. Return rows as structured data when programs need to compare
or filter them; hand-built CSV strings lose quoting and null semantics. Bound
YouTube listing sizes, transcript output, request time and metadata fan-out.
Mark generated captions explicitly, retain fetch time, and offer excerpt or
offset reads rather than repeatedly returning the same truncated transcript.

Anthropic recommends tools organized around actual workflows, concise relevant
results and realistic task evaluation; this supports the current move toward
direct question tools, with a smaller default surface. See
[Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents).
For programmatic composition, OpenAI recommends compact structured returns,
documented failures and idempotent actions. See
[Programmatic Tool Calling](https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling).

## Current model usage

| Path | What the code does | Recommended treatment |
| --- | --- | --- |
| Four MCP servers | Fetch, cache, resolve, calculate and format data; the calling conversational model synthesizes the answer | Keep deterministic work here. Add enforceable contracts before adding another model layer |
| Reddit legacy scripts | `OpenAIQuery.py` calls Chat Completions; its fallback is `gpt-3.5-turbo`; `live_process.py` selects `gpt-5-nano-2025-08-07`; batch submission selects `gpt-5-mini` | Clearly mark the legacy/offline path. If retained, standardize model configuration, validate outputs and benchmark it separately |
| Draft web app | Direct OpenAI/Ollama text streaming or a local Claude bridge | Treat this as a separate product path with its own evidence limits |
| Claude bridge | Starts the `sonnet` alias with tools disabled and an empty strict MCP configuration | It cannot use these MCP servers; a better MCP server will not improve this path unless integration is deliberately changed |

These are code configurations, not evidence of which model ran in previous
sessions. The current review did not benchmark models or change the selected
models. The highest-value improvement is making the right evidence and action
boundaries easy for any capable calling model to use. Model choice can then be
compared against the same held-out tasks.

## Implementation order and acceptance checks

1. **Repair the boundaries.** Close SQL external-file access; redact preview
   credentials; scope proposals and make execution replay-safe. Acceptance:
   harmless forbidden-file fixtures never read; synthetic secrets never appear;
   replay/concurrent execution attempts never send a second write; uncertain
   outcomes block automatic resubmission.
2. **Repair answer correctness.** Separate current ownership from historical
   scoring; isolate league caches; use full schedules for injury timing; fix
   ambiguous identity, coordinate weather and partial-score handling. Acceptance:
   cover each reproduction above with fixtures at the public tool boundary.
3. **Repair startup and reproducibility.** Handle partial venvs; add a bounded
   `doctor` command reporting server versions, dependency/import health,
   configuration presence and recovery instructions without values. Lock tested
   dependency versions and test upgrades deliberately. Preserve the documented
   `mcp_launch.sh setup <name>` then `/mcp` recovery workflow.
4. **Improve contracts incrementally.** Add annotations, schema constraints,
   typed results and consistent errors to the most-used tools first. Snapshot
   discovery schemas and validate responses through actual stdio calls.
5. **Measure agent outcomes.** Build a fixed set of realistic questions with
   verifiable results, then compare the old and improved interfaces. Include
   Monday pickups, an explicit historical question, an injured player without
   usage, a partial name, stale official evidence, an unavailable deep free
   agent, a manual lineup change that affects FLEX timing, a duplicate write
   retry, Reddit budget exhaustion and an international venue.

Score factual correctness, proper week/scoring/identity, evidence coverage,
preserved kickoff flexibility, consent handling, tool selection, calls, output
size, latency and retries. A shorter answer is not a win if it omits decisive
evidence. Use fixture replay for reproducibility and a small separate live
smoke suite for upstream changes. OpenAI's
[MCP evaluation example](https://developers.openai.com/cookbook/examples/evaluation/use-cases/mcp_eval_notebook)
illustrates combining outcome checks with programmatic tool-use checks.

CI already runs the weekly tests indirectly through `npm test`; that coverage
should be preserved. The same script does not run the Reddit or weather suites.
Add those, launcher recovery tests and a YouTube contract suite. Cold network
installs and paid model evals were not performed in this review.

Reproduce the existing test totals from the repository root:

```bash
.venv-league-sim/bin/python -m unittest discover -s engine/weekly -p 'test_*.py' -q
.venv-reddit-scraper/bin/python -m unittest discover -s engine/reddit-scraper -p 'test_*.py' -q
.venv-league-sim/bin/python -m unittest discover -s engine/weather -p 'test_*.py' -q
```

The two uncommitted handcuff-guidance edits are consistent with the intended
workflow: compare actual carries, high-value touches and targets when a starter
is absent, and distinguish snaps from opportunity. They do not repair the SQL
boundary on which that workflow now relies.
