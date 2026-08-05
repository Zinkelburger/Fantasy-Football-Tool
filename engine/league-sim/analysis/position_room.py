"""Where a player sits in his own team's position room on the draft board.

Is he his team's WR1, how far back is the next one, and did his team
spend a real pick at his position this year? All of it is knowable on
draft day: preseason ADP + that season's roster + that year's draft.

This is **description, not prediction**. The room order is read off ADP,
so it is not a disagreement with the market — finding 25 measured the
room features adding nothing on top of ADP as a ranking input. What it
is good for is telling a drafter who a player has to beat out, which the
ADP number alone does not say.

It lives in its own file because it outlived the projection model it was
born in: that model is retired (see archive/season-projection-model/),
but the room readout still ships in the draft tool's player note.

Usage: position_room.py      (writes the three per-format CSVs)
Output: data/market/position_room_2026{,_half,_ppr}.csv
"""
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from simfl.pool import build_pool                       # noqa: E402
from simfl.config import DEFAULT_SCORING                # noqa: E402
from simfl.data import norm_name                        # noqa: E402

DATA = ROOT / "data"
MKT = DATA / "market"
POSITIONS = ("QB", "RB", "WR", "TE")

MISS_ADP = 250.0      # off the draft board entirely
GAP_CAP = 200.0       # cap on ADP gaps so one outlier can't dominate
# PFR draft-table codes -> nflverse roster codes
PFR2NFL = {"GNB": "GB", "KAN": "KC", "LAR": "LA", "LVR": "LV",
           "NOR": "NO", "NWE": "NE", "SFO": "SF", "TAM": "TB"}
_FMT = {0.0: "std", 0.5: "half", 1.0: "ppr"}
ROOM_COLS = ("room_rank", "room_ahead", "room_ahead_gap", "room_behind",
             "room_behind_gap", "rook_pick", "rook_name")

SCORINGS = (("standard", 0.0, "position_room_2026.csv"),
            ("half PPR", 0.5, "position_room_2026_half.csv"),
            ("full PPR", 1.0, "position_room_2026_ppr.csv"))


def roster(year):
    """gsis_id -> team / position / name for one season's skill players."""
    r = pd.read_parquet(MKT / f"roster_{year}.parquet")
    r = r[r.position.isin(POSITIONS)].dropna(subset=["gsis_id"])
    r = r.drop_duplicates("gsis_id", keep="last")
    return r.set_index("gsis_id")[["team", "position", "full_name"]]


def adp_by_pid(year, ppr=0.0):
    """gsis_id -> preseason ADP for `year`.

    Past years come from the sim pool (the FFC board). The upcoming
    season has no stat lines yet, so the pool can't be built — it comes
    from the ADP snapshot engine/update_ranks.py writes, matched on
    name + position."""
    snap = MKT / f"adp_{year}.csv"
    if not snap.exists():
        return {p.pid: p.adp for p in build_pool(year, DEFAULT_SCORING)
                if p.adp is not None}
    idx = {}
    for pid, r in roster(year).iterrows():
        if pd.notna(r.full_name):
            idx.setdefault((r.position, norm_name(r.full_name)), pid)
    fmt = _FMT[ppr]
    out = {}
    with open(snap, newline="") as f:
        for row in csv.DictReader(f):
            pid = idx.get((row["pos"], norm_name(row["player"])))
            if pid is None:
                continue
            for col in (f"ffc_{fmt}", f"sleeper_{fmt}"):
                try:
                    out[pid] = float(row[col])
                    break
                except (KeyError, TypeError, ValueError):
                    continue
    return out


def rookie_capital(year):
    """(team, position) -> (overall pick, name) for the earliest pick a
    team spent at that position in the `year` draft."""
    d = pd.read_parquet(MKT / "draft_picks.parquet")
    out = {}
    for r in d[d.season == year].itertuples():
        k = (PFR2NFL.get(r.team, r.team), r.position)
        if k not in out or r.pick < out[k][0]:
            out[k] = (float(r.pick), r.pfr_player_name)
    return out


def room_standing(year, ppr=0.0):
    """gsis_id -> his standing in his own team's position room."""
    ros = roster(year)
    adp = adp_by_pid(year, ppr)
    rook = rookie_capital(year)
    name = {pid: r.full_name for pid, r in ros.iterrows()}

    rooms = {}
    for pid, r in ros.iterrows():
        rooms.setdefault((r.team, r.position), []).append(
            (adp.get(pid, MISS_ADP), pid))

    out = {}
    for (team, pos), mates in rooms.items():
        mates.sort()
        rp, rn = rook.get((team, pos), (300.0, ""))
        for i, (own, pid) in enumerate(mates):
            ahead = mates[i - 1] if i else None
            behind = mates[i + 1] if i + 1 < len(mates) else None
            drafted = own < MISS_ADP
            has_behind = behind is not None and behind[0] < MISS_ADP
            out[pid] = dict(
                room_rank=i + 1,
                room_ahead=name.get(ahead[1], "") if ahead else "",
                room_ahead_gap=(round(min(GAP_CAP, own - ahead[0]))
                                if ahead and drafted else ""),
                room_behind=name.get(behind[1], "") if has_behind else "",
                room_behind_gap=(round(min(GAP_CAP, behind[0] - own))
                                 if has_behind and drafted else ""),
                rook_pick=int(rp) if rp < 300 else "",
                rook_name=rn if rp < 300 else "",
                # ln of the earliest pick spent at his position; the one
                # depth-chart read that is NOT taken off the ADP board.
                tm_rook_pick=float(np.log(rp)),
            )
    return out


def main():
    ros = roster(2026)
    for label, ppr, fname in SCORINGS:
        rooms = room_standing(2026, ppr)
        dst = MKT / fname
        with open(dst, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["name", "pos", "team", *ROOM_COLS])
            n = 0
            for pid, r in ros.iterrows():
                d = rooms.get(pid)
                if d is None or pd.isna(r.full_name):
                    continue
                w.writerow([r.full_name, r.position, r.team,
                            *(d[c] for c in ROOM_COLS)])
                n += 1
        print(f"{label:9s} {n:4d} players -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
