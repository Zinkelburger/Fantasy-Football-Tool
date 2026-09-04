# Note-writer brief

Working dir: /home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper
Python:      /home/anbernal/Projects/Fantasy-Football-Tool/.venv-reddit-scraper/bin/python
Ignore RuntimeWarning lines about sys.prefix. Call the module directly with
`python -c "import mcp_server as S; ..."` — do NOT use the MCP tools, a server
started earlier may be running older code. Do not edit any code.

You turn stored claims into the markdown note the draft tool shows. One player
at a time.

## Loop

1. `S.note_queue(40)` — take players from the top. Skip any already `current`.
2. `S.player_claims("<exact name>")` — read all of it. The output begins with
   a ready-made header line; paste it verbatim as the note's first line.
3. Write the note (format below) to a file, then:
   `S.write_note("<name>", open("<file>").read(), publish=True)`
   `publish=True` writes `data/notes/<Player>.md`, which is what the site
   bundles. Without it the note only lands in a staging directory.
4. Next player.

Write temp files under a subdirectory named for yourself. Parallel writers
share a scratchpad and will otherwise overwrite each other.

## Format

    **Name** (TEAM, POS, bye N) — board rank R · as of YYYY-MM-DD
    <- the header line player_claims printed, verbatim

    **Room sentiment:** one line of substance. No superlatives, no "the room is
    buzzing". If the honest summary is "thin and split", write that.

    - Injury and role first, because those are the only things the 2025
      backtest found worth having. Say who says it: "per beat report",
      "the GM said", "one commenter". Date anything that changed.
    - Carry `only while:` conditions into the prose. "Rodriguez is the
      pass-protection back" is misleading without "while LeQuint Allen is out".
    - When a later claim supersedes an earlier one, report ONE story with a
      direction. Not two contradictory quotes side by side.
    - Market and sentiment last, and briefly.
    - Quote the thread only where the wording is the evidence.
    - Never invent a stat, a projection or a range. If the claims don't say it,
      it doesn't go in.

    **Draft take:** one sentence. The site previews a note by its LAST line, so
    this is what people read on the board. Make it decide something.

## Rules that matter

- **Weight by basis.** team_official > beat_report > analyst > consensus >
  single_commenter. A GM quote outranks fifty upvotes.
- **Sentiment is the weakest thing you have.** The 2025 backtest found note
  tone added no draft edge over ADP, and that hyped players mildly
  underperformed. Its one sharp edge was negative: notes that pan a player were
  the strongest signal in the study. So report a fade case plainly and do not
  inflate a bull case.
- **A player nobody discussed gets an honest short note**, not a padded one:

      **Room sentiment:** no discussion found in the corpus.

      - Nobody is talking about this player. That is itself the signal: no
        hype, no reported role change, no injury chatter.

      **Draft take:** late-round dart or waiver name; nothing in the community
      data argues for reaching.

- **Availability beats everything.** If the claims say a player is on IR, PUP,
  the commissioner exempt list, or was waived, that belongs in the first bullet
  and in the draft take. The board's rank does not know it.
- Do not mention thread ids or claim plumbing in the note. It is read by
  someone mid-draft.

Report at the end: how many notes written, any player whose claims contradicted
themselves in a way you could not resolve, and anything the format could not
carry.
