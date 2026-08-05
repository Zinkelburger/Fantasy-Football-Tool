# 29 — What hits, round by round (and the answer barely changes in PPR)

**Confidence: Medium-High** for the hit-rate structure and the
format-invariance (1,489 drafted players over eight ADP boards, all
three scorings, per-season stability shown below); **Medium** for the
trait profile of late hits (significant, but found by exploration in
this same sample — treat as pre-registered only from 2026 forward).

## TL;DR

Eight years of draft boards, scored three ways. Starter-rate falls
smoothly from ~81% in round 1 to ~5% in round 15, and the shape is the
same in standard, 0.5PPR, and full PPR — only 3.8% of drafted RB/WR
seasons flip top-24 status between standard and PPR. The "stash
running backs late" instinct fails: late-round WRs hit slightly MORE
than late RBs in every format (the gap is inside noise, so treat it as
"no RB edge exists", not "WRs are the play"). What does separate late
hits from late busts: youth at the pass-catching positions — late WR
hits are 1.7 years younger than the busts, TE hits 1.9 years, both
p ≈ 0.01 — and position: TE and QB remain ~40-50% likely to return a
starter as late as rounds 9-11, when RB and WR are already lotteries.

## The data

Every player with an ADP on our 12-team boards, 2018-2025 (n = 1,489
after ~2 name mismatches a year). Round = ceil(overall ADP / 12),
capped at 15. Outcome = positional finish by season TOTAL points
(health and volume count — that is what wins leagues), scored three
ways with the league's exact per-category floors
(`analysis/player_model.py league_pts`). Cuts: **starter** = top-12
QB/TE, top-24 RB/WR; **usable** = top-18/36; **smash** = top-6/12. A
drafted player with no season counts as a bust, not missing data.

## Starter-hit rate by round band (std / half / ppr)

| Band | QB | RB | WR | TE |
|---|---|---|---|---|
| R1-2 | 91/91/91 (n=11) | 76/76/76 (n=104) | 67/69/69 (n=72) | 100/100/100 (n=7) |
| R3-5 | 62/62/62 (n=34) | 50/49/50 (n=107) | 54/53/52 (n=127) | 60/57/57 (n=30) |
| R6-8 | 55/55/55 (n=44) | 32/34/34 (n=96) | 30/29/29 (n=113) | 51/43/49 (n=35) |
| R9-11 | 41/41/41 (n=51) | 12/11/12 (n=92) | 17/18/19 (n=94) | 43/49/51 (n=37) |
| R12-15 | 16/16/16 (n=74) | 7/7/6 (n=133) | 8/8/8 (n=156) | 22/25/25 (n=72) |

Per-round (all positions pooled, std): 81, 68, 63, 54, 44, 46, 32,
34, 27, 20, 24, 15, 21, 7, 5.

Reading it: the QB/TE columns stay startable absurdly deep because
"startable" is top-12 at a 12-team position — which is exactly why
[finding 05](05-never-pay-up-for-te.md) and
[finding 06](06-qb-timing.md) say what they say. RB and WR fall off a
cliff after round 8.

## Late rounds: the RB-stash myth

Rounds 9-15, starter rate:

| Format | RB | WR | diff | p (permutation) |
|---|---|---|---|---|
| std | 8.9% (n=225) | 11.2% (n=250) | −2.3% | 0.43 |
| half | 8.4% | 11.6% | −3.2% | 0.29 |
| ppr | 8.4% | 12.0% | −3.6% | 0.22 |

The RB-minus-WR gap was negative in six of eight seasons (std). None
of it is significant — the honest headline is "late RBs do NOT hit
more than late WRs", in any format, and PPR tilts what little there
is further toward the receivers. The appeal of the late RB is
conditional value — the handcuff who pays exactly when your starter
sits ([finding 13](13-handcuffs-are-free-insurance.md)) — not
season-long hit rate, and deliberately tilting a bench toward RBs
bought ~1% of championships
([finding 19](19-bench-composition.md)).

## What a good late pick looks like

Hits vs busts, rounds 9-15, permutation p on the age gap:

| Pos | hits | age: hit − bust | p |
|---|---|---|---|
| WR | 28 | **−1.73 years** | 0.011 |
| TE | 32 | **−1.89 years** | 0.009 |
| RB | 20 | +0.16 | 0.84 |
| QB | 33 | −0.67 | 0.57 |

Pooled WR+TE: −1.48 years, p = 0.002. Rookie share alone is not
significant (+8% WR, p = 0.33) — it is youth generally, not rookies
specifically. Prior-year volume (targets/carries per game) separates
nothing late — everyone available in round 11 had a mediocre role
last year; that is why they are available. At RB no observable trait
separated late hits from busts: a late RB is a lottery ticket, and
the only structure we know of is the handcuff link above.

Suggestive but thin (noted, not claimed): in rounds 6-8, rookie RBs
were 6% of hits but 23% of busts — the mid-priced rookie RB in a
murky committee looks like the worst version of the position.

## Formats: checked, and it barely matters

- 41 of 1,068 drafted RB/WR seasons (3.8%) flip top-24 status
  between standard and full PPR.
- The band table above moves by 0-8 points of hit rate; no ordering
  changes. PPR's only consistent lean: late WR/TE gain a little.
- The three per-player repricing findings re-run under each format
  (`analysis/format_check.py`): TD luck
  ([16](16-td-luck-regresses.md)) stays negative (−0.151 std /
  −0.131 half / −0.116 ppr, 7 of 8 season pairs negative in each);
  WR targets ([17](17-buy-targets-not-efficiency.md)) stay positive
  but smaller in PPR (+0.194 → +0.108; receptions being points means
  current PPR scoring already carries much of the volume signal);
  hot finishes ([15](15-late-season-momentum-myth.md)) stay ~zero
  everywhere (+0.04 to +0.05).

So: strategy built on standard scoring transfers. The one caveat we
have NOT retested under PPR is the simulation family (zero-RB, round
sweeps, bench composition — findings 01/02/14/19/22); those sims run
the family's standard league and a PPR re-run is queued behind the
env-v5 rerun.

## Methodology

`analysis/round_profile.py` (tables 1-5 printed; per-pick rows in
`data/market/round_profile.csv`), `analysis/format_check.py` for the
format re-runs. ADP from `data/adp_YYYY.json` (FantasyPros wayback);
finishes from cached nflverse weeklies; ages from roster birthdates
at Sept 1; rookie = `rookie_years.json` match. Permutations shuffle
labels within season (5,000 draws).

## Caveats

- The trait analysis (age of late hits) was found by exploring this
  sample, not pre-registered — the 2026 season is its first
  out-of-sample test. The band hit rates and the RB/WR null carry no
  such caveat; they are direct tabulations with stable per-season
  signs.
- "Starter by season total" rewards health. A per-game definition
  shrinks every gap slightly but reorders nothing we report.
- One ADP source per year; late-round ADP is soft everywhere.
