# Site plan — the stats engine behind the six products

Goal (2026-08): a fantasy site with (1) draft assist tool, (2) strategy
blogs, (3) weekly rankings with movement reasons, (4) season projection
lists, (5) week-in-review, (6) waiver wire column. This doc maps the
products onto the stats engine, what already exists in this repo, and
the build order. Scope here: the stats part.

## The four input families (answer to "is Vegas all we want?")

Vegas is one of four input families, not the model. Every product
below draws on some mix of:

| family | signals | status |
|---|---|---|
| Production & usage | weekly stats, usage-based expected points, targets/carries, snap trends (nflverse) | HAVE — engine/league-sim/data, EP blend validated (finding 26: usage is the #1 weekly signal). SURFACED 2026-08-04: `analysis/export_opportunity.py` → board "2025 expected" column + hot/cold tags, draft-tool ▾/▴ flags; its weekly CSV is the ready feed for waiver spikes + week-in-review |
| Market | game lines → implied totals (weekly env), player props (in-season player prior), ADP (draft market), preseason team environment | HAVE lines 1999-2025 + live via Odds API (.env key); props tool ready, posts Sept; historical props behind $59 one-month plan |
| Context | injuries/status, depth charts, weather, team ratings (own Elo/SRS, nfelo), QB-Elo, salary/contracts, draft capital | HAVE historical; need in-season weekly refresh |
| Narrative | reddit/blogs/podcasts scraped + LLM-summarized | PARTIAL — engine/reddit-scraper/ exists; research/reddit-notes-study verdict: tone adds NO projection edge over ADP. Use for *explanations*, not numbers |

Key architecture rule learned from the findings: **the projection
engine and the narrative engine are separate systems.** Numbers come
from the first three families (testable, LOYO-validated); scraped
narrative exists to *explain* movement and make content readable
(product 3's "reasons up/down", products 2/5) — it is not a
projection input, because we measured that it isn't one.

## Product → engine mapping

1. **Draft assist tool** — season board (engine/league-sim
   `analysis/player_model.py`, beats ADP at QB/WR/TE, +stack at RB) +
   wait-cost pick logic (`PickValue`, finding 23 slope logic) + rules
   from findings (QB by r6, TE discipline, K last). Prior art: legacy
   Go draft tool (archive/go-tool) + webapp/ static port +
   chrome-extension pick sync.
2. **Strategy blogs** — findings 01–26 are the drafts: discipline
   (03), RB-vs-WR curves (23), hindsight optima (24), PPR imports
   warning (02), waiver reality (22). Mostly editing work, not new
   research. Format-conditional (STD vs PPR) per finding 02.
3. **Weekly rankings** — weekly model (`analysis/weekly_model.py` M4:
   form + usage-EP + DvP + implied total + home; rank corr .43-.63 by
   pos) + props-implied overlay in-season (`market_implied.py props`)
   + K/DST models (gap) + narrative layer for movement reasons (gap).
4. **Season projections** — player_model board + rookie model (gap) +
   K/DST season models (gap). FantasyPros accuracy submission needs
   full-position coverage.
5. **Week in review** — pure content: actuals vs our projections +
   biggest surprises (we already compute residuals); narrative engine
   dresses it up. Cheap once 3 exists.
6. **Waiver wire column** — weekly model on FA-eligible players +
   wire-value findings (22: wire ≈ QB/K holes; 05: TE store) +
   usage-spike detection (EP jump = the buy signal, finding 17/B4).

## Gaps, prioritized

1. **K + DST models — BOTH DONE** (engine/league-sim findings 27/28).
   DST: opponent implied total = .304 within-week rank corr,
   everything else adds ≤.005. K: .186 ceiling, kicker's own history
   worth .079 — stream win prob + dome/wind + coach FG-tendency.
   Full-position weekly boards are now possible.
2. **In-season data refresh** — weekly cron: nflverse stats, injuries,
   lines, props → recompute boards. All sources update in-season;
   nothing new to build, just wiring.
3. **Rookie season model** (blocks 4): draft capital + landing spot;
   backlogged as finding-25 caveat.
4. **Narrative engine** (blocks 3's reasons, 5): engine/reddit-scraper +
   podcast/blog feeds → per-player weekly summary via LLM batch.
   Explicitly NOT a projection input.
5. **Accuracy harness**: score our weekly/season lists against
   FantasyPros ECR + actuals each week (their scraping is easy; the
   submission contest is optional gravy). This is the flywheel — it
   tells us weekly whether the engine is actually good.
6. **Props backtest** (optional, $59 one month): settles how much
   weight props deserve vs our model before the season starts.

## What "use Vegas as input" means concretely (already measured)

- Implied team total: helps QB weekly (+.03 rank corr), nothing else
  (finding 26). It's IN M4 already.
- Props (in-season): the market's own per-player projection — likely
  the strongest weekly prior for starters; paper-trade or backtest.
- Preseason environment (implied_2026.csv): draft-day context layer,
  not a model feature (tested null season-long).
- Weather: priced into totals; skip as a feature, keep for content.

## In-season app roadmap (added 2026-08-04)

Goal: a fantasy player manages their week from our UI instead of
FantasyPros/ESPN. Ordered by value ÷ build cost, mapped to what
already exists:

1. **League sync (the enabler).** Extend the chrome extension to
   scrape ESPN *league rosters* (it already scrapes ESPN draft rooms;
   same chrome.storage → bridge.js pipe into the site). Site marks
   every player available/taken/mine automatically. Fallback shipped
   today: manual click-to-mark on the weekly boards, localStorage.
   No backend needed — that's the constraint that makes this cheap.
2. **Waiver central** = weekly boards × sync: available players only,
   color-coded, ranked by our models. D/ST + K versions shipped
   today (manual marks); skill positions when the weekly model goes
   live in September. The buy signal is plumbed:
   `analysis/export_opportunity.py --year 2026` emits per-player-week
   EP + EWMA series (opportunity_weekly CSV) — the waiver list is
   "FA-eligible, sorted by ewma_ep − ewma_pts".
3. **Week in review / "post game."** Actuals vs our projections
   (residuals already computed), luck read (all-play vs actual
   record), biggest surprises. Product 5 in the list above — cheap
   once weekly boards are live. Per-player "scored X on Y expected"
   lines come straight from the same opportunity_weekly CSV.
4. **Start/sit assistant.** v1 is just the weekly boards + finding-21
   injury rules surfaced as a compare-two-players widget.
5. **Are they playing?** Finding 21's status table (Out/Doubtful = 0%,
   Questionable = 69% at 83% strength) + weekly injury-report feed.
6. **Matchup tracker / league analyzer** — later; both need live
   scoring or full-league rosters, so they ride on #1.

Not doing: radar charts, trade calculators, news-article "primers"
(narrative engine may cover this later — it's product 3's movement
reasons wearing a different hat).

## The site itself (built 2026-08-04, `site/`)

Static SPA, same design family as the draft tool (dark, same position
palette). Views: Home / Weekly (D/ST + K live now from lines; skill
tabs open in September) / 2026 Board (model + market environment) /
Research (all 28 findings rendered as posts with confidence pills) /
Draft Tool (full-screen mode — site chrome hides, iframes `webapp/`,
floating exit). Data rebuilt by `site/build_site.py` from tracked repo
outputs; serve repo root with `python3 -m http.server 8080` →
`/site/`.

## Build order (stats part)

1. K + DST weekly/season models → full-position boards.
2. Accuracy harness vs FantasyPros ECR (start logging immediately in
   September — every week of delay is lost evaluation data).
3. In-season refresh cron + props overlay.
4. Rookie model.
5. Narrative engine for movement reasons.
6. Week-in-review generator off the residuals.
