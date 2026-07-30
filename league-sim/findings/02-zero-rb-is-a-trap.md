# 02 — Zero RB (and WR-heavy) are PPR imports: the costliest plans in this format

**Confidence: High** (simulation-verified, n=1,440 seasons each;
numbers are environment v3 — see finding 13's version table)

## TL;DR

Zero RB — the most popular "smart" strategy in fantasy content — is
the worst plan tested: **9.7% titles vs Robust RB's 20.3%**, i.e. it
forfeits half your championship equity, and its .548 all-play trails
every other disciplined strategy by 1.5–5 points. Against a noisy
human field even a bad plan beats baseline — the trap isn't losing to
the family, it's paying ~5 points of edge for a thesis the format
doesn't support. WR-heavy fails less badly (.585) for the same reason
in miniature.

## The data

From the same backtest as finding 01 (environment v3):

| Strategy | All-play | Playoffs | Titles |
|---|---|---|---|
| Robust RB (the alternative) | .598 | 74.2% | 20.3% |
| WR heavy | .585 | 72.8% | 15.8% |
| Zero RB | **.548** | **62.5%** | **9.7%** |
| Baseline (family mirror) | .500 | 50.2% | 7.6% |

Zero RB per-year: .525, .523, **.618**, .567, .522, .535. Its lone
good year is 2022 — the RB-bust season its thesis predicts — and even
then it merely matched plain BPA (.612) while Robust RB fell to .580.
One vindicating year in six, and the vindication was a tie with
having no thesis at all.

## Why the internet's favorite strategy fails here

Zero RB's logic requires at least one of:
1. **Receptions pay** (PPR) — inflating the WRs you hoard. Here they
   pay zero.
2. **A TE-eligible flex** — extra outlet for cheap pass-catcher value.
   Here the FLEX is RB/WR only.
3. **A deep RB waiver wire** to backfill mid-season. In a 12-team
   league the sim's emergent wire rarely holds startable RBs — the
   other eleven teams roster ~66 RB slots (and with news-aware
   claims, promoted handcuffs vanish instantly).

All three preconditions are absent in this league. The strategy is
calibrated for the formats podcasts assume, and nearly all mainstream
draft content assumes PPR.

## Methodology

Identical harness to finding 01 (METHODS.md). `ZeroRB` bans RB before
round 6, then attacks RB volume; `WRHeavy` soft-prefers WR rounds 1–6
without a hard ban. Both share the universal competence layer (need
filling, K last, QB/TE caps), so the failure is the *plan*, not
sloppiness. v1 of this finding said Zero RB lost to the family
outright (3.3% titles); under the properly-noisy v2/v3 bots any
discipline beats the family, so the claim is now correctly stated as
opportunity cost. Reproduce:
`venv/bin/python -m simfl.grid --heroes zero_rb,wr_heavy -n 240`.

## Caveats

- A Zero RB drafter with elite WR-picking skill could beat these bots
  — the sim tests the allocation, not talent evaluation.
- 2022 shows the thesis isn't insane, just mispriced for this format:
  it needs an RB-bust year merely to break even with BPA.
- If the league ever moves to PPR or adds TE to the flex, retest
  before repeating this claim.
