"""Is NEWS_PROMOTE = 0.75 the right multiplier?

Replays the sim's exact promotion rule against reality: every week a
team's top preseason RB (ADP <= 120) sat and a teammate RB played,
compare the backup's ACTUAL points that week to
    max(backup's own EWMA, k * starter's projection)
for a range of k, plus the no-promotion baseline (k=0).  Error metrics
tell us which k predicts promoted-backup scoring best and whether 0.75
is biased high or low.
"""

import numpy as np

from common import SEASONS
from simfl.config import DEFAULT_SCORING
from simfl.lineup import STARTER_ADP_CUTOFF, ProjectionTable
from simfl.pool import build_pool


class RawTable(ProjectionTable):
    """ProjectionTable without the news promotion applied."""

    def _promote_backups(self, pool, max_week):
        pass


def collect_events():
    events = []
    for year in SEASONS:
        pool = build_pool(year, DEFAULT_SCORING)
        raw = RawTable(pool)
        by_team = {}
        for p in pool:
            if p.pos == "RB" and p.team:
                by_team.setdefault(p.team, []).append(p)
        for rbs in by_team.values():
            rbs.sort(key=lambda p: p.draft_rank)
            starter = rbs[0]
            if starter.adp is None or starter.adp > STARTER_ADP_CUTOFF:
                continue
            spell = 0
            for w in range(1, 18):
                if starter.played(w):
                    spell = 0
                    continue
                if starter.on_bye(w):
                    continue
                spell += 1
                cuff = next((p for p in rbs[1:] if p.played(w)), None)
                if cuff is None:
                    continue
                events.append({
                    "year": year, "week": w, "spell": spell,
                    "starter": starter.name, "cuff": cuff.name,
                    "starter_proj": raw.proj(starter, w),
                    "cuff_raw": raw.proj(cuff, w),
                    "cuff_actual": cuff.points(w),
                })
    return events


if __name__ == "__main__":
    ev = collect_events()
    actual = np.array([e["cuff_actual"] for e in ev])
    sproj = np.array([e["starter_proj"] for e in ev])
    craw = np.array([e["cuff_raw"] for e in ev])
    spell = np.array([e["spell"] for e in ev])
    print(f"n={len(ev)} promotion weeks, 2020-2025")
    print(f"promoted backup actually scored: mean {actual.mean():.1f}, "
          f"median {np.median(actual):.1f} ppg")
    print(f"sidelined starter projection:    mean {sproj.mean():.1f} ppg")
    print(f"implied ratio mean(actual)/mean(starter_proj) = "
          f"{actual.mean() / sproj.mean():.2f}")
    print(f"backup's own EWMA (no news):     mean {craw.mean():.1f} ppg\n")

    print("k     mean prediction   bias(pred-actual)   MAE")
    for k in [0.0, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0]:
        pred = np.maximum(craw, k * sproj)
        print(f"{k:.2f}   {pred.mean():13.1f}   {(pred - actual).mean():+16.1f}"
              f"   {np.abs(pred - actual).mean():5.1f}")

    print("\nBy absence-spell week (does the rule age well?):")
    for lo, hi, tag in [(1, 1, "wk 1 of absence"), (2, 3, "wks 2-3"),
                        (4, 99, "wk 4+ (long/season-ending)")]:
        m = (spell >= lo) & (spell <= hi)
        if not m.any():
            continue
        r = actual[m].mean() / sproj[m].mean()
        print(f"  {tag:26s} n={m.sum():4d}  backup actual {actual[m].mean():4.1f} "
              f"vs starter proj {sproj[m].mean():4.1f}  ratio {r:.2f}")
