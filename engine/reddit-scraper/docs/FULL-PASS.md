# A full pass: every player, from a cleared chat

This is the whole pipeline as a runbook. It assumes nothing about the
conversation that came before it, and every step is resumable — re-running any
of them skips what is already done.

    cd /home/anbernal/Projects/Fantasy-Football-Tool/engine/reddit-scraper
    PY=../../.venv-reddit-scraper/bin/python

`$PY -c "import mcp_server as S; ..."` is how everything below is called.
RuntimeWarning lines about sys.prefix are noise. Call the module directly
rather than the MCP tools: a server started earlier may be running older code.

Needs Reddit API credentials in `.env` (free, see README). No OpenAI key — the
agents reading the threads are the model.

---

## 0. Refresh the inputs (minutes)

    $PY refresh_pool.py --dry-run     # then without --dry-run to apply
    python3 ../update_ranks.py        # ESPN/Sleeper/FFC market ranks, no auth
    $PY ../fetch_juicebox.py          # per-platform ranks, no auth

`refresh_pool.py` corrects the pool's teams against Sleeper's live roster. The
pool itself comes from a FantasyPros overall-ADP export, which is a **manual
download** and the one thing here no script can fetch — without a fresh one the
board's own `Rank` column keeps whatever it had. Sleeper cannot supply it: it
has no ADP and no notion of who is draftable.

If you changed the pool, delete `corpus/index_cache.json`.

## 1. Sweep (about 15 minutes)

    S.sweep_many("fantasyfootball,DynastyFF,fantasyfootballadvice,Fantasy_Football",
                 top=120, hot=120, new=250, days=30, min_comments=8)

    S.sweep_many("Jaguars,GreenBayPackers,raiders,eagles,bengals,buccaneers,Colts,"
                 "CHIBears,LosAngelesRams,Seahawks,detroitlions,Texans,NYGiants,"
                 "Patriots,AZCardinals,miamidolphins,ravens,KansasCityChiefs,"
                 "buffalobills,steelers",
                 top=40, hot=40, new=120, days=25, min_comments=5,
                 require_relevance=True)

Team subreddits carry the beat reporting first and are otherwise game threads
and memes, so `require_relevance` is on for them: it keeps only posts whose
title names a draftable player or reads like a report. It skips roughly 120
posts per subreddit. Leave it off for r/fantasyfootball.

Resumable — already-cached posts are skipped, so re-running costs only the
listing calls.

## 2. Warm the index (about 100 seconds, once)

    S._mention_index()

Resolves every new post and caches per-post mention counts and sizes. Do this
once up front; otherwise the first worker to call `next_threads` pays it while
the rest queue behind it.

## 3. Distil — fan out (the long part)

Give each agent `docs/AGENT_BRIEF.md` and a worker name. They self-assign:
`next_threads` leases threads so N agents get disjoint work with no
coordinator, and a lease expires on its own if an agent dies.

Six at a time is comfortable. Each does 5 threads and reports back. Repeat
until `S.claims_stats()` shows the queue drained of anything worth reading.

    S.thread_shortlist(30)   # what the queue thinks is valuable, and why

Ranking favours small beat reports over big opinion threads, on measured
grounds: over the first 27 threads distilled, "Crod getting the nod over Tuten"
produced 3.64 hard claims per 10k characters and the Ringer AMA produced 0.07.
Read `thread_shortlist` before spending agents if you want to sanity-check it.

## 4. Write notes — fan out again

    S.note_queue(40)                      # players with claims
    S.note_queue(40, include_silent=True)  # the whole board, silent ones too

Give each agent `docs/NOTE_BRIEF.md` **and an explicit list of player names**.
Unlike distilling, note writing has no lease: two writers handed the same
queue will pick the same players off the top and the second silently overwrites
the first. Read `note_queue` yourself, slice it into disjoint blocks of six to
eight names, and give each writer its own block. That is the dispatcher's job,
not the writer's.

They read `player_claims`, then call `write_note(..., publish=True)`, which
writes `data/notes/<Player>.md` — the file the site bundles.

`note_queue` prints its own status legend and sort order. Only `current` can be
skipped; `unverified` means a note exists but nothing records what it was
written from, which is not the same as done.

Eight notes written this way on 2026-09-04 ran 1,800-2,900 characters. Two
writers reviewing the brief afterwards both caught the same two faults in it,
which is why it now names a length target and states which of "later
supersedes earlier" and "weight by basis" wins when they disagree. Ask your
writers for that kind of feedback and fold it back in — the brief is the part
of this pipeline that improves fastest.

## 5. Ship

    cd ../.. && python3 build_deploy.py
    git add -A && git commit

`build_deploy.py` rebundles the webapp and site data. The corpus itself is
gitignored on purpose — Reddit's API terms don't allow republishing scraped
comments and this repo is public. Only the generated notes ship.

---

## What to keep an eye on

- **Claims are typed for a reason.** `injury` and `role` with a
  `team_official` or `beat_report` basis are the ones the 2025 backtest found
  worth having. `sentiment` tested at no edge over ADP. A pass that produces
  mostly sentiment has read the wrong threads.
- **The registry learns.** Agents call `report_non_player` when they see a
  coach or reporter treated as a player. It is the only part of the resolver
  that improves from being read, and it started this season at zero.
- **An empty thread is a correct answer.** `release_thread` exists so a worker
  who reads an offensive-line trade and finds nothing can say so. Without it
  the only way to free a lease was to invent a claim.
- **The board does not know about injuries.** Fifteen players have hard-sourced
  claims saying they are unavailable, and seven sit inside the board's top 150.
  Notes are currently the only place that shows up.
