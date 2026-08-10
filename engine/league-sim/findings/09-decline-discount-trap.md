# 09 — WRs coming off a collapse year bust more, at every age

**Confidence: Low.** **Retracted** — the effect does not replicate.
See the correction below.

> **Corrected 2026-08-06.** The n=17 headline was too thin to carry a
> claim this strong. Re-run at every price across ten drafts
> (2016–2025, `scripts/wr_archetypes.py --full`) the cohort grows to
> 44 fallen studs, and the trap disappears: **+2 points of top-24 rate
> [−11, +15]** against WRs costing the same pick, price-standardized.
> The raw board-wide gap is −2 points, also indistinguishable from
> zero. No price band shows it either — rounds 4–7, the window this
> page was written from, is −7 points with a CI from −30 to +20.
>
> "A cheap price on a former star means the market knows something"
> is the intuition. Over ten years the market simply priced him
> correctly: he does neither better nor worse than his cost. The
> draft tool now says that instead of calling him a trap.

The "he was great two years ago, he'll bounce back" buy is a trap.
Mid-round WRs who were top-20 two seasons ago and collapsed last
season busted **53%** of the time against 42% for other mid-rounders,
and finished 9 more spots below their cost on average. A cheap price
on a former star usually means the market knows something. This is not
the age discount (finding 10) or the bad-team discount (finding 08),
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
(n=8). Youth does **not** rescue the archetype.

## Why the market gets this one right

A production collapse has a cause that persists: declining
athleticism, a broken offense, a role lost to a younger teammate.
Survivorship memory makes the archetype *feel* +EV. Everyone remembers
Higgins '24; nobody remembers Golladay '21. It is the single
worst-performing discount type tested.

Jackels relevance: Amari Cooper '24 and Tyreek '25 sat next to this
profile. Tyreek is a boundary case — his 2024 was bad by his own
standards, not a sub-WR35 collapse. The rule: buy a mid-round discount
that comes from *team narrative* (08), not one that comes from the
player's own tape.

## Methodology

Same cohort machinery as finding 08 (`scripts/wr_archetypes.py`);
"fallen" flag = positional finish ≤20 in year−2 AND (>35 or no
qualifying season) in year−1, computed from 2018+ finish tables so
2020 draftees have full lookback.

## Caveats

- n=17 across six years. The bust-rate gap (53 vs 42) is ~1 SE wide.
- Medium confidence comes from the mechanism, the age-split
  consistency, and the lopsided tail — the busts are *total* zeroes
  (Golladay −56, Chark −88 vs cost).
- Definition sensitivity untested; top-20/35 thresholds chosen once.
- Hits cluster in players who kept elite target share during the down
  year (Diggs, Allen, Higgins). Target-share retention may be the real
  discriminator. Worth testing when 2026 data lands.
