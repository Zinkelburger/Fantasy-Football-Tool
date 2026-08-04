# 18 — "Injury-prone" is mostly myth (except TE, and maybe RB)

**Confidence: Medium** — the QB/WR null is well-powered and solid;
the TE persistence is significant but rests on 24 repeat cases; the
RB effect wouldn't survive a multiple-comparisons correction.

## TL;DR

Being hurt this year barely predicts being hurt next year. Weeks
listed Out/Doubtful correlate year-over-year at r = +0.07 (n = 1,212)
— statistically detectable (p = 0.015) but explaining **half a
percent** of the variance. At QB and WR the persistence is exactly
zero. The exceptions: **TEs** who missed 2+ weeks repeat at 38% vs a
19% baseline (r = +0.20, p = 0.008), and RBs at 30% vs 18% —
suggestive but weaker. Injury history adds *nothing* to next-year
PPG prediction once you know PPG (partial r = −0.01, p = 0.63).

## The data

Weeks listed **Out or Doubtful** on official NFL injury reports
(regular season), 2017→2025, same rosterable sample as findings 15–17.

| Pos | y/y r | p | P(2+ wk Out next yr \| 2+ this yr) | \| 0 this yr | diff p |
|---|---|---|---|---|---|
| QB | +0.04 | 0.58 | 15.0% (n=20) | 17.3% | 0.88 |
| RB | +0.07 | 0.15 | 30.3% (n=66) | 18.3% | 0.037 |
| WR | +0.03 | 0.54 | 23.2% (n=82) | 25.2% | 0.71 |
| TE | **+0.20** | **0.008** | **37.5%** (n=24) | 18.5% | 0.039 |

Read the WR row twice: previously-injured WRs repeated *less* often
than never-injured ones. That's what a true zero looks like.

Honest scoring of the positives: eight tests were run in this table.
TE's r (p = 0.008, clustered CI [+0.06, +0.31]) is the only result
that survives that scrutiny; the RB repeat-rate (p = 0.037) and TE
repeat-rate (p = 0.039) are each one moderately-unlucky draw from
surviving it. Hence Medium, not High.

## What it means at the draft

- **Never discount a QB or WR for injury history.** When a family
  member says a WR is "made of glass," that's a buying opportunity —
  the discount is real, the risk isn't.
- A modest discount on TEs (and, more weakly, RBs) coming off
  multi-week injuries is defensible — plausibly because the injuries
  that recur (soft-tissue, high-contact roles) concentrate there.
- Don't expect injury history to predict *production*: among players
  healthy enough to stay rosterable, weeks-Out adds zero PPG signal
  beyond PPG itself.

## Methodology

`scripts/next_season_signal.py`, injuries from
`nflreadpy.load_injuries` (cached `data/injuries_2017_2025.parquet`),
`game_type == "REG"`. "2+" threshold chosen once, before testing.
p-values by permutation; the pooled CI is player-clustered.

## Caveats

- Injury reports only cover rostered players: someone who spent the
  whole next season on IR (or out of the league) has no next-year
  row and drops out. This *understates* persistence for
  career-altering injuries — the finding is about the ordinary
  sprains-and-hamstrings range, not Achilles tears.
- Weeks *listed* Out ≠ games missed (bye-week reports, players
  benched while nominally hurt). Treated as a proxy throughout.
- No injury-type split yet (soft-tissue vs contact) — the reports
  carry `report_primary_injury`, so this is testable if the TE/RB
  result matters for a real draft call. Backlogged.
