# 11 — The Methuen Jackels audit: best drafts in the league, two leaks

**Confidence: High** (it's the league's own data, fully enumerated)

## TL;DR

2024: the **#1 draft haul of all 12 teams**. 2025: #4. Combined 24-4,
double #1 seeds, double runner-up (see finding 12 for why that isn't a
process indictment). The repeatable strengths: value patience, elite
mid-round WR selection, correct QB and kicker timing. The leaks:
paying premium prices for TEs (twice) and the round-4/5 discounted
veteran WR (twice).

## Draft-by-draft

### 2024 (seat 6) — grade: A

| Rd | Pick | vs ADP | Outcome |
|---|---|---|---|
| 1 | CeeDee Lamb (#6) | +4 | WR10, fine |
| 2 | Derrick Henry (#19) | fell 9 | **RB2, 304 pts** |
| 3 | Josh Allen (#30) | fell 6 | **QB2, 364 pts** |
| 4 | Josh Jacobs (#43) | fell 27 | **RB5, 243 pts** |
| 5 | Amari Cooper (#54) | fell 8 | WR60 — leak #2 |
| 6 | Tee Higgins (#67) | fell 13 | WR14 |
| 7 | Terry McLaurin (#78) | fell 14 | **WR5, 180 pts** |
| 8 | Dalton Kincaid (#91) | fell 21 | TE27 — leak #1 |
| 9–14 | Moss, Hubbard, Doubs, Mitchell, Davis, Wright | | Hubbard → RB13; rest mostly missed |
| 16 | Younghoe Koo (last real pick) | | PK20 — correct timing, irrelevant outcome |

Haul: **1,779** perfect-lineup points — #1 of 12 (2nd place 1,699).
Nearly every pick arrived *below* market price: patience, not reaching.

### 2025 (seat 11) — grade: B+

| Rd | Pick | vs ADP | Outcome |
|---|---|---|---|
| 1 | Amon-Ra St. Brown (#11) | +2 | **WR3** |
| 2 | Bucky Irving (#14) | reach 2 | RB35 (injury) |
| 3 | Jaxon Smith-Njigba (#35) | fell 5 | **WR2, 232 pts** |
| 4 | Tyreek Hill (#38) | fell 8 | WR104 (season-ending injury) |
| 5 | Patrick Mahomes (#59) | par | QB11, fair |
| 6 | Sam LaPorta (#62) | fell 4 | TE24 — leak #1 again |
| 7 | Croskey-Merritt (#83) | **reach 102** | RB28 — bold, worked out par |
| 8 | Chris Olave (#86) | fell 14 | **WR6, 159 pts** |
| 9–14 | Judkins (RB26 ✓), White, Ford, Najee (6 pts), **Dowdle (RB17 ✓)**, Burden | | |
| 15 | Chad Ryland | | PK19 — correct timing |

Haul: **1,529** — #4 of 12. The gap to 2024 is mostly three injury
wipeouts (Tyreek + Irving + Najee = 138 combined points).

## League-wide draft-haul ranks

Perfect-lineup points from drafted rosters only (isolates drafting
from waivers/lineup skill):

- **2024:** Jackels 1779 · Rubber Ducks 1699 · **Bombers 1672 (champ)** ·
  Lancers 1629 · … · Cape Crusaders 1178
- **2025:** Bombers 1657 · Poptarts 1622 · Parent Trap 1535 ·
  **Jackels 1529** · … · **Buckhead Bullies 1380 (champ, 7th)** ·
  Rubber Ducks 1089

## Hindsight replays

Replaying each draft pick-by-pick with perfect knowledge of the
season (opponents' picks held fixed, take the best-total legal player
at each Jackels slot): the clairvoyant 2024 roster delivers 2,189
points → **the real draft captured 81% of theoretical perfection**
(74% in 2025). More telling: the clairvoyant drafts *keep most of the
actual picks* — 2024's keeps Henry, Jacobs, Hubbard, McLaurin, Lamb,
Higgins; 2025's keeps JSN, ASB, Olave, Dowdle, Judkins,
Croskey-Merritt. The player identification is near-optimal; the
residual gap is concentrated in the two leaks plus injury luck.

## The two leaks, quantified

1. **TE price** (see finding 05): Kincaid pick 91 → 53 pts; LaPorta
   pick 62 → 62 pts. Two years, two premium slots, TE27/TE24 returns,
   while ~free TEs (Jonnu 126, Goedert 118) outscored both.
2. **Discounted veteran WR in rounds 4–5** (findings 09–10): Cooper
   '24 (age 30) → 74 pts; Tyreek '25 (age 31) → 30 pts. Cooper fits
   the flagged profiles; Tyreek is defensible-but-unlucky (age bucket
   unresolved, finding 10). Combined cost vs their slot expectation:
   roughly a top-20 WR season's worth of points across two years.

## Methodology

- Source: ESPN league exports (`data/espn/league_{2024,2025}.json`),
  picks joined to nflverse via `load_ff_playerids` (ESPN id → gsis id),
  scored under league-exact settings.
- "Draft haul" = points a roster would score with a *perfect* lineup
  set every week (upper bound; removes lineup-skill and waiver
  effects). Same formula for all 12 teams.
- Hindsight replay rules: at each Jackels pick, choose the maximum
  season-total player not yet drafted by anyone at that moment,
  subject to roster legality (fill all starting slots, positional
  caps, K at the end). Opponents' actual picks stand.
- Reproduce: `venv/bin/python scripts/jackels_review.py`.

## Caveats

- "Perfect lineups" flatter everyone equally; relative ranks are the
  meaningful part.
- Hindsight replays are a ceiling no human reaches — 81% capture is
  the headline *because* the ceiling is absurd.
- D/ST picks excluded throughout (not modeled).
