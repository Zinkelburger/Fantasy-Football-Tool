# 05 — Never pay up for TE; the pure-wire punt is drying up

**Confidence: High** for "don't pay up" (descriptive + sim + your own
drafts agree). **Medium** for the trend claim (three recent seasons).

## TL;DR

Every season, half or more of the year's top-8 tight ends cost a
round-8-or-later pick — or nothing at all. So never spend an early
pick on one. One update, though: the extreme version (draft no TE,
live off free agents) is drying up — undrafted TEs cracking the
top-8 went **3, 2, 3** in 2020–22, then **0, 1, 0** in 2023–25.
Verdict: take your TE in round 10+, hit the wire only if he busts,
and never pay up.

## The data

Rest-of-season (after week 3) top-8 TEs, tagged by acquisition cost —
`[FA]` = undrafted per that year's 12-team ADP board:

- **2020**: Kelce[21] 13.8 · Waller[65] 11.1 · **Taysom Hill[FA] 10.3** ·
  Kittle[26] 9.6 · Andrews[42] 7.6 · **Tonyan[FA] 7.5** · Gronk[68] 7.1 ·
  **Irv Smith[FA] 6.4**
- **2021**: Andrews[48] 12.3 · **Hill[FA] 11.2** · Kittle[31] 10.3 ·
  Kelce[10] 8.8 · **Knox[FA] 7.5** · Henry[125] 7.3 · Gronk[82] 7.1 ·
  Goedert[90] 7.1
- **2022**: Kelce[16] 12.2 · Kittle[39] 9.0 · Hockenson[90] 8.2 ·
  **Hill[FA] 8.2** · Goedert[67] 7.0 · **Engram[FA] 6.5** ·
  **Juwan Johnson[FA] 6.5** · Ertz[98] 6.4
- **2023**: Andrews[32] · Kittle[55] · **LaPorta[160]** · Njoku[99] ·
  Kelce[5] · Hockenson[43] · Kmet[122] · Schultz[122] — zero FAs
- **2024**: Hill[131] 11.5 · Kittle[70] 11.1 · McBride[72] 8.7 ·
  **Jonnu Smith[FA] 8.5** · Bowers[117] 8.5 · Andrews[56] 8.4 ·
  LaPorta[41] 7.8 · Njoku[105] 7.6
- **2025**: McBride[26] 11.8 · Kittle[38] 9.8 · Bowers[18] 9.7 ·
  LaPorta[58] 8.3 · **Goedert[142] 8.1** · **Pitts[140] 7.5** ·
  **Fannin[248] 7.3** · Kelce[70] 6.9 — zero FAs, but three at ADP 140+

Simulation cross-check (environment v3, see finding 13): a full
punt-TE-and-stream bot finished at .584 all-play vs .591 for plain
disciplined drafting — a statistically marginal ~0.7-point cost,
effectively *par*. The picks saved by not paying for a TE offset the
streaming losses. Meanwhile the value
curve (finding 07) shows TE7 ≈ 6.9 PPG vs TE12 ≈ 5.8 — beyond the top
few, everyone's TE is roughly the same guy.

Case study from your own drafts (finding 11): Kincaid at pick 91 in
2024 → TE27 (53 pts); LaPorta at pick 62 in 2025 → TE24 (62 pts). Two
premium prices, two scrub outcomes, while Jonnu Smith (126 pts) and
Goedert (118) were nearly free.

## Methodology

- "Top-8 ROS" = rank by PPG over weeks 4–17, min 6 games played after
  week 3, all TEs (drafted or not). ADP tags from the year's standard
  12-team board; `[FA]` = absent from that board entirely.
- Sim cross-check: `PuntTE` strategy (no TE before round 12, weekly
  TE streaming policy), 1,440 seasons, harness per METHODS.md.
- Reproduce: `venv/bin/python -m simfl analyze streaming --pos TE`
  and `venv/bin/python -m simfl.grid --heroes punt_te -n 240`.

## Caveats

- The 0/1/0 recent-FA trend is three data points; the mechanism
  (leagues draft more TEs deep now that Bowers/LaPorta-type breakouts
  are famous) is plausible but unproven.
- "Round 10+" is calibrated to a 12-team room that drafts ~14–16 TEs
  total; in a room that hoards TEs, adjust earlier.
- An *elite* TE hit (Kelce '20, McBride '25) is genuinely valuable —
  the claim is that the price at which the league sells them (rounds
  2–6) has not been worth it in this window, not that TEs don't matter.
