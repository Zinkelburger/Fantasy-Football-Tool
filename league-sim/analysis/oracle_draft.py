"""Hindsight-optimal drafts: what does a perfect draft look like?

Beam-search the best possible 15-round snake draft for one seat
against 11 DETERMINISTIC BPA bots (draft the ADP board, fill needs
sanely — the "basic bots that play well"). The oracle knows every
player's actual weekly scores. Objective: total weeks 1-14 points
with hindsight-optimal weekly lineups, no waivers — pure draft value.

Because the bots are deterministic, the whole future board is a
function of the hero's picks alone, so the hero's problem is a search
tree: beam search over (pick sequence), candidates pruned to the top
few remaining players per eligible position by rest-of-season points.

72 solutions (6 years x 12 seats) are mined for patterns: position
sequence by round, timing vs ADP, which positional finish-ranks get
bought, and the size of the oracle-vs-heuristic gap.

Usage:
    oracle_draft.py --test    # one seat: beam-width sanity + timing
    oracle_draft.py           # full 72-seat run + pattern report
"""
import random
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simfl.config import DEFAULT_LEAGUE as LG, DEFAULT_SCORING, SEASONS
from simfl.draft import POS_CAPS, run_draft, snake_order
from simfl.models import Team
from simfl.pool import build_pool
from simfl.strategies import make

WKS = list(range(1, 15))
NT, ROUNDS = LG.n_teams, LG.rounds
PI = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4}
CAPS = tuple(POS_CAPS[p] for p in PI)
START = tuple(LG.starters.get(p, 0) for p in PI)   # (1,2,2,1,1) + FLEX
BEAM = 64
CANDS = {"QB": 2, "RB": 3, "WR": 3, "TE": 2, "K": 1}


class Board:
    """Immutable per-year facts, index-addressed."""

    def __init__(self, pool):
        ps = sorted(pool, key=lambda p: p.draft_rank)
        self.players = ps
        self.pos = [PI[p.pos] for p in ps]
        self.rank = [float(p.draft_rank) for p in ps]
        self.adp = [p.adp for p in ps]
        self.wk = [tuple(p.points(w) if p.played(w) else 0.0 for w in WKS)
                   for p in ps]
        self.tot = [sum(w) for w in self.wk]


def unfilled(cnt):
    """(need per pos incl. FLEX-as-index-5, total)"""
    need = [max(0, START[i] - cnt[i]) for i in range(5)]
    flex_pool = cnt[1] + cnt[2]
    flex = max(0, LG.starters["FLEX"] - max(0, flex_pool - START[1] - START[2]))
    return need, flex, sum(need) + flex


def eligible(cnt, remaining):
    need, flex, ntot = unfilled(cnt)
    if remaining <= ntot:
        out = {i for i in range(5) if need[i]}
        if flex:
            out |= {1, 2}
        return out
    out = set()
    for i in range(5):
        if cnt[i] >= CAPS[i]:
            continue
        if i == 4 and remaining > 2:    # K waits for the endgame
            continue
        out.add(i)
    return out


def bot_pick(board, taken, cnt, nroster):
    """Deterministic BPA: min draft_rank * (0.93 need / 1.08 not)."""
    rnd = nroster + 1
    elig = eligible(cnt, ROUNDS - nroster)
    need, flex, _ = unfilled(cnt)

    def banned(i):
        return ((board.pos[i] == 0 and cnt[0] >= 1 and rnd < 10)
                or (board.pos[i] == 3 and cnt[3] >= 1 and rnd < 11))

    for use_bans in (True, False):
        cands = []
        for i in range(len(board.players)):
            if i in taken or board.pos[i] not in elig:
                continue
            if use_bans and banned(i):
                continue
            cands.append(i)
            if len(cands) == 40:
                break
        if cands:
            break
    best, bs = None, None
    for i in cands:
        p = board.pos[i]
        fills = need[p] > 0 or (flex > 0 and p in (1, 2))
        s = board.rank[i] * (0.93 if fills else 1.08)
        if bs is None or s < bs:
            best, bs = i, s
    return best


def hero_eval(board, picks):
    """Weeks 1-14 points with hindsight-optimal lineups."""
    total = 0.0
    for w in range(14):
        qb = te = k = 0.0
        rbs, wrs = [], []
        for i in picks:
            pts = board.wk[i][w]
            p = board.pos[i]
            if p == 0:
                qb = max(qb, pts)
            elif p == 3:
                te = max(te, pts)
            elif p == 4:
                k = max(k, pts)
            elif p == 1:
                rbs.append(pts)
            else:
                wrs.append(pts)
        rbs.sort(reverse=True)
        wrs.sort(reverse=True)
        base = sum(rbs[:2]) + sum(wrs[:2])
        r3 = rbs[2] if len(rbs) > 2 else 0.0
        w3 = wrs[2] if len(wrs) > 2 else 0.0
        total += qb + te + k + base + max(r3, w3)
    return total


def advance(board, taken, counts, seat, from_pick, to_pick, order):
    """Apply deterministic bot picks in [from_pick, to_pick)."""
    for g in range(from_pick, to_pick):
        s = order[g]
        if s == seat:
            continue
        i = bot_pick(board, taken, counts[s], sum(counts[s]))
        taken.add(i)
        c = list(counts[s]); c[board.pos[i]] += 1
        counts[s] = tuple(c)


def oracle_seat(board, seat, beam_width=BEAM):
    order = snake_order(NT, ROUNDS)
    hero_picks_at = [g for g, s in enumerate(order) if s == seat]
    taken0, counts0 = set(), [(0, 0, 0, 0, 0)] * NT
    advance(board, taken0, counts0, seat, 0, hero_picks_at[0], order)
    beam = [(0.0, taken0, tuple(counts0), ())]
    for lvl in range(ROUNDS):
        nxt = []
        g_now = hero_picks_at[lvl]
        g_next = hero_picks_at[lvl + 1] if lvl + 1 < ROUNDS else len(order)
        for _, taken, counts, picks in beam:
            elig = eligible(counts[seat], ROUNDS - lvl)
            cands = []
            per = Counter()
            for i in sorted((j for j in range(len(board.players))
                             if j not in taken and board.pos[j] in elig),
                            key=lambda j: -board.tot[j]):
                pname = "QBRBWRTEK"
                pos_i = board.pos[i]
                key = pos_i
                lim = CANDS[("QB", "RB", "WR", "TE", "K")[pos_i]]
                if per[key] >= lim:
                    continue
                per[key] += 1
                cands.append(i)
            for i in cands:
                t2 = set(taken); t2.add(i)
                c2 = list(counts)
                cc = list(c2[seat]); cc[board.pos[i]] += 1
                c2[seat] = tuple(cc)
                advance(board, t2, c2, seat, g_now + 1, g_next, order)
                p2 = picks + (i,)
                nxt.append((hero_eval(board, p2), t2, tuple(c2), p2))
        nxt.sort(key=lambda t: -t[0])
        beam = nxt[:beam_width]
    return beam[0]


def bot_rosters(board, seat):
    """Final rosters of the 11 bots when the hero seat is filled by the
    oracle path is irrelevant for bot totals? No — the board interacts.
    For all-play we re-derive bot rosters alongside a given hero pick
    sequence."""


def replay(board, seat, hero_seq):
    """Replay full draft with scripted hero picks; return all rosters."""
    order = snake_order(NT, ROUNDS)
    taken = set()
    counts = [(0, 0, 0, 0, 0)] * NT
    rosters = [[] for _ in range(NT)]
    hi = 0
    for g, s in enumerate(order):
        if s == seat:
            i = hero_seq[hi]; hi += 1
        else:
            i = bot_pick(board, taken, counts[s], sum(counts[s]))
        taken.add(i)
        c = list(counts[s]); c[board.pos[i]] += 1
        counts[s] = tuple(c)
        rosters[s].append(i)
    return rosters


def all_play(board, rosters, seat):
    """Hero weekly all-play vs 11 bots, everyone hindsight lineups."""
    weekly = []
    for r in rosters:
        pts = []
        for w in range(14):
            sub = [(board.wk[i][w], board.pos[i]) for i in r]
            qb = max([p for p, q in sub if q == 0], default=0)
            te = max([p for p, q in sub if q == 3], default=0)
            k = max([p for p, q in sub if q == 4], default=0)
            rbs = sorted((p for p, q in sub if q == 1), reverse=True)
            wrs = sorted((p for p, q in sub if q == 2), reverse=True)
            fl = max(rbs[2] if len(rbs) > 2 else 0,
                     wrs[2] if len(wrs) > 2 else 0)
            pts.append(qb + te + k + sum(rbs[:2]) + sum(wrs[:2]) + fl)
        weekly.append(pts)
    wins = tot = 0
    for w in range(14):
        for s in range(NT):
            if s == seat:
                continue
            tot += 1
            wins += weekly[seat][w] > weekly[s][w]
    return wins / tot


def heuristic_roster(pool, year, seat, hero):
    """Draft via the real engine (hero vs 11 bpa), return hero pids."""
    rng = random.Random(year * 1000 + seat)
    strat = [make("bpa") for _ in range(NT)]
    strat[seat] = make(hero)
    for s in strat:
        s.bind_year(year)
    teams = [Team(idx=j, name=str(j), strategy=s)
             for j, s in enumerate(strat)]
    run_draft(pool, teams, LG, rng)
    return [p.pid for p in teams[seat].roster]


def main():
    test = "--test" in sys.argv
    years = SEASONS[:1] if test else SEASONS
    seats = [0] if test else range(NT)

    seq_rows = []            # (year, seat, [(round, posname, idx)], total, ap)
    gaps = defaultdict(list)
    for year in years:
        pool = build_pool(year, DEFAULT_SCORING)
        board = Board(pool)
        pid_ix = {p.pid: i for i, p in enumerate(board.players)}
        # hindsight positional finish rank
        finish = {}
        for pos in range(5):
            ids = sorted((i for i in range(len(board.players))
                          if board.pos[i] == pos),
                         key=lambda i: -board.tot[i])
            for r, i in enumerate(ids, 1):
                finish[i] = r
        if test:
            import time
            for bw in (24, 48, 64, 96):
                t0 = time.time()
                sc, *_ = oracle_seat(board, 0, bw)
                print(f"beam {bw:3d}: {sc:7.1f} pts  "
                      f"({time.time()-t0:.1f}s)", flush=True)
            return
        for seat in seats:
            sc, _, _, picks = oracle_seat(board, seat)
            rosters = replay(board, seat, picks)
            ap = all_play(board, rosters, seat)
            seq_rows.append((year, seat, picks, sc, ap, board, finish))
            for hero in ("bpa", "robust_rb", "pick_value"):
                pids = heuristic_roster(pool, year, seat, hero)
                hpts = hero_eval(board, [pid_ix[p] for p in pids])
                gaps[hero].append(sc - hpts)
            gaps["oracle_pts"].append(sc)
            gaps["oracle_ap"].append(ap)
        print(f"done {year}", flush=True)

    # ---- pattern mining ---------------------------------------------
    n = len(seq_rows)
    print(f"\n=== {n} hindsight-optimal drafts vs disciplined BPA rooms ===")
    print(f"oracle: {st.mean(gaps['oracle_pts']):.0f} pts/season, "
          f"all-play {st.mean(gaps['oracle_ap']):.3f}")
    for hero in ("bpa", "robust_rb", "pick_value"):
        print(f"  gap over {hero:10s}: {st.mean(gaps[hero]):+6.0f} pts/season")

    posname = ("QB", "RB", "WR", "TE", "K")
    by_round = defaultdict(Counter)
    reach = defaultdict(list)
    undrafted = defaultdict(int)
    ranks_bought = defaultdict(list)
    first3 = Counter()
    qb1_round, te1_round = [], []
    for year, seat, picks, sc, ap, board, finish in seq_rows:
        seen_qb = seen_te = False
        for rnd, i in enumerate(picks, 1):
            pn = posname[board.pos[i]]
            by_round[rnd][pn] += 1
            overall = None
            adp = board.adp[i]
            if adp is None or adp > 180:
                undrafted[rnd] += 1
            else:
                order = snake_order(NT, ROUNDS)
                gpick = [g for g, s in enumerate(order) if s == seat][rnd-1]+1
                reach[rnd].append(adp - gpick)
            ranks_bought[(rnd, pn)].append(finish[i])
            if rnd <= 3:
                first3[pn] += 1
            if pn == "QB" and not seen_qb:
                qb1_round.append(rnd); seen_qb = True
            if pn == "TE" and not seen_te:
                te1_round.append(rnd); seen_te = True

    print("\nposition share by round (72 optimal drafts):")
    print("rnd  " + "".join(f"{p:>6s}" for p in posname)
          + "   med(ADP-pick)  undrafted%")
    for rnd in range(1, ROUNDS + 1):
        c = by_round[rnd]
        row = "".join(f"{c.get(p,0)/n:6.0%}" for p in posname)
        md = (f"{st.median(reach[rnd]):+9.0f}    " if reach[rnd]
              else "        -    ")
        print(f"{rnd:3d}  {row}   {md} {undrafted[rnd]/n:9.0%}")

    tot3 = sum(first3.values())
    print("\nfirst-3-round mix: " + "  ".join(
        f"{p}:{first3.get(p,0)/tot3:.0%}" for p in posname))
    print(f"QB1 round: median {st.median(qb1_round):.0f} "
          f"(p25 {sorted(qb1_round)[n//4]}, p75 {sorted(qb1_round)[3*n//4]})")
    print(f"TE1 round: median {st.median(te1_round):.0f}")
    print("\nhindsight finish-rank bought (median), rounds 1-6:")
    for rnd in range(1, 7):
        parts = []
        for p in posname:
            v = ranks_bought.get((rnd, p))
            if v:
                parts.append(f"{p}{st.median(v):.0f} (n={len(v)})")
        print(f"  rnd {rnd}: " + "  ".join(parts))


if __name__ == "__main__":
    main()
