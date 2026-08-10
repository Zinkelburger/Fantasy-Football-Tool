# 08 — Mid-round alpha WRs on doubted teams nearly double the hit rate

**Confidence: Medium** inside the mid-round window this page tests.
**The edge does not generalize** — see the correction below.

> **Corrected 2026-08-06.** Re-run at every price over ten drafts
> (2016–2025, `scripts/wr_archetypes.py --full`) instead of the 36–120
> slice below. Board-wide the archetype looks even better than this
> page claims — 44% top-24 against 29% for other WRs, a +15 point gap
> whose CI excludes zero. That gap is **price mix, not an edge.**
> Bad-team WR1s are disproportionately early picks (30% of them cost a
> top-three-round pick, against 18% of other WRs), and ~two thirds of
> *any* WR at that price finishes top-24. Standardizing each band's
> gap to the peers' price mix leaves **+7 points [−4, +20]** — no
> longer distinguishable from zero. Split by era it flips sign (−7.2
> in 2016–20, +1.6 in 2021–25).
>
> **"But he has more upside" — checked, no.** The obvious objection to
> the above is that hit rate measures competence, not ceiling: the
> reason to reach for the alpha on a bad roster is the WR1-overall
> season. Price-standardized, that is not there either — top-5 −2.3
> [−5.8, +1.4], top-12 −1.6 [−7.6, +4.9], beating his price by 40+
> ranks +2.2 [−6.3, +14.5]. His 75th and 90th percentile price-adjusted
> finishes (+22.2 and +36.2) sit *below* his peers' (+23.8 and +38.9)
> without any correction at all. Note the shape of the raw gap as the
> bar rises: +15 points at top-24, +3.8 at top-12, +0.8 at top-5. A
> real ceiling effect widens as the bar rises; price mix melts, which
> is what this does.
>
> The mid-round table below still stands as a description of that
> window. It is not a rule you can carry to another price, so the
> draft tool does not mark these players at all.

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

Examples from inside the window: McLaurin 2024 (WAS, 24% prior wins,
team-WR1) went as the WR32 and finished WR5. Olave 2025 (NO, 29%,
team-WR1) went WR34 and finished WR6. JSN 2025 fits the spirit —
Seattle's clear alpha after the Metcalf trade, doubted offense, WR14
price to WR2 — but his ADP of 30 sits just above this cohort's band.

## Why it works

- Bad teams trail, so they pass. The alpha concentrates targets.
- Standard scoring pays yardage, which garbage time supplies freely.
- The market prices the *team* narrative into the *player*. Target
  share transfers value even when the team stays bad.

The inverse cell fits the story. Mid-round **WR1s on good teams** bust
46% of the time. Those are often aging vets priced on reputation — the
Cooper/Tyreek shape (findings 09–10).

## Update 2026-08-06: does room rank work on its own?

The correction above killed the *bad-team* half of the archetype. The
obvious follow-up is the other half, asked in the form a drafter
actually faces: forget the team's record — is this receiver his own
offense's first, second or third option? That is knowable on the clock
from the board itself, which would make it the cheapest read here.

Tested board-wide on 701 priced WR seasons, 2016–2025
(`scripts/wr_room_rank.py`). Raw, it looks overwhelming:

| Room rank by ADP | n | Median ADP | Top-24 | Bust (>WR45) |
|---|---|---|---|---|
| His team's WR1 | 315 | 44 | **48%** | 32% |
| WR2 | 256 | 104 | 24% | 51% |
| WR3 | 98 | 149 | 8% | 68% |
| WR4 | 26 | 228 | 0% | 85% |

And that table is almost entirely price. Room rank *is* a price
variable — the median team-WR1 costs pick 44, the median WR2 costs pick
104. Standardized to the peers' price mix, the way the correction above
demands:

| Test | Cohort | Top-24 gap, price-matched |
|---|---|---|
| Not his team's WR1 | 386 vs 315 | −15.0% [−30.0%, +0.8%] |
| **…in the mid-round window (ADP 36–120)** | 179 vs 157 | **−4.9% [−15.2%, +5.8%]** |
| …rounds 4–7 only | 83 | −6.3% [−19.8%, +7.3%] |
| …rounds 8–12 only | 94 | −1.1% [−15.4%, +11.8%] |

**No mark.** The board-wide gap crosses zero, and inside the very
window this page is written from it is −4.9% — indistinguishable from
nothing. Whatever "he's only the WR2 on his own team" tells you, the
draft board has already charged for it.

One cell did come back significant: receivers **third or lower** in
their own room bust 21 points more often than same-priced peers
(+21.3% [+1.7%, +37.7%], n=130), and leave-one-year-out never flips
(+14.5% to +26.0%). It still fails the bar, on the same test that sank
the headline archetype — the era split:

| Era | Bust gap, price-matched |
|---|---|
| 2016–20 | −1.9% [−25.2%, +31.3%] |
| 2021–25 | **+38.8% [+24.8%, +48.9%]** |

The entire effect lives in the second half of the sample. That is not
distinguishable from overfitting to the recent era, and
[finding 10](10-wr-age-effects.md) — the one WR archetype that earned a
draft-day mark — cleared this exact test by holding in *both* eras. So
this stays a note, not a rule. If it survives 2026–27 out of sample it
becomes interesting.

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
- Reproduce: `venv/bin/python scripts/wr_archetypes.py`; the room-rank
  update above is `venv/bin/python scripts/wr_room_rank.py`.

## Caveats

- n=47 in the headline cell. The 43%-vs-25% gap carries a CI of ±14
  points. Treat it as a strong lean, not a law.
- Thresholds (.45 wins, ADP 36–120, top-24) were chosen once, not
  scanned — and chosen after seeing the drafts that inspired the test.
  Future seasons are the out-of-sample check.
- This says who to pick within rounds 5–9. It is not a reason to spend
  more early picks on WRs (finding 02 still stands).
