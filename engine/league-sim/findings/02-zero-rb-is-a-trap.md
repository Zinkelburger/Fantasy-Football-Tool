# 02 — Zero RB (and WR-heavy) are PPR imports: the costliest plans in this format

**Confidence: High.** 1,440 simulated seasons each. Environment v3 —
see finding 13's version table.

Zero RB — skipping running backs early to load up on receivers — is
the most popular "smart" strategy in fantasy content. In this format
it was the worst plan we tested: **9.7% championship rate vs 20.3%**
for opening RB-RB-RB. That's half your title odds, gone. The strategy
was built for PPR leagues, where every catch scores a point. In
standard scoring with an RB/WR flex there is no cheap way to make up
the running back points you passed on. WR-heavy fails the same way,
just less badly (.548 vs .585 all-play, both behind every other
disciplined plan).

## The data

From the same backtest as finding 01 (environment v3):

| Strategy | All-play | Playoffs | Titles |
|---|---|---|---|
| Robust RB (the alternative) | .598 | 74.2% | 20.3% |
| WR heavy | .585 | 72.8% | 15.8% |
| Zero RB | **.548** | **62.5%** | **9.7%** |
| Baseline (family mirror) | .500 | 50.2% | 7.6% |

Zero RB per-year: .525, .523, **.618**, .567, .522, .535. Its one
good year is 2022, the RB-bust season its thesis predicts. Even then
it merely matched plain BPA (.612) while Robust RB fell to .580. One
vindicating year in six, and the vindication was a tie with having no
thesis at all.

## Update 2026-08-03: the MockoScience imports (environment v5)

A league-mate surfaced the r/fantasyfootball "MockoScience 2025 PPR"
permutation study. We imported its four named strategies not already
tested here (their definitions, credited — `DualWRRB`,
`ThreePillars`, `Rainbow`, `HeroWR` in `simfl/strategies.py`) and ran
them in our format (12T **STD**, RB/WR flex; v5, n=432 paired vs
robust_rb):

| Strategy (their def) | All-play | Titles | paired Δ vs robust_rb |
|---|---|---|---|
| Dual WR-RB (2+2 by r5, *their #1*) | .595 | 18% | **−0.016 ± 0.011** |
| Hero WR | .594 | 22% | −0.017 ± 0.011 |
| Three Pillars (QB/RB/WR by r3) | .568 | 19% | −0.043 ± 0.013 |
| Rainbow (QB/WR/RB/TE by r4) | .561 | 12% | **−0.050 ± 0.013** |

Their own caveat ("applicable only to PPR — HPPR results are way more
RB heavy") is exactly right, one format further. The loss ordering
tracks how many early picks each shape diverts from the RB curve
(finding 23's 45%-steeper decay). Rainbow also pays the early-TE tax
(finding 05). Their #1 PPR strategy is a significant loser here.
Format is not a detail; it's most of the answer.

Their per-seat claim (slots 1–4 and 10–12 best) is unresolvable at
this sample (36–72 leagues/seat, se ≈ .015). The family-null room
shows no seat effect beyond noise; robust_rb hints at late-middle
seats. Proper test remains backlog B8.

## Why it fails here

Zero RB's logic requires at least one of:

1. **Receptions pay** (PPR) — inflating the WRs you hoard. Here they
   pay zero.
2. **A TE-eligible flex** — extra outlet for cheap pass-catcher
   value. Here the FLEX is RB/WR only.
3. **A deep RB waiver wire** to backfill mid-season. In a 12-team
   league the sim's emergent wire rarely holds startable RBs — the
   other eleven teams roster ~66 RB slots, and with news-aware claims
   promoted handcuffs vanish instantly.

All three are absent in this league. The strategy is calibrated for
PPR, and nearly all mainstream draft content assumes PPR.

## Methodology

Identical harness to finding 01 (METHODS.md). `ZeroRB` bans RB before
round 6, then attacks RB volume; `WRHeavy` soft-prefers WR rounds 1–6
without a hard ban. Both share the universal competence layer (need
filling, K last, QB/TE caps), so the failure is the *plan*, not
sloppiness. v1 of this finding said Zero RB lost to the family
outright (3.3% titles); under the properly-noisy v2/v3 bots any
discipline beats the family, so the claim is now stated as
opportunity cost. Reproduce:
`venv/bin/python -m simfl.grid --heroes zero_rb,wr_heavy -n 240`.

## Caveats

- A Zero RB drafter with elite WR-picking skill could beat these
  bots. The sim tests the allocation, not talent evaluation.
- 2022 shows the thesis isn't insane, just mispriced for this format:
  it needs an RB-bust year merely to break even with BPA.
- If the league moves to PPR or adds TE to the flex, retest before
  repeating this claim.
