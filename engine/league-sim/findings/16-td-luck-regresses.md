# 16 — TD luck regresses hard (the one repricing edge in this study)

**Confidence: High** (p = 0.0002, effect negative in 8/8 season
pairs, clustered CI well clear of zero, coherent mechanism)

## TL;DR

Touchdowns over expectation are luck, and the market keeps paying for
them. A skill player's TDs-over-expected (actual minus the nflverse
`ff_opportunity` model's expected TDs) has **zero year-over-year
persistence** (r = +0.05, CI [−0.02, +0.12]) — yet TDs are ~40% of
non-PPR scoring. Players in the luckiest TD quintile score **−1.6 PPG
less** the following year than the unluckiest quintile after matching
on PPG (CI [−2.2, −1.0]); the gap was negative in **all eight**
season pairs (sign test p = 0.004). Over a 14-week fantasy season
that's ~23 points of hidden movement per flagged player.

## The data

Same sample as finding 15 (rosterable players, 2017→2025). TDOE =
(rush+rec TD) − (expected rush+rec TD), from `ff_opportunity`'s
play-level model of TD probability given field position, target
depth, etc.

| Test | Estimate | p | 95% CI (player-clustered) | n |
|---|---|---|---|---|
| TDOE persistence y/y | +0.046 | — | [−0.02, +0.12] | 956 |
| TDOE/gm → next-yr PPG, controlling PPG | **−0.151** | 0.0002 | [−0.22, −0.09] | 957 |
| Lucky-vs-unlucky quintile gap (Δ PPG) | **−1.63** | — | [−2.2, −1.0] | 957 |

Per-season gaps: −0.2, −1.2, −1.4, −2.3, −2.1, −1.3, −2.1, −2.9 —
negative in 8/8 (one-sided sign p = 0.004); the partial correlation
is negative in 7/8.

Two honest nulls attached to the same analysis:

- **QBs**: pass-TDOE partial r = −0.146, p = 0.056, CI [−0.28, +0.02],
  n = 168. Same direction, same size — but not independently
  significant at this sample. Treat QB TD-luck as Medium-confidence
  corroboration, not its own proof.
- **xTD is NOT a better raw projector**: r(xTD → next TD) beats
  r(TD → next TD) by only +0.014 (CI [−0.03, +0.06]). The value of
  expected TDs is *flagging outliers*, not replacing projections.

## Why the market misses it

TD rate per opportunity is nearly all noise (a 60-yard bomb vs a
tackle at the 1), but TDs dominate highlight reels, season-recap
points totals, and therefore ADP. Opportunity (touches, red-zone
usage) persists; conversion doesn't. Everyone drafting off last
year's finish is drafting the conversion luck too.

## 2026 draft lists (from 2025, `ff_opportunity`)

Fade at cost (TDs over expected):

| Player | Pos | TD | xTD | TDOE |
|---|---|---|---|---|
| Jahmyr Gibbs | RB | 18 | 10.7 | **+7.3** |
| Dallas Goedert | TE | 11 | 5.5 | +5.5 |
| De'Von Achane | RB | 12 | 6.6 | +5.4 |
| Tee Higgins | WR | 11 | 6.4 | +4.6 |
| Jonathan Taylor | RB | 20 | 15.4 | +4.6 |
| Tucker Kraft (8 gm) | TE | 6 | 1.8 | +4.2 |
| James Cook | RB | 14 | 10.2 | +3.8 |
| Puka Nacua | WR | 11 | 8.2 | +2.8 |
| Josh Jacobs | RB | 14 | 11.4 | +2.6 |

QBs: Hurts +5.9, Goff +4.4, Allen +3.3 pass-TDs over expected.

Buy (TDs under expected):

| Player | Pos | TD | xTD | TDOE |
|---|---|---|---|---|
| Justin Jefferson | WR | 2 | 8.6 | **−6.6** |
| CeeDee Lamb | WR | 3 | 7.8 | −4.8 |
| Christian McCaffrey | RB | 17 | 20.6 | −3.6 |
| Tyler Warren | TE | 5 | 8.3 | −3.3 |
| Jakobi Meyers | WR | 3 | 5.8 | −2.8 |
| Brian Thomas Jr. | WR | 3 | 5.2 | −2.2 |
| Kenneth Walker III | RB | 5 | 7.0 | −2.0 |

QBs: Dak **−10.7**(!), Mahomes −8.1, Bo Nix −4.3.

These shift priors ~1–2 PPG; they don't override role changes,
age, or injury. A fade means "don't pay the TD-inflated price,"
not "never roster."

## Methodology

`scripts/next_season_signal.py`. Expected TDs summed over regular-
season weeks from `nflreadpy.load_ff_opportunity` (cached at
`data/ff_opportunity_2017_2025.parquet`). Quintiles computed within
the analysis sample; "gap" = mean(next-yr PPG − this-yr PPG) of top
TDOE quintile minus bottom quintile. Stats machinery as in finding 15.

## Caveats

- xTD is itself a model; systematic biases (e.g. elite-finisher
  effects) would inflate apparent "luck." Mitigation: even the
  luckiest *quintile* — full of genuinely good players — regressed
  in 8/8 years.
- A few players (goal-line hammers, Tyreek-tier burners) may sustain
  positive TDOE across years; with persistence r = 0.05 they are
  rare. Check usage before fading a repeat offender.
- Lists use 2025 stats only; injuries/roles already changed some
  prices (e.g. Jefferson's down year has other causes too — see
  finding 17, where he's also the #2 target-excess buy).
