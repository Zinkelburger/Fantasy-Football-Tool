# 26 — Team ratings, matchups, weather, WR/CB: worth ~1 point a week at QB/RB, ~nothing season-long

**Confidence: High** (24 seasons of games for the ratings; 36,246
player-weeks LOYO for the weekly model)

## TL;DR

Do team-strength ratings help fantasy? Barely. Season-long: nothing
beats last year's simple points-per-game, and even that only reaches
a 0.42 correlation with next year — team quality churns too much to
project a season on. Week-to-week: knowing the opponent is worth
about +1 point of accuracy at QB and RB and nothing at WR; wind
hurts QBs (−1.8) and leaves RBs alone; and the WR-vs-cornerback
matchup data everyone sells is pure noise — it doesn't even agree
with itself. The Vegas line already prices nearly all of this.

## The questions (league-mate's, near-verbatim)

Can we use team Elo (nfelo-style)? How stable is it year to year? Does
it correlate with points scored? Can it flag high-powered offenses, or
power a weekly "they're facing a bad defense" model?

nfelo.com's game file isn't public, so we compute our own from
`data/market/games.csv` (results + Vegas closing lines, 2002–2025):
538-style Elo (K=20, HFA=55, MOV multiplier, ⅓ season regression) and
per-season offense/defense SRS (opponent-adjusted points for/against,
least squares). Sanity: our Elo correlates 0.847 with Vegas closing
spreads and predicts margins within 0.5 MAE of the closing line
(10.75 vs 10.23) — a simple Elo lands exactly where it should:
close behind the market, never ahead of it.

## Answers, in numbers

| question | answer |
|---|---|
| Elo stability year-over-year | corr **0.594** |
| Offense SRS stability | 0.436 |
| Defense SRS stability | **0.329** — defense persists least; "tough D matchup" ages fastest |
| Elo vs same-season points scored | 0.768 (off-SRS 0.958, by construction) |
| Last year's rating → NEXT year's PF/g | Elo 0.377, off-SRS 0.410, **naive PF/g 0.419** |
| Vegas implied team total vs actual weekly points | corr 0.393, MAE 7.4 |

The next-season row is the draft-relevant one: nothing beats last
year's raw points-per-game, and it only manages ~0.42. Team quality is
real but churns; a player model already embeds most of it through the
player's own production.

## Season-long test: environment features in the projection model

Added last-season off-SRS and Elo of the player's upcoming team to
finding 25's ridge model: pooled LOYO Spearman **0.679 → 0.679**.
Per-position deltas ±0.005, coefficient signs unstable. **Verdict: team
environment adds nothing season-long** — kept in the script as a
documented null.

## Weekly test: the "bad defense" model

Panel: 36,246 player-weeks (2018–2025, ≥2 prior appearances), target =
that week's fantasy points. First the claim itself, descriptively —
average points vs stingiest → softest quartile of defense-vs-position:

| | QB | RB | WR | TE |
|---|---|---|---|---|
| matchup spread | **+1.3** | **+1.2** | +0.3 | +0.4 |

True but small — and near-zero at WR (WR/CB matchup talk is mostly
noise at this resolution). Then the nested models, LOYO rank
correlation within (week, position):

| model | QB | RB | WR | TE |
|---|---|---|---|---|
| M1 form (EWMA pts) | .391 | .611 | .539 | .437 |
| M2 + usage-expected pts | .406 | **.629** | **.567** | **.475** |
| M3 + opponent rating | .415 | .630 | .566 | .476 |
| M4 + Vegas implied total + home | **.434** | .629 | .566 | .476 |

Three lessons:

1. **The big weekly upgrade is usage-based expected points**, not
   matchups — +.02 to +.04 rank corr everywhere (finding 17 at weekly
   scale; the sim's v5 projection blend already ships this).
2. **Opponent and Vegas only matter at QB** (+.028 over usage). QB
   coefficients: each Vegas implied point ≈ +0.19 fantasy pts, home ≈
   +0.7. This is exactly the position the league streams — matchup
   thinking pays where finding 06's streamers live, nowhere else.
3. MAE barely moves anywhere (weekly outcomes are ~7-point-MAE noise
   at the team level, worse per player). Matchup-based start/sit
   between two comparable players is a coin flip with a 1-point thumb
   on the scale.

## Weather: wind matters, cold is mild, RBs are the survivors

Roof/temp/wind are in `games.csv`. Player points relative to each
player's own trailing EWMA (controls for who plays in December):

| bucket | n | QB | RB | WR | TE |
|---|---|---|---|---|---|
| dome | 10,957 | +0.68 | +0.24 | +0.25 | +0.23 |
| mild outdoor | 18,537 | +0.04 | +0.15 | −0.06 | +0.23 |
| cold ≤32°F | 1,476 | −1.31 | +0.17 | −0.19 | −0.31 |
| windy ≥15mph | 2,764 | **−1.79** | **+0.08** | **−0.63** | −0.43 |

The "snow games make RBs unstoppable" folklore has a true core, stated
correctly: **bad weather doesn't make RBs better — it makes everyone
else worse.** Wind is the variable that bites (passing efficiency),
cold alone is mild. But adding weather features to the weekly model
(M5) moves QB from .434 to only .436 and nothing else — **Vegas
implied totals already price the forecast**; by the time you see 20mph
wind, the total has moved. Use weather for start/sit only via the
implied total, and for the RB-relative tilt in truly bad games.

## WR/CB matchups: the observable signal does not exist at this resolution

A league-mate asked about FantasyPoints' WR/CB matchup report
(alignment charts + per-CB quality; site since taken down). True CB
assignment is proprietary charting data. We built the reproducible
reduced form from play-by-play 2022–2025 (`analysis/wr_cb_proxy.py`,
40,485 WR targets): each WR's target mix by pass direction × each
defense's directional FP-allowed rating.

Verdict, in two numbers:

- **Split-half reliability of a defense's directional FP allowed:
  left 0.18, middle 0.07, right 0.12.** A defense's "stingy left
  side" in odd weeks barely exists in even weeks *of the same
  season*. Nothing built on this statistic can predict, because it
  isn't a stable property of the defense.
- **LOYO weekly WR prediction: form .451 → +team DvP .451 →
  +directional .451.** Zero, to three decimals.

**And we scored their actual product.** A full-slate snapshot of the
report (2025 week 5, via wayback; hand-transcribed, 77 active WRs,
`analysis/fp_matchup_test.py`) against that week's real points:
their **MATCHUP score correlates −0.03 with actual scoring** — nothing
— and the "bad matchup" quartile *outscored* the "good matchup"
quartile 7.5 to 6.2. Their ADVANTAGE score does correlate (0.45), but
entirely through its skill component: their own plain columns beat it
(FP/RR 0.48, **route% 0.50** — literally "how many routes does he
run" was the best predictor on the page). Adding MATCHUP to a
skill-only baseline moves R² 0.297 → 0.304 with a wrong-signed
coefficient. One week can only detect |r| > ~0.2, but three
independent tests now agree (team DvP ≈ +0.3 pts, directional
reliability ≈ 0.1, their product ≈ 0.0): detecting r = 0.1 would need
~10 more hand-transcribed weeks and still wouldn't change a start/sit
decision. Volume and form are the signal; the matchup layer is noise.

The McLaurin-vs-shadow-corner story is the best version of the idea —
a *charted* elite shadow CB erasing an outside-only WR — and it's
precisely what free data cannot see (and what our directional proxy
isn't). One memorable confirmed prediction is availability bias, not
validation. If historical FantasyPoints tables were ever exported
(wayback snapshots exist), testing *their* matchup scores against
outcomes would be the only way to credit the charted version; until
then, WR/CB matchup talk earns no place in the model.

## Injury history: finding 18 survives multivariate control

Added 2-year games-missed rate to the season model (finding 25):
coefficients QB −0.28, **RB +0.03**, WR −0.09, TE −0.19; pooled LOYO
0.679 → 0.676 (noise). "Injury-prone" still predicts ~nothing at
RB/WR once production and age are controlled; the mild QB negative is
confounded with benchings (missed games ≠ injuries in this feature).
Kept as a documented null.

## The nfelo ecosystem, backtested (2026-08-03)

github.com/greerreNFL publishes the model outputs the website doesn't:
`nfelo_games.csv` (full model history + projected lines, 2009–2025),
the continued FiveThirtyEight QB-Elo (`nfeloqb`, per-QB rolling values
1920–2026), and preseason Vegas **win-total lines** 2003–2022
(`nfl-win-total-data`). All cached in `data/market/`, backtested in
`analysis/nfelo_study.py`:

- **nfelo is the best free team rating** — MAE 10.09 vs the closing
  line's 10.11 on 3,929 games (it ties/edges Vegas, which is its whole
  claim; our simple Elo: 10.75). Use nfelo when a team rating is
  needed.
- **…and it still doesn't matter for fantasy.** Next-season PF/g corr:
  nfelo 0.376 = our Elo 0.377 < naive last-year PF 0.419. The ~0.4
  wall from this finding's earlier section is not a rating-quality
  problem — team scoring churns on things no rating carries.
- **QB-Elo is the one usable signal.** Same-season corr with QB
  fantasy PPG = 0.78 — it's a live QB quality index. Start-of-season
  value predicts that season's PPG at 0.554 (vs 0.538 for last-year
  PPG); partial beyond last-year PPG +0.12 (n=187, ~1.7σ) —
  weak-positive as a draft signal, but the per-game `qb_adj` columns
  quantify starter-vs-backup downgrades, which is streaming/opponent
  context our sim currently ignores (backlog B15).
- **Preseason win-total lines beat every stat-based environment
  signal** — corr 0.458 with that season's PF/g vs 0.421 for lag PF —
  confirming "the market's offseason-aware projection is the best team
  prior." But the dataset ends 2022 and season-long environment
  features add ~nothing to the player model regardless (above), so
  this is a reference point, not a feature.

## Live market pipeline (The Odds API, 2026-08-03)

A league-mate's free-tier key (in `.env`, never committed — public
repo) opens the current-odds endpoints: 500 credits/month, historical
endpoints locked (paid, ~$30/mo for 20k credits — that plan would fund
the props backtest we can't run free: ~2-3k credits for 3 weeks).
`analysis/market_implied.py`:

- **`season` mode (run 2026-08-03, 3 credits):** all 272 games of the
  2026 schedule already carry spreads/totals/h2h from ~9 books.
  Consensus lines → implied team totals → the market's 2026 scoring
  environment, at draft time (`data/market/implied_2026.csv`). This is
  the live replacement for the win-total prior above (whose historical
  dataset ends 2022). Top: Rams 26.6 implied ppg (matches their
  league-best 2025 off-SRS), Lions/Bills/Bengals ~26. Bottom:
  Cardinals/Jets 18.5. Use as draft-day environment reference, not a
  model feature (the season-long null above still applies).
- **`props` mode (in-season):** converts player props (pass yds/TDs,
  rush yds, rec yds, anytime TD — receptions skipped, STD scoring) to
  implied fantasy points. ~80 credits per week, fits the free tier.
  Props post during game week (empty in August). Plan: paper-trade
  props-implied vs the weekly model's M4 each week of 2026 — the
  free-tier version of the backtest, accumulated forward.

## What a lines professional has that we now have / still lack

Have now: closing spread/total (implied team totals), rest days, home,
QB starters per game, our own team ratings, weather (tested above).
Still missing: coordinator/scheme continuity (no clean free source),
preseason win totals (not in nflverse), CB coverage charting
(proprietary), injury *forecasts* (finding 21 models absence length
once injured, not who gets injured).

## Methodology

`analysis/team_ratings.py` (ratings + all correlation numbers; writes
`data/market/team_ratings.csv`), `analysis/weekly_model.py` (panel,
nested LOYO). Defense-vs-position rating: cumulative points allowed to
the position vs league average through week w−1, shrunk by n/(n+4).
nfelo's public QB-Elo file is cached at `data/market/qb_elos.csv` for
future QB-adjustment work; unused so far.

## Caveats

- Defense-vs-position uses fantasy points allowed, not play-level
  quality; better opponent metrics (EPA/pass-rate-allowed) could add
  a little, most plausibly at QB.
- The weekly panel conditions on the player actually playing (no
  injury-out rows), so it measures projection quality, not
  availability calls.
- Implied totals use closing lines — draft-day and Tuesday-waiver
  decisions see earlier, softer numbers.
