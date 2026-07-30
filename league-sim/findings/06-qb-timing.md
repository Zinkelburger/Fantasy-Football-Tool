# 06 — Early QB is fairly priced; late-QB-plus-streaming costs

**Confidence: Medium-High** (sim + descriptive agree; effect sizes
moderate; numbers are environment v3 — see finding 13's version table)

## TL;DR

Even at 4-pt passing TDs, expensive QBs return real points — the cost
curve is *not* flat — and the sim says the market prices that roughly
fairly: taking a QB early is fine (.592, dead even with disciplined
no-conviction drafting at .591), while deliberately waiting past
round 10 and leaning on waivers measurably costs (.563, −2.9 points).
Take your QB when a top-6 one is available in rounds ~3–6 (finding 14
sweeps every round: 4–6 is the peak).

## The data

**Cost curve** (drafted QBs with 6+ games, 2020–2025; figure
`fig6_qb_cost.png`): median season PPG falls from **~21 at ADP 20** to
**~17 at ADP 85** to **~13 at ADP 170**. That's an 8-PPG spread — the
largest top-to-replacement drop of any position in absolute points
(finding 07: QB1 23.5 → QB13 16.3).

**Simulation** (1,440 seasons each):

| Strategy | All-play | Playoffs | Titles |
|---|---|---|---|
| Early QB (elite QB by ~rd 3) | .592 | 74.3% | 15.8% |
| BPA (disciplined, no QB conviction) | .591 | 74.2% | 15.3% |
| Late QB (none before rd 10, stream 2nd) | **.563** | 68.6% | 12.6% |
| Family baseline | .500 | 50.2% | 7.6% |

**Waiver supply** (why streaming fails): free agents in the
rest-of-season top-8 QBs by year — 1 (Herbert '20), 0, 2, 2, 1
(Mayfield '24), 0. In two of six seasons the wire held *nothing*, and
the hits were mostly identifiable only in hindsight (Kyler '23 was
ranked #38 through week 3).

## Interpretation

QB is the one position where "pay up" and "wait" are both defensible
*at the market price* — Early QB neither wins nor loses vs the
disciplined no-conviction baseline.
What loses is the strong version of waiting: planning to start a
round-10+ QB plus wire pickups. In a 12-team league, 24 QB slots
roster essentially every startable passer; the emergent wire is bare.

Practical rule: don't reach for the QB1 overall, but when a top-6 QB
is sitting there in rounds 3–6 (Josh Allen at pick 30 in your 2024
draft → QB2, 364 pts), take him. Never leave the draft planning to
stream the position.

## Methodology

- Cost curve: all drafted QBs 2020–2025 with ≥6 games; season PPG vs
  overall ADP; medians per ADP bin. League-exact scoring.
- Sim: `EarlyQB` (strong QB preference from round 2 while QB-less) and
  `LateQB` (QB banned before round 10, QB-streamer waiver policy),
  METHODS.md harness.
- Wire supply: same construction as finding 05 with pos=QB.
- Reproduce: `venv/bin/python -m simfl analyze streaming --pos QB`,
  `venv/bin/python -m simfl.grid --heroes early_qb,late_qb -n 240`,
  `venv/bin/python -m simfl.plots` (fig6).

## Caveats

- Early QB's .592 is *par vs BPA's .591*, not an edge — the finding
  kills late-QB dogma rather than crowning early-QB.
- The 4-pt pass TD setting matters: at 6 points, early QB would likely
  become an outright edge (untested here).
- Late QB fails partly through the sim's streaming policy; a manager
  with elite QB-picking instincts could do better than the bot, but
  the supply numbers above bound how much better.
