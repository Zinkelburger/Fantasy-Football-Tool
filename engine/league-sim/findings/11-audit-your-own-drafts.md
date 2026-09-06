# 11 — Auditing your own drafts: what a league export can and cannot tell you

**Confidence: High** for the null itself (the CIs are wide but the
method is exact). **High** for the methodological point, which is
finding 36's endogeneity warning reproduced on real data.

You can export your league, replay every draft, and score each team's
haul against the rules the other findings settled. We built that audit.
**It found nothing** — and the reason it found nothing is the useful
part of this page.

Run it on your own league:

```bash
venv/bin/python analysis/draft_leaks.py
venv/bin/python analysis/draft_leaks.py --years 2023 2024 2025
```

It reads ESPN league exports, replays all twelve drafts per season, and
reports every team anonymously. Nobody is named.

## The audit

Six rules, each settled elsewhere, checked against 72 team-seasons
(12 teams × 6 drafts). "Haul" is the points a drafted roster would
score with a perfect lineup every week — an upper bound that strips out
waivers and lineup skill, so it grades the draft alone. Hauls are
z-scored inside each season.

| Rule broken | Finding | Broke it | Haul gap | 95% CI |
|---|---|---|---|---|
| TE taken in rounds 5–9 | [33](33-te-same-pick.md) | 47 (65%) | **+0.59** | [+0.11, +1.10] |
| First QB after round 5 | [36](36-draft-order.md) | 32 (44%) | −0.24 | [−0.71, +0.22] |
| Bought above market (mean pick−ADP < 0) | [03](03-adp-discipline-is-not-an-edge.md) | 29 (40%) | −0.18 | [−0.67, +0.29] |
| Fewer than 2 RB in rounds 1–4 | [36](36-draft-order.md) | 25 (35%) | +0.39 | [−0.06, +0.81] |
| Drafted a 2nd TE | [36](36-draft-order.md) | 25 (35%) | −0.06 | [−0.54, +0.40] |
| More WR than RB drafted | [07](07-what-a-starter-is-worth.md) | 40 (56%) | +0.22 | [−0.24, +0.67] |

Five of six cross zero. The sixth — the TE dead zone — is
**significant in the wrong direction**: the teams that broke finding
33's clearest rule had *better* drafts.

Roster shape shows nothing at all:

| Drafted WRs | n | Mean haul z |
|---|---|---|
| 4 or fewer | 10 | −0.60 |
| 5 | 15 | +0.14 |
| 6 | 28 | +0.07 |
| 7 or more | 19 | +0.10 |

Going receiver-heavy — the thing finding 02 calls the costliest plan it
tested — is flat from five WRs upward in real drafts.

## Why the audit is blind

**1. The outcome variable is wrong.** Haul aggregates sixteen picks.
Every rule in the table is about *one* pick's opportunity cost. Finding
33 can see the TE effect because it compares the TE to the WR/RB taken
at the *same pick*; haul cannot, because a manager who nails rounds 1–4
has a big haul whatever he does at TE in round 6.

**2. Endogeneity — finding 36 warned about exactly this.** There, the
observational "late RBs win" gap vanished the moment the simulator
*forced* the timing, because good drafters take a late RB when a good
late RB is on the board. Every row above has the same disease. The
first TE band makes it visible:

| First TE taken | n | Mean haul z |
|---|---|---|
| Rounds 1–4 | 17 | −0.19 |
| Rounds 5–9 | 47 | +0.21 |
| Round 10+ | 8 | −0.80 |

Read causally this says "take your TE in the dead zone." Read honestly
it says managers who spent a premium pick on a TE had less left over,
and managers who forgot about TE entirely until round 10 were not
paying attention generally. The middle band is where *normal* drafting
lives, and normal drafting beats both failure modes. The rule finding
33 tested — what that same pick would have returned at another position
— is invisible here.

**3. n = 72, and the CIs say so.** A ±0.5 SD interval cannot resolve
effects the sims measure at a few points of title rate. Absence of
evidence, at this sample size, is close to no evidence at all.

## What to do instead

**Audit your drafts for rule compliance, not for outcome correlation.**
Your league export can tell you, exactly and cheaply, *whether you
followed a rule*. It cannot tell you whether the rule is true — that
takes a same-pick test or a forced-arm simulation, and those live in
the findings the rules came from.

This distinction matters most in the year a broken rule pays off. A
drafter who takes his TE in round 5 and lands the TE2 overall will read
his own result as vindication. The audit above would agree with him.
Both are wrong for the same reason: one draw from a 30%-hit-rate bucket
is not evidence about the bucket.

The corollary is that self-auditing has a specific, narrow use — it
catches *habits*. A rule you broke once is noise. A rule you broke
three drafts running is a habit, and the finding that rule came from is
the evidence about whether the habit costs you.

## Methodology

- Source: ESPN league exports (`data/espn/league_{2020..2025}.json`),
  picks joined to nflverse via `load_ff_playerids` (ESPN id → gsis id),
  scored under league-exact settings. D/ST excluded (not modeled).
- Haul = perfect-lineup points from drafted players only, same formula
  for every team, z-scored within season because league scoring drifts.
- Gaps are violators minus compliers, 4,000-sample bootstrap CI.
- Reproduce: `venv/bin/python analysis/draft_leaks.py`.

## Caveats

- One league. Twelve managers, six drafts, shared player pool —
  team-seasons inside a year are not independent (one manager's steal
  is another's miss).
- "Perfect lineups" flatter everyone equally; the z-scores are the
  meaningful part, not the raw hauls.
- This page is a null result about a *method*, not evidence against
  findings 03, 07, 33 or 36. Those rest on same-pick tests and forced
  simulation arms, both of which hold the confound fixed in a way a
  72-row observational cut cannot.
