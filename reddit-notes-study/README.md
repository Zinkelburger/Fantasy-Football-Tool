# Do the reddit draft notes actually help? (2024–2025 backtest)

Backtest of the scraped player note files (`2024/analysis/`,
`2025/go/analysis/` — 599 files) against real season results, asking one
question: **do the notes make draft picks better than plain ADP?**

Verdict up front: **the notes are real information, not glaze — but
nearly all of their value is already priced into ADP. Used the way the
Go tool uses them (choose within the next-10 ADP window) they are free
to slightly positive. Used against ADP they are catastrophic. Their
single strongest signal is negative: players the notes pan are bad
picks.**

Method, honesty rules, and limitations: [METHODOLOGY.md](METHODOLOGY.md).
Raw outputs: [results/](results/). Full per-player dataset:
[data/final_dataset.csv](data/final_dataset.csv).

## The laws

1. **Never deviate from ADP blindly.** Picking a random player from the
   next-10 window cost 32 (2024) and 93 (2025) season points vs pure
   ADP over 240 simulated seasons each. Reaching is expensive by
   default; any deviation needs a reason.
2. **The notes' red flags are their sharpest edge.** Deliberately
   drafting the worst-noted player of the window cost 91 / 37 points —
   in 2024, 59 points *worse* than random deviation. In the top-120
   range, players with lean-negative notes beat their draft cost only
   19–31% of the time (Chris Olave '24, Joe Mixon '25, Kaleb Johnson
   '25, Zamir White '24...). Treat a clearly negative note as a real
   reason to pass.
3. **Within the window, following the notes is free and maybe slightly
   good.** Taking the best-noted of the next 10 came out +9 / +14
   points (never negative in any tested year; pooled ≈ +11, barely
   clearing its error bar). A gentler tiebreak nudge was an exact wash
   (−3 / +2). Consistent view across both: tone-guided choice inside
   the ADP window recovers the full cost of deviating, plus little or
   nothing on top.
4. **Never pay a premium for hype.** Strongly-hyped (+2) players beat
   their cost only ~35% of the time (Tyreek Hill was +2-noted in 2024
   and finished 20 WR-ranks under price). Tone correlates with ADP at
   r ≈ 0.42–0.46 — reddit mostly re-states the market. The edge test,
   corr(tone, beating-ADP), is ~0 in both years (−0.09 / −0.05, n.s.;
   r ≈ 0 within the top 120).
5. **ADP does the heavy lifting.** Market rank alone predicts positional
   finish at Spearman 0.70 both years. Tone alone manages 0.25–0.35,
   and that is entirely explained by its correlation with ADP.
6. **The files are not glaze.** Only ~35% of 2024 files and ~22% of 2025
   files are positive-toned; 90% of 2024 files name at least one real
   concern. The failure mode is redundancy with ADP, not sycophancy.

## Headline numbers

**Mock drafts** — 240 full league-sim seasons per strategy per year
(12-team snake vs family-calibrated bots, rotating seat, waivers,
playoffs), paired against the same rooms drafting pure ADP
(`results/mock_draft_output.txt`):

| Strategy (window = next 10 by ADP) | ΔPF 2024 | ΔPF 2025 |
|---|---|---|
| Take best-noted of window          | +9 ± 15  | +14 ± 12 |
| Notes nudge near-ties (8%/point)   | −3 ± 10  | +2 ± 8   |
| Take *worst*-noted of window       | −91 ± 16 | −37 ± 16 |
| Random pick from window            | −32 ± 18 | −93 ± 17 |

(Baseline ≈ 1,130–1,155 PF, so 20 PF ≈ 1.7%. The anti-notes vs random
gap is the proof the tone carries signal; the best-noted vs random gap
— +41 and +107 — shows the notes pick the right player *within* a
window even though they can't beat the window's own ADP order by much.)

**Correlation study** — per-player tone vs beating draft cost
(`results/correlation_output.txt`): edge ≈ 0 everywhere it matters;
see laws 4–5.

## What this means for the Go tool

Keep the flow (ADP window + note summaries) — it tested as free-to-
positive. Two changes would follow the evidence: surface **negative**
notes loudly (that's the real signal), and don't rank suggestions by
enthusiasm — a +2 note is not a stronger buy than +1; in both years the
loudest hype was the worst value at cost.

## Reproducing

```bash
cd reddit-notes-study/scripts
../../league-sim/venv/bin/python prep_data.py
# LLM scoring step: see scoring_prompt.md (produces data/sentiment_scores.csv)
../../league-sim/venv/bin/python analyze.py    > ../results/correlation_output.txt
../../league-sim/venv/bin/python mock_drafts.py 240 > ../results/mock_draft_output.txt
```

Study run July 2026 (both seasons complete). Two seasons is a small
sample: the robust findings are the two controls (laws 1–2); the +11-
point pooled effect of law 3 is at the edge of resolution and should be
re-tested after 2026.
