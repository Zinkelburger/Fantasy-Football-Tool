# External data sources

Every outside feed the draft pipeline depends on, with links, how to
refresh it, and how stale it is allowed to get. **If you are an AI agent
picking this repo up: check the "last fetched" dates below against today
and tell the user which feeds need re-downloading before a draft.**

Data itself lives in `data/juicebox/<year>/`, whose `SOURCES.json` records the
exact fetch date and each sheet's own self-reported update date.

---

## 1. JuiceBoxOne — "Abusing Fantasy Draft Rankings"

- **Link:** https://docs.google.com/spreadsheets/d/1HTixsrRtIIpnUafVkOIhET83vCFjKXSUGiG24-5jTHY/edit
- **Gives us:** per-platform draft ranks — ESPN, Sleeper, Yahoo, CBS,
  Fleaflicker, Sleeper Superflex — each in Standard / Half PPR / PPR, plus
  a 1-10 "Landmine" risk score (new in 2026) and FantasyPros ECR.
- **Used by:** `data/ranks/{std,0.5_ppr,ppr}_with_depth.csv` → the `ESPN_Rank`
  and `Sleeper_Rank` columns, which drive the draft tool's "is this player
  going earlier on my platform" comparison. Our family league is on ESPN, so
  the ESPN column is the one that matters.
- `engine/update_ranks.py` is the routine refresh: it rebuilds the main board
  from current FFC ADP for each scoring format, then fills ESPN/Sleeper
  comparison columns from their APIs. ESPN is overall ADP order, not a
  standard-only feed or draft-room order. JuiceBox's platform ranking is a
  separate measurement; downloading its sheet does not update the main board.
- **What only this sheet has:** the per-platform splits beyond ESPN/Sleeper
  (Yahoo, CBS, Fleaflicker, Superflex), the 1-10 Landmine risk score, and
  FantasyPros ECR. The live API has none of that.
- **Coverage:** ~197 players (top of the board only; deep bench is blank).
- **Last fetched: 2026-09-04.** Sheet self-reported update: 2026-09-04.

## 2. JuiceBoxOne — "JuiceSheets Draft Cheat Sheets"

- **Link:** https://docs.google.com/spreadsheets/d/199izMhbkOOjTsNmrK-D56dYnnViJBYFfBEtxK268h4Y/edit
- **Gives us:** projected season fantasy points (`Proj Std/Half/PPR`) plus
  ADP and a VALUE column. The **`Combined` tab** is the useful one: one row
  per player with team, bye, ESPN/Sleeper/Yahoo ranks and all three
  projections side by side.
- **Used by:** `engine/league-sim/analysis/compare_juicebox.py` — an outside
  projection to sanity-check our own model against. Not a model input;
  it is a second opinion.
- **Coverage:** 167 players (30 QB / 57 RB / 60 WR / 20 TE).
- **Last fetched: 2026-09-04.** Sheet self-reported update: 2026-09-04.

### Refreshing both sheets (optional comparison data)

Both are public, so no auth, no API key, no manual download:

```bash
python engine/fetch_juicebox.py --year 2026
```

It pulls every tab of both workbooks via Google's `/export?format=xlsx`
endpoint, writes them to `data/juicebox/2026/juicebox_*.csv`, and rewrites
`data/juicebox/2026/SOURCES.json` with the fetch date. Refresh the actual draft
boards independently from the repository root:

```bash
python3 engine/update_ranks.py
python3 webapp/build_data.py
```

**Staleness policy:** these sheets are edited through the preseason
(injuries, depth charts, holdouts). Anything older than ~1 week is
suspect during August; re-fetch the morning of a draft.

## 3. Current draft boards — Fantasy Football Calculator

- **Source:** https://fantasyfootballcalculator.com/adp/standard/12-team/all
- **Refresh:** `python3 engine/update_ranks.py`, then
  `python3 webapp/build_data.py` for the local dashboard or
  `python3 build_deploy.py` to assemble the full site.
- **Main board:** recent 12-team mock ADP, fetched independently for standard,
  half-PPR and PPR. Rank is overall order; the ADP column stores average pick.
  This is a market baseline, not expert rankings or ESPN-only drafting behavior.
- **Missing players:** retained for search/roster tracking with blank Rank/ADP;
  missing comparison values are cleared rather than inherited from old data.
- **Freshness:** `data/ranks/SOURCES.json` records fetch time, sample dates,
  scoring, team count, and draft count. The dashboard displays the sample date.
  Failed, incomplete, mismatched or >7-day-old FFC samples abort before writing
  boards. The existing GitHub workflow refreshes the boards and dashboard twice
  weekly; run the command again before drafting.
- **2026-09-06 refresh:** samples through September 5. Standard sample: 1,606
  mocks, August 29–September 5. Josh Jacobs ADP 54.1; RJ Harvey ADP 121.4.
- **Historical FantasyPros export:**
  `engine/reddit-scraper/FantasyPros_2026_Overall_ADP_Rankings.csv` was downloaded
  August 3 and remains input to the scraper pool. It is no longer the current
  draft-board source. `build_player_csv.py` is for rebuilding that pool; use
  `--no-board`, or follow any full rebuild with `engine/update_ranks.py`.

## 4. r/fantasyfootball corpus

- **Gives us:** the per-player draft notes in `data/notes/*.md`.
- **Refresh:** `sweep_subreddit` from the MCP server (or `python -c "import mcp_server as S; print(S.sweep_subreddit(top=120, hot=120, new=250, days=30, min_comments=15))"` in `engine/reddit-scraper`), then distil and rewrite notes per the README there
  (~4 minutes, needs Reddit API creds in `.env`; see `engine/reddit-scraper/README.md`).
- **Not committed** — Reddit's API terms don't allow republishing scraped
  comments, and this repo is public. Only the generated summaries ship.
- **Last swept: 2026-09-04** — 1,392 posts, 116,219 comments. r/fantasyfootball
  plus DynastyFF, fantasyfootballadvice, Fantasy_Football, and 20 team subreddits
  (team subs use `require_relevance`, which skipped ~120 off-topic posts each).

## 5. nflverse / Odds API (engine/league-sim only)

Historical stats, injuries, depth charts, contracts and betting lines used
by the simulation and projection work. See `engine/league-sim/findings/METHODS.md`.
The Odds API key lives in `.env`, never in the repo.

## 6. Live feeds — Sleeper and ESPN (the in-season app)

All of these are public and need no key, which is what makes live
tracking possible on a static site with no backend. Re-checked
2026-08-05 against real leagues.

- **Sleeper** — `https://api.sleeper.app/v1`, `access-control-allow-origin: *`.
  League, rosters, users, per-week matchups with live `players_points`,
  transactions. Look a user up by username, no auth at any step. An
  unknown username returns `null` with HTTP 200, not a 404.
  - `/players/nfl` is the id→name/pos/team map: **14.6 MB raw, 2.5 MB
    gzipped, ~2.6s**. `site/sleeper.js` filters it to ~4,260 relevant
    players (0.44 MB) and keeps that in localStorage for a day, which
    is the most often Sleeper wants it fetched.
  - `/projections/nfl/regular/{season}/{week}` answers with ~9,400
    player ids, **but only about 810 of them carry a points field** —
    the rest are deep-roster bodies with nothing but an ADP stub. Don't
    quote the 9,400 as coverage; it isn't. Bye-week teams get no
    projection at all (1–2 players against ~14 for a playing team).
- **ESPN scoreboard** — `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`,
  `access-control-allow-origin: *`. Gives `displayClock`, `period` and
  game state per team — the clock that drives the remaining-points
  model (finding 35). Takes `?week=N&seasontype=2&dates=YYYY`, which
  matters: without it you get whatever week ESPN thinks is current, so
  a Tuesday visit reads the wrong clock. It also returns
  `week.teamsOnBye` outright, which beats inferring byes from absence.
- **ESPN fantasy leagues** — `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{id}`.
  - **Public leagues work from the browser with no auth at all.** ESPN
    echoes our Origin back, allows credentials, and allows
    `X-Fantasy-Filter` on preflight — so even the free-agent list
    (`view=kona_player_info`) is reachable. Rosters, settings,
    schedule, live scores and **ESPN's own weekly projections**
    (`statSourceId: 1`, `statSplitTypeId: 1`) all arrive in one call.
  - **Private leagues are not a CORS problem.** CORS passes fine. The
    blocker is that `espn_s2`/`SWID` are `.espn.com` cookies, so a
    request from our origin is third-party and the browser never
    attaches them. The browser extension holds host permission for
    espn.com, so it *can* make that request, and `site/espn.js` falls
    back to it on a 401 (see `chrome-extension/background.js`).
  - **Transactions are unreliable.** `view=mTransactions2` accepts the
    request and answers 200 with no `transactions` key at all on the
    leagues we could test. Valid `filterType` values are `WAIVER`,
    `FREEAGENT`, `ROSTER`, `TRADE_ACCEPT`, `DRAFT`; `TRADE` and
    `LINEUP` are rejected with a 400. Undocumented, so written down
    here. The Moves tab says so rather than rendering an empty list
    that reads like "no moves".
  - Useful id maps (`proTeamId`, `lineupSlotId`, `defaultPositionId`)
    live at the top of `site/espn.js`, checked against
    `site.api.espn.com/.../teams`.
- **ESPN fan / "which leagues am I in"** — `https://fan.api.espn.com/apis/v2/fans/{SWID}?useCookieAuth=true&…`.
  Keyed on the `SWID` cookie, so only the extension can call it —
  same third-party-cookie reason as private leagues above. Returns
  every league a SWID belongs to, which is what lets My league show
  your leagues instead of asking for an id.
  - **Undocumented and UNVERIFIED as of 2026-08-06** — written from
    the known response shape, not from a live call, because it needs a
    signed-in ESPN session. Leagues hang off `preferences[].metaData.entry`,
    with the league in `entry.groups[].groupId`/`groupName` and your
    team in `entry.entryId`/`entry.name`; football is `gameId: 1`.
    `fanLeagues()` in `chrome-extension/background.js` reads it loosely
    and returns nothing rather than something wrong.
  - Falls back to the `kona_v3_environment_season_ffl` cookie, which
    carries `{leagueId, seasonId, teamId}` for the last league you
    looked at and no names. Stable for years; the site fills the names
    in with one `view=mTeam` preview call.
  - Covered by the existing `https://*.espn.com/*` host permission —
    `fan.api.espn.com` matches it, so no new permission was needed.
- **Yahoo** needs OAuth and therefore a backend; not supported.

## 7. nflverse play-by-play (in-game model)

- **Link:** `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_<year>.parquet`
- **Gives us:** every play with `game_seconds_remaining`, fantasy
  attribution (passer/rusher/receiver), `spread_line`, `total_line`.
- **Used by:** `engine/league-sim/analysis/ingame_model.py` (QB/RB/WR/TE)
  and `analysis/kdst_sigma.py` (K, and the D/ST full-game sigma) →
  finding 35 → `data/market/ingame_params.json` → `site/data/ingame.json`.
- **Not committed** — ~20 MB/season, gitignored by `**/data/pbp/`.
  Refresh with `python engine/league-sim/analysis/ingame_model.py --fetch`,
  then `python engine/league-sim/analysis/kdst_sigma.py`. The ignore
  rule is unanchored deliberately: a run from the wrong directory once
  left a second 98 MB copy at a nested path that the old pinned rule
  didn't cover.
- **Last fetched: 2026-08-05** (2021–2025).
- **Staleness:** refit once the 2026 season is a few weeks old; the
  clock curve is stable year to year, the sigma table less so.

## 8. Preseason win totals (backtest history only)

- **Links:** https://github.com/greerreNFL/nfl-win-total-data (2003–2022,
  no longer updated) and https://www.sportsoddshistory.com/nfl-win/
  (2023–2025, scraped 2026-08-05).
- **Gives us:** each team's August Vegas win-total line —
  `engine/league-sim/data/market/win_totals_sos.csv` and
  `win_totals_2023_2025.csv`.
- **Used by:** `engine/league-sim/analysis/good_offense_tiebreak.py`
  (finding 30: the market's team number is real but already in ADP).
- **Staleness:** static history; nothing to refresh until the 2026
  season ends (then add the 2026 row for future backtests).

---

## How our model and JuiceBoxOne's projections compare

Checked 2026-08-03 via `engine/league-sim/analysis/compare_juicebox.py`, against
`engine/league-sim/data/market/model_board_2026.csv` (the standard-scoring
board; `_half.csv` and `_ppr.csv` sit alongside it):

| position | n | rank correlation |
|---|---|---|
| all matched | 155 | **0.911** |
| RB | 51 | 0.898 |
| WR | 56 | 0.823 |
| TE | 19 | 0.768 |
| QB | 29 | 0.656 |

Two independently-built projections agreeing at rho 0.91 is a decent sanity
check on both — **no reason to rerun or retune our model on this evidence.**
QB is the weakest agreement, which is consistent with our own finding that
QB is the position where usage-based features add least.

The disagreements are where any edge would be. We are materially higher on
Malik Nabers, Courtland Sutton, Marvin Harrison Jr., Baker Mayfield and
J.K. Dobbins; JuiceBoxOne is materially higher on A.J. Brown, Jayden
Daniels, Terry McLaurin, Jaylen Waddle and Bhayshul Tuten. Neither list is
validated against 2026 outcomes yet — that is what the accuracy harness in
`SITE_PLAN.md` (gap 5) is for.

## In-season weekly feeds (engine/weekly, from 2026-09-10)

| feed | endpoint | auth | refreshed |
|---|---|---|---|
| NFL state (season/week) | `https://api.sleeper.app/v1/state/nfl` | none | every build |
| Play-by-play, weekly player stats, schedules (with lookahead lines), injuries, depth charts, player id crosswalk | nflverse via `nflreadpy` | none | Tue + Sat (GitHub Actions) and on `refresh_week()` |
| Live lines (DraftKings) | `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard` | none; **send no browser User-Agent** (403 otherwise) | every build |
| ESPN league: rosters, free agents, projections, matchups | `lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/<y>/segments/0/leagues/<id>` | `espn_s2` + `SWID` cookies (private league) | on each tool call |
| ESPN league writes: lineup, add/drop, waiver claims | `lm-api-writes.fantasy.espn.com/.../transactions/` | cookies; gated behind a previewed token + user confirmation | only when asked |
| FantasyPros ECR (weekly) | `https://api.fantasypros.com/public/v2/json/nfl/<y>/consensus-rankings` | `FANTASYPROS_API_KEY` (optional) | every build when keyed |
| Reddit (search, megathreads) | Reddit API via PRAW | `CLIENT_ID`/`CLIENT_SECRET` in engine/reddit-scraper/.env | on each tool call |

Not used: ffverse `ep_weekly_<season>` (no 2026 file as of 2026-09-10; our
own model in finding 39 agrees with it at r = .95–.98 on 2025).
