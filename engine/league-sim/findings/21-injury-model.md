# 21 — The injury model: what a Friday tag is actually worth

**Confidence: High** for P(play | status) and the Questionable
discount, n=991 played-while-listed weeks. **Medium** for per-injury
durations (n=28–111 per type) and the rust effect.

## What a Friday tag means

Eight years of injury reports.

**Out or Doubtful means he is not playing.** Play rates of 0.1% and
1%. Treat both as zero.

**Questionable means 69% to play, at about 83% of his usual
production.** Nearly full strength for QBs. A real discount for TEs.

Once a player sits out with an injury, the typical absence is 2 weeks
and a quarter of the time he never plays again that season. The longer
he has been out, the worse the outlook: average total absence climbs
2.7 → 3.6 → 4.7 weeks as misses pile up. His first game back runs
15–25% below normal.

## 1. P(plays Sunday | Friday report status), 2018–2025

| Status | n | P(play) |
|---|---|---|
| Questionable | 1,689 | **69%** |
| Doubtful | 185 | 1% |
| Out | 1,065 | 0.1% |

By position, Questionable: WR 75%, TE 74%, RB 68%, **QB 47%**. A
listed QB is a coin flip to suit up. If he plays, he's fine.

## 2. Playing through it: points vs own healthy baseline

Healthy-week control, same leave-one-out ratio on unlisted weeks:
median 0.89. Single weeks always sit below a mean baseline, so compare
to 0.89, not to 1.0.

| | n | median ratio | EV (mean) ratio |
|---|---|---|---|
| All Questionable-played | 991 | 0.67 (vs 0.89 healthy) | **0.83** |
| QB | 89 | 0.89 | 0.88 |
| RB | 320 | 0.72 | 0.90 |
| WR | 486 | 0.61 | 0.80 |
| TE | 96 | 0.54 | **0.76** |

Rules of thumb: a Questionable **QB who plays is full price**; a
Questionable **RB** costs ~10%; a Questionable **WR** ~20%; a
Questionable **TE** ~25% — bench the TE on any close call.

## 3. Once he sits (Out/Doubtful), how long is he gone?

675 absence spells of fantasy-relevant players (≥3 games, ≥4 ppg):

| First-week injury | n | median wks | mean wks | P(never returns that yr) |
|---|---|---|---|---|
| Ankle | 111 | 2 | 2.8 | 28% |
| Knee | 103 | 2 | 3.2 | 28% |
| Hamstring | 88 | 2 | 2.5 | **10%** |
| Concussion | 81 | 1 | 2.0 | 27% |
| Shoulder | 35 | 2 | 1.8 | 17% |
| Foot | 29 | 3 | 4.1 | **34%** |
| Groin | 28 | 1 | 2.0 | 21% |

The hazard *rises* with time already missed. Given ≥1 week out, mean
total absence is 2.7 weeks and 25% are season-ending. Given ≥3 weeks
out, 4.7 and 34%. Injuries that linger are the bad ones.

That is why the sim's drop rule — 3 straight misses and no return means
knowably done — is sound. By then a third of them are never coming
back and real news has said so.

Hold/cut guide: hamstrings come back (hold); feet are the stealth
season-enders; concussions are short *or* career-alteringly long.

## 4. Rust: the first game back

First game after an absence: median **0.75×** baseline after a 1-week
absence, **0.67×** after 2+ weeks (healthy control 0.89). Expect
~15–25% less than normal in his first week back. This overlaps with §2,
since returnees are usually tagged Questionable.

## What the simulator now uses (environment v4)

- Real Friday statuses ride on every player (`load_injury_reports`,
  `PlayerSeason.week_status`); `set_lineup` discounts Questionable
  players by the §2 EV ratios (QB/RB ×0.90, WR ×0.80, TE ×0.75) when
  ranking — flips ~5% of team-week start/sit calls.
- Handcuff news promotion recalibrated from 577 real promotion weeks
  (`analysis/validate_promote.py`): k = 0.85 first week of an absence,
  0.55 weeks 2–3, 0.30 after. Was a flat 0.75, which overvalued stale
  news by ~1 ppg.
- Knowably-done players (3+ straight misses, never return) are
  droppable and worth 0 — dead roster spots at week 14 fell to ~0.1
  per team.

**All sim results produced before these changes are stale.** Clear
`results*/` before regenerating; the grid skips existing cells.

## Methodology

- Join: nflverse injury reports (`data/injuries_2017_2025.parquet`,
  `gsis_id`) × weekly scoring at league rules, 2018–2025 regular
  season, QB/RB/WR/TE with ≥3 games and ≥4 ppg that year.
- Baseline = player's mean points in *unlisted* played weeks that
  season (≥4 required, ≥5 ppg); control uses leave-one-out.
- Spell = consecutive missed non-bye weeks starting with an
  Out/Doubtful listing after the player had appeared that season.
- Reproduce: `venv/bin/python analysis/injury_model.py`.

## Caveats

- Injury labels are coarse. "Knee" is a sprain or an ACL; the table is
  the blend, so it understates the tail once an MRI says ligament.
- "Never returns that year" counts any reason — IR, benched, cut. It
  is the roster-planning number, not a medical one.
- The Questionable discount conflates snap limits, pitch counts, and
  true degradation. Fine for start/sit, wrong for talent evaluation.
- Game-time surprises are not modeled: sim managers know actives at
  lineup lock. The Q discount narrows this; a full treatment needs
  per-seat attentiveness modeling.
