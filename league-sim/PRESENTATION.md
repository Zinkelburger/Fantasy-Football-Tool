# How to Win Our League

### Backtested strategy for a 12-team ESPN standard league, 2020–2025

Every claim below comes from `league-sim`: real draft boards (ADP),
real weekly NFL results, and ~13,000 fully simulated seasons — snake
draft, weekly lineups, waivers with rolling priority, playoffs. Not
best-ball; the bots manage their teams all season using only
information available at the time. The "family field" drafts off the
rankings with realistic human noise, likes RBs and rookies, and picks
up whoever just had a big game — competent, balanced, normal.

Our format matters for everything that follows: **non-PPR, whole-point
scoring, 4-pt pass TD, FLEX takes RB/WR only, no TE**.

---

## 1. What a starter is worth — `fig1_scarcity.png`

Average PPG by positional rank, 2020–2025. Three facts fall out:

- **RB value collapses fast**: RB1 ≈ 19 ppg, RB10 ≈ 12, RB22 (a
  typical RB2/flex) ≈ 10. The top of the position is where the points
  live.
- **WR is flatter**: WR1 ≈ 16, WR16 ≈ 9.5. Mid WRs are replaceable;
  in *our* league they can't even flex into a TE slot to gain value.
- **Kickers are interchangeable**: K1 to K16 is ~3 ppg. TE after the
  elite three is scrubs all the way down (TE7 ≈ 7 ppg).

## 2. The tournament — `fig4_strategies.png` (headline slide)

Each strategy played 1,440 seasons (240 per year, every draft seat)
against eleven family drafters:

| Strategy | All-play | Playoffs | Titles | (baseline 8.3%) |
|---|---|---|---|---|
| **Robust RB (RB-RB-RB)** | **.518** | **53%** | **11.2%** | **+35% titles** |
| Early QB | .502 | 51% | 7.6% | par |
| Family baseline | .500 | 51% | 7.6% | (the null works) |
| Hero RB | .495 | 47% | 8.1% | par |
| Punt TE + stream | .494 | 49% | 8.1% | par |
| BPA (follow ADP exactly) | .491 | 48% | 8.2% | par |
| Late-round QB | .466 | 41% | 6.3% | −24% titles |
| WR heavy | .463 | 39% | 4.4% | −47% titles |
| Zero RB | .459 | 40% | 3.3% | −60% titles |

**The finding: in this format, the draft is won at running back, early.**
Hammering RB with the first three picks is the only strategy that
beats a competent field — 35% more championships than baseline.

**The anti-finding is bigger: Zero RB — the internet's favorite
strategy — is a catastrophe here.** It's built for PPR leagues where
receptions pay and the flex takes TEs. Import it into standard scoring
and you win 60% fewer titles. WR-heavy fails the same way. Podcast
advice is calibrated to a format we don't play.

Also delicious: following ADP perfectly (.491) is *no better* than the
family's noisy, biased drafting (.500). Discipline isn't the edge.
Positional allocation is.

## 3. Honesty slide — `fig5_heatmap.png`

Robust RB is not safe, it's *correct on average*: it posted .57, .57,
.59 in 2021/2024/2025 and got wrecked (.43) in 2022–23 when the top
RBs busted. Six seasons is a small sample; the claim is "best expected
value," not "wins every year." Show this slide so nobody calls the
backtest cherry-picked when their RB1 tears an ACL.

## 4. Position mini-verdicts

**Kickers — `fig2_kicker_persistence.png`.** The week-1 top kicker
finished rest-of-season #27, #19, #18, #10, #27 (2020–24); in 2025 he
lost the job entirely. Weeks 1–4 leaders do no better. Draft any
kicker with your last pick, only swap on byes. Never chase.

**TE — `fig3_te_supply.png`.** Every year, half the rest-of-season
top-8 TEs cost a round-8+ pick or nothing (LaPorta ADP 160, Goedert
142, Fannin 248). But note the trend: true free-agent top-8 TEs went
3, 2, 3 in 2020–22, then 0, 1, 0 in 2023–25 — the *pure* wire play
dried up. Verdict: never pay up early, take a TE round 10+, stream
only if he busts. Full punt-and-stream sims out neutral (.494), not
winning.

**QB — `fig6_qb_cost.png`.** Even at 4-pt pass TDs, early QBs return
real points (median ~21 ppg at ADP 20 vs ~13 at ADP 170) — and the
sim agrees the price is roughly fair: Early QB .502, par. But *Late-
round QB + streaming* costs (.466): the wire held zero rest-of-season
top-8 QBs in two of six years. Verdict: take a QB when the value
comes (rounds 3–6); don't build a plan around finding one on waivers.

## 5. What to actually do at our draft

1. **Rounds 1–3: running backs.** Yes, all three, unless something
   absurd falls.
2. Rounds 4–6: best WR available; take the QB when a top-6 one is
   still there.
3. TE in round 10 or later. Never earlier.
4. Kicker with the last pick. Any of them.
5. In-season: fix bye/injury holes immediately, judge free agents on
   *this season's* production (pedigree lies), don't cut early picks
   in September, and don't chase last week's box score.

## Method appendix (one slide, small font)

- Data: FantasyFootballCalculator 12-team standard ADP 2020–24 (with
  real per-pick stdev, used for the family noise model); 2025 ADP from
  a Wayback Machine snapshot of FantasyPros standard consensus;
  weekly stats via nflverse.
- No decision in the sim uses future information. Preseason
  expectations come from the previous season's positional curves.
- Drafted players who missed their whole season (Watson '21,
  Mixon '25) stay draftable — busts are part of history.
- Validation: a family bot inside the family field scores all-play
  .500 and titles ≈ 1/12 in every season.
- Caveats: six seasons; strategies tested against *this* family
  model; waiver behavior is stylized; D/ST ignored (last-round pick,
  different mechanics).

*Everything is reproducible: `python -m simfl compare`,
`python -m simfl analyze ...`, `python -m simfl.plots` in
`league-sim/`.*
