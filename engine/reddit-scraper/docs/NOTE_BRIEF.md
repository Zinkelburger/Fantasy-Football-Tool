# Note-writer brief

Working dir: /home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper
Python:      /home/anbernal/Projects/Fantasy-Football-Tool/.venv-reddit-scraper/bin/python
Ignore RuntimeWarning lines about sys.prefix. Call the module directly with
`python -c "import mcp_server as S; ..."` — do NOT use the MCP tools, a server
started earlier may be running older code. Do not edit any code.

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
   `publish=True` writes `data/notes/<Player>.md`, the file the site bundles.
   Without it the note only lands in staging and nobody sees it.

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

**Length: aim for 1,200-2,500 characters**, four to six bullets. A 40-claim
player earns the top of that range; most do not. Longer is not better — this is
read mid-draft.

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

## Report back

How many notes written and for whom, any player whose claims contradicted
themselves in a way you could not resolve, and anything the brief or the tools
got wrong. The brief is revised from what writers report, so be blunt.
