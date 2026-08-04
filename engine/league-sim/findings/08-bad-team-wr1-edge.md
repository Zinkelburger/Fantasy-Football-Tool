# 08 — Mid-round alpha WRs on doubted teams nearly double the hit rate

**Confidence: Medium** (n=47 in the key cell; clear effect, one era window)

## TL;DR

In the middle rounds, target a team's clear #1 receiver on a team
coming off a losing season. Those WRs finished top-24 **43%** of the
time vs **25%** for mid-round WRs with neither trait — nearly double
the hit rate. Bad teams still throw to somebody: the market discounts
the whole roster, and the alpha receiver is the mispriced part.

## The data

All drafted WRs with ADP 36–120, 2020–2025 (n=206):

| Archetype | n | Top-24 finish | Bust (>WR45) | Avg finish vs cost |
|---|---|---|---|---|
| **Team-WR1 + bad prior team** | 47 | **43%** | **38%** | −14.0 |
| Team-WR1, decent team | 52 | 37% | 46% | −21.9 |
| Not WR1, bad team | 30 | 30% | 33% | −9.3 |
| Neither | 77 | 25% | 47% | −15.0 |

(Note all cells are negative on "vs cost" — mid-round WRs as a class
underperform their ADP slot; the archetype question is *which* ones
salvage it.)

Jackels case studies: McLaurin 2024 (WAS, 24% prior wins, team-WR1;
went as the WR32 → finished WR5), Olave 2025 (NO, 29%, team-WR1;
WR34 → WR6). JSN 2025 fits the spirit (Seattle's clear alpha after
the Metcalf trade, doubted offense, WR14 price → WR2), though his ADP
(30) sits just above this cohort's band.

## Mechanism (why this isn't just a quirk)

- Bad teams trail → pass volume; the alpha concentrates targets.
- Standard scoring pays yardage, which garbage time supplies freely.
- The market prices the *team* narrative into the *player*, but target
  share transfers value even when the team stays bad.

The inverse cell supports the story: mid-round **WR1s on good teams**
(46% bust) are often aging vets whose price rests on reputation —
the Cooper/Tyreek shape (see findings 09–10).

## Methodology

- Cohort: WRs on the year's 12-team standard ADP board, 36 ≤ ADP ≤ 120
  (≈ rounds 4–10).
- "Team-WR1" = lowest ADP among same-NFL-team WRs that season.
- "Bad prior team" = previous season win% ≤ .45 (nflverse schedules).
- Outcomes: positional finish by season total among all WRs (busts
  from injury count as busts — that's the real risk you buy).
- Known impurity: NFL team is the nflverse *latest* team that season,
  so mid-season trades (Cooper '24 CLE→BUF) can misattribute; a few
  players of ~206 affected, both directions.
- Reproduce: `venv/bin/python scripts/wr_archetypes.py`.

## Caveats

- n=47 in the headline cell: the 43%-vs-25% gap is large but its CI is
  ±14 points. Treat as a strong lean, not a law.
- Thresholds (.45 wins, ADP 36–120, top-24) were chosen once, not
  scanned — but they were still chosen *after* seeing the Jackels
  picks that inspired the test. Out-of-sample confirmation = future
  seasons.
- The edge is about *who to pick within rounds 5–9*, not a reason to
  spend more early picks on WRs (finding 02 still stands).
