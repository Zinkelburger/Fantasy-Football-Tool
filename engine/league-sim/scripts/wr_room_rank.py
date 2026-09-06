"""Does a receiver's rank inside his own team's WR room predict anything
the price does not already know?

Finding 08 tested "clear WR1 on a losing team" as one combined archetype
and the bad-team half did not survive price standardization. This script
tests the *other* half on its own, in the form a drafter actually faces
on the clock: he is looking at a receiver, and he can see whether that
receiver is his own offense's first, second or third option by ADP.

Rules of the road are finding 08's, unchanged and reused from
wr_archetypes.py: price-standardized outcome gaps (direct
standardization over round-aligned bands), bootstrap CIs, and the same
top-24 / bust-45 thresholds. A raw gap is never the answer -- room rank
correlates hard with price, and the whole question is what is left once
price is held fixed.

Run from league-sim root:
  venv/bin/python scripts/wr_room_rank.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wr_archetypes as wa

HIT, BUST = wa.HIT, wa.BUST


def build_rooms(years):
    """wr_archetypes rows + each receiver's ordinal rank in his own room."""
    rows = wa.add_resid(wa.build(list(years)))
    by_team = {}
    for r in rows:
        by_team.setdefault((r["year"], r.get("team")), []).append(r)
    return rows


def add_room_rank(rows, pools):
    """room_rank = 1 for the team's first WR off the board, 2 for the
    second, etc. Computed from ADP order, so it is knowable on the clock."""
    groups = {}
    for r in rows:
        groups.setdefault((r["year"], r["team"]), []).append(r)
    for (_, team), grp in groups.items():
        if team is None:
            continue
        for i, r in enumerate(sorted(grp, key=lambda x: x["adp"])):
            r["room_rank"] = i + 1
    for r in rows:
        r.setdefault("room_rank", None)
    return rows


def report(rows, label, flag):
    """Full battery for one flag: board-wide, per band, era, LOYO."""
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    n = sum(1 for r in rows if flag(r))
    print(f"  n={n} flagged, {len(rows)-n} peers\n")

    print("  outcome            flagged   peers    gap (price-standardized)")
    for name, test in (("top-12 finish", lambda r: r["finish"] <= 12),
                       ("top-24 finish", lambda r: r["finish"] <= HIT),
                       (f"bust (>WR{BUST})", lambda r: r["finish"] > BUST)):
        sel = [r for r in rows if flag(r)]
        peer = [r for r in rows if not flag(r)]
        s, lo, hi = wa.stratified(rows, flag, test)
        sig = "*" if not lo <= 0 <= hi else " "
        print(f"  {name:<18} {sum(test(r) for r in sel)/len(sel):6.0%} "
              f"{sum(test(r) for r in peer)/len(peer):7.0%}    "
              f"{s:+5.1%} [{lo:+5.1%},{hi:+5.1%}]{sig}")

    print("\n  by price band (within-band, price already held fixed):")
    print("  band          n     top-24 flagged/peers    mean price-adj gap")
    for bname, band in wa.FULL_BANDS:
        e = wa.effect(rows, flag, band)
        if e.get("diff") is None:
            print(f"  {bname:<12} n={e['n']:<4} (too few)")
            continue
        sig = "*" if not e["hitd"][1] <= 0 <= e["hitd"][2] else " "
        print(f"  {bname:<12} {e['n']:<5} {e['hit']:6.0%} / {e['peer_hit']:<6.0%}"
              f"      {e['diff']:+6.1f}   hit gap {e['hitd'][0]:+5.1%}"
              f" [{e['hitd'][1]:+5.1%},{e['hitd'][2]:+5.1%}]{sig}")

    # Robustness is run per outcome, not just on top-24: a flag can be
    # noise on hit rate and real on bust rate (they are different
    # questions -- "does he start" vs "does he ruin the pick").
    early = [r for r in rows if r["year"] <= 2020]
    late = [r for r in rows if r["year"] >= 2021]
    for name, test in (("top-24 finish", lambda r: r["finish"] <= HIT),
                       (f"bust (>WR{BUST})", lambda r: r["finish"] > BUST)):
        print(f"\n  robustness -- {name} (price-standardized):")
        for nm, sub in (("era 2016-20", early), ("era 2021-25", late)):
            s, lo, hi = wa.stratified(sub, flag, test)
            print(f"    {nm:<14} {s:+5.1%} [{lo:+5.1%},{hi:+5.1%}]")
        outs = []
        for y in sorted({r["year"] for r in rows}):
            s, _, _ = wa.stratified([r for r in rows if r["year"] != y],
                                    flag, test)
            outs.append(s)
        print("    leave-one-year-out: " + " ".join(f"{s:+.1%}" for s in outs))
        print(f"    -> range [{min(outs):+.1%}, {max(outs):+.1%}], "
              f"sign flips: {'YES' if min(outs)*max(outs) < 0 else 'no'}")


if __name__ == "__main__":
    rows = wa.add_resid(wa.build(list(wa.FULL_YEARS)))
    rows = add_room_rank(rows, None)
    rows = [r for r in rows if r.get("room_rank")]

    print(f"built {len(rows)} priced WR seasons, {min(r['year'] for r in rows)}"
          f"-{max(r['year'] for r in rows)}")
    dist = {}
    for r in rows:
        dist[r["room_rank"]] = dist.get(r["room_rank"], 0) + 1
    print("room-rank distribution:",
          " ".join(f"WR{k}:{v}" for k, v in sorted(dist.items())))

    # Raw picture first, then the standardized tests.
    print("\n== raw (NOT price-adjusted -- room rank tracks price hard) ==")
    print("  room rank   n     median ADP   top-24   bust")
    for rr in sorted(dist):
        sel = [r for r in rows if r["room_rank"] == rr]
        if len(sel) < 10:
            continue
        adps = sorted(r["adp"] for r in sel)
        print(f"  WR{rr:<9} {len(sel):<5} {adps[len(adps)//2]:9.0f}   "
              f"{sum(r['finish'] <= HIT for r in sel)/len(sel):5.0%}  "
              f"{sum(r['finish'] > BUST for r in sel)/len(sel):5.0%}")

    report(rows, "NOT his team's #1 WR by ADP (the whole board)",
           lambda r: r["room_rank"] > 1)
    report(rows, "3rd or lower in his own room (the whole board)",
           lambda r: r["room_rank"] >= 3)

    mid = [r for r in rows if wa.BAND[0] <= r["adp"] <= wa.BAND[1]]
    print(f"\n\n### restricted to the mid-round window ADP "
          f"{wa.BAND[0]}-{wa.BAND[1]} (n={len(mid)})")
    report(mid, "NOT his team's #1 WR -- mid-round window only",
           lambda r: r["room_rank"] > 1)
