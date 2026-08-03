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
  going earlier on my platform" comparison. **This is the only source for
  those columns** — without it they are blank and all three scoring formats
  collapse to identical boards. Our family league is on ESPN, so the ESPN
  column is the one that matters.
- **Coverage:** ~197 players (top of the board only; deep bench is blank).
- **Last fetched: 2026-08-03.** Sheet self-reported update: 2026-07-31.

## 2. JuiceBoxOne — "JuiceSheets Draft Cheat Sheets"

- **Link:** https://docs.google.com/spreadsheets/d/199izMhbkOOjTsNmrK-D56dYnnViJBYFfBEtxK268h4Y/edit
- **Gives us:** projected season fantasy points (`Proj Std/Half/PPR`) plus
  ADP and a VALUE column. The **`Combined` tab** is the useful one: one row
  per player with team, bye, ESPN/Sleeper/Yahoo ranks and all three
  projections side by side.
- **Used by:** `league-sim/analysis/compare_juicebox.py` — an outside
  projection to sanity-check our own model against. Not a model input;
  it is a second opinion.
- **Coverage:** 167 players (30 QB / 57 RB / 60 WR / 20 TE).
- **Last fetched: 2026-08-03.** Sheet self-reported update: 2026-07-31.

### Refreshing both sheets

Both are public, so no auth, no API key, no manual download:

```bash
python scripts/fetch_juicebox.py --year 2026
```

It pulls every tab of both workbooks via Google's `/export?format=xlsx`
endpoint, writes them to `data/juicebox/2026/juicebox_*.csv`, and rewrites
`data/juicebox/2026/SOURCES.json` with the fetch date. Then rebuild the boards:

```bash
cd reddit-scraper
python build_player_csv.py FantasyPros_2026_Overall_ADP_Rankings.csv --juicebox ../data/juicebox/2026
python ../webapp/build_data.py
```

**Staleness policy:** these sheets are edited through the preseason
(injuries, depth charts, holdouts). Anything older than ~1 week is
suspect during August; re-fetch the morning of a draft.

## 3. FantasyPros overall ADP export

- **Link:** https://www.fantasypros.com/nfl/adp/overall.php (use the CSV
  export button; the file lands as `FantasyPros_<year>_Overall_ADP_Rankings.csv`)
- **Gives us:** the board ordering (`AVG` ADP), team, **bye week**, position,
  and a Sleeper ADP column. Manual download — not scripted.
- **Used by:** `reddit-scraper/build_player_csv.py`, which produces both
  `reddit-scraper/combined_with_depth.csv` (scraper input) and the three
  `data/ranks/*_with_depth.csv` board files.
- **Caveat:** the 2026 export carries Sleeper / RTSports / Real-Time columns
  but **no ESPN column** — that is why source 1 above is required.
- **Last downloaded: 2026-08-03** (`reddit-scraper/FantasyPros_2026_Overall_ADP_Rankings.csv`).

## 4. r/fantasyfootball corpus

- **Gives us:** the per-player draft notes in `data/notes/*.md`.
- **Refresh:** `cd reddit-scraper && python fetch_corpus.py && python match_players.py`
  (~4 minutes, needs Reddit API creds in `.env`; see `reddit-scraper/README.md`).
- **Not committed** — Reddit's API terms don't allow republishing scraped
  comments, and this repo is public. Only the generated summaries ship.
- **Last swept: 2026-08-03** — 280 posts, 22,878 comments, 60-day window.

## 5. nflverse / Odds API (league-sim only)

Historical stats, injuries, depth charts, contracts and betting lines used
by the simulation and projection work. See `league-sim/findings/METHODS.md`.
The Odds API key lives in `.env`, never in the repo.

---

## How our model and JuiceBoxOne's projections compare

Checked 2026-08-03 via `league-sim/analysis/compare_juicebox.py`, against
`league-sim/data/market/model_board_2026.csv`:

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
