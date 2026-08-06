# 24 — Hindsight-optimal drafts: the ceiling is ~+685 pts, and it lives in the mid rounds

**Confidence: High** for the numbers — exact search, deterministic
opponents. The oracle has information, not skill.

## The ceiling

If you knew exactly how every player's season would go, what is the
best possible 15-round draft? Exact search, all 6 seasons, every draft
seat.

- **Even a perfect draft loses ~4% of its weekly head-to-heads**
  (1,894 pts/season, .964 all-play). Nothing removes variance.
- **Perfect foresight is worth ~+685 points a season** over a
  disciplined drafter. The gap between the best and worst disciplined
  strategies is ~17 points by the same yardstick. Draft-order
  cleverness fights over tens of points. Knowing which players will
  hit is worth hundreds. Player evaluation, not draft strategy, is the
  game.
- The search converged: beam 24 → 96 found identical solutions. These
  are true ceilings, not estimates.

## What perfect drafts look like (72 solutions)

| rnd | QB | RB | WR | TE | K | med reach vs ADP | undrafted% |
|---|---|---|---|---|---|---|---|
| 1 | 10% | **58%** | 32% | 0% | 0% | +4 | 0% |
| 2 | 36% | 25% | 29% | 10% | 0% | +3 | 0% |
| 3 | **50%** | 32% | 18% | 0% | 0% | +14 | 0% |
| 4–5 | 2% | **55%** | 42% | 1% | 0% | +8 | 3% |
| 6–8 | 0% | 44% | 28% | 28% | 0% | +13 | 17% |
| 9–13 | 20% | 24% | 44% | 16% | 0% | +12 | 36–58% |
| 14–15 | 1% | 21% | 27% | 2% | 50% | — | 54–83% |

Patterns, most transferable to a drafter *without* foresight first.

1. **RB1 overall is usually the right first pick even in hindsight.**
   58% of optimal drafts open RB, and the median round-1 RB bought is
   the season's actual RB1. The top of the RB curve is not a
   family-room artifact — it is finding 23's +35-pt same-rank premium
   seen from the other side.
2. **The actual QB1 season is worth a round-2/3 pick, and the oracle
   buys it in 69 of 72 drafts** (rounds 1–3, median finish rank
   bought: QB1). This is finding 06's "early QB is fairly priced" with
   the veil lifted: the *option* is fairly priced because you don't
   know which QB it is; the *right* QB is a bargain. Consistent with
   the sharp-room result, where early-QB access has real value.
3. **TE almost never deserves an early pick.** 3% of first-three
   picks, all generational seasons; median TE1 acquisition is round 7.
   Kicker: endgame, always (engine-enforced for everyone).
4. **Rounds 4–8 are where the season is won.** The oracle spends them
   RB-heavy, buying players who *finish* RB6–7 / WR2–4 at round-4–8
   prices. The market's biggest pricing errors — the difference
   between the 685-pt ceiling and the 17-pt heuristic spread —
   concentrate in the middle rounds, not round 1, where the oracle
   mostly agrees with ADP.
5. **Perfect drafters reach.** The median pick comes ~4–14 spots
   *ahead* of ADP in every round. Against a disciplined room, waiting
   for value never pays: anyone at market price gets taken at market
   price. Partly an artifact of deterministic opponents; a noisy room
   rewards slightly later timing.
6. **The endgame is for lottery stashes, not safe veterans.** 83% of
   final-round picks, and ~half of rounds 12–14, are players the market
   didn't draft at all (ADP > 180) — the season's wire heroes, drafted
   preemptively. With waivers on, this is the pool findings 22/05 show
   the league fights over.

## What transfers

The +685 is foresight, not achievable skill: which RB finishes RB6,
which undrafted WR breaks out, which QB has the QB1 season.

The transferable claims are structural — RB first, the QB timing
option, TE/K discipline, mid-round concentration of market error,
endgame lottery tickets.

All realistic heuristics land within ~17 pts of each other by this
same yardstick. That is finding 03's "discipline is ~90% of the edge"
restated at the ceiling. Past discipline, draft-order cleverness is
nearly exhausted. Further edge has to come from *player-level
information* (findings 15–18, 21's research direction) or from
in-season management, not sequencing.

## Methodology

`analysis/oracle_draft.py`. Deterministic BPA opponents make the
future board a pure function of the hero's picks, so the hero's
problem is a search tree: beam search (width 64), candidates pruned
to the top 3 RB/WR, top 2 QB/TE, top 1 K remaining by rest-of-season
points at each pick; legality identical to the engine's
(`DraftState` caps, endgame forcing, K timing). Evaluation:
hindsight-optimal weekly lineups (exact for this lineup structure),
weeks 1–14, no waivers for anyone. Beam-width sweep 24/48/64/96
returns identical optima (`--test`). Heuristic baselines drafted by
the real engine against the same 11 bots and scored by the same
hindsight-lineup evaluator, so the gap isolates draft selection.
All-play: hero vs the 11 bot rosters, everyone on hindsight lineups.
The 100%-K-in-round-14 cell is a tie-break artifact (K in 14 vs 15
yields identical rosters; the beam picks one).

## Caveats

- No waivers compresses reality. In the live sim the wire delivers
  part of what the oracle drafts in rounds 10–15, so the practical
  ceiling over a waiver-active manager is smaller than 685.
- Deterministic opponents overstate the reach-ahead-of-ADP pattern.
  Against noisy rooms the optimal timing shifts later.
- Hindsight lineups inflate *absolute* points for oracle and baselines
  alike (~134/wk vs ~86 realistic). Only gaps and shares are
  meaningful.
- 4-pt passing TDs. The QB1-in-round-2/3 pattern would strengthen at 6
  points, weaken in 2-QB-less formats with deeper benches.
