# Distiller brief

Working dir: /home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper
Python:      /home/anbernal/Projects/Fantasy-Football-Tool/.venv-reddit-scraper/bin/python
Write every temp file under a subdirectory of your own named after your worker
id. Parallel workers share a scratchpad root and will otherwise overwrite each
other's thread dumps mid-read. `python -c "import mcp_server"` only works from
the working dir above, so put an absolute path inside the Python call rather
than a shell redirect after a cd.

Ignore RuntimeWarning lines about sys.prefix. Call the module directly with
`python -c "import mcp_server as S; ..."` — do NOT use the MCP tools, a server
started earlier is running older code. Do not edit any code.

Loop, until you have done the number of threads you were told:

1. Claim work:
   S.next_threads(1, worker="<your name>")
2. Read it whole:
   S.distill_thread("<id>")
   If the footer says "page 1 of N" with N>1, read every page:
   S.distill_thread("<id>", page=k)
3. Write claims as a JSON array to a file, then:
   S.submit_claims(open("<file>").read())
   It rejects a bad batch whole and names the problem. Fix and resubmit until
   it says "stored". Submitting releases the lease.
4. Anyone you saw treated as a player who is not one (coach, beat writer,
   retired player, someone outside the pool):
   S.report_non_player("Full Name", "coach|reporter|retired|not in pool")
5. Go back to 1.

## What a good claim is

Fields: player (exact pool name from the index), type (injury|role|market|
sentiment), claim (<400 chars, your words), basis (team_official|beat_report|
consensus|single_commenter), thread (the id), optional comment (id) and
conditional_on.

- Record what the thread SAYS, not what you believe. A wrong consensus is
  still a fact about the market.
- An AMA host, national ranker or podcaster is basis `analyst`. He has no
  access a beat writer has, but the room weights him above one commenter.
- Strategy is not a claim. "Punt TE", "TE1 to TE12 is four points a week",
  "RBs in the first three rounds" are about the draft, not a player. Forcing
  them into sentiment for whoever got named loses the argument and pollutes
  the player. Skip them.
- A claim is about ONE player. If a thread says two players cannibalize each
  other that is two claims, with the other name in conditional_on — each
  player's note has to stand alone.
- Injury and role facts with a beat or team basis are the valuable ones.
  Sentiment is worth least — one claim per player with a count, never one per
  comment. The TOP-LEVEL NOMINATIONS block gives you counts and upvotes; cite
  them rather than counting by hand.
- conditional_on is the field whole-thread reading buys: "Rodriguez is the
  pass-protection back" is misleading without "while LeQuint Allen is out".
- One sentence naming six players is not six copies of one claim. Split it by
  what it actually says about each.
- Nothing worth saying about a player means no claim for him. An empty
  distillation of a thin thread is a correct answer.
- People not in the pool get no claims, even when the index mapped them onto
  someone who is.

Report at the end: threads done, the exact "stored ..." line for each, any
non-players you registered, and anything the claim schema could not express.
Under 200 words.
