# 30 — Good-offense tiebreak: the market already priced it

**Confidence: High** on both halves. The team-level signal is positive
in 23 of 23 seasons. The player-level null is stable across every
threshold we tried (1,414 close-ADP pairs, eight boards).

Two questions, opposite answers.

Does the preseason betting market know which offenses will score? Yes,
reliably. The August win-total line correlated with actual points per
game at mean Spearman +0.45 across 2003-2025, positive in all 23
seasons. 2025 was +0.39, and the top-8 teams by line averaged 25.5 PPG
against the bottom-8's 18.0.

Should you therefore break a draft tie toward the player on the better
offense? No. Among same-position players drafted within 6 ADP slots of
each other whose teams' lines sat 1.5+ wins apart, the better-offense
player finished with more points **46%** of the time (646/1414,
2018-2025). At or below a coin flip in every position and under every
variant tested.

ADP already carries the team context. The offense number is real
information about *teams* — it drives our K and D/ST boards — and zero
information about *which of two similarly-drafted players to take*.

## The signal and its proxy

The 2026 board shows a market-implied PPG per offense, built by summing
implied totals from the full-schedule betting lines
(`analysis/market_implied.py`, Aug 2026 snapshot). No free historical
snapshots of that exist, so the backtest uses the preseason **win-total
line** — the market's August team number — as the stand-in. On the 2026
snapshot the two rank teams near-identically (Spearman 0.923, Pearson
0.919), so the win line is a fair proxy for "implied PPG, in August."

Sources: `win_totals_sos.csv` (nfelo, 2003-2022) plus
`win_totals_2023_2025.csv` (preseason lines archived by
sportsoddshistory.com; fetched 2026-08-05, actual-wins column verified
against `games.csv` — one team off by one win, unused either way).
Actual scoring from `games.csv`, regular season only.

## Team level: Vegas picks offenses well

Spearman between the August line and that season's actual offensive
PPG, per season 2003-2025:

- mean **+0.45**, range +0.18 (2022) to +0.80 (2009)
- **23 of 23 seasons positive** — the signal has never pointed the
  wrong way in the sample
- 2025, the season asked about: **+0.39**. The top-8 offenses by
  August line averaged 25.5 real PPG vs 18.0 for the bottom-8. Misses
  exist (KC was lined 11.5 wins and finished #21 in scoring; the Rams
  were lined 9.5 and led the league) but the group call was right.

This squares with [finding 26](26-team-environment.md): our own
stat-based team ratings added nothing, and the market prior was the one
season-long team signal that graded out.

## Player level: the tiebreak fails

Design: every drafted QB/RB/WR/TE on the 2018-2025 ADP boards (top
180, n=1,370 player-seasons matched to rosters), season totals under
league-exact standard scoring; a drafted player with no season row
counts as zero, not missing. Take all same-position, same-season pairs
drafted within 6 ADP slots of each other — a genuine draft-room
coin-flip — where the two teams' win lines differed by 1.5+ wins, and
ask who actually finished with more points.

| slice | better offense won |
|---|---|
| QB | 38/80 (48%) |
| RB | 314/666 (47%) |
| WR | 271/615 (44%) |
| TE | 23/53 (43%) |
| **all** | **646/1414 (46%)** |

Per season it clears 50% in only 2 of 8 seasons: 53% at best, 35% at
worst. Robustness — widening the ADP window to 12, demanding a 2.5 or
3-win gap, cutting to ADP ≤ 100, scoring per-game with an 8-game
minimum — moves the number between 44% and 51%, never meaningfully
above the flip. (The naive binomial p for "beats a coin flip" is
0.9995; overlapping pairs share players, so that p is
anti-conservative and the per-season signs are the honest read.)

ADP is set by drafters who can all read the same Vegas lines, so team
quality is in the price
([finding 03](03-adp-discipline-is-not-an-edge.md)). What the price
misses runs the *other* way: bad teams concentrate their volume on
fewer mouths ([finding 08](08-bad-team-wr1-edge.md)), and 46% < 50%
hints the market may even overpay a touch for good-offense
association. We claim the null, not the fade.

## What this changes

- The 2026 board's market table stays — as **team environment context**
  and as the input the [kicker](28-kicker-model.md) and
  [D/ST](27-dst-model.md) draft lists are actually built from.
- The board copy that told readers to use it as a skill-position
  tiebreak is withdrawn and now says the opposite, citing this finding.
- The per-player offense readout on the site shows the number with the
  caveat, not as advice.

## Reproduce

`venv/bin/python analysis/good_offense_tiebreak.py` — sections 1-4
print every number above.
