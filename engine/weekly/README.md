# engine/weekly — the in-season engine

Deterministic weekly data plus MCP tools for start/sit, waivers and
ESPN roster moves. Nothing here decides anything; it puts the numbers
in front of the agent (a Claude Code session with the `ff-weekly` and
`ff-reddit` servers) and the agent puts the question to you.

```
python build_week.py            # fetch + compute the current week -> data/weekly/
python ep_model.py fit          # refit the expected-points model (once a season)
python mcp_server.py            # the MCP server (Claude Code starts it from .mcp.json)
python -m unittest test_weekly  # no venv needed
```
Interpreter: `.venv-league-sim/bin/python` or `engine/league-sim/.venv/bin/python`

From the repo root, run the full regression suite with the weekly environment:

```sh
PATH="$PWD/.venv-league-sim/bin:$PATH" npm test
```

This includes offline news/rankings failure cases and MCP stdio integration
tests, plus the browser end-to-end suite. Live feeds can have coverage gaps;
check their source manifests and warnings before using an empty result.
(nflreadpy, polars, numpy, mcp); `engine/mcp_launch.sh weekly` picks whichever exists.

## What gets computed

| module | writes | what |
|---|---|---|
| `lines.py` | `data/weekly/lines_<season>.csv` | Vegas spread/total per team-week; ESPN's DraftKings line overlays the nflverse lookahead for the current week. D/ST + K ranks per findings 27/28. |
| `ep_model.py` | `model/ep_coefficients.json` | Opportunity score model: per-position OLS from play-by-play usage to fantasy points (finding 39). |
| `opportunity.py` | `data/weekly/opportunity_<season>*.csv` | Per player-week expected points, actual points, leak-free EWMA seeded from last season. |
| `injuries.py` | `data/weekly/injuries_<season>.csv`, `depth_<season>.csv` | NFL official injury report; latest depth chart. |
| `team_context.py` | `data/weekly/team_context_<season>.csv` | Per team-week EPA, success rate, PROE, CPOE, explosive/deep rates, sacks, plays — each with a percentile against 2021-2025 team-games and a rank within the week. Computed locally from play-by-play. `fit` rebuilds the committed baseline. |
| `club_reports.py` | `data/weekly/club_injuries_<season>_wkNN.csv` | The same official report scraped live from all 32 club sites, with each practice day in its own column; also club transactions and depth charts. Mid-week updates without a rebuild. |
| `bluesky.py` | – | Curated news-wire accounts off the public AT Protocol app view (no key). `feed --match <names>` for the last N hours; `check` for which accounts are still alive. |
| `fantasypros.py` | `data/weekly/ecr_<season>_wkNN.csv` | Expert consensus ranks from the paid API, only with `FANTASYPROS_API_KEY`. |
| `fftiers.py` | the same `ecr_*.csv` | Keyless fallback: Boris Chen's public bucket, the same FantasyPros consensus **plus tiers**. Gitignored — third-party data, regenerated on demand. |
| `build_week.py` | `data/weekly/latest.json`, `week_<season>_wkNN.json` | The bundle `site/build_site.py` turns into the weekly page. |
| `advisor.py` | – | Pure functions: projection blend, exact lineup optimiser, positional needs, drop candidates, add/drop proposals. |
| `espn_league.py` | – | ESPN read (settings, rosters, free agents, matchup, projections) and write (lineup, add/drop, waiver claim). |

`.github/workflows/weekly.yml` runs `build_week.py` Tuesday 10:00 UTC
and Saturday 12:00 UTC and commits `data/weekly/`; Cloudflare Pages
redeploys foss.football from the push.

## Credentials

Copy `.env.example` to `engine/weekly/.env` (or put the same keys in
`engine/league-sim/.env`; both are read, both gitignored, so redo this on
each machine). The league is private, so
`ESPN_S2` + `ESPN_SWID` are needed for any roster tool; without them
only the public tools work. `ESPN_TEAM_ID` is optional (found from
your SWID). `FANTASYPROS_API_KEY` is optional: without it the consensus
ranks come from `fftiers.py` instead, which needs no credential. The key
buys start/sit grades and full-depth coverage; the keyless feed buys
tiers and stops at the startable players (QB 26, RB 40, WR 60, TE 24,
K/DST 20, FLX 20-95), so most of the waiver tail has no rank either way.

## The MCP tools (`ff-weekly`)

Public, from `data/weekly/`: `weekly_checklist`, `week_status`,
`refresh_week`, `vegas_lines`, `opportunity_scores`, `player_lookup`,
`injury_report`, `dst_rankings`, `kicker_rankings`,
`fantasypros_rankings`, `team_context`.

Your league (ESPN read): `league_settings`, `my_roster`,
`lineup_recommendation`, `free_agents`, `waiver_recommendations`,
`propose_transaction`.

ESPN write, gated: `execute_transaction(token, confirmed=True)` and
`apply_lineup(token, confirmed=True)`. The token comes from the
preview tool; `confirmed` is the agent's promise that you said yes.
Nothing is sent without both.

Weekly research follows [RESEARCH.md](RESEARCH.md), also returned by
`weekly_checklist()`: establish roster decisions, batch up to six players in
`research_brief`, verify original reports, and optionally read at most two
selected threads with `read_research_thread`. Discovery is cached and fetches
no comments. One targeted `search_reddit` or `latest_threads` call can fill a
specific gap. The tool output reports freshness, limits and missing coverage.

The existing `game_threads`, `game_thread_report` and `live_mentions` tools
remain for explicitly requested live-game analysis. Draft corpus sweeps are a
separate workflow. The GitHub workflow above builds weekly data; it does not
run this personalized research or deliver a report by itself.

## Projection recipe (advisor.py)

```
ep_adj = ewma_ep × clip(sqrt(team_implied / 22.5), 0.8, 1.2)
proj   = mean(espn_proj, ep_adj)        K / D-ST: espn_proj
proj  ×= injury multiplier (QUESTIONABLE .8, DOUBTFUL .15, OUT/IR 0)
proj   = 0 on bye
value  = mean(espn_proj, ewma_ep)       no matchup/injury: for waivers
```
The lineup optimiser is exact over the roster's eligible slots, keeps
locked players where they are, and lists the moves as one ESPN ROSTER
transaction.
