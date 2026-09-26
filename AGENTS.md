# Fantasy Football Tool

- Preserve unrelated working-tree changes. Never print or publish ESPN cookies
  or API keys. Use `.venv-league-sim/bin/python` for weekly Python commands.
- For questions about the team, injuries, matchups, waivers or lineups, read
  `engine/weekly/RESEARCH.md` (also `ff-weekly.weekly_checklist()`). Follow only
  the relevant task path. `docs/TEAM-QUESTIONS.md` (`research_sources()`) maps
  questions to tools and explains local caches/refresh. Live data establish current
  facts; old chats and memory are context, not current roster/status evidence.
- Verify season, decision week, scoring and actual league availability. Pass
  the decision week explicitly; Monday pickup planning usually means next week.
- Recommendations do not authorize ESPN writes. Use the existing exact
  proposal/token and confirmation workflow when the user requests a move.
- Current injury status comes from official club reports, not old ESPN tags.
  `docs/NEWS-SOURCES.md` covers practice days, source timing, Bluesky and rankings.
  There is no usable chance-to-play model; `research/injury_predictor/` is abandoned.
- Keep numerical projections separate from narrative judgment. Do not turn a
  point gap into a win probability or an opportunity gap into points a player is due.
- Preserve kickoff flexibility in every final lineup, including after a manual
  starter change: `docs/LINEUP-SLOTTING.md`. Surface timing-only moves.
- Reddit is reachable only through `ff-reddit` MCP, including pasted permalinks.
  Never use web/curl/wget, mirrors or `.json` endpoints to bypass it.
- Weather uses `ff-weather.weather(place)` / `game_weather(week)` and the saved
  stadium mapping; it is context only, not a ranking adjustment.
- Defense recommendations follow finding 27: lowest opponent implied total,
  never ESPN fantasy projections for ranking or ties. See `docs/DEFENSE-PUBLISHING.md`.
- For defense publication/site updates, read `.cursor/rules/defense-publication.mdc`
  and `docs/DEFENSE-PUBLISHING.md`. For expected-points publication, read
  `docs/EXPECTED-POINTS-PUBLISHING.md`. Public destination: andrewbernal.com in
  `../Andrew-Bernal-Website`; this repo owns the engine. Use saved market inputs,
  preserve prior edition bytes/routes, and publish new dated editions.
- Grade the full pregame list; a good outcome alone does not validate a model.
