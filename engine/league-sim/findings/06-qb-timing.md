# 06 — Early QB is fairly priced; late-QB-plus-streaming costs

**Confidence: Medium-High** (sim + descriptive agree; effect sizes
moderate; numbers are environment v3 — see finding 13's version table)

## TL;DR

Expensive quarterbacks are worth it — they're just not a bargain.
Early QBs really do score more (roughly 8 more PPG at the top of the
market than the bottom), and the sim says drafts price that about
right: taking one early neither helps nor hurts (.592 all-play, even
with .591 for drafting with no QB opinion at all). What *does* hurt
is waiting past round 10 and planning to stream off waivers: −2.9
points, because most years the wire holds no good QBs. Sweet spot:
take a top-6 QB in rounds ~3–6 (finding 14 sweeps every round: 4–6
is the peak).

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

## Update 2026-08-02 (environment v5, independent confirmation)

The wait-cost drafter (`pick_value`) spends 18% of its first-three
picks on QB when left alone. Banning that (`pv_late_qb`, no QB before
r6) moves it +0.005 ± 0.010 in the family room — nothing — which is
this finding's "fairly priced" claim re-derived from a different
direction at v5. In the *sharp* room (finding 03) the same ban
*costs* −0.008: against opponents who don't let QBs slip ~7 picks the
way the family does, the early-QB option has real value. Both rooms
agree the late-QB plan is the losing one.

The hindsight-optimal drafts (finding 24, 2026-08-03) explain *why*
the option prices fairly: the oracle buys the season's actual QB1 in
rounds 2–3 in 69 of 72 optimal drafts. The right QB is a round-2
bargain every year — "fairly priced" is entirely a statement about
not knowing which one it is.

## Caveats

- Early QB's .592 is *par vs BPA's .591*, not an edge — the finding
  kills late-QB dogma rather than crowning early-QB.
- The 4-pt pass TD setting matters: at 6 points, early QB would likely
  become an outright edge (untested here).
- Late QB fails partly through the sim's streaming policy; a manager
  with elite QB-picking instincts could do better than the bot, but
  the supply numbers above bound how much better.
