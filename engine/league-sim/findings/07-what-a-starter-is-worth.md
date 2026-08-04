# 07 — What a starter is worth: the value curves behind everything

**Confidence: High** (descriptive averages over six full seasons)

## TL;DR

Average PPG by end-of-season positional rank, 2020–2025, league
scoring. Every strategic conclusion in this directory is downstream of
this table's shape: RB falls off a cliff, WR is flat, TE is
elite-or-nothing, K is a rounding error, QB is high but replaceable.

## The data

(figure: `figures/fig1_scarcity.png`)

| Rank | QB | RB | WR | TE | K |
|---|---|---|---|---|---|
| #1 | 23.5 | 19.1 | 15.7 | 11.2 | 11.5 |
| #4 | 20.8 | 15.1 | 12.4 | 8.2 | 10.0 |
| #7 | 18.9 | 13.6 | 11.5 | 6.9 | 9.5 |
| #10 | 17.8 | 12.3 | 10.6 | 6.1 | 9.1 |
| #13 | 16.3 | 11.6 | 9.9 | 5.7 | 8.6 |
| #16 | 15.5 | 11.0 | 9.5 | 5.1 | 8.4 |
| #22 | 14.0 | 9.8 | 8.5 | 4.4 | 7.9 |
| #28 | 11.9 | 8.6 | 8.0 | 3.6 | 7.1 |

Reading it against this league's lineup (1 QB / 2 RB / 2 WR / TE /
RB-WR FLEX / K in 12 teams — so the "last starter" is roughly QB12,
RB30, WR30, TE12, K12):

- **RB**: RB1→RB10 loses 6.8 PPG; the position's entire premium lives
  in the first ~12 names. This is finding 01's engine.
- **WR**: WR7→WR28 loses only 3.5 PPG. Mid WRs are near-commodities —
  which is why WR-heavy fails (02) and why the mid-round WR game is
  about hit *rate*, not slot (08).
- **TE**: TE1 (11.2) is a genuine weapon; TE7 (6.9) is barely above
  TE12 (5.9). Elite-or-punt; the league sells the middle at round-5
  prices (05).
- **QB**: biggest absolute drop (23.5 → 16.3 by QB13), but the last
  starter still scores 16+ — more than any RB2. High floor is why
  waiting is survivable; steep top is why streaming isn't (06).
- **K**: 11.5 → 8.4 across the entire startable population. Three
  points separate the best from the worst starter (04).

## Methodology

- For each season 2020–2025: rank all players at each position by
  season PPG (min 6 games), take PPG at each rank, average the curves
  across the six seasons.
- PPG (not season total) avoids conflating quality with games played;
  the min-games filter removes cameo distortion.
- Scoring is league-exact standard (whole-point floors, 4-pt pass TD).
  These curves would look materially different in PPR — WR/TE flatten
  upward — which is exactly why imported advice misleads (02).
- Reproduce: `venv/bin/python -m simfl analyze scarcity` and
  `venv/bin/python -m simfl.plots` (fig1).

## Caveats

- End-of-season ranks are hindsight; a *draft-time* version of this
  chart (points by ADP slot) is noisier but same-shaped (fig6 shows
  the QB version).
- Averaging six seasons smooths real year-to-year swings (2023's RB
  top-tier was much weaker than 2024's); the strategy backtests, not
  the averaged curve, carry the year-risk story (01's per-year row).
