# site/ — the static site

Static SPA in the same visual family as `webapp/` (same palette,
same position colors). No build tooling, no dependencies — plain
HTML/CSS/JS over prebuilt JSON.

## Run

```bash
# from the repo root (so the draft-tool iframe can reach ../webapp/)
python3 -m http.server 8080
# -> http://localhost:8080/site/
```

## Views

- **Home** — hero + section cards + the honesty-policy strip.
- **Weekly** (`#/weekly`) — D/ST and K streaming boards, generated
  from current lines (findings 27/28 logic). Skill-position tabs go
  live in September when the weekly model has current-season form.
- **2026 Board** (`#/board`) — season projection board
  (finding 25 model) with an ADP column showing where the draft market
  disagrees with the model (green +n = market drafts him n spots later
  than we rank him), + the market's implied 2026 team environment.
- **Research** (`#/blog`) — all numbered findings rendered as posts,
  newest first, with confidence pills.
- **Draft Tool** (`#/draft`) — full-screen mode: hides the site
  chrome and iframes `../webapp/index.html`, floating ✕ to exit.

## Deploy — foss.football on Cloudflare Pages

`python3 build_deploy.py` (repo root) assembles the whole thing into
`public/`: this site at `/`, the draft tool at `/webapp/`, plus
`_headers`/`_redirects`/`robots.txt`. Two ways to ship it:

- **Git integration (recommended)** — Cloudflare dashboard → Workers &
  Pages → Create → Pages → connect this repo. Build command
  `python3 build_deploy.py`, output directory `public`. Every push to
  main redeploys; the `refresh-ranks` GitHub Action's twice-weekly data
  commits redeploy too.
- **Direct upload** — `python3 build_deploy.py && npx wrangler pages
  deploy public --project-name foss-football`.

Then add the custom domain (`foss.football` + `www`) under the project's
Custom domains tab; the `_redirects` file already folds `www` into the
apex. The Chrome extension manifest lists `https://foss.football` as a
bridge origin (with `all_frames: true` so pick sync works inside the
Draft Tool iframe) — reload the unpacked extension after pulling.

## Refresh data

```bash
python3 engine/update_ranks.py  # (repo root) pull current ESPN/Sleeper/FFC
                                # ranks into data/ranks/*.csv + ADP snapshot
python3 site/build_site.py      # rebuild this site's JSON from tracked files
```

Reads (all tracked in-repo): `engine/league-sim/data/market/
model_board_2026{,_half,_ppr}.csv` (one board per scoring format,
all three written by `analysis/player_model.py`), `implied_2026.csv`,
`games.csv` (week-1 lines), and `engine/league-sim/findings/NN-*.md`.
Re-run after a model refresh or a new finding. In-season, the weekly builder extends to skill positions
(SITE_PLAN items 2–3).

Note: nflverse `spread_line` is the HOME margin (positive = home
favored) — opposite sign convention from The Odds API handicap. This
has bitten twice; see `build_weekly()`.
