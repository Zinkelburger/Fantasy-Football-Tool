# 37 — What our room actually pays for: reach by round

**Confidence: Medium-High** for the RB discount (three bands clear
zero, monotone, n=64/97/95). **Medium** for the early-TE premium (both
early bands clear zero, but the rounds 1–3 interval barely does, on
n=12). **Medium-High** for the QB null — the apparent early QB reach is
one season.

Our league reaches for tight ends early and lets running backs fall,
and both effects live in rounds 4–6. That is the same window
[finding 36](36-draft-order.md) says decides the draft.

This is a room-tendency finding, not a general one. It describes the
twelve managers in this league, measured against national ADP. It is
deliberately not published to the site.

## The pooled table hides it

`draft_tendencies.py` has always printed reach by position. Pooled
across sixteen rounds, tight end comes out at **−0.4** — dead neutral,
nothing to see. That number is two opposite effects cancelling: the
room reaches for TEs in rounds 1–6 and lets them rot after round 10.
Splitting by round band is the whole finding.

Sign convention throughout, matching `report()`: **negative = taken
earlier than national ADP** (reached for), positive = fell past it.

## The data

1,001 skill picks with an ADP, 2020–2025, against FFC 12-team
**standard** ADP (`simfl/data.py` `FFC_URL`) — our exact format, so
none of this is a scoring-format artifact. Median reach with a 95%
bootstrap CI; `*` marks an interval excluding zero.

| band | pos | n | median | 95% CI | |
|---|---|---|---|---|---|
| rd 1–3 | RB | 96 | +0.5 | [−0.1, +0.9] | |
| rd 1–3 | WR | 86 | −0.9 | [−2.0, −0.1] | * |
| rd 1–3 | **TE** | 12 | **−4.6** | [−5.5, −0.1] | * |
| rd 1–3 | QB | 22 | −9.1 | [−21.8, +1.8] | |
| rd 4–6 | **RB** | 64 | **+5.5** | [+0.2, +8.8] | * |
| rd 4–6 | WR | 93 | +3.0 | [−2.0, +4.3] | |
| rd 4–6 | **TE** | 30 | **−5.3** | [−9.9, −0.6] | * |
| rd 4–6 | QB | 29 | −1.0 | [−7.2, +4.4] | |
| rd 7–10 | **RB** | 97 | **+8.7** | [+6.0, +15.3] | * |
| rd 7–10 | WR | 105 | −3.5 | [−9.0, +3.5] | |
| rd 7–10 | TE | 28 | −6.0 | [−14.2, +4.2] | |
| rd 7–10 | QB | 29 | +8.3 | [+1.5, +16.0] | * |
| rd 11–16 | RB | 95 | +12.1 | [+5.7, +17.2] | * |
| rd 11–16 | WR | 96 | +12.1 | [+3.5, +17.1] | * |
| rd 11–16 | TE | 26 | +21.1 | [+9.0, +31.8] | * |
| rd 11–16 | QB | 33 | +30.0 | [+25.3, +34.1] | * |

The round 11–16 row is mechanical — everyone falls at the end of a
draft, because ADP compresses and players drop out of the top 200.
Ignore it. The signal is rounds 1–10.

## 1. The room pays for TE early, and only TE

Tight end is the only position that reaches in *both* early bands:
−4.6 in rounds 1–3, −5.3 in rounds 4–6. Median reach per year in
rounds 1–6:

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| −5.5 | −9.9 | +6.4 | −3.7 | −13.4 | −4.5 |

Five of six years reached. 2022 is the exception.

This is the premium to decline. [Finding 05](05-never-pay-up-for-te.md)
says never pay up for TE; [finding 33](33-te-same-pick.md) prices it
exactly — reaching 8 picks for a TE cost 3.7 points of title rate,
paying par cost ~1.7, and only taking him at a discount was free;
[finding 36](36-draft-order.md) finds TE timing inside its own noise
and a TE2 actively worse than nothing. Our room's TE run lands in
rounds 4–6, at the top of finding 33's rounds 5–9 dead zone.

Finding 33's rule was "let him come to you, never pay a premium to
guarantee you get one." This finding says what that costs here: about
five picks above market, every year but one.

## 2. Running backs fall to us, and it compounds

The mirror image, and the part worth acting on:

| band | median | CI | |
|---|---|---|---|
| rd 1–3 | +0.5 | [−0.1, +0.9] | top RBs go at ADP |
| rd 4–6 | +5.5 | [+0.2, +8.8] | * |
| rd 7–10 | +8.7 | [+6.0, +15.3] | * |

Monotone, and the two later bands are comfortably clear of zero. Share
of rounds-1–6 picks that fell 5+ past ADP:

| RB | WR | QB | TE |
|---|---|---|---|
| **31%** | 23% | 27% | 19% |

Highest of any position. The picks this room spends reaching on tight
ends are funded by letting running backs slide, and rounds 4–6 is
where that shows up.

Every other line of evidence points the same way:
[01](01-robust-rb-wins.md) (RB-RB-RB wins),
[23](23-early-rb-vs-wr.md) (same-rank talent premium),
[24](24-hindsight-optimal-drafts.md) (58% of perfect drafts open RB),
[36](36-draft-order.md) (two or three RBs in rounds 1–4),
[07](07-what-a-starter-is-worth.md) (the RB curve is the steep one).
The novel part is that in *this* room the market pays us to do it.

## 3. The early QB reach is one season, not a tendency

Nationally, ESPN's blended ADP takes QBs about 14 picks earlier than
FFC mock ADP and TEs about 39 picks earlier (both real-room boards
agree on TE: Sleeper-standard is −23 against FFC on the same players).
It would be natural to assume our room inherits both. **It inherits
the TE half only.**

Rounds 1–3 QB reads −9.1 with a CI of [−21.8, +1.8] — does not clear
zero. Per-year medians in rounds 1–6:

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| +4.3 | **−27.9** | +8.4 | −7.0 | +0.1 | −1.0 |

The entire effect is 2021, when someone took a quarterback at pick 3.
Three of six years the room let QBs *fall*. Do not preempt a run that
does not reliably happen.

Supply, for planning: QBs gone by pick 60 ran 6, 10, 4, 8, 6, 6; the
first QB off the board went #19, #3, #38, #24, #13, #22. So at a
round 5–6 turn there is normally a QB6–QB7 available — enough to
satisfy [finding 36](36-draft-order.md)'s "QB by round 5" without
reaching, but close enough to the edge not to slide past round 6.

## What to do with it

1. **Rounds 1–3 behave normally.** RB reach is +0.5, WR −0.9. Take the
   board; there is no room-specific edge here.
2. **Rounds 4–6 are where our league's shape is exploitable.** The TE
   run starts and RBs begin falling 5–9 picks past ADP. Let the tight
   ends go, take the QB in that window if a top-6 is sitting there, and
   spend the rest on the discounted RBs.
3. **Skip the TE hallway entirely** — it is finding 33's dead zone and
   our room bids it up about five picks on top.

## Methodology

- `analysis/draft_tendencies.py`, function `reach_by_round()`. Real
  ESPN league picks 2020–2025 (`data/espn/picks.parquet`, 1,152 picks,
  1,001 with an ADP) joined to FFC 12-team standard ADP via
  `simfl.data.load_adp`.
- reach = `overall − adp`; negative = reached early. Same convention as
  the pooled table in `report()`.
- Median rather than mean: reach is skewed by a few huge reaches and a
  long tail of players who fell out of the top 200. CIs are 4,000
  bootstrap resamples of the median, seeded.
- National comparison in section 3 from
  `data/market/adp_2026.csv` (ESPN / Sleeper / FFC, per format),
  160 players priced by all boards.
- Reproduce: `venv/bin/python analysis/draft_tendencies.py`.

## Caveats

- **Small n per cell.** Early TEs are 12 picks (rounds 1–3) and 30
  (rounds 4–6) across six drafts. The rounds 1–3 upper bound is −0.1 —
  it barely clears zero. Treat the magnitudes as directional.
- **Managers change.** This is six years of history for a league whose
  roster of humans is not fixed. 2022 reverses the TE sign.
- **This is not "the market is wrong."**
  [Finding 03](03-adp-discipline-is-not-an-edge.md) says ADP
  discipline is not an edge, and [finding 25](25-player-model.md) found
  no ranking input beating ADP. The claim here is narrower: our room's
  *price* for TE sits above the national price, and findings 05/33/36
  say TE is not worth the national price either.
- **2025 uses a different yardstick.** ADP for 2025 is FantasyPros
  standard consensus recovered via Wayback, not FFC (see
  `simfl/data.py`), so that row is measured against a slightly
  different board.
- Reach measures the room against national ADP, not against value.
  A position can be "reached for" and still be the right pick.

## Provenance

Came out of checking whether a Subvertadown VBD sensitivity study
(r/fantasyfootball, thread `1w73qao`, in the scraper corpus) had
anything to offer this league. It did not — the study varies PPR,
league size, superflex and WR slots, and we sit at the baseline of all
four. Running its *method* against our own room's prices is what
produced the above. The settings-sensitivity question it actually
answers is queued as B17 in [BACKLOG.md](BACKLOG.md).
