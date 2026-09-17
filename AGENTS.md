# Fantasy Football Tool

- Weekly roster, pickup, and lineup work follows `engine/weekly/RESEARCH.md`.
- Verify season, decision week, scoring, roster, and actual league availability.
  Monday pickup planning usually targets the next week; pass it explicitly.
- Preserve unrelated working-tree changes. Never print or publish ESPN cookies.
- Defense publication and accuracy work follows `docs/DEFENSE-PUBLISHING.md`.
  The public destination is andrewbernal.com, in the sibling
  `../Andrew-Bernal-Website` repo. This repo owns the fantasy engine.
- Expected points publication follows `docs/EXPECTED-POINTS-PUBLISHING.md`:
  a dated edition per completed week, built from the committed weekly bundle.
- Keep numerical projections separate from narrative research. A good outcome
  does not establish that the model is accurate; grade the full pregame list.
- There is no usable "chance to play" model. `research/injury_predictor/` is
  abandoned research and is not wired into the weekly engine: it recalls only
  56% of players who sat, so it cannot answer the one question it is asked.
  Do not revive it for a lineup call. Use the official Wed–Fri practice reports
  and the Friday game designation. See that directory's README.
- Mid-week practice status comes from `engine/weekly/club_reports.py` (all 32
  club sites, one column per practice day) and news from
  `engine/weekly/bluesky.py`; `docs/NEWS-SOURCES.md` lists every source, what
  it contains and when it posts. Clubs post each day's report late afternoon
  ET, so a blank Thursday column means "not posted yet", not "no change".
- Defense recommendations use our finding 27 methodology: lowest opponent
  implied total first. Do not use ESPN fantasy projections to rank or break
  ties. ESPN supplies roster availability, league scoring, and actual results.
- Recommendations do not authorize ESPN roster writes. Use the existing exact
  proposal/token and confirmation workflow when the user requests a move.

- For “update the site / make Week N defense picks,” read
  `.cursor/rules/defense-publication.mdc`. Treat it as the existing publication
  workflow: requested week, saved market snapshot, concise copy, tests and live
  deployment when requested. Do not expand into model building or broad research.
- Use saved US Odds API data (under 24 hours old), paired within bookmakers;
  missing later-week lines stay pending. Never fetch odds in builds/page visits.
- A new edition must have its own archive URL. Preserve original week routes and
  prior snapshot bytes, including during same-week revisions.
