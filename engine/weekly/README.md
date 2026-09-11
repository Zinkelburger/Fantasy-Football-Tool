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
Interpreter: `.venv-league-sim/bin/python` (nflreadpy, polars, numpy, mcp).

## What gets computed

| module | writes | what |
|---|---|---|
| `lines.py` | `data/weekly/lines_<season>.csv` | Vegas spread/total per team-week; ESPN's DraftKings line overlays the nflverse lookahead for the current week. D/ST + K ranks per findings 27/28. |
| `ep_model.py` | `model/ep_coefficients.json` | Opportunity score model: per-position OLS from play-by-play usage to fantasy points (finding 39). |
| `opportunity.py` | `data/weekly/opportunity_<season>*.csv` | Per player-week expected points, actual points, leak-free EWMA seeded from last season. |
| `injuries.py` | `data/weekly/injuries_<season>.csv`, `depth_<season>.csv` | NFL official injury report; latest depth chart. |
| `fantasypros.py` | `data/weekly/ecr_<season>_wkNN.csv` | Expert consensus ranks, only with `FANTASYPROS_API_KEY`. |
| `build_week.py` | `data/weekly/latest.json`, `week_<season>_wkNN.json` | The bundle `site/build_site.py` turns into the weekly page. |
| `advisor.py` | – | Pure functions: projection blend, exact lineup optimiser, positional needs, drop candidates, add/drop proposals. |
| `espn_league.py` | – | ESPN read (settings, rosters, free agents, matchup, projections) and write (lineup, add/drop, waiver claim). |

`.github/workflows/weekly.yml` runs `build_week.py` Tuesday 10:00 UTC
and Saturday 12:00 UTC and commits `data/weekly/`; Cloudflare Pages
redeploys foss.football from the push.

## Credentials

Copy `.env.example` to `.env`. The league is private, so
`ESPN_S2` + `ESPN_SWID` are needed for any roster tool; without them
only the public tools work. `ESPN_TEAM_ID` is optional (found from
your SWID). `FANTASYPROS_API_KEY` is optional.

## The MCP tools (`ff-weekly`)

Public, from `data/weekly/`: `weekly_checklist`, `week_status`,
`refresh_week`, `vegas_lines`, `opportunity_scores`, `player_lookup`,
`injury_report`, `dst_rankings`, `kicker_rankings`,
`fantasypros_rankings`.

Your league (ESPN read): `league_settings`, `my_roster`,
`lineup_recommendation`, `free_agents`, `waiver_recommendations`,
`propose_transaction`.

ESPN write, gated: `execute_transaction(token, confirmed=True)` and
`apply_lineup(token, confirmed=True)`. The token comes from the
preview tool; `confirmed` is the agent's promise that you said yes.
Nothing is sent without both.

Reddit (`ff-reddit` server): `search_reddit`, `player_news`,
`weekly_threads`, then `fetch_thread` + `thread_digest` for a full
read of a megathread.

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
