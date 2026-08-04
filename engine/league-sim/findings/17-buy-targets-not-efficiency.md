# 17 — Buy targets, not efficiency (YAC and catch rate add nothing)

**Confidence: High** for the WR target signal (p = 0.0004, positive
in 7/8 season pairs) and for the efficiency nulls (well-powered);
the RB/TE analogues are weaker.

## TL;DR

Among WRs with the same PPG, the one earning **more targets per game**
outscores the other next season — partial r = +0.19 beyond PPG
(p = 0.0004, CI [+0.11, +0.27], n = 438), positive in 7/8 season
pairs. Meanwhile the *efficiency* stats everyone cites add nothing
once PPG is known: YAC/reception (+0.06, p = 0.11), catch rate
(−0.02, p = 0.74), even catch-rate-over-expected (+0.02, p = 0.73).
Volume is the skill the market underprices; efficiency is how last
year's points happened.

## The data

Same sample and stats machinery as findings 15–16. "Partial vs
next-yr PPG" = correlation after residualizing both variables on
current-year PPG.

| Signal (beyond current PPG) | partial r | p | n | Verdict |
|---|---|---|---|---|
| WR targets/game | **+0.194** | 0.0004 | 438 | real edge |
| RB carries/game | +0.090 | 0.09 | 344 | weak echo, ns |
| TE targets/game | +0.067 | 0.39 | 175 | ns |
| YAC/reception (50+ tgt) | +0.059 | 0.11 | 718 | no edge |
| Catch rate (70+ tgt) | −0.015 | 0.74 | 493 | no edge |
| Catch rate over expected (70+ tgt) | +0.016 | 0.73 | 493 | no edge |

The subtlety worth a slide: **YAC/rec is a real, stable skill**
(y/y r = 0.48, p = 0.0002 for WRs) — it just doesn't help you,
because the skill is already baked into the PPG you can see. Catch
rate is the same story even after adjusting for target depth with
`ff_opportunity`'s expected receptions. A stable stat and a useful
stat are different things.

## Why targets specifically

In this non-PPR league a target earns 0 points, so a
volume-over-efficiency WR *looks* worse than he is: his PPG
understates his opportunity, and opportunity is what persists.
Points built on 9 targets/game repeat; points built on 17.8
yards/catch don't. (This is the same logic that made the TD-luck
fade work in finding 16 — bet on what persists, fade what doesn't.)

## 2026 lists (2025 targets vs PPG trend, WRs)

Volume buys (targets/gm far above what their PPG implies):
Ja'Marr Chase (11.6 tpg), **Justin Jefferson** (8.3 tpg on 6.5 PPG —
double-flagged: also the biggest TD-unlucky buy in finding 16),
Wan'Dale Robinson, Chris Olave, CeeDee Lamb, Amon-Ra St. Brown.

Efficiency-dependent fades (PPG outran their volume): Christian
Watson, Alec Pierce, **Tee Higgins** (double-flagged: also +4.6 TDs
over expected), Jameson Williams.

## Methodology

`scripts/next_season_signal.py`. Targets/YAC from
`nflreadpy.load_player_stats` (cached `data/adv_weekly_2017_2025.
parquet`), regular season only; expected receptions from
`ff_opportunity`. Thresholds (50+/70+ targets) set before testing;
the catch-rate null also holds at 100+.

## Caveats

- Tested within rosterable WRs; says nothing about waiver-tier
  players earning their first targets.
- The target signal is calibrated on 2017–2024 offenses; a league-
  wide scheme shift would move the coefficient, not likely the sign.
- "Efficiency adds nothing *beyond PPG*" — efficiency still matters
  as a scout's input to whether the targets stay. It's the *extra*
  predictive weight that's zero, so never pay for efficiency at
  equal production.
