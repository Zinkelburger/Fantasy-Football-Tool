# Season projection models — retired 2026-08-05

Two models lived here: a **season projection model** for returning
players (findings 25, 32) and a **rookie-year model** (finding 31).
Both are retired from the product. Neither beat the thing it was
supposed to beat.

This file is the back room: what they were, **exactly where every input
came from**, what was tried, what failed, and what a future model has to
clear to earn its way back onto the site. Read it before building the
next one — most of the obvious ideas in this space have already been
tested here and are written down below as nulls.

---

## 1. Why they were retired

**Season model.** Leave-one-year-out over 2018–2025, every board scored
on the same 1,217 ADP-covered player-seasons:

| pos | ADP board | model |
|---|---|---|
| QB | **.553** | .428 |
| RB | **.694** | .640 |
| WR | **.643** | .614 |
| TE | **.502** | .492 |
| pooled | **.598** | .544 |

Paired over 32 position-years: **model − ADP = −0.055 ± 0.019, wins
9/32.** Then finding 32 took the same boards into 9,000 simulated
leagues and measured what a draft list is actually for:

| draft list | all-play | titles |
|---|---|---|
| pure ADP | **.595** | **20.7%** |
| ADP + 25% model | .594 | 18.7% |
| ADP + 50% model | .580 | 14.8% |
| pure model | .522 | 10.8% |
| family-bot control | .500 | 9.3% |

Every step toward the model made drafting worse.

**Rookie model.** Ties NFL draft order — **−0.001 ± 0.023 over 36
position-classes, wins 15/36**. Thirteen features (combine, landing
spot, cap) reproduce "rank them by where the NFL drafted them." Against
rookie ADP it shows no edge where a test is even possible (RB in 7
classes, WR in 3; QB and TE cannot be tested at all, see §4).

**The final autopsy — is it a good tiebreaker?** This was the fallback
claim ("use it to choose between players priced the same") and it was
never tested until retirement day. Every same-position pair within 24
ADP slots, LOYO predictions, clustered by position-year — when the model
disagrees with ADP, how often is it right?

| pos | model wins disagreements | se | years >50% | pairs |
|---|---|---|---|---|
| QB | **.559** | .038 | 6/8 | 229 |
| TE | .521 | .046 | 5/8 | 142 |
| WR | .490 | .011 | 1/8 | 1276 |
| RB | .455 | .021 | 2/8 | 825 |

Only QB shows anything (~1.5σ — suggestive, not proven). **At RB the
model is actively worse than the board** (−2.1σ). WR is dead flat on
1,276 pairs. Note the inversion: QB is the model's *worst* position on
whole-list ordering and its *best* on local calls, which makes sense —
the market nails the global QB pecking order, but among three QBs
priced within a round the model has something.

Checked and rejected: the QB tiebreak edge is **not** just "the paid QB
plays." `room_share` alone as a tiebreaker scores .477, a null. Whatever
the QB signal is, it only appears in the multivariate fit.

---

## 2. Where every input came from

All public, all free. Fetched **2026-08-04** unless noted.

| input | source | landed at |
|---|---|---|
| weekly stats 2017–25 | nflverse `load_player_stats` via `nflreadpy` (see `simfl/data.py`) | `data/weekly_{year}.parquet` |
| usage/advanced weekly (targets, target share, carries) | nflverse advanced weekly | `data/adv_weekly_2017_2025.parquet` |
| expected points from usage | nflverse **`ff_opportunity`** | `data/ff_opportunity_2017_2025.parquet` |
| contracts + per-season cap hits | **OverTheCap**, mirrored by nflverse `contracts` | `data/market/historical_contracts.parquet` |
| draft picks (capital) | nflverse `draft_picks` (PFR-sourced) | `data/market/draft_picks.parquet` |
| combine measurables | nflverse `combine` | `data/market/combine.parquet` |
| rosters 2017–2026 (age, team, experience) | nflverse `rosters/roster_{year}` | `data/market/roster_{year}.parquet` |
| game results + Vegas lines | Lee Sharpe / nflverse `nfldata/games.csv` | `data/market/games.csv` |
| QB Elo | `greerreNFL/nfeloqb` `qb_elos.csv` | `data/market/qb_elos.csv` |
| team offense/Elo ratings | **ours**, `analysis/team_ratings.py` off `games.csv` | `data/market/team_ratings.csv` |
| ADP 2018–2025 (the benchmark) | **FFC** (Fantasy Football Calculator), standard, cached by the sim | `data/adp_{year}.json` |
| ADP 2026 | `engine/update_ranks.py` snapshot (ESPN + Sleeper + FFC, per format) | `data/market/adp_2026.csv` |

Fetcher: **`engine/league-sim/scripts/fetch_market_data.py`**
(base URL `https://github.com/nflverse/nflverse-data/releases/download`).

### Gotchas that cost real time — read these

1. **`fetch_market_data.py` skips any file that already exists.**
   Re-running it is a no-op. To refresh you must delete first:
   `rm data/market/historical_contracts.parquet data/market/roster_2026.parquet`
2. **`cap_number` is in millions, `cap_percent` is a fraction** (0.032 =
   3.2%). Dividing by 1e6 silently yields zeros.
3. **2026 rookies have no cap numbers** in the OTC release (all 226
   missing as of 2026-08-04). Any position-room cap denominator is
   therefore slightly overstated, and a drafted rookie contributes $0.
4. **`ff_opportunity`'s `season` column is a string.** Compare with
   `.astype(int)` or every year filter silently returns empty.
5. **Roster parquets are one row per player-season** with a `week`
   column that is *not* a weekly snapshot — don't read it as depth chart.
6. **PFR draft-table team codes ≠ nflverse roster codes**
   (`GNB/KAN/LAR/LVR/NOR/NWE/SFO/TAM`). Map in
   `analysis/position_room.py:PFR2NFL`.
7. **`build_pool(2026)` throws** — no weekly stats exist for a season
   that hasn't started. Upcoming-season ADP must come from
   `adp_2026.csv`.
8. FFC purged its 2025 board; that year's ADP was recovered from a
   Wayback snapshot of FantasyPros.

---

## 3. What the models were

**Season model** (`code/player_model.py`): ridge regression, one fit per
position, standardized, λ by nested leave-one-year-out. Target =
next-season fantasy PPG, league-exact scoring, refit per format
(std/half/PPR). Trained on 2,232 player-seasons. Panel filter: ≥4 games
and ≥2 PPG in season *t*, present on a *t+1* roster, ≥1 game in *t+1*.

20 features: `ppg, games, ppg_prev, ep_ppg, eff_gap, td_luck_pg, tgt_pg,
tgt_share, carry_pg, rush_ypg, age, yrs, ln_dpick, cap_pct, room_share,
cap_rank, new_team, tm_rook_pick, team_off_prev, team_elo_prev,
miss_rate_2yr`.

Lineage: extends **Kapania (2012), "Predicting Fantasy Football
Performance with Machine Learning Techniques," Stanford CS229**
(cs229.stanford.edu/proj2012/Kapania-FantasyFootballAndMachineLearning.pdf)
— his stated limitations (no age, no playing-time context, no injuries,
one prior season, RBs only) were the original to-do list.

**Rookie model** (`code/rookie_model.py`): same shape, target = rookie
-year points per *scheduled* game (16 pre-2021, 17 after), so busts and
never-played count as the zeros they were. 13 features: draft capital,
draft age, eight combine tests, position-room cap already committed,
prior-season team offense, and one relative-ADP read (the best incumbent
ADP at his team+position).

Final boards as shipped: `model_board_2026.csv`, `rookie_board_2026.csv`.

---

## 4. The two evaluation bugs — do not repeat these

Both models originally reported *beating* their benchmark. Both were
wrong the same way: **the benchmark was asked an easier or narrower
question than the model.**

**Finding 25's bug.** The model and the naive baseline were scored on
all 2,232 panel rows; ADP was scored only on the 1,217 it covers. The
extra 1,015 are undrafted deep players (WR 2.9 PPG vs 7.4 for drafted
ones). Ranking a field that spans stars to scrubs is far easier, so the
model banked the free call "the undrafted guys finish worse" — which ADP
was never graded on. Worth ~+.14 pooled. The tell: the naive baseline
gained the same amount from the same mistake.

**Finding 31's bug.** Every rookie the fantasy market never priced got a
**tied** worst-rank of 999 — 74% of the panel. Same player set, so it
looked safe (the old write-up explicitly argued it was), but a tied
block is not a ranking: the model got a distinct number for all 721
rookies and earned credit for sorting a group ADP was never asked to
sort. Only 185 of 721 rookies (26%) are ever priced, and the market
prices just 1–5 rookie QBs and 0–2 rookie TEs a class — so **QB and TE
cannot be tested against rookie ADP at all.**

**The check to run on any future model:** does the benchmark have a
real, distinct opinion on every row you are scoring? If not, score only
the rows where it does, and say how many that is.

---

## 5. Ideas already tested and dead

Don't spend a weekend re-deriving these.

| idea | result |
|---|---|
| retrain on the draftable population only | −0.048 ± 0.017 vs ADP, no help |
| give the model ADP itself as a feature | pulls to a tie (−0.004), never past it |
| ADP + ¼ or ½ model rank-stack | +0.007/+0.012 on rank corr — but **worse in sims** (finding 32); do not use |
| depth-chart room order (rank in room, gap to next man, room size) | real predictor (RB "is the alpha" +0.94σ), lifts the standalone model .550→.577 — but **adds nothing on top of ADP** (−0.001 ± 0.005) because it is read *off* ADP |
| `room_share` alone as a QB tiebreaker | .477, null |
| team environment (Elo, off-SRS) as season features | null, finding 26 |
| injury history (`miss_rate_2yr`) | null, findings 18 + 26 |
| combine measurables (rookies) | noise, \|β\| < 0.2 almost everywhere |
| WR/CB directional matchup | split-half reliability 0.07–0.18, finding 26 |
| preseason Vegas win line as a player tiebreak | 46%, finding 30 |
| synthetic season generation | built, validated, then **removed at the user's request** — broke cross-player correlation (real QB-WR1 weekly corr 0.35, synthetic 0.00). Don't rebuild unasked. |

**Survivor worth keeping:** `tm_rook_pick` (ln of the earliest pick a
team spent at the player's position). It is the one depth-chart input
*not* read off ADP, and its coefficient is positive at all four
positions (QB +0.25, RB +0.41, WR +0.32, TE +0.21) — an early rookie at
your position costs the incumbent. Effect on rank accuracy was
+0.0024 ± 0.0025, i.e. unproven. It now lives in
`analysis/position_room.py`.

---

## 6. What a future model must clear

Any replacement has to beat, **on the ADP-covered population, LOYO,
paired, reported with a standard error**:

1. **ADP, pooled Spearman .598** — and per position: QB .553, RB .694,
   WR .643, TE .502.
2. **Pure ADP in the sim: .595 all-play, 20.7% titles** (finding 32's
   harness). Rank correlation is *not* the objective — most of the ADP
   pool goes in rounds you rebuild off waivers, so ordering it better
   buys little while disagreements near the top cost real picks.
3. For a tiebreaker claim: **>50% on same-tier disagreements**, per
   position, clustered by year. Current bar: QB .559, TE .521, WR .490,
   RB .455.

The most promising untried input is **college production** for the
rookie model (target share, breakout age, yards per route). Free
cfbfastR mirrors are play-by-play only (~100MB/season, ESPN ids that
don't join our sports-reference slugs); CollegeFootballData needs an API
key. Given the rookie model currently only ties draft order, this is
the only thing likely to move it.

---

## 7. How to revive

The scripts still run in place at
`engine/league-sim/analysis/{player_model,rookie_model}.py`; the copies
in `code/` here are the exact retired versions in case those drift.

```bash
cd engine/league-sim
./venv/bin/python analysis/player_model.py     # eval table + 2026 boards
./venv/bin/python analysis/rookie_model.py     # both head-to-heads + board
```

**`player_model.py` was left in `analysis/` on purpose**: 14 other
scripts import it as a data-access layer (`season_stats`, `roster`,
`cap_table`, `team_rating`, `spearman`, `ridge_fit`, `standardize`),
including the machinery behind findings 26, 29 and 30. Retiring the
*model* did not mean deleting the *library*. If you refactor, move those
helpers to a neutral module first and fix all 14 importers.

`room_standing` was extracted to **`analysis/position_room.py`** and is
still live — it feeds the draft tool's per-player note ("He's CIN's WR2
on the draft board — 31 picks behind Ja'Marr Chase"). That is
description, not prediction, and it survives the retirement.

## 8. Related findings

- [25](../../engine/league-sim/findings/25-player-model.md) — season model, corrected
- [31](../../engine/league-sim/findings/31-rookie-model.md) — rookie model, corrected
- [32](../../engine/league-sim/findings/32-draft-sim.md) — the 9,000-league simulation that settled it
- [16](../../engine/league-sim/findings/16-td-luck-regresses.md), [17](../../engine/league-sim/findings/17-buy-targets-not-efficiency.md) — the descriptive results that *did* survive and still ship as board context
