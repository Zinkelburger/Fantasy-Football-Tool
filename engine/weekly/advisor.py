"""Deterministic start/sit and waiver logic.

Nothing in here talks to the network. It takes rows the fetchers
already wrote (ESPN roster/free agents, the opportunity table, the
week's lines, injuries) and produces the same answer every time for the
same inputs. The agent's job is to read these outputs next to the
Reddit/news context and decide; the arithmetic lives here.

Projection for a player this week
---------------------------------
  ep_adj  = ewma_ep * clip(sqrt(team_implied / league_avg_implied), 0.8, 1.2)
  proj    = mean of the available sources among {espn_proj, ep_adj}
            (K and D/ST: espn_proj only; our lines rank is shown beside it)
  proj   *= injury multiplier (OUT/IR/SUSP 0, DOUBTFUL .15, QUESTIONABLE .8)
  proj    = 0 on a bye

The matchup term is deliberately mild: finding 26 measured the team-
environment effect on skill players as real but small next to usage.

"Value" for waiver decisions is not this week's projection; it is
  value = mean of {ewma_ep, espn_proj} (whatever exists), no matchup or
  injury term, so a stud on a bye is not a drop candidate.

Which slot a starter sits in
----------------------------
Points first, then timing. `optimal_lineup` picks the starting eleven on
projection alone, then re-labels that same set so the open slots (OP,
FLEX, RB/WR, WR/TE) hold the starters with the latest kickoffs. Same
players, same projected total; only the labels move. See
`reslot_by_kickoff` and `docs/LINEUP-SLOTTING.md`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from itertools import combinations
from zoneinfo import ZoneInfo

from common import ESPN_SLOTS, NON_STARTING_SLOTS, SKILL

MATCHUP_EXP = 0.5
MATCHUP_CLIP = (0.8, 1.2)
LEAGUE_AVG_IMPLIED = 22.5
# Per-position replacement level when no free-agent pool was supplied.
REPLACEMENT_DEFAULT = {"QB": 12.0, "RB": 6.0, "WR": 6.0, "TE": 4.0, "K": 6.0, "DST": 5.0}

DEDICATED = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "DST", 17: "K"}

# How open a starting slot is: how many positions ESPN will accept in it.
# A dedicated slot takes one, RB/WR and WR/TE take two, FLEX takes three,
# OP (superflex) takes four. This is the whole ordering `reslot_by_kickoff`
# needs -- the more positions a slot accepts, the more of the bench and the
# wire can still fill it after a late scratch, so the later the kickoff that
# belongs in it.
SLOT_OPENNESS = {0: 1, 1: 1, 2: 1, 4: 1, 6: 1, 16: 1, 17: 1,
                 3: 2, 5: 2, 23: 3, 7: 4}
EASTERN = ZoneInfo("America/New_York")
# Guard on the bitmask search below. A real lineup fills about nine slots.
MAX_RESLOT = 14


def matchup_factor(imp_own: float | None, avg: float = LEAGUE_AVG_IMPLIED) -> float:
    if not imp_own:
        return 1.0
    f = (imp_own / avg) ** MATCHUP_EXP
    return max(MATCHUP_CLIP[0], min(MATCHUP_CLIP[1], f))


def _mean(vals: list[float | None]) -> float | None:
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def project(player: dict, opp_row: dict | None, line: dict | None,
            fmt: str = "std", on_bye: bool = False, ecr: dict | None = None) -> dict:
    """Attach proj / value / flags to a copy of an ESPN player row."""
    p = dict(player)
    flags: list[str] = []
    ewma = opp_row.get(f"ewma_ep_{fmt}") if opp_row else None
    espn = p.get("espn_proj")
    imp_own = line.get("imp_own") if line else None
    ep_adj = ewma * matchup_factor(imp_own) if ewma is not None else None
    if p["pos"] in SKILL:
        proj = _mean([espn, ep_adj])
    else:
        proj = espn
    value = _mean([espn, ewma]) if p["pos"] in SKILL else espn
    if proj is None:
        proj = 0.0
        flags.append("no projection")
    if on_bye:
        proj = 0.0
        flags.append("BYE")
    inj = p.get("injury", "ACTIVE")
    if inj and inj != "ACTIVE":
        flags.append(inj)
        proj *= p.get("injury_mult", 1.0)
    if line is None and not on_bye:
        flags.append("no line yet")
    if p.get("locked"):
        flags.append("locked")
        if p.get("espn_actual") is not None:
            proj = p["espn_actual"]
            flags.append(f"played: {p['espn_actual']:.1f} actual")
    p.update({
        "proj": round(proj, 2),
        "value": round(value, 2) if value is not None else None,
        "sources": {"espn_proj": espn, "ewma_ep": round(ewma, 2) if ewma is not None else None,
                    "ep_adj": round(ep_adj, 2) if ep_adj is not None else None,
                    "last_ep": opp_row.get(f"last_ep_{fmt}") if opp_row else None,
                    "last_pts": opp_row.get(f"last_pts_{fmt}") if opp_row else None,
                    "games": opp_row.get("games") if opp_row else None,
                    "ecr": ecr},
        "matchup": {"opp": line.get("opp"), "home": line.get("home"),
                    "imp_own": line.get("imp_own"), "imp_opp": line.get("imp_opp"),
                    "spread": line.get("spread"), "total": line.get("total"),
                    "kickoff": line.get("kickoff")} if line else None,
        "flags": flags,
    })
    return p


# ------------------------------------------------------------------ lineup
def kickoff_dt(player: dict) -> datetime | None:
    """When this player's game starts, in UTC, or None if we do not know.

    nflverse writes a naive Eastern stamp ("2026-09-13T13:00"); the ESPN
    scoreboard overlay writes UTC with a Z. Both can appear in the same
    week's lines file, so normalise before comparing -- 13:00 ET and
    17:00Z are the same kickoff, and a raw string sort reads them as four
    hours apart in the wrong direction.
    """
    raw = (player.get("matchup") or {}).get("kickoff")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=EASTERN)
    return dt.astimezone(timezone.utc)


def kickoff_label(player: dict) -> str:
    """"Mon 20:15 ET" for display, or "" when the kickoff is unknown."""
    dt = kickoff_dt(player)
    return dt.astimezone(EASTERN).strftime("%a %H:%M ET") if dt else ""


def reslot_by_kickoff(starters: list[tuple[int, dict | None]]) -> list[tuple[int, dict | None]]:
    """Re-label an already-chosen lineup so open slots hold late kickoffs.

    Points decide who starts; this decides only which slot each starter is
    labelled with, so it never changes the projected total. The rule, in
    one line: of the players you have already decided to start, the one
    whose game kicks off last goes in the most open slot, and the Thursday
    game never does.

    It matters because a slot is a constraint on replacement, not on
    scoring. If a starter is declared inactive 90 minutes before kickoff,
    whoever sits in FLEX can be swapped for any RB/WR/TE still on the bench
    or the wire, while the same player labelled RB can only be replaced by
    an RB. Leaving the open slots unlocked as long as possible is free: no
    lineup is ever worse for it, and occasionally it is the difference
    between a replacement and a zero.

    Locked players (game underway) keep their slot. Players whose kickoff
    we do not know sort as earliest, so a missing line never promotes
    someone into FLEX on no evidence.
    """
    movable = [(i, s, p) for i, (s, p) in enumerate(starters)
               if p is not None and not p.get("locked")]
    n = len(movable)
    if n < 2 or n > MAX_RESLOT:
        return starters
    openness = [SLOT_OPENNESS.get(s, 1) for _, s, _ in movable]
    if len(set(openness)) < 2:
        return starters                       # nothing to compete for
    times = [kickoff_dt(p) for _, _, p in movable]
    known = sorted({t for t in times if t is not None})
    if len(known) < 2:
        return starters                       # one kickoff, or none known
    # Dense rank, unknown kickoff = 0 = below the earliest known one.
    rank = [known.index(t) + 1 if t is not None else 0 for t in times]
    ok = tuple(tuple(j == k or movable[j][1] in (movable[k][2].get("eligible_slots") or ())
                     for k in range(n))
               for j in range(n))

    # Maximising sum(openness[slot] * rank[player]) over the legal
    # assignments pairs the most open slot with the latest kickoff
    # (rearrangement inequality), and respects eligibility where it cannot.
    @lru_cache(maxsize=None)
    def best(j: int, used: int) -> float:
        if j == n:
            return 0.0
        return max((openness[j] * rank[k] + best(j + 1, used | (1 << k))
                    for k in range(n) if not used & (1 << k) and ok[j][k]),
                   default=float("-inf"))

    order, used = [], 0
    for j in range(n):
        target = best(j, used)
        # The player already in this slot is tried first, so an equally
        # good arrangement is never churned into a pointless move.
        pick = next((k for k in [j] + [x for x in range(n) if x != j]
                     if not used & (1 << k) and ok[j][k]
                     and openness[j] * rank[k] + best(j + 1, used | (1 << k)) >= target),
                    None)
        if pick is None:
            return starters                   # no legal assignment; leave it
        order.append(pick)
        used |= 1 << pick
    out = list(starters)
    for j, k in enumerate(order):
        out[movable[j][0]] = (movable[j][1], movable[k][2])
    return out


def timing_note(starters: list[tuple[int, dict | None]]) -> list[str]:
    """One line per open slot: who is in it and when he actually plays.

    Flags the case `reslot_by_kickoff` cannot fix -- an open slot stuck
    with an early game because no later-starting starter is eligible for
    it -- since that one is a roster problem, not a slotting mistake.
    """
    kicks = [k for k in (kickoff_dt(p) for _, p in starters if p) if k is not None]
    latest = max(kicks, default=None)
    lines = []
    for slot, p in starters:
        if p is None or SLOT_OPENNESS.get(slot, 1) < 2:
            continue
        when = kickoff_label(p) or "kickoff unknown"
        tail = ""
        if latest is not None and kickoff_dt(p) != latest:
            later = [q["name"] for _, q in starters if q and kickoff_dt(q) is not None
                     and (kickoff_dt(p) is None or kickoff_dt(q) > kickoff_dt(p))
                     and slot in (q.get("eligible_slots") or ())]
            tail = ("  <- forced: no later-starting eligible starter" if not later
                    else "  <- later starters available: " + ", ".join(later[:3]))
        lines.append(f"  {ESPN_SLOTS.get(slot, slot):6} {p['name']:24} {when}{tail}")
    return lines


def optimal_lineup(players: list[dict], slots: dict[int, int]) -> dict:
    """Exact best assignment of players to starting slots by `proj`.

    Locked players (game started) keep whatever slot they are in; a
    locked bench player cannot be started. Slot eligibility is the
    player's own ESPN eligibleSlots list. Once the starters are chosen,
    `reslot_by_kickoff` re-labels them so the open slots hold the latest
    kickoffs; that never changes who starts or what the lineup projects,
    and the moves it causes are tagged `"timing": True`. Returns
      {"total": pts, "starters": [(slot, player)], "bench": [player],
       "moves": [{player_id, from_slot, to_slot, name}]}
    """
    slot_list: list[int] = []
    for s, n in sorted(slots.items()):
        if s in NON_STARTING_SLOTS:
            continue
        slot_list += [s] * n
    # Dedicated slots first so the search prunes early; flex last.
    slot_list.sort(key=lambda s: (s not in DEDICATED, s))

    fixed: dict[int, dict] = {}      # slot index -> locked starter
    free_players = []
    for p in players:
        if p.get("locked") and p.get("slot") not in NON_STARTING_SLOTS and p.get("slot") in slot_list:
            # occupy the first unfilled instance of that slot
            for i, s in enumerate(slot_list):
                if s == p["slot"] and i not in fixed:
                    fixed[i] = p
                    break
        elif not p.get("locked"):
            free_players.append(p)
    free_players.sort(key=lambda p: -p["proj"])

    best = {"total": -1.0, "assign": None}

    def rec(i: int, used: frozenset, total: float, assign: tuple):
        if i == len(slot_list):
            if total > best["total"]:
                best["total"], best["assign"] = total, assign
            return
        if i in fixed:
            rec(i + 1, used, total + fixed[i]["proj"], assign + ((i, fixed[i]),))
            return
        s = slot_list[i]
        # Upper bound prune: remaining slots can't beat best with top projs.
        tried = 0
        for p in free_players:
            if p["id"] in used or s not in p["eligible_slots"]:
                continue
            rec(i + 1, used | {p["id"]}, total + p["proj"], assign + ((i, p),))
            tried += 1
            # Every player in a dedicated slot beyond the top few of that
            # position cannot matter; cap the branching.
            if tried >= 6:
                break
        rec(i + 1, used, total, assign + ((i, None),))   # leave slot empty

    rec(0, frozenset(), 0.0, ())
    assign = best["assign"] or ()
    starters, used = [], set()
    for i, p in assign:
        starters.append((slot_list[i], p))
        if p:
            used.add(p["id"])
    bench = [p for p in players if p["id"] not in used]
    # Points chose the starters; kickoff order chooses their labels.
    by_points = {p["id"]: s for s, p in starters if p}
    starters = reslot_by_kickoff(starters)
    moves = _moves(players, starters, slots)
    for m in moves:
        m["timing"] = by_points.get(m["player_id"], m["to_slot"]) != m["to_slot"]
    return {"total": round(max(best["total"], 0.0), 2), "starters": starters,
            "bench": bench, "moves": moves}


def _moves(players, starters, slots) -> list[dict]:
    """Slot changes to get from the current lineup to `starters`."""
    target: dict[int, int] = {}
    for slot, p in starters:
        if p:
            target[p["id"]] = slot
    ir_slot = 21 if 21 in slots else None
    moves = []
    for p in players:
        cur = p.get("slot")
        if cur == ir_slot:
            continue                       # never touch IR here
        want = target.get(p["id"], 20)     # 20 = bench
        if cur != want and not p.get("locked"):
            moves.append({"player_id": p["id"], "name": p["name"],
                          "from_slot": cur, "to_slot": want,
                          "from": ESPN_SLOTS.get(cur), "to": ESPN_SLOTS.get(want)})
    # Bench-outs first so ESPN never sees two players in one slot.
    moves.sort(key=lambda m: (m["to_slot"] != 20, m["to_slot"]))
    return moves


# ------------------------------------------------------------------ waivers
# "Replacement level" is the N-th best free agent at the position: what
# is on the wire any week, not the one good player everybody will bid
# on. "Best available" is that one player, used for upgrade flags.
REPLACEMENT_NTH = {"QB": 2, "RB": 3, "WR": 3, "TE": 2, "K": 2, "DST": 2}
# How many players at a position a roster should carry above replacement:
# the starting slots, plus the flex share and one bench body for RB/WR.
def depth_needed(slots: dict[int, int]) -> dict[str, int]:
    need = {pos: 0 for pos in REPLACEMENT_DEFAULT}
    flex = 0
    for s, n in slots.items():
        if s in DEDICATED:
            need[DEDICATED[s]] += n
        elif s not in NON_STARTING_SLOTS:
            flex += n
    if flex:
        need["RB"] += 1
        need["WR"] += 1
    need["RB"] += 1
    need["WR"] += 1
    return need


def _healthy(p: dict) -> bool:
    return p.get("injury", "ACTIVE") in ("ACTIVE", "QUESTIONABLE", "PROBABLE", "DAY_TO_DAY")


def replacement_levels(free_agents: list[dict]) -> dict[str, float]:
    """N-th best free-agent `value` per position (see REPLACEMENT_NTH)."""
    out = dict(REPLACEMENT_DEFAULT)
    for pos in out:
        vals = sorted([p["value"] for p in free_agents if p["pos"] == pos and p.get("value") is not None],
                      reverse=True)
        n = REPLACEMENT_NTH[pos]
        if len(vals) >= n:
            out[pos] = vals[n - 1]
    return out


def best_available(free_agents: list[dict]) -> dict[str, dict | None]:
    out = {}
    for pos in REPLACEMENT_DEFAULT:
        cands = [p for p in free_agents if p["pos"] == pos and p.get("value") is not None]
        out[pos] = max(cands, key=lambda p: p["value"]) if cands else None
    return out


def positional_needs(roster: list[dict], free_agents: list[dict], slots: dict[int, int],
                     byes_next: dict[str, int] | None = None) -> list[dict]:
    """Where the roster is thin, in plain terms, ranked by urgency.
    byes_next: team -> the upcoming bye week (within the next 2 weeks)."""
    byes_next = byes_next or {}
    repl = replacement_levels(free_agents)
    best = best_available(free_agents)
    starters_at = {pos: 0 for pos in REPLACEMENT_DEFAULT}
    flex = 0
    for s, n in slots.items():
        if s in DEDICATED:
            starters_at[DEDICATED[s]] += n
        elif s not in NON_STARTING_SLOTS:
            flex += n
    needs = []
    for pos, n_start in starters_at.items():
        mine = sorted([p for p in roster if p["pos"] == pos], key=lambda p: -(p.get("value") or 0))
        healthy = [p for p in mine if _healthy(p)]
        out = [p for p in mine if p not in healthy]
        want = n_start + (1 if pos in ("RB", "WR") and flex else 0)
        above = [p for p in healthy if (p.get("value") or 0) >= repl[pos]]
        bye_hits = [p for p in healthy[:want] if p.get("team") in byes_next]
        if out:
            needs.append(dict(pos=pos, kind="injured", urgency=3 if len(healthy) < want else 1,
                              detail=f"{', '.join(p['name'] + ' (' + p['injury'] + ')' for p in out)}"
                                     f"; {len(healthy)} healthy for {want} starting spots"))
        # K and D/ST are streamed one week at a time; "depth" is not a
        # concept there, and sub-point gaps are noise (finding 28).
        streamed = pos in ("K", "DST")
        if len(above) < want and not streamed:
            needs.append(dict(pos=pos, kind="thin", urgency=2,
                              detail=f"only {len(above)} of {want} needed {pos}s beat replacement level "
                                     f"({repl[pos]:.1f}, the #{REPLACEMENT_NTH[pos]} free agent)"))
        if bye_hits and len(healthy) - len(bye_hits) < want:
            needs.append(dict(pos=pos, kind="bye", urgency=2,
                              detail=f"{', '.join(p['name'] + ' wk' + str(byes_next[p['team']]) for p in bye_hits)} on bye soon with no cover"))
        worst_starter = healthy[want - 1] if len(healthy) >= want else None
        b = best[pos]
        margin = 1.5 if streamed else 1.0
        if worst_starter and b and b["value"] > (worst_starter.get("value") or 0) + margin:
            needs.append(dict(pos=pos, kind="upgrade", urgency=1,
                              detail=f"{b['name']} ({b['value']}) on the wire beats your #{want} "
                                     f"{worst_starter['name']} ({worst_starter.get('value')})"))
    needs.sort(key=lambda n: (-n["urgency"], n["pos"]))
    return needs


def drop_candidates(roster: list[dict], lineup: dict, free_agents: list[dict]) -> list[dict]:
    """Bench players ranked most-droppable first: lowest value relative to
    replacement level at the position. Excludes starters, locked players
    (ESPN won't allow it mid-game), IR-slot players, and the only K / D/ST."""
    repl = replacement_levels(free_agents)
    starters = {p["id"] for _, p in lineup["starters"] if p}
    counts = {}
    for p in roster:
        counts[p["pos"]] = counts.get(p["pos"], 0) + 1
    out = []
    for p in roster:
        if p["id"] in starters or p.get("slot") == 21 or p.get("locked"):
            continue
        if p["pos"] in ("K", "DST") and counts.get(p["pos"], 0) <= 1:
            continue
        v = p.get("value") or 0.0
        out.append({**p, "surplus": round(v - repl.get(p["pos"], 0.0), 2)})
    out.sort(key=lambda p: (p["surplus"], p.get("pct_owned", 0)))
    return out


def proposals(roster: list[dict], lineup: dict, free_agents: list[dict],
              slots: dict[int, int] | None = None, max_props: int = 8) -> list[dict]:
    """Add/drop pairs worth asking about.

    gain  = free agent's value minus the value of the roster player he
            would push out of the position's needed depth (or replacement
            level if the depth isn't filled) -- so a backup QB behind a
            healthy starter gains nothing, however good his raw number
    cost  = the drop's value above replacement, if any
    delta = gain - cost, and only pairs with delta > 0.5 are proposed."""
    slots = slots or {0: 1, 2: 2, 3: 1, 4: 2, 6: 1, 16: 1, 17: 1, 20: 7}
    drops = drop_candidates(roster, lineup, free_agents)
    if not drops:
        return []
    repl = replacement_levels(free_agents)
    need = depth_needed(slots)
    mine = {}
    for p in roster:
        if _healthy(p) and p.get("value") is not None:
            mine.setdefault(p["pos"], []).append(p["value"])
    for v in mine.values():
        v.sort(reverse=True)
    d = drops[0]
    cost = max(0.0, d["surplus"])
    fas = sorted([p for p in free_agents if p.get("value") is not None and p.get("team")],
                 key=lambda p: -p["value"])[:80]
    out = []
    for fa in fas:
        if fa["id"] == d["id"]:
            continue
        vals = mine.get(fa["pos"], [])
        n = need.get(fa["pos"], 1)
        displaced = vals[n - 1] if len(vals) >= n else repl[fa["pos"]]
        gain = fa["value"] - displaced
        delta = round(gain - cost, 2)
        if delta <= 0.5:
            continue
        why = []
        if fa.get("pct_change", 0) >= 5:
            why.append(f"+{fa['pct_change']}% owned this week")
        src = fa.get("sources", {})
        if src.get("last_ep") is not None and src.get("last_pts") is not None \
                and src["last_ep"] > src["last_pts"] + 2:
            why.append("usage ahead of scoring (buy before the box score catches up)")
        if fa.get("injury", "ACTIVE") != "ACTIVE":
            why.append(fa["injury"])
        if len(vals) < n:
            why.append(f"fills a {fa['pos']} hole (you carry {len(vals)}, want {n})")
        else:
            why.append(f"pushes out your #{n} {fa['pos']} ({displaced})")
        out.append(dict(add=fa["name"], add_id=fa["id"], add_pos=fa["pos"], add_team=fa["team"],
                        add_value=fa["value"], add_proj=fa["proj"], waiver=fa.get("waiver", False),
                        drop=d["name"], drop_id=d["id"], drop_pos=d["pos"], drop_value=d.get("value"),
                        delta=delta, notes=why))
    out.sort(key=lambda p: -p["delta"])
    return out[:max_props]
