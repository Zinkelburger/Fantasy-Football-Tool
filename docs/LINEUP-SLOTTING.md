# Which slot a starter sits in

Points decide **who** starts. Kickoff time decides **which slot** you label
them with. The second decision is free — it never changes the projected
total — and it is the one most managers get backwards.

**The rule.** Set your best lineup first, ignoring kickoff times entirely.
Then, among the players you have already decided to start, move the latest
kickoffs into the open slots (OP/superflex, FLEX, RB/WR, WR/TE) and leave
the earliest in the dedicated ones. **Never put a Thursday — or Wednesday —
night player in a flex slot.** In a superflex league the OP slot gets the
later of your two quarterbacks.

## Why it is worth doing

A slot is a constraint on *replacement*, not on scoring. A FLEX slot accepts
any RB/WR/TE; an RB slot accepts an RB. If a starter is declared inactive
90 minutes before his game, whoever is sitting in the open slot is the one
you can still replace out of the bench or off the wire.

The canonical case: 6:50pm ET on Monday, September 9 2024, Christian
McCaffrey ruled inactive for the Monday night game after practising limited
all week and saying publicly he expected to play. A manager with McCaffrey
in FLEX could replace him with any RB, WR or TE they still had. A manager
with him in the RB slot could only use another RB.

The cost is zero. You are not benching anyone, changing anyone's
projection, or "forcing" anything — you have already committed to the
lineup, and the position labels do not score points. It is upside on the
weeks it matters and a no-op on the weeks it does not.

## Caveats worth knowing

- If your league locks free agents at the first kickoff of the week, the
  wire half of the benefit is gone; the bench half still stands.
- It cannot always be honoured. With three startable RBs, two RB slots and
  one FLEX, the flex *must* be an RB — the latest-kickoff receiver is not
  eligible for it. `timing_note()` labels that case `forced` so it reads as
  a roster shape, not a slotting mistake.
- It is not a tiebreaker for *who* starts. Never start a worse player
  because he plays later.

## What is hardcoded

`engine/weekly/advisor.py`:

- `SLOT_OPENNESS` — how many positions each ESPN slot accepts. Dedicated
  slots 1, RB/WR and WR/TE 2, FLEX 3, OP 4. The more a slot accepts, the
  later the kickoff that belongs in it, so this ordering is the whole rule.
- `kickoff_dt(player)` — the player's kickoff normalised to UTC. nflverse
  writes a naive Eastern stamp (`2026-09-13T13:00`), the ESPN scoreboard
  overlay writes UTC with a `Z`, and both can land in the same week's lines
  file. Comparing the raw strings puts 13:00 ET and 17:00Z four hours apart
  in the wrong direction.
- `reslot_by_kickoff(starters)` — runs inside `optimal_lineup` after the
  starters are chosen. Maximises `sum(openness[slot] * kickoff_rank[player])`
  over the legal assignments of that same set, which by the rearrangement
  inequality pairs the most open slot with the latest kickoff and respects
  eligibility where it cannot. Locked players keep their slot. An unknown
  kickoff ranks below the earliest known one, so a missing line never
  promotes anyone into FLEX on no evidence. Ties keep the current
  arrangement, so the tool never proposes a move that changes nothing.
- `timing_note(starters)` — one line per open slot for the agent's report.

`engine/weekly/mcp_server.py`: `lineup_recommendation()` prints that note,
and tags each move it causes `(slot timing only, no points change)` so the
user can tell a points move from a labelling move before approving.

Tests: `engine/weekly/test_weekly.py::SlotTiming`.

## Source

r/fantasyfootball, [*[Noobs Corner] Our annual reminder on how to use your
FLEX and OP slots*](https://reddit.com/r/fantasyfootball/comments/1wbov9m/noobs_corner_our_annual_reminder_on_how_to_use/),
posted 2026-09-09. The two-step phrasing ("set your best lineup, then move
the later starters into the flex") is u/cbmgreatone's, quoted in that post
from a 2020 thread. Community advice, not a measured finding — there is no
backtest here and none is needed, because the claim is that the move is
free, not that it is worth N points a week.
