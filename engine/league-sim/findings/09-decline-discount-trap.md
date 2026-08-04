# 09 — WRs coming off a collapse year bust more, at every age

**Confidence: Medium** (n=17; direction consistent across both age halves)

## TL;DR

Mid-round WRs who were top-20 two seasons ago but collapsed below
WR35 last season — the "he'll bounce back" discount buy — busted
**53%** of the time vs 42% for other mid-rounders, and their average
return ran 9 spots further below cost. The discount you're buying is
usually information, not opportunity. Distinguish this from the *age*
discount (finding 10) and the *team-narrative* discount (finding 08),
which behave differently.

## The data

Cohort: ADP 36–120, top-20 positional finish two years prior, >35 (or
absent) last year:

| Cohort | n | Top-24 | Bust (>45) | Avg vs cost |
|---|---|---|---|---|
| Fallen former stud | 17 | 29% | **53%** | **−23.7** |
| All other mid-round WRs | 189 | 33% | 42% | −15.0 |

The full list, best-to-worst outcome:

- **Hits (5):** Brandin Cooks '20, Stefon Diggs '25, Tee Higgins '24,
  Keenan Allen '23, JuJu Smith-Schuster '20
- **Meh (3):** Deebo Samuel '25, Diontae Johnson '23, T.Y. Hilton '20
- **Busts (9):** Jarvis Landry '21, Courtland Sutton '21, DeAndre
  Hopkins '22, Robert Woods '22, Kenny Golladay '21, Allen Robinson
  '22, Christian Kirk '24, Julio Jones '21, DJ Chark '21

Split by age: under-29 fallen studs busted 56% (n=9), 29+ busted 50%
(n=8) — youth does **not** rescue the archetype.

## Why the market gets this one right

A production collapse usually has a cause that persists: declining
athleticism, a broken offense, a role lost to a younger teammate.
Survivorship memory (everyone remembers Higgins '24, nobody remembers
Golladay '21) makes the archetype *feel* +EV when it's the single
worst-performing discount type tested.

Jackels relevance: Amari Cooper '24 and Tyreek '25 were adjacent to
this profile (Tyreek is a boundary case — his 2024 was bad-by-his-
standards rather than a sub-WR35 collapse). The clean rule: a
mid-round discount is buyable when it comes from *team narrative*
(08) and not buyable when it comes from the player's own tape.

## Methodology

Same cohort machinery as finding 08 (`scripts/wr_archetypes.py`);
"fallen" flag = positional finish ≤20 in year−2 AND (>35 or no
qualifying season) in year−1, computed from 2018+ finish tables so
2020 draftees have full lookback.

## Caveats

- n=17 across six years — the bust-rate gap (53 vs 42) is ~1 SE wide.
  What earns Medium confidence is the coherent mechanism, the
  age-split consistency, and the lopsided tail (the busts are *total*
  zeroes: Golladay −56, Chark −88 vs cost).
- Definition sensitivity untested (top-20/35 thresholds chosen once).
- Hits cluster in players who kept elite target share during the down
  year (Diggs, Allen, Higgins) — target-share retention may be the
  real discriminator, worth testing when 2026 data lands.
