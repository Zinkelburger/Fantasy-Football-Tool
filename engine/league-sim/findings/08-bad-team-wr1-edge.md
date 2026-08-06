# 08 — Mid-round alpha WRs on doubted teams nearly double the hit rate

**Confidence: Medium.** n=47 in the key cell. Clear effect, one era
window.

In the middle rounds, take a team's clear #1 receiver on a team coming
off a losing season. Those WRs finished top-24 **43%** of the time
against **25%** for mid-round WRs with neither trait. Bad teams still
throw to somebody. The market discounts the whole roster, and the
alpha receiver is the mispriced part.

## The data

All drafted WRs with ADP 36–120, 2020–2025 (n=206):

| Archetype | n | Top-24 finish | Bust (>WR45) | Avg finish vs cost |
|---|---|---|---|---|
| **Team-WR1 + bad prior team** | 47 | **43%** | **38%** | −14.0 |
| Team-WR1, decent team | 52 | 37% | 46% | −21.9 |
| Not WR1, bad team | 30 | 30% | 33% | −9.3 |
| Neither | 77 | 25% | 47% | −15.0 |

Every cell is negative on "vs cost." Mid-round WRs as a class
underperform their ADP slot. The archetype question is *which* ones
salvage it.

Jackels case studies: McLaurin 2024 (WAS, 24% prior wins, team-WR1)
went as the WR32 and finished WR5. Olave 2025 (NO, 29%, team-WR1) went
WR34 and finished WR6. JSN 2025 fits the spirit — Seattle's clear
alpha after the Metcalf trade, doubted offense, WR14 price to WR2 —
but his ADP of 30 sits just above this cohort's band.

## Why it works

- Bad teams trail, so they pass. The alpha concentrates targets.
- Standard scoring pays yardage, which garbage time supplies freely.
- The market prices the *team* narrative into the *player*. Target
  share transfers value even when the team stays bad.

The inverse cell fits the story. Mid-round **WR1s on good teams** bust
46% of the time. Those are often aging vets priced on reputation — the
Cooper/Tyreek shape (findings 09–10).

## Methodology

- Cohort: WRs on the year's 12-team standard ADP board, 36 ≤ ADP ≤ 120
  (≈ rounds 4–10).
- "Team-WR1" = lowest ADP among same-NFL-team WRs that season.
- "Bad prior team" = previous season win% ≤ .45 (nflverse schedules).
- Outcomes: positional finish by season total among all WRs. Busts
  from injury count as busts — that's the real risk you buy.
- Known impurity: NFL team is the nflverse *latest* team that season,
  so mid-season trades (Cooper '24 CLE→BUF) can misattribute. A few
  players of ~206 affected, both directions.
- Reproduce: `venv/bin/python scripts/wr_archetypes.py`.

## Caveats

- n=47 in the headline cell. The 43%-vs-25% gap carries a CI of ±14
  points. Treat it as a strong lean, not a law.
- Thresholds (.45 wins, ADP 36–120, top-24) were chosen once, not
  scanned — and chosen after seeing the Jackels picks that inspired
  the test. Future seasons are the out-of-sample check.
- This says who to pick within rounds 5–9. It is not a reason to spend
  more early picks on WRs (finding 02 still stands).
