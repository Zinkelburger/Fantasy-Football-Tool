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
| `player_claims` | one player's claims, newest first, grouped by type |
| `claims_stats` | what is distilled, what is left, where claims came from |
| `write_note` | save a finished markdown note |

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
