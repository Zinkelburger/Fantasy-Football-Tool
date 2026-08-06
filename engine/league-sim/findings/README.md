# Findings

Every factoid from the league-sim project, one file per claim, each
with its data, exact methodology, and an honest confidence rating.
Shared infrastructure (data sources, scoring, simulator design,
validation) lives in [METHODS.md](METHODS.md) — read that once first.

**Confidence scale**
- **High** — large sample or simulation-verified, survives robustness
  checks, coherent mechanism.
- **Medium** — real signal in this window, but modest sample or one
  specification weakens it.
- **Low** — suggestive only; do not build a slide on it without the
  caveats attached.

**Simulator status (2026-08-01): environment v5.** On top of v4's
injury realism (real Friday reports drive start/sit, finding 21;
promotion recalibrated 0.85/0.55/0.30; knowably-done players get cut),
a waiver-realism audit fixed three measured artifacts: managers no
longer claim players who are knowably out for the year (was 25% of the
default policy's adds), a sniped hole claim now falls through to a
midweek free-agency grab instead of an empty starting slot (was ~2.6
empty hero slots/season, mostly TE/K), and no manager drops the only
active body at a starting position. Version history in
[finding 13](13-handcuffs-are-free-insurance.md). **Every "sim v3" and
"sim v4" number below is stale until the grid reruns** — directionally
plausible, not citable. Clear `results*/` before rerunning; the grid
silently reuses cached cells. "Data" findings measure reality directly
and are unaffected.

| # | Finding | Evidence | Confidence |
|---|---|---|---|
| [01](01-robust-rb-wins.md) | RB-RB-RB is the best title-rate plan: 20.3% championships, 2.4× baseline (v5 spot-check: .610/21%; edge is room-specific, see update) | sim v3 + v5 spot-check | High |
| [02](02-zero-rb-is-a-trap.md) | Zero RB and WR-heavy are PPR imports: the costliest plans tested (9.7% vs 20.3% titles); v5 update — all four MockoScience PPR strategies lose here too (−1.6 to −5.0 all-play vs robust_rb) | sim v3 + v5 spot-check | High |
| [03](03-adp-discipline-is-not-an-edge.md) | CORRECTED: discipline IS the edge (~90% of it); sharp-room test shows robust_rb's edge is room-specific, wait-cost math's survives | sim v5 | High |
| [04](04-kickers-are-noise.md) | Early-season kicker scoring predicts nothing; never chase | data | High |
| [05](05-never-pay-up-for-te.md) | Top-8 TE production is available late every year; the pure-wire punt is drying up. **Its "never spend an early pick" is partly superseded by [33](33-te-same-pick.md)** — the two agree the middle rounds are the trap, not the elite tier | data + sim v3 | High |
| [06](06-qb-timing.md) | Early QB is fairly priced; late-QB-plus-streaming measurably costs (v5 re-confirms; early QB gains real value vs sharp rooms) | data + sim v3 + v5 spot-check | Medium-High |
| [07](07-what-a-starter-is-worth.md) | Positional value curves: why rounds 1–3 are RB rounds here | data | High |
| [08](08-bad-team-wr1-edge.md) | Mid-round alpha WRs on doubted teams nearly double the hit rate | data | Medium |
| [09](09-decline-discount-trap.md) | WRs coming off a collapse year bust more at every age | data | Medium |
| [10](10-wr-age-effects.md) | Age 29–30 looks like a danger zone — partially survives scrutiny, partially overfit | data | Low-Medium |
| [11](11-methuen-jackels-audit.md) | The Jackels drafted best-in-league; the leaks are TE price and one WR archetype | data | High (it's your data) |
| [12](12-championship-variance.md) | Back-to-back runner-up finishes are variance, not process failure | data + sim v3 | High |
| [13](13-handcuffs-are-free-insurance.md) | Handcuffs are correctly-priced insurance: free to hold, no edge (also: environment version table) | data + sim v3 | Medium-High |
| [14](14-qb-round-sweep.md) | QB timing sweep: rounds 4–6 is the sweet spot; past 10 costs real points | sim v3 — stale | Medium-High |
| [15](15-late-season-momentum-myth.md) | Late-season momentum is a myth: last weeks add zero beyond full-season PPG (RB whisper only) | data | High |
| [16](16-td-luck-regresses.md) | TD luck regresses in 8/8 years (~1.6 PPG quintile gap) — 2026 fade/buy lists | data | High |
| [17](17-buy-targets-not-efficiency.md) | WR targets add signal beyond PPG; YAC and catch rate add none | data | High |
| [18](18-injury-prone-is-mostly-myth.md) | "Injury-prone" barely persists — zero at QB/WR, real at TE, suggestive at RB | data | Medium |
| [19](19-bench-composition.md) | Bench RBs are real lottery tickets (21% vs 13% sustained runs) but hoarding them adds ~nothing — tiebreak only | data + sim v3 | Medium-High |
| [20](20-second-qb-te.md) | A 2nd QB/TE is a free choice (all contrasts null); only late QB2 timing and punting TE1 cost | sim v3 — stale | High |
| [21](21-injury-model.md) | Injury reference: Questionable = 69% to play at 83% strength (QB free, TE −25%); median absence 2 wks, rising hazard | data | High |
| [22](22-waiver-wire-reality.md) | **CORRECTED 2026-08-05** — the wire is worth **~30 pts/season (+0.031 all-play)**, 3× the stale v4 number (two v4 bugs crippled the with-wire arm). It is *all* hole-patching: a holes-only policy gets +35.4 on 4.3 claims, weekly bench churn gets only +30.3 on 14.2. A full roster has an empty starting slot ~7×/season (K 2.5, TE 1.5, QB 1.2). Waiver QBs are real (11.4 pts/wk); everything else is a body (~4.5) | sim v5 | High |
| [23](23-early-rb-vs-wr.md) | Early RB > early WR is a per-game talent premium (+35 pts at rank 1, crossover ~rank 38), already priced into ADP — the edge is taking the faster-decaying position first; floor flips at rank ~12 | data + sim v5 | High |
| [24](24-hindsight-optimal-drafts.md) | Hindsight-optimal drafts: perfect foresight is worth +685 pts/season vs disciplined drafting (heuristics differ by ~17); optima open RB1, buy the actual QB1 in rounds 2–3, win the season in rounds 4–8, and spend the endgame on undrafted breakouts | exact search | High |
| [25](25-player-model.md) | **CORRECTED 2026-08-05** — the ridge projection model (20 features incl. salary/cap-share, TD luck, age, draft capital; extends Kapania 2012) does **not** beat the ADP board: it loses at all four positions (−0.055 ± 0.019 paired). The earlier "+.09/+.11/+.15 at QB/WR/TE" scored the model on 2,232 players and ADP on only the 1,217 it covers. Only ADP+½·model wins, by +0.006 ± 0.005. Depth-chart room order is a real predictor but adds nothing on top of ADP (it is read off ADP) | data | High (correction) |
| [26](26-team-environment.md) | Team Elo/ratings: y-o-y stability 0.59, next-season scoring corr only ~0.4 — zero gain season-long; weekly matchup worth +1.3/+1.2 pts at QB/RB and ~0 at WR; Vegas + opponent features help only QB. Weather: wind −1.8 QB/−0.6 WR, RBs immune, already priced into totals. WR/CB directional matchup: split-half reliability 0.07–0.18, zero predictive value. Injury history: null survives multivariate control | data | High |
| [27](27-dst-model.md) | D/ST weekly model: opponent implied total alone = .304 within-week rank corr (naive .127); O-line, giveaways, own defense, even backup-QB status add ≤.005 — the closing line prices it all. Stream by implied total; don't pay for "good defense" | data | High |
| [28](28-kicker-model.md) | Kicker weekly model: .186 ceiling (half of D/ST), kicker's own history worth .079 — stream the situation (win prob, dome/wind, coach FG-tendency), never the kicker; everything beyond Vegas = +0.02 | data | High |
| [29](29-round-profile.md) | Starter rate by round 81%→5%, same in std/half/PPR; late-RB-stash is a myth (R9-15 RB 8.9% vs WR 11.2%); late WR/TE hits are young (−1.7/−1.9 yrs); TE/QB stay startable deep | data | High |
| [30](30-good-offense-tiebreak.md) | Preseason Vegas win line → team PPG is real (rho +.45, 23/23 seasons) but **dead as a player tiebreak**: same-position pairs within 6 ADP slots, better offense won only 46% — ADP already prices team quality | data | High |
| [31](31-rookie-model.md) | **CORRECTED 2026-08-05** — the rookie model (draft capital + combine + landing spot, no absolute ADP) **ties NFL draft order** (−0.001 ± 0.023 over 36 position-classes) and shows no edge over rookie ADP where that can be tested. The earlier "beats rookie ADP at QB/WR/TE" gave the 74% of rookies the market never priced a tied worst-rank; only 26% are priced, and QB/TE can't be tested at all. Board's value is coverage (80 rookies vs ~20), not accuracy; at RB the crowd wins | data | High (correction) |
| [32](32-draft-sim.md) | 9,000 simulated leagues (2020-25, seat-rotated, shared luck) settle finding 25 on the outcome that matters: pure ADP .595 all-play / 20.7% titles > 25% model tilt 18.7% > 50/50 blend 14.8% > pure model 10.8% > family control 9.3%. **Every step toward the model makes drafting worse** — the model is context, never list order. Discipline is the edge | sim | High |
| [33](33-te-same-pick.md) | The same-pick test: early TEs (R1-4, 2018-25) beat the WR/RBs drafted at the same picks 69% of the time and bust at half the rate (8% vs 20-24%); ex-Kelce the edge shrinks to +6 pts but never flips. Hit odds cliff after R4 (86→53→30→16% top-6). **But on titles (sim v5, 3,600 seasons/arm) no forced timing beat just taking the board (19.8%)** — loss tracks the *price*: reach 8 picks −3.7pts, pay par −1.7, discount ~0. Let him fall to you; never rounds 5-9 | data + sim v5 | Medium-High |
| [34](34-roster-shape.md) | **RETRACTED same day** — priced roster shape by forcing positional templates; templates cost ~10 pts of drafted talent by reaching, and the RB/WR ones secretly pinned QB=1/TE=1 so they tested "no backup QB/TE" instead. Shape orderings unusable. What survives: wire-off costs −31, independently reproducing finding 22. Live version is finding 36 | sim v5 | Low (retracted) |
| [35](35-in-game-model.md) | **Live win probability.** Fantasy points accrue linearly with the game clock (quarters 21.6/28.6/22.6/27.1%; the only bumps are the two 2-minute drills), so `remaining = 0.92 × proj × frac_left` is the whole model — game script, live production and Vegas add 1–2% combined. Same-team WR↔WR correlation is **0.00**; only QB↔own pass-catcher (0.28) and opposing QB↔QB (0.12) are real. Every simulation is overconfident at the tails (we say 85%, reality 78%); zero-inflated marginals, stack correlation and heteroskedastic sigma **all fail to fix it**, and a flat 0.87 shrink toward 50% beats all three. Ceiling is set by projection quality, not simulation machinery | data (5 seasons pbp) | High / Medium |
| [36](36-draft-order.md) | QB timing is the only draft-order lever: round 4 +10 pts, round 10 −17 (27-pt spread, monotone). Everything else is noise — QB2 wins +0.4% titles ±2.9, TE timing flat, late RB vs late WR +1.6 ±2.3. A TE2 is worse than nothing. Open 2-3 RB in rounds 1-4. The observational "late RBs win" gap is endogenous and vanishes when forced | sim v5 | High |

Open hypotheses with test designs live in [BACKLOG.md](BACKLOG.md)
(B4–B12: waiver expected-points, RYOE screening, O-line health,
rookie RB paths, seat advantage, rookie-reach EV, QB2 insurance,
WR archetypes out-of-sample, pass-protection proxies).

Reproduce anything:

```bash
venv/bin/python -m simfl analyze kickers|streaming|scarcity
venv/bin/python -m simfl.grid --heroes all -n 240   # strategy backtest
venv/bin/python -m simfl.plots                      # all figures
venv/bin/python scripts/wr_archetypes.py            # findings 08-10
venv/bin/python scripts/jackels_review.py           # finding 11
venv/bin/python scripts/next_season_signal.py       # findings 15-18 (--quick to skip stats suite)
venv/bin/python analysis/rb_wr_curves.py            # finding 23 curves + figure
venv/bin/python analysis/rb_wr_swap.py              # finding 23 causal swap test
venv/bin/python analysis/sharp_room.py              # finding 03 sharp-room table
venv/bin/python analysis/oracle_draft.py            # finding 24 (--test for beam sanity)
venv/bin/python scripts/fetch_market_data.py        # contracts/draft/rosters for finding 25
venv/bin/python analysis/player_model.py            # finding 25 model + 2026 board
venv/bin/python analysis/team_ratings.py            # finding 26 Elo/SRS + stability
venv/bin/python analysis/weekly_model.py            # finding 26 next-week model + weather
venv/bin/python analysis/wr_cb_proxy.py             # finding 26 WR/CB proxy (fetches pbp)
venv/bin/python analysis/nfelo_study.py             # finding 26 nfelo backtest
venv/bin/python analysis/market_implied.py season   # 2026 market environment (needs .env key)
venv/bin/python analysis/dst_model.py               # finding 27 D/ST model
venv/bin/python analysis/kicker_model.py            # finding 28 kicker model
venv/bin/python analysis/te_same_pick.py            # finding 33 TE same-pick test + figures
venv/bin/python analysis/wire_worth.py              # finding 22 headline pairing
venv/bin/python analysis/wire_decompose.py          # finding 22 holes vs churn vs naive
venv/bin/python analysis/wire_hole_value.py         # finding 22 value of one patched hole
venv/bin/python analysis/roster_shape.py --formats std,half,ppr  # finding 34
venv/bin/python analysis/roster_shape.py --formats std --nowire --nsims 40  # finding 34 wire-off arm
venv/bin/python analysis/flowchart.py               # finding 36 QB timing + QB2/TE2
venv/bin/python analysis/qb2_usefulness.py          # finding 36 QB2 starts + titles
venv/bin/python analysis/te_timing.py               # finding 36 TE window sweep
venv/bin/python analysis/bench_tilt_v5.py           # finding 36 late RB vs late WR
venv/bin/python analysis/draft_shape_bands.py       # finding 36 observational bands
```
