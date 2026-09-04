# Distiller brief

Working dir: /home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper
Python:      /home/anbernal/Projects/Fantasy-Football-Tool/.venv-reddit-scraper/bin/python
Write every temp file under a subdirectory of your own named after your worker
id. Parallel workers share a scratchpad root and will otherwise overwrite each
other's thread dumps mid-read. `python -c "import mcp_server"` only works from
the working dir above, so put an absolute path inside the Python call rather
than a shell redirect after a cd.

Ignore RuntimeWarning lines about sys.prefix. Call the module directly rather
than through the MCP tools — a server started earlier is running older code.
Do not edit any code.

An agent's shell resets its working directory between calls, and a bare `cd`
ahead of `python -c "import mcp_server"` is not enough. Write a script file:

    import sys, os
    REPO = "/home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper"
    sys.path.insert(0, REPO); os.chdir(REPO)
    import mcp_server as S

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
- `market` means draft cost, not money. An NFL contract standoff is a
  `market` claim only in the sense that it is not one: if the holdout
  threatens availability it is `injury`, and if it threatens nothing it is not
  a claim. Filing it under market makes it read as ADP to anything downstream.
- **Money is evidence, not a type.** A vet-min deal, a $24M cap hit, an
  extension, where a rookie went in the NFL draft — the room cites these to
  argue a depth-chart position, and that is what they are. File the claim as
  `role` and put the number in the prose as the reason. Four workers in one
  session each found this on their own and each guessed differently; the
  answer is `role`, because the fact being asserted is who plays, not what he
  costs to draft.
- **Availability is an `injury` claim even when nobody is hurt.** IR, PUP, the
  commissioner exempt list, a suspension, a waiver, a 53-man roster bubble.
  The type is named for the common case, not the only one, and availability is
  the thing the note writer puts first and the board does not know. Filing a
  cut candidate under `role` buries it. Say in the claim what the mechanism is
  and, if the timing is unsettled — a suspension that starts only after a plea
  — put that in `conditional_on`.
- **Say what a market number is denominated in.** Round-and-pick, auction
  dollars and dynasty pick packages all land in `market` and read alike once
  they are prose. "goes 6.05 in 12-team" and "$4 in auction" and "traded for a
  2027 2nd" are three different currencies; name the one you mean.
- An AMA host, national ranker or podcaster is basis `analyst`. He has no
  access a beat writer has, but the room weights him above one commenter. A
  credentialed outsider — a doctor reading a public injury video — is `analyst`
  too: real expertise, no access to the player.
- **A player quoted on the record about himself is `team_official`.** He is the
  team's own personnel speaking for attribution, and on a question of fact —
  how his foot feels, whether he practised — nobody outranks him. Apply the
  same caution the note brief gives coaches: best source in the thread for what
  happened, most motivated one for what happens next. "I'll be ready Week 1"
  from a player who has not practised is a quote to report and attribute, not a
  cleared status. Do not file it as `single_commenter` — the commenter is only
  the person relaying it, and that loses the source entirely.
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
- supersedes takes the thread id of an earlier claim this one overtakes — or a
  short phrase ("the practice-exit report earlier in this thread") when the
  correction sits inside the thread you are reading and there is no other id to
  point at. Both forms are valid; the tool's own contract says so. Use it on
  any later report of the same event — a practice exit, then the beat
  writer calling it a cramp the next day, is one story with a direction.
  **Later supersedes earlier only at equal or stronger basis.** A commenter
  relaying camp hearsay two days after Rapoport reported a player will miss
  time is lag, not a correction, and marking it `supersedes` tells the note
  writer to lead with the weaker source. When the newer report is genuinely
  weaker, file it as its own claim and let `conditional_on` say what it is
  waiting on. This is the same rule the note brief applies downstream; if the
  two ever read differently, the note brief is the one that is right.
  The basis test governs competing accounts of the **same** fact. An event that
  *resolves* the earlier report is not a competing account and supersedes it at
  any basis: a transaction, a roster move, an official designation, a game
  actually played. A beat writer wondering on 8/23 whether Jeanty's season is
  over is answered by him being on the 8/31 roster, and the answer wins even
  though the person reporting it ranks lower. Ask whether the later claim is
  re-asserting the same fact or reporting its outcome.
- One sentence naming six players is not six copies of one claim. Split it by
  what it actually says about each.
- Nothing worth saying about a player means no claim for him. An empty
  distillation of a thin thread is a correct answer: call
  S.release_thread("<id>", "why") instead of submit_claims. That frees the
  lease and retires the thread. Never invent a filler claim to have something
  to submit — an offensive-line trade where the index found only name
  collisions is a release, not one weak sentiment claim.
- People not in the pool get no claims, even when the index mapped them onto
  someone who is.

Report at the end: threads done, the exact "stored ..." line for each, any
non-players you registered, and anything the claim schema could not express.
Under 200 words.
