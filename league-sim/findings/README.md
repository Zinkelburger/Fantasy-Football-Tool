# Findings

Every factoid from the league-sim project, one file per claim, each
with its data, exact methodology, and an honest confidence rating.
Shared infrastructure (data sources, scoring, simulator design,
validation) lives in [METHODS.md](METHODS.md) — read that once first.

**Confidence scale**
- **High** — large sample or simulation-verified, survives robustness
  checks, coherent mechanism.
- **Medium** — real signal in this window, but modest sample or one
  specification weakens it.
- **Low** — suggestive only; do not build a slide on it without the
  caveats attached.

| # | Finding | Confidence |
|---|---|---|
| [01](01-robust-rb-wins.md) | RB-RB-RB is the best title-rate plan: 20.3% championships, 2.4× baseline | High |
| [02](02-zero-rb-is-a-trap.md) | Zero RB and WR-heavy are PPR imports: the costliest plans tested (9.7% vs 20.3% titles) | High |
| [03](03-adp-discipline-is-not-an-edge.md) | CORRECTED: discipline IS the edge (~90% of it) — the v1 "no edge" result was an opponent-model artifact | High |
| [04](04-kickers-are-noise.md) | Early-season kicker scoring predicts nothing; never chase | High |
| [05](05-never-pay-up-for-te.md) | Top-8 TE production is available late every year; the pure-wire punt is drying up | High |
| [06](06-qb-timing.md) | Early QB is fairly priced; late-QB-plus-streaming measurably costs | Medium-High |
| [07](07-what-a-starter-is-worth.md) | Positional value curves: why rounds 1–3 are RB rounds here | High |
| [08](08-bad-team-wr1-edge.md) | Mid-round alpha WRs on doubted teams nearly double the hit rate | Medium |
| [09](09-decline-discount-trap.md) | WRs coming off a collapse year bust more at every age | Medium |
| [10](10-wr-age-effects.md) | Age 29–30 looks like a danger zone — partially survives scrutiny, partially overfit | Low-Medium |
| [11](11-methuen-jackels-audit.md) | The Jackels drafted best-in-league; the leaks are TE price and one WR archetype | High (it's your data) |
| [12](12-championship-variance.md) | Back-to-back runner-up finishes are variance, not process failure | High |
| [13](13-handcuffs-are-free-insurance.md) | Handcuffs are correctly-priced insurance: free to hold, no edge (also: environment version table) | Medium-High |
| [14](14-qb-round-sweep.md) | QB timing sweep: rounds 4–6 is the sweet spot; past 10 costs real points | Medium-High |
| [15](15-late-season-momentum-myth.md) | Late-season momentum is a myth: last weeks add zero beyond full-season PPG (RB whisper only) | High |
| [16](16-td-luck-regresses.md) | TD luck regresses in 8/8 years (~1.6 PPG quintile gap) — 2026 fade/buy lists | High |
| [17](17-buy-targets-not-efficiency.md) | WR targets add signal beyond PPG; YAC and catch rate add none | High |
| [18](18-injury-prone-is-mostly-myth.md) | "Injury-prone" barely persists — zero at QB/WR, real at TE, suggestive at RB | Medium |
| [19](19-bench-composition.md) | Bench RBs are real lottery tickets (21% vs 13% sustained runs) but hoarding them adds ~nothing — tiebreak only | Medium-High |

Open hypotheses with test designs live in [BACKLOG.md](BACKLOG.md)
(B4–B12: waiver expected-points, RYOE screening, O-line health,
rookie RB paths, seat advantage, rookie-reach EV, QB2 insurance,
WR archetypes out-of-sample, pass-protection proxies).

Reproduce anything:

```bash
venv/bin/python -m simfl analyze kickers|streaming|scarcity
venv/bin/python -m simfl.grid --heroes all -n 240   # strategy backtest
venv/bin/python -m simfl.plots                      # all figures
venv/bin/python scripts/wr_archetypes.py            # findings 08-10
venv/bin/python scripts/jackels_review.py           # finding 11
venv/bin/python scripts/next_season_signal.py       # findings 15-18 (--quick to skip stats suite)
```
