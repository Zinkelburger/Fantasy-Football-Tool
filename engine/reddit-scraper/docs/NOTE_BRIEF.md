# Note-writer brief

Working dir: /home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper
Python:      /home/anbernal/Projects/Fantasy-Football-Tool/.venv-reddit-scraper/bin/python
Ignore RuntimeWarning lines about sys.prefix. Call the module directly rather
than through the MCP tools — a server started earlier may be running older code.
Do not edit any code.

An agent's shell resets its working directory between calls, and a bare `cd`
ahead of `python -c "import mcp_server"` is not enough. Write a script file:

    import sys, os
    REPO = "/home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper"
    sys.path.insert(0, REPO); os.chdir(REPO)
    import mcp_server as S

Do every player in ONE process — the import is slow and nothing caches across
processes, so a call per player is far more expensive than a single batch.

You turn stored claims into the markdown note the draft tool shows, one player
at a time. `write_note` REPLACES any existing note for that player; there is no
merge.

## Loop

1. Work the list of players you were given. If you were given none:
   `S.note_queue(60, include_silent=True)` and take from the top.
   **Two writers must never share a player** — there is no lock on note
   writing, so whoever dispatches you is responsible for handing out disjoint
   names. If you picked your own from the queue, say which ones in your report.
2. `S.player_claims("<exact name>")` — read all of it. Its first block is a
   ready-made header line; paste it verbatim. The date in it is generated at
   call time, so it is today's.
3. Write the note to a file under a subdirectory named for yourself, inside
   whatever scratchpad directory you were given, then:
   `S.write_note("<name>", open("<file>").read(), publish=True)`
   `publish=True` writes the REPO ROOT's `data/notes/<Player>.md` — that is
   `/home/anbernal/Projects/Fantasy-Football-Tool/data/notes/`, NOT a `data/`
   under the working dir, which does not exist. Three writers lost time looking
   in the wrong place. Without `publish=True` the note only lands in staging
   (`corpus/dossiers/`, which IS under the working dir) and nobody sees it.

Statuses in `note_queue`: rewrite everything except `current`. `unverified`
means a note exists but nothing records what it was written from — treat it as
needing a rewrite, not as done.

## Format

    **Name** (TEAM, POS, bye N) — board rank R · as of YYYY-MM-DD
    <- the header line player_claims printed, verbatim

    **Room sentiment:** one line of substance. No superlatives, no "the room is
    buzzing". If the honest summary is "thin and split", write that.

    - Injury and role first. Those are the only things the 2025 backtest found
      worth having. Say who says it: "per beat report", "the GM said", "one
      commenter". Date anything that changed.
    - Carry `only while:` conditions into the prose. "Rodriguez is the
      pass-protection back" is misleading without "while LeQuint Allen is out".
    - Market and sentiment last, and briefly. Omit any block the player has no
      claims for — plenty of players have no market or no sentiment, and that
      is not something to go hunting for.
    - Quote a thread only where the wording is the evidence.
    - Never invent a stat, projection or range. If the claims don't say it, it
      doesn't go in.

    **Draft take:** one sentence. The site previews a note by its LAST line, so
    this is what people read on the board. Make it decide something.

**Length is set by the claim count, not by a target.** Read how much the player
actually has before you decide how long his note should be. Most of the queue is
thin; the length band below describes what a well-covered player earns, and it is
never a quota.

**A one- or two-claim player gets a two-line note, and that is correct.** This
is the most common case in the queue, not an edge case: report the claim, say
who said it, stop. Six hundred characters is a finished note when six hundred
characters is what is known. The length target describes what a well-covered
player earns, never a quota to reach — and the only way to pad a thin note is to
invent, which is the one thing you must not do. A writer who hits 1,200
characters on a single single-commenter claim has written fiction.

**A well-covered player — five claims or more — runs 1,200-2,500 characters**,
four to six bullets. Most players never reach the bottom of that range.

**2,500 is a soft ceiling, and a 25-plus-claim player may pass it.** Three
writers in one session each trimmed twice and still landed at 2,600-2,800 on
players like Tuten and Loveland, where a team_official quote, a beat practice
report, several named analysts disagreeing and a real market split are all
load-bearing. Going further would have meant deleting sourced facts, which is
worse than a long note. Never pad to reach the band; never cut a sourced fact to
fit under it. If you are over 2,800, you are probably keeping sentiment you
could drop — cut there first, since it is the weakest thing you have.

Longer is not better — this is read mid-draft.

## Judgement rules

**Weight by basis:** `team_official > beat_report > analyst > consensus >
single_commenter`. This ordering also prints at the bottom of every
`player_claims` call; if the two ever disagree, the tool is right and the
mismatch is a bug worth reporting.

**A coach is the best source for a fact and the worst for a forecast.**
`team_official` outranks everything on what happened — he is on IR, he took
first-team reps, he is the starter. On what *will* happen it is the most
motivated source in the thread. Canales saying "very optimistic he'll be
available" while the player still has not practised is coach-optimism, not a
cleared status, and the room said as much about LaFleur on Jacobs. Report the
quote, attribute it, and let the practice record carry the conclusion.

**Later supersedes earlier only at equal or stronger basis.** A commenter
repeating a hamstring two days after the beat writer reported full practice is
lag, not news. When a genuine reversal happens at equal weight, report one
story with a direction rather than two contradictory quotes.

**Availability beats everything.** IR, PUP, the commissioner exempt list, a
waiver — first bullet and in the draft take. The board's rank does not know it.

**Board rank and ADP are not two opinions.** `player_claims` prints an ADP above
the header and a board rank inside it; they are different scales over the same
input, not a disagreement, so never report the gap between them as news. The
comparison that matters is the header's board rank against what the *market
claims* say the room actually pays.

**Say so when the board and the room disagree on price.** The board rank in
your header can be weeks stale. If the market claims consistently put a player
somewhere else — Brooks at board rank 127 while the room drafts him round 7-8,
Lloyd at 189 while the room takes him in the 6th — that gap is one of the most
decision-relevant things on the page. Name it in the market bullet.

**Sentiment is the weakest thing you have.** The backtest found note tone added
no edge over ADP and that hyped players mildly underperformed. Its one sharp
signal was negative: notes that panned a player were the study's best
predictor. So report a fade case plainly and never inflate a bull case.

**A player nobody discussed gets an honest short note.** These only appear in
`note_queue` with `include_silent=True`:

    **Room sentiment:** no discussion found in the corpus.

    - Nobody is talking about this player. That is itself the signal: no hype,
      no reported role change, no injury chatter.

    **Draft take:** late-round dart or waiver name; nothing in the community
    data argues for reaching.

**Names are evidence, ids are plumbing.** Keep the people: Schefter,
Gutekunst, the beat writer, the coach. Drop thread ids, comment ids, claim
counts and basis labels. An upvote count stays only where the number is the
evidence that a view is settled. A national analyst nobody outside an AMA would
recognise is better as "one analyst" than as a surname.

**Keep a recurring analyst's surname; flatten the one-off AMA guest.** The
flattening rule exists so a reader is not asked to weigh a name they have never
seen — but several analysts recur across this corpus as distinct, traceable
voices, and erasing them costs real information. Two tests, either one enough to
keep the name: he shows up on more than one player, or he is in conflict with
another analyst on this one. "one analyst says RB25, another says RB40" tells
the reader less than the same sentence with the names in it, and reads worse
besides. Writers reported this twice; believe them over the impulse to genericise.

## Report back

How many notes written and for whom, any player whose claims contradicted
themselves in a way you could not resolve, and anything the brief or the tools
got wrong. The brief is revised from what writers report, so be blunt.
