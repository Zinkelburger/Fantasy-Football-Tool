# Reddit Scraper — per-player draft notes

Scrapes r/fantasyfootball (plus saved FF Hound articles) for discussion of each
draftable player, filters it down to high-confidence mentions, and has an LLM
summarize each player into a markdown note used by the draft tool.

Past seasons' final notes live in `../2024/analysis/` and `../2025/go/analysis/`.
The intermediate scraped text (`raw_data/`, `filtered_data/`, `ff-hound/`,
`markdown_data/`) is **gitignored on purpose** — see `API-TOS.md`: scraped Reddit
comments can't be republished, and this repo is public. Only the generated
summaries get committed.

## Pipeline

```
combined_with_depth.csv          player list: name, team, pos, ADP, depth, nickname
        │
        ▼
main_scrape_reddit_api.py        PRAW search of r/fantasyfootball, tiered name
        │                        matching (full name / nickname = high confidence,
        │                        unique last name = medium, shared last name = low)
        ▼
filtered_data/<slug>_reddit_discussion.txt     (+ <slug>_processing_metadata.json)
        │
        ▼
process_ff_hound.py              greps saved FF Hound HTML (ff-hound/*.html)
        │                        for player mentions
        ▼
filtered_data/<slug>_ff_hound_discussion.txt
        │
        ▼
combine_analyses.py              merges the two per player
        │
        ▼
filtered_data/<slug>_final_discussion.txt
        │
        ▼
live_process.py                  one API call per player (or submit_batch.py /
        │                        get_batch_results.py for the 50%-cheaper Batch API)
        ▼
markdown_data/<Player Name>.md   final note per player
```

`run_full_analysis.py` runs the first three steps in order. `workflow.py` is a
menu-driven wrapper around the batch scripts. The summarizers prefer
`_final_discussion.txt` and fall back to `_reddit_discussion.txt` if the
combine step wasn't run. Shared naming/prompt logic lives in `pipeline_utils.py`.

Every step is resumable: already-produced output files are skipped, so a
crashed run can just be restarted.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp docs/example-.env .env   # then fill in real values
```

`.env` needs (see `docs/example-.env`):

- `CLIENT_ID` / `CLIENT_SECRET` — Reddit script app from https://www.reddit.com/prefs/apps
- `USER_AGENT` — any descriptive string
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, live summarizer; default `gpt-5-nano-2025-08-07`)
- `OPENAI_BATCH_MODEL` (optional, batch summarizer; default `gpt-5-mini`)

## Doing a full pass

`docs/FULL-PASS.md` is the runbook: refresh inputs, sweep, warm the index, fan
agents out to distil, fan them out again to write notes, ship. It assumes no
prior conversation and every step is resumable. The two agent briefs it hands
out are `docs/AGENT_BRIEF.md` (thread -> claims) and `docs/NOTE_BRIEF.md`
(claims -> the note the site shows).

`refresh_pool.py` corrects the pool's teams against Sleeper's live roster,
which is public and needs no key. It is not a replacement for the FantasyPros
ADP export — Sleeper has no ADP and no notion of who is draftable — but it
fixes what the export goes stale on. Run 2026-09-04 against an export taken
2026-08-10, it found six players on new teams (Keenan Allen to Indianapolis,
Kayshon Boutte to Houston, Najee Harris to the Giants, Kaleb Johnson to Green
Bay, Jaydon Blue to Philadelphia, Emari Demercado to Dallas) and one free agent
who had signed. Every one of them was already in our own claims, which is the
useful part: the scraper notices roster moves before the board does.

## Each season's checklist

1. Download the FantasyPros overall-ADP export **and** the six JuiceBoxOne
   per-platform ranking CSVs (ESPN/Sleeper × Standard/Half PPR/PPR — this is
   where the draft tool's ESPN and Sleeper comparison columns come from, and
   what makes the three scoring formats differ). Then:
   `python build_player_csv.py FantasyPros_<year>_Overall_ADP_Rankings.csv --juicebox <dir>`
   This regenerates `combined_with_depth.csv` (nicknames carry over) and the
   three `../go/*_with_depth.csv` board files. Without `--juicebox` the boards
   still build, but ESPN_Rank is blank and all three formats are identical —
   `go test ./...` fails on `TestRankVariationExists` until the data is supplied.
2. Save current FF Hound sleeper/bust articles as HTML into `ff-hound/`
   (optional — the pipeline runs Reddit-only without it).
3. `python run_full_analysis.py` — the scrape takes hours; it's resumable.
4. `python live_process.py` — or `submit_batch.py` then `get_batch_results.py`
   (up to 24h turnaround).
5. Copy `markdown_data/` into the year's analysis directory for the draft tool.

The season year in prompts and Reddit search queries is derived from the
current date (`pipeline_utils.current_season_year()`), so nothing needs
editing year to year.

## Name resolution (`resolve_names.py`)

`match_players.py` guarded single-name matching by testing tokens against
`/usr/share/dict/words`. That dict is 480k entries on Fedora and includes
proper nouns, so it blocked 360 of the pool's 525 name tokens — Burrow, Hurts,
Herbert, Stroud, Daniels, Maye, Purdy — leaving 9 of 39 QBs with any
single-token alias. Benchmarked against one r/fantasyfootball QB thread with a
hand-built ground truth of 215 references, it recovered 16%.

`resolve_names.py` replaces the guard. The pool, not the dictionary, decides
ambiguity: 235 of 271 surnames have exactly one owner among draftable players
and need no disambiguation at all. What's left is scored on context — team,
position, a nearby full-name mention, capitalization, thread title — and only
what stays contested is handed to an LLM. Same benchmark: **93%**, with 6% of
mentions needing adjudication.

Capitalization is read at two levels, because one rule does not fit both kinds
of collision. Ordinary English (`Will`, `Just`, `Take`) needs a capital that
is **not** sentence-initial — at the start of a sentence every word is
capitalized, so the capital proves nothing, and "Just the waiting sucks" is not
Justice Hill. Surnames that happen to be dictionary words (`Love`, `Price`,
`Washington`) need only a capital: "Love in the 9th" is the player, "i love
him" is not. Truncation guesses get the strict rule, since a false positive is
likelier there than a real mention.

Also handled, each worth measurable recall on the benchmark: slash-separated
lists (`TLaw/Dak/Purdy/Nix`), possessives (`Nix's`), misspellings via edit
distance (`Mahommes`, `Murry`), initial+surname (`J Allen`), and apostrophe
folding so the `Wandale Robinson` people type reaches `Wan'Dale Robinson`.

**Surnames carry the load.** Of 2,545 confidently resolved mentions, 1,396 come
from a bare surname — more than full names, first names and nicknames put
together. Two rules protect that, both measured on the same 2,960 comments:

*A possessive prefers the form the pool knows.* `_strip` drops a trailing `'s`,
which turns a plural surname into a different player's first name: `Adam's`
became Adam Randall (ADP 306) in all six occurrences that meant Davante Adams,
and `Jayden Daniel's` became Daniel Jones while also blocking the full-name
match. The apostrophe-folded form is tried first and only falls back when the
pool does not own it — `Cook's` folds to `cooks`, which owns nothing, so it
still reaches James Cook.

*A bare first name next to another name is somebody else.* People do use first
names, but only distinctive ones — Bijan, Puka, Saquon, Rhamondre, CeeDee. The
ordinary ones show up as the front half of a non-player's name: Matt Nagy, Adam
Schefter, Mike McDaniel, Andy Reid, Josh Gordon, Matthew Berry, Kyle Shanahan,
Calvin Austin. Every one of those 42 mentions resolved to a real but wrong
player. So a first-name-only alias is dropped when it abuts another capitalized
name, and the two directions take different evidence, because English
capitalizes the start of every sentence: *after* the token an unfamiliar
capitalized word is a surname (Nagy, Schefter, Gutekunst), while *before* it
only a name the pool already knows counts, or "Targeting Dak" and "Assuming
Bijan" would both be gated. Punctuation between the two exempts the pair, since
`Odunze, Evans, Watson` is a list and `Puka/Jamaar` a slash run — which is why
`tokenize_spans` records whether a separator preceded each token.

Abbreviations are **not** generated. Initialisms (`CMC`, `JSN`, `BTJ`),
initial+surname-prefix forms (`TLaw`, `CRod`) and truncations (`Skat`, `Monty`)
are real, but deriving them from a rule costs far more than it earns. Measured
over 2,960 r/fantasyfootball comments, the three generators produced 79 good
mentions against 2,451 junk candidates — `it` for Isaac TeSlaa (496 hits), `me`
for Mike Evans, `by` for Bryce Young, `then` for TreVeyon Henderson, `dont` for
Dontayvion Wicks, `ball` for Braelon Allen. Only the lowercase gate held them
back, and it leaked whenever the word was capitalized: "she gives off Lavar
Ball vibes" resolved to Braelon Allen at `unique` tier, no adjudication.

The hand-written `Nickname` column scored 147 good to 2 junk over the same
corpus, so that is where abbreviations live. Pipe-separate to give one player
several: `Sun God|ARSB`. Dropping the generators cut the alias table from 2,435
keys to 1,449 and removed 2,451 junk candidates (84% of the gated bucket) while
*raising* accepted mentions from 2,583 to 2,608, because junk aliases had been
stealing tokens from real ones.

    python resolve_names.py --selftest
    python resolve_names.py --text "Dak, Tlaw, Purdy, Nix, Shough for me."

### How good is the disambiguation, measured (Sept 2026)

Audited blind: 84 confidently-resolved mentions sampled across the 47,613-comment
corpus, stratified by how the player was reached. The token, its comment and the
thread title were read *without* the resolver's answer, judged, and compared
after. **81 of 84 correct — 96%.**

The three misses say more than the number:

| token | resolver | truth |
|---|---|---|
| `Chubb` | Chuba Hubbard | Nick Chubb, not in the pool |
| `Douglas` | Caleb Douglas | Pop Douglas, not in the pool |
| `Smith` | DeVonta Smith | Jaxon Smith-Njigba ("Jaxson Smith Injigba") |

Two of three are not disambiguation failures at all. They are people outside the
337-man pool being mapped onto whoever shares their name — the failure the
thread-first design already anticipates and the reason the index is labelled a
retrieval aid. **Picking the wrong player from among pool players happened once
in 84.**

### A misspelling is not a word

The audit turned up one real bug. `fuzzy_alias` gated edit-distance matching on
capitalization alone, and at the start of a sentence every word is capitalized —
the same trap the exact-match path already knew about. Over the corpus:

    'Maybe'      -> Drake Maye          336
    'Browns'     -> Chase Brown         240
    'Thank'      -> Tank Bigsby         186
    'Bench'      -> Jack Bech           146   ("Bench:" in every rate-my-team post)
    'Cleveland'  -> Colston Loveland     51
    'McDaniels'  -> Jayden Daniels       46

All false, 100% of the time. The fix is one rule: **a misspelling is not an
English word.** This is the opposite of the call made for exact surname
matching, where the dictionary was thrown out because it blocked Burrow, Hurts
and Herbert — and the inversion is the point. An exact hit on "Burrow" is
evidence; an edit-distance hop from "Maybe" to "Maye" is not.

A dictionary word may still fuzzy-match if the same player is named elsewhere in
the comment by an alias that did not need fuzzing. That keeps `Kyler Murry`,
where "Kyler" sits right beside it, and drops "Maybe I'm just biased", where no
Drake Maye appears anywhere. Misspellings travel with the name they misspell;
ordinary words do not.

Fuzzy matches went 2,371 -> 1,018 and confident mentions 50,595 -> 48,759 (3.6%),
nearly all of it junk. Selftest still 22/22, including the `Murry` case. What
survives is what fuzzy matching is for: `Charbs`, `Skatt`, `Chubba`, `Jamar`,
`Treyveon`, `Allgier`, `Monongai`, `Ebuka`.

Known residue: `Andy` still reaches Andy Borregales (a kicker, ADP 218) 17 times
when it means Andy Reid. The abutting-capital rule catches "Andy Reid" and misses
"Andy loves good RBs". Kickers draw no claims, so it costs nothing downstream.

### Should we go back to requiring full names?

No, and the numbers are not close.

| | share of confident mentions |
|---|---|
| surname only | 55% |
| full name | 23% |
| first name only | 15% |
| nickname / initialism | 7% |

Full-name-only keeps 23% of mentions. More to the point, **34% of the claims
actually stored came from threads where that player was never once named in
full** — Chase's own "little hyperextension" quote, Saquon's 80% first-team
snap share, Jaylen Warren's spot on the official depth chart, the entire Tee
Higgins market read. Requiring full names does not make those claims safer; it
deletes them.

It also aims at the wrong target. Full names would have fixed all three audit
misses, but so does reading the thread — and that is already how notes get
written. Under thread-first the resolver does not assert anything: it says where
to look, and the model reading the thread says what is true. A wrong index entry
is visible and costs a moment; a missing one is invisible and costs a fact.

The one place resolver output becomes a fact unread is the nominations tally,
which is why it is capped at top-level comments, labelled as counting names in a
nomination slot rather than agreement, and carries upvotes so a reader can see
what the room actually endorsed.

## Adjudication (`adjudicate.py`)

Anything with more than one candidate goes to an LLM rather than being settled
by ADP. Cost is a bad tiebreaker: Jeremiyah Love (RB, ADP 20) outranks Jordan
Love (QB, ADP 141), so "wait for Love in the 9th" in a QB thread points at the
wrong player. Measured on the benchmark thread, 336 mentions produced 42
needing a real decision — about 12% — and the heuristic guess was wrong on
several of them (`Caleb` -> Caleb Douglas rather than Caleb Williams, `Allen`
-> Keenan rather than Josh).

Each queued item carries the sentence with the token marked, the whole comment,
the reply chain above it, the thread title, every candidate's 2026 team /
position / ADP, and the players already identified in the same comment. The
model answers with a player, `null` for "not a player", or `unsure` to leave it
pending.

A `null` verdict is never promoted. "Not a player here" does not generalize to
"not a player anywhere": blacklisting the token would take the real mentions
with it, every capital-L Love along with the verb.

Verdicts are pinned to an occurrence — comment id plus position — so the same
surname resolves differently in different threads. A token answered the same
way three times with no contradiction is promoted to a default in
`alias_overrides.json` and stops being asked about. Promotion is a **prior, not
a collapse**: the other candidates stay in the table, and team/position context
still overturns it, so settling `Allen` as Josh does not make Braelon
unreachable. A token with any contradicting verdict — `Love`, which is both a
player and a verb — never promotes and is asked about every time.

`resolved_mentions()` is what dossiers and stats read: it applies verdicts, so
adjudicating actually changes the output rather than only its own bookkeeping.

    python adjudicate.py --pending
    python adjudicate.py --batch 20

## Running it from Claude Code without an OpenAI key (`mcp_server.py`)

`mcp_server.py` exposes the pipeline over MCP so a Claude Code session can be
the LLM: fetching, alias building and resolution stay deterministic in Python,
while the session adjudicates the ambiguous ~6% and writes the notes. Reddit
credentials are still needed — there is no unauthenticated way to read Reddit
at volume, the public `.json` endpoints 403 — but `OPENAI_API_KEY` becomes
optional.

Registered in `.mcp.json` at the repo root. Tools:

| tool | does |
|---|---|
| `fetch_thread` | one thread (permalink or id) into the corpus |
| `sweep_subreddit` | top/hot/new sweep into the corpus, resumable |
| `corpus_stats` | per-player mention counts + tier breakdown |
| `player_dossier` | every resolved sentence for one player |
| `adjudication_stats` | how much resolved itself, how much awaits judgement |
| `next_batch` | mentions needing adjudication, with full context |
| `submit_verdicts` | record verdicts; auto-promotes consistent tokens |
| `roster_context` | look up the 2026 pool by team, position or name |
| `resolve_text` | spot-check why a string did or didn't match |
| `thread_digest` | one whole thread — reply tree + player index |
| `distill_thread` | a thread plus the contract for turning it into claims |
| `submit_claims` | validate and store typed claims |
| `player_claims` | one player's claims, newest first, grouped by type, plus the note format |
| `player_threads` | every thread mentioning one player, and which are still undistilled |
| `note_queue` | players whose note is missing, undated, or older than their newest claim |
| `claims_stats` | what is distilled, what is left, where claims came from |
| `write_note` | save a finished markdown note; `publish=True` also writes `data/notes/` |
| `next_threads` | claim the next undistilled threads, best first, leased so a fleet does not collide |
| `report_non_player` | register a coach / reporter / retired player so the resolver stops mapping him onto a real one |
| `sweep_many` | sweep several subreddits in one call |

### Thread-first is the path to prefer (`thread_digest`)

`player_dossier` hands back isolated sentences, and that turns out to strip
exactly the context that decides what they mean. Three failures are structural,
not bugs to be fixed:

- **48% of mentions come from sentences naming more than one player**, and the
  sentence is copied verbatim into every one of their dossiers. One draft recap
  lands in fourteen. It says nothing about any of them.
- **The same sentence can mean opposite things.** "Gibbs, Chase and CeeDee are
  safe barring an injury to Goff/Burrow/Allen" is reassurance for the first
  three and a warning about the last three. Ten dossiers, identical text, no
  record of which side the player sits on.
- **Players outside the 337-man pool get shredded.** "Pop Douglas" is not
  draftable, so he became Isiah Pacheco (via the curated `Pop`) plus Caleb
  Douglas (via the surname). Same shape as "Calvin Austin" landing on Austin
  Ekeler.

The average comment is 136 characters and the sentence pulled from it is 95;
76% of comments are one or two sentences. Extraction is buying a rounding error
and paying for it in meaning. Whole threads cost about 2x the sentence extracts
(101k tokens vs 53k for a 14-thread corpus) and read each comment exactly once,
rather than once per player named in it.

So `thread_digest` returns the post, the full reply tree, and the resolver's
index of who appears in the thread. The resolver stays — demoted from extractor
to retriever, which is the job it is good at (~98% on which player a name means,
audited blind over 45 mentions). The index is explicitly labelled as a
retrieval aid, because a single thread shows why it cannot be trusted as truth:

- in the Jaguars thread every `Allen` is **LeQuint** Allen, but the promoted
  `allen -> Josh Allen` default in `alias_overrides.json` beat the team context
  four times, at `context` tier — the exact override that promotion was supposed
  to leave beatable.
- **Jadarian Price is absent from the index entirely**, though the thread
  compares him to Tuten three times, because `price` is a stopword and needs a
  non-sentence-initial capital. "Price is the only one." does not qualify.

A model reading the thread gets both right without being told. That is the
argument for the whole design: the index says where to look, the thread says
what is true.

### Counting is not a model's job

"Call your shot: who will be the biggest bust" drew 821 comments, 305 of them
top-level and 186 of those naming exactly one player. That is a show of hands,
and the contract asks for one sentiment claim per player *with a count* — but
a model reading a digest that had to stop at 60k characters cannot count what
it did not see, and counting is the one thing the resolver does better than a
reader anyway. So `thread_digest` now prepends a tally of top-level comments
per player with their upvotes, whenever a thread has one. The upvotes are the
half a count hides:

    Jeremiyah Love         x14   ↑1324
    Christian McCaffrey    x18   ↑29

Eighteen people nominated McCaffrey and the room shrugged; fourteen nominated
Love and the room agreed. The tally counts a name in a nomination slot, not
agreement — "not Achane" still counts for Achane — and says so.

### Paging and pruning

A long thread is paged rather than truncated: the bust thread is five calls of
40k characters, the footer says which page you are on, and the distill
contract says to read them all before submitting. Pruning drops downvoted
comments and short leaves that name nobody ("water is wet", "who?", the
187-downvote joke chain) while keeping any comment with a substantive reply
under it. Measured over the first 15 threads it removes 10-20% of characters
depending on the length threshold; it is a convenience, not a saving, and
`prune=False` shows everything. Token cost was never the constraint — reading
labour is, and that is what the fan-out below is for.

### Refreshing notes without rewriting all of them

Injury and role facts change daily in late August, and they are exactly the
claims the backtest says carry signal. The shipped notes were written from an
August 3 sweep; by September 4 the Chase note did not know about a knee, and
the Tuten note said to "check Rodriguez's foot" when the live question was
LeQuint Allen's camp. A note that cannot say how old it is cannot be trusted
on anything time-sensitive, so the header carries `as of YYYY-MM-DD` and
`note_queue` flags every note that is missing, undated, or older than the
newest claim about its player. File mtime is not used: it is a git checkout
time, and the Chase note's mtime was two days *after* the injury it knew
nothing about.

The refresh loop is `sweep_subreddit` -> `claims_stats` (undistilled
threads) -> `distill_thread` each -> `note_queue` -> `player_claims` ->
`write_note(publish=True)` for the players it lists. Only threads and players
with something new get touched.

### Running a fleet

A 30-day sweep is ~285 threads and 6.5M characters. One session reading that in
sequence is not a plan. The pipeline is built so N agents can read it at once
without a coordinator, and the parent session only writes notes.

The primitive is `next_threads(count, worker)`. It hands back the highest-value
unclaimed threads and **leases** them for 45 minutes, so six agents calling it
simultaneously get disjoint work instead of all starting at the top of the same
list. Submitting claims for a thread releases its lease; a crashed agent's lease
simply expires. The lock is `O_EXCL` on a file in `corpus/` — one machine, short
critical section, nothing fancier is warranted.

Priority is not thread size. Ranked by: reporting over opinion, how many
draftable players are in it, recency (a September practice report supersedes an
August one), and size with size *capped*, because an 800-comment joke thread
carries less than a 100-comment beat report. The `Official: [Rate My Team]` /
`[Who Do I Draft?]` dailies sort dead last at a flat −1000: they are 6% of the
corpus by text and almost none of it is a claim. `thread_kind` even labels the
daily Trade thread "news", because the word *trade* is in the title — which is
exactly why the penalty is a floor and not a nudge.

Each worker loops:

    S.next_threads(1, worker="wA")   # claim
    S.distill_thread(id)             # read every page
    S.submit_claims(json)            # validates, stores, releases the lease
    S.report_non_player(...)         # anything mis-resolved that isn't a player

`submit_claims` rejects a malformed batch whole and names the problem, so an
agent converges without supervision, and `claims.append` dedupes so a retried
thread stores nothing twice. Have workers call the Python module directly rather
than the MCP tools: a server started before an edit still runs the old code.

The brief that works is `docs/AGENT_BRIEF.md`. Load-bearing parts: read every
page before submitting; sentiment is one claim per player with a count, never
one per comment; `conditional_on` is why whole threads are worth reading; an
empty distillation of a thin thread is a correct answer; and each worker writes
temp files under its own subdirectory, because parallel workers otherwise
overwrite each other's thread dumps mid-read.

Six workers over three threads each produced 1,361 claims across 217 players in
about fifteen minutes of wall clock. Four of the six independently asked for the
same missing field — a `basis` for a national analyst who is not a beat writer —
which is why `analyst` now exists.

### Size is a cost, not a benefit

The first fleet run made the priority function measurable. Hard claims
(`team_official` or `beat_report`) per 10k characters, over the first 27 threads:

| thread | chars | hard/10k |
|---|---|---|
| Crod getting the nod over Tuten | 16k | 3.64 |
| Chase not practicing today | 4k | 2.23 |
| Puka left practice early | 20k | 2.02 |
| Ringer Fantasy Football Show AMA | 149k | 0.07 |
| Who are you fading for no good reason | 115k | 0.00 |
| punting TE is the way to go | 100k | 0.00 |

The valuable threads are small news posts. The giant opinion threads cost the
most to read and yield almost nothing durable — and the 2025 backtest already
priced their output, sentiment, at zero. So priority rewards clearing a size
floor and then *penalises* length, and AMAs take a flat −45: they read like a
goldmine, a named analyst answering questions all day, and produced one hard
claim from 149k characters plus none at all from 130k more.

### What 27 threads said, and what 464 said

The table above was measured over the first 27 threads distilled, and it did not
survive the full pass. Across 464:

| | discussion | news |
|---|---|---|
| claims produced | **2,874** | 1,297 |
| `beat_report` + `team_official` | **226** | 163 |
| `role` + `market` | **1,714** | 700 |

Discussion threads out-produce news threads on every measure, including the
hard-sourced half the pipeline is tuned to find. Two reasons, and both were
invisible from inside the ranking:

**Beat quotes get relayed.** A coach speaks, and the sentence reaches the corpus
inside a discussion thread rather than as its own post — Hafley on Achane's
40-touch workload, McDaniel on a three-back rotation, Philadelphia's OC on
Barkley as the focal point. `thread_kind` reads titles, so a relayed quote reads
as opinion. That is also why `basis` labels look wrong so often: the relay is
real reporting wearing a commenter's clothes.

**The players who most need coverage generate no news.** An elite, healthy player
in a settled role is never the subject of a beat report — there is nothing to
report. After the news-first pass, 21 of the board's top 60 had notes resting on
no beat or team source at all: Gibbs, Bijan, Jonathan Taylor, Smith-Njigba,
Achane, Bowers, McBride. Everything known about them — Smith-Njigba at 0.33
targets per route run, McBride's 60-target lead over TE2, the fact that only six
backs cleared a 70% snap share in 2025 and the board's number-one pick is not
among them — lives in exactly the long threads the size penalty buries.

So the size penalty is right about *arguments* and wrong about *analysis*, and it
cannot tell them apart from a title. Read the discussion threads too; the brief's
"strategy is not a claim" rule is what keeps the punt-TE posts from turning into
noise, and a distiller reading a whole thread applies it better than any filter
on the title does.

### The exception: length is not the same as dilution

The size penalty is right about opinion threads and was wrong about one class of
post, in a way that hid the best material in the corpus for a month.

`Player Updates from Beat Writers & National Reporters (8/11)` is 24k characters
of per-team bullets, each naming a draftable player and the reporter who broke
the item, with source links — the author says he includes the names "for clearer
transparency". A sibling post covers 8/9. Between them they sat undistilled with
**zero claims** while far thinner threads were read, and they later produced
**130 claims across roughly 90 players, 111 of them `beat_report`** — the basis
tier the backtest says is the only one that pays.

Two things buried them, and the second is the real bug:

- Length. They are long, so the penalty applied. But they are long because they
  are *dense*: nearly every line is a named beat writer on a specific player.
  Characters measure dilution only when the extra characters are argument.
- **The index only read the first 600 characters of a post body.** Everything
  past the lede was invisible, so a post naming 75 draftable players indexed as
  nine — all of them from the comments. The ranking was not weighing these posts
  and finding them wanting; it could not see them. The lede still counts double
  as the statement of what a thread is about, and the rest of the body now counts
  once, like a comment, with its length included in the size figure.

The lesson generalises past this fix. Every signal the queue ranks on is measured
by the resolver, so a blind spot in the resolver is invisible in the ranking
rather than merely underweighted — it looks exactly like a thread that has
nothing in it. When a ranking says a thread is empty, that is a claim about the
index, not about the thread.

### An AMA has no show of hands

The nominations tally was wrong on AMAs and a worker caught it. Top-level
comments there are questions and greetings, and greetings resolve to players:
"Love the show" gave Jeremiyah Love ten nominations, "Hey Brandon" reached
Brandon Aubrey, and every "Thanks Daniel!" became Daniel Jones. Shape separates
them — 187 of 305 top-level comments name exactly one player in the biggest-bust
thread (61%), against 111 of 649 in the Ringer AMA (17%) — so the tally only
appears above 35%. The greetings themselves are fixed by registering the hosts.

### The registry is the part that learns

`non_players.json` holds people who are not draftable: coaches, beat writers,
retired players, anyone outside the 337-man pool. The pool cannot represent
someone it does not contain, so without this every such person is shredded onto
whoever shares his name. It was the largest remaining error class in the audit
above — two of three misses.

A registered full name is blocked as a span, which is what stops `Andy` reaching
a kicker: consuming `Andy Reid` whole means no shorter n-gram inside it can
match. A registered *first* name additionally stops resolving on its own unless
the pool player is corroborated elsewhere in the comment, which is what kills
"Andy loves good RBs" while leaving "Bijan" and "Josh Allen" untouched. Surnames
are deliberately **not** gated this way — they are 55% of all mentions, and
gating `Johnson` or `Brown` would cost far more than it saves.

Andy Borregales went from 31 confident mentions, every one of them Andy Reid or
Randy Moss, to zero. Seeded with 76 names found by scanning the corpus for
capitalized pairs that collide with the pool, hand-checked (edit distance alone
calls `Matt Nagy` a variant of `Matt Gay`), and verified against the pool so a
real player can never be registered. `report_non_player` refuses a name that is
in the pool, and refuses a single token, since one token would block a surname
the pool legitimately owns.

This is the only part of the resolver that learns from being read. Every agent
that notices a coach being treated as a player makes the next agent's index
better.

## Claims, not prose (`claims.py`)

Threads do not become notes directly. They become **typed claims**, and claims
become notes. Prose cannot be merged across threads, date-ordered, deduped or
tested; once a beat writer's snap-count observation and a pile of bust
nominations are the same paragraph, nothing downstream can tell them apart.

Every claim carries four things prose loses:

    type            injury | role | market | sentiment
    basis           team_official > beat_report > consensus > single_commenter
    date            so a status claim can be superseded
    conditional_on  what would make it stop being true

`conditional_on` is the field that pays for whole-thread reading. "Rodriguez is
the pass-protection back" is actively misleading without "while LeQuint Allen is
out for camp" — and the sentence extracts had both facts, in different
dossiers, with the causation severed.

`type` is the field that makes the pipeline testable. The 2025 backtest
(`../reddit-notes-study/`) found note *tone* added no draft edge over ADP and
that hyped players mildly underperformed — but it measured notes where usage
facts and sentiment were fused into one string. Splitting them makes the real
question askable: **do role and injury claims beat ADP even though sentiment
does not?** That is unanswerable while both live in the same sentence.

The two passes:

```
distill_thread(id) -> read the whole thread -> submit_claims([...])   once per thread
player_claims(name) -> merge, newest first -> write_note(name, md)    once per player
```

Ordering is what makes the second pass work. Chase hyperextended a knee on the
25th and said the same day he could have kept practising; on the 26th he did not
practise at all. Newest-first puts the setback above the reassurance, so the
note reports one story with a direction instead of two contradictory quotes.
The old pipeline had no notion of time and could not have done this.

`thread_kind()` labels each thread news or discussion. The title gets the broad
test and the body a much narrower one — injury vocabulary is everywhere in a
fantasy thread, and the biggest-bust prompt opens "*non injury related
preferably*", so only an actual attribution counts as reporting in a body.

    python -c "import mcp_server as S; print(S.claims_stats())"

## A prior, not a collapse (`_apply_default`)

Promotion turns a token answered consistently three times into a default. Added
as a flat +3 bonus it was not a prior at all — against team evidence worth +2 it
simply won, and `allen -> Josh Allen` beat LeQuint Allen four times in a thread
about the Jacksonville backfield, at `context` tier, with the JAX running back
sitting in the pool. The bonus now applies only where the default is already
tied for best on evidence: it decides between candidates the context does not
separate, and yields where another candidate has strictly better evidence. In
that thread Josh Allen went from four confident mentions to none, three
resolved to LeQuint, and the rest went to adjudication where they belong.

Nothing here calls an API — the batches are built for whatever model reads
them, which in a Claude Code session is the session itself.

## Notes

- `main.py` is the legacy first-pass scraper, superseded by
  `main_scrape_reddit_api.py`. Kept for reference.
- Ideas for next season: `TODO-2026.md`.
- Caveat from the 2025 backtest (`../reddit-notes-study/`): note *tone* added no
  draft edge over ADP, and hyped players mildly underperformed. Treat these notes
  as qualitative context (injury/situation flags), not a ranking signal.
