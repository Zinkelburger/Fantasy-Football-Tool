# Team question workflow review — September 25, 2026

**Follow-up implementation:** the [current tool/source map](TEAM-QUESTIONS.md)
now documents practice-report and news tools, another team's roster/lineup read,
local Reddit thread search, persistent weather caching, explicit refresh/offline
controls and week-safe bundle/matchup selection. The original review below
records what was implemented at the first pass; its remaining-tool list is
historical. Follow-up validation: 101 weekly, 27 Reddit research and 18 weather
tests passed; fresh MCP reads verified live practice/news/roster/weather results,
cache reuse, and offline Reddit lookup (including a missing retained snapshot).

The largest opportunity is to make the evidence easier to consume correctly.
The root instructions were only 51 lines. Shortening them helps navigation, but
cannot by itself fix ambiguous tool output, stale status tags or unsupported
interpretations. Keep one shared entry point and a task-oriented runbook, then
move repeated data assembly behind the existing MCP server.

## Evidence reviewed

Screened the user messages, model metadata and tool names in 18 recent local
project logs. Seven fantasy sessions from September 22–24 identify their model
as `claude-opus-5-5`; an eighth Opus 5.5 session concerned a PR rather than team
advice. Earlier logs include Opus 5 and Sonnet 5 and are not attributed to 5.5.
Detailed review focused on the injury, start/sit, matchup and league-comparison
answers below, alongside the current repo code and guidance. This is a process
audit, not a controlled model comparison or a re-verification of today's news.

Local source logs are under
`~/.claude/projects/-home-anbernal-Projects-Fantasy-Football-Tool/`.
References below are session IDs and JSONL line numbers at review time. Raw
transcripts, private league exports and credentials are not copied here.

| Observed behavior | Evidence | Process implication |
|---|---|---|
| A prior-week OUT tag was initially treated as this week's Flowers status, then corrected on follow-up. | `22b984a6-35ef-4ff1-a4a4-9e0fddecc326`, answers at lines 87 and 155 | Carry the report week and timestamp with the status; read the current club report before making an availability claim. |
| The Diggs season-rank question was answered with his weekly ECR, including speculation that the user remembered his Buffalo years. | `448b6370-d854-4a0f-ac73-fad25a771841`, line 112 | Distinguish season production, weekly rank, usage EP and the blended projection before explaining disagreements. |
| The answer called Smith-Njigba Diggs's teammate. The rankings tool displayed an unlabeled opponent after a blank team field; the roster independently identified Diggs's team. | Same session, tool results at lines 99–101 and answer at 112; `fftiers.parse` and `fantasypros_rankings` | This has a concrete presentation cause: label `team` and `opp`, with missing values explicit. Do not interpret opponent codes as team assignments. |
| A 93.5–89.5 projection became a 55–60% win estimate, acknowledged as a rough estimate rather than model output. | `f55e07d7-399c-48e6-8e9f-73f6c785696f`, line 142 | Labeling a guess does not calibrate it. Give the point gap and lineup scenarios; reserve percentages for a validated probability model. |
| Follow-up lineup prose moved the earlier Skattebo kickoff back into RB/WR after previously presenting the optimizer's CMC timing move. | `22b984a6-35ef-4ff1-a4a4-9e0fddecc326`, lines 87, 155 and 166 | Recheck the complete legal slot assignment after changing a starter manually. Timing is part of the delivered answer. |
| Strong regression language was walked back only after the user challenged it. Even the correction quoted historical finding-39 figures despite a superseding audit. | `f55e07d7-399c-48e6-8e9f-73f6c785696f`, lines 195 and 254; finding 39's September 15 correction | Consult the latest correction first. Separate retrospective usage, future prediction, efficiency persistence and the false idea of being owed points. |
| Basic injury and opponent questions needed shell-level assembly. | First Flowers question: four Bash calls; first opponent review: nine Bash calls, including club reports, Bluesky and direct imports of league/advisor code | Expose existing functions through narrow read tools. These counts exclude later user-requested feature/research work in those sessions. |

The chats also did useful work: corrected the decision week, exposed projection
components, surfaced timing-only moves initially, and often disclosed unverified
sources. Explicit user requests for research and new tools account for much of
the longer sessions; their full-session tool counts are not evidence of waste.

## Changes made in this review

- Reduced `AGENTS.md` from 51 to 31 lines: shared constraints and task routing.
- Added a one-line `CLAUDE.md` import of `AGENTS.md`; no duplicate rule body.
- Made the defense publication rule conditional rather than always applied.
  The root still explicitly routes publishing requests to it, and its actual
  publication instructions are unchanged.
- Reworked `RESEARCH.md` from 146 to 124 lines into task paths, evidence checks,
  bounded Reddit research and answer delivery. Narrow injury questions no
  longer imply a full roster/rankings audit. Explicit whole-roster discussion
  can use more than one six-player batch without pretending to cover everyone.
- Moved optional source details to `docs/NEWS-SOURCES.md`, retaining the existing
  Subvertadown scoring/privacy and First Down saved-page/freshness restrictions.
  Corrected that catalogue's obsolete claim that no paid key means no ECR.
- Labeled ranking output `team=... opp=...`, with `unknown` for absent values;
  added a regression covering missing teams, known teams and absent opponents.
- Replaced the rankings tool's assertion that tiers imply coin flips or real
  performance gaps with a description of expert-rank clustering.

The existing uncommitted source integrations, research and data changes were
preserved. No model weights, ESPN roster, public edition or deployment changed.

## Next implementation priorities

1. **Expose current practice reports and news through ff-weekly.** Wrap
   `club_reports.build`/coverage and `bluesky.wire`; reuse their parsing,
   bounds and failures. Return season/week, per-day participation, official
   designation, source/retrieval times, links and pending/unavailable coverage.
   Preserve the distinction between news-wire reports and official designations.
   A current roster OUT flag must not silently become an official current-week
   OUT designation. Add freshness to the existing cached injury tool as well.
2. **Expose an opponent roster/matchup comparison.** Reuse `espn_league`,
   `projector` and `advisor.optimal_lineup` instead of writing scratch scripts.
   Return current starters, optimized starters, locked players and explicit
   replacement scenarios with the same scoring recipe on both sides. Keep
   roster-strength value separate from this week's projection. Do not add a
   made-up probability field.
3. **Make manual lineup scenarios reusable.** A read-only preview accepting
   chosen starters should validate eligibility and apply the existing kickoff
   reslotting before issuing an exact proposal. This closes the gap between an
   optimizer recommendation and a later conversational preference.
4. **Only then consider a compact team briefing.** Compose those existing reads
   into one result with per-source timestamps and missing inputs. Avoid a second
   projection model or one timestamp that makes all sources appear equally fresh.
   Batch only the players implicated by the question, and refresh the required
   source rather than the entire weekly build.

These tool additions are recommendations, not implemented capabilities.
The runbook includes the working CLI paths in the meantime.

## Instruction loading and memory

The inspected Claude log reports client version 2.1.281. Current Claude Code
supports `AGENTS.md` directly under its default project-instruction setting;
absence of `CLAUDE.md` does **not** prove the old sessions missed instructions.
The import is an explicit shared entry point that also supports sessions without
direct AGENTS loading. Confirm active memory files in a new session. See
[Claude's instruction-loading documentation](https://code.claude.com/docs/en/memory).
Codex reads root guidance through its own
[AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Local auto-memory still contains obsolete setup prose: the MEMORY index says
ESPN cookies are needed while its linked note says reads were verified, and the
setup note describes andrewbernal.com as a dashboard-domain change. Current
publication docs correctly identify the sibling website repo. Replace these
dated setup claims with pointers to the live status tool and publication docs;
do not store live roster/injury facts in persistent memory. Those external memory
files were inspected but not changed by this repo cleanup.

## Validation and follow-up evaluation

All 88 weekly tests passed, including the new rankings regression and existing
MCP stdio integration. `git diff --check` passed. The runtime change is confined
to ranking presentation/documentation; this does not establish that future
model answers improve. Reconnect ff-weekly to load the changed Python formatter;
`weekly_checklist()` reads the Markdown file on each call.

For a real before/after evaluation, replay the following questions with the same
dated tool fixtures and the same model/settings. Score correctness first, then
tool calls and time to the first useful answer. Repeat cases to assess variability.
Do not use live changing data for the comparison or enable ESPN writes.

| Replay case | Required behavior |
|---|---|
| Prior-week OUT, current report pending | Report current availability as unresolved; identify the next report and kickoff decision deadline. |
| Season WR10 but weekly WR34 | Explain the different time horizons and projection ingredients without dismissing the user's premise. |
| Rankings supply opponent but no team | Never infer a teammate relationship from that abbreviation. |
| User challenges a close start/sit pick | Recheck evidence; state any change and reason; keep a legal lineup with kickoff flexibility. |
| Opponent QB may be replaced | Show comparable lineup scenarios and point gaps without an unsupported win percentage. |
| Player below expected points | Distinguish a descriptive gap from a guaranteed rebound; use the current research correction. |
| User asks for Reddit on both rosters | Declare batches and actual coverage; verify material original reports; never equate an empty sample with no news. |
| Ordinary team question | No publishing, broad model rebuild, code installation or roster write unless separately requested. |

The replay evaluation has not been run. It is the next check before claiming
that shorter guidance or a particular model produces more reliable advice.
