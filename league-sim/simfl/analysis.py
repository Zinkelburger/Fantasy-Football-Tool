"""Descriptive analyses straight from the historical data (no sim):
the evidence slides that motivate each strategy.

- kicker_persistence: does the hot week-1 kicker stay hot?
- streaming_supply: if you punt TE/QB on draft day, what does the
  waiver wire actually offer, and when is it identifiable?
- scarcity: points by positional rank — why the early rounds are RB/WR
  and why K is a last-round pick.
"""

from .config import SEASONS, DEFAULT_SCORING
from .models import PlayerSeason
from .pool import build_pool

MIN_GAMES = 6


def _pools(years):
    return {y: build_pool(y, DEFAULT_SCORING) for y in years}


def _ppg(p: PlayerSeason, weeks) -> float:
    pts = [p.week_pts.get(w, 0.0) for w in weeks if w in p.week_pts]
    return sum(pts) / len(pts) if pts else 0.0


def _ros(p: PlayerSeason, after: int, last: int = 17) -> float:
    """Rest-of-season PPG over games actually played after `after`."""
    return _ppg(p, range(after + 1, last + 1))


def _games_after(p: PlayerSeason, after: int, last: int = 17) -> int:
    return sum(1 for w in p.week_pts if after < w <= last)


def kicker_persistence(years=SEASONS) -> list[dict]:
    """For each season: the top kicker after week 1 (and weeks 1-4),
    where they finished rest-of-season among kickers."""
    out = []
    for y, pool in _pools(years).items():
        ks = [p for p in pool if p.pos == "K"]
        ros_rank = sorted([k for k in ks if _games_after(k, 1) >= MIN_GAMES],
                          key=lambda p: -_ros(p, 1))
        wk1 = max(ks, key=lambda p: p.week_pts.get(1, -1))
        wk1_ros = next((i + 1 for i, p in enumerate(ros_rank) if p.pid == wk1.pid), None)
        by4 = sorted([k for k in ks if sum(1 for w in k.week_pts if w <= 4) >= 3],
                     key=lambda p: -_ppg(p, range(1, 5)))
        top4 = by4[0] if by4 else None
        ros4_rank = sorted([k for k in ks if _games_after(k, 4) >= MIN_GAMES],
                           key=lambda p: -_ros(p, 4))
        t4_ros = (next((i + 1 for i, p in enumerate(ros4_rank) if p.pid == top4.pid), None)
                  if top4 else None)
        out.append({
            "year": y, "n_kickers": len(ros_rank),
            "wk1_top": wk1.name, "wk1_pts": wk1.week_pts.get(1, 0),
            "wk1_top_ros_rank": wk1_ros,
            "wk1_4_top": top4.name if top4 else "-",
            "wk1_4_top_ros_rank": t4_ros,
        })
    return out


def streaming_supply(pos: str, years=SEASONS, top_n: int = 8,
                     after: int = 3) -> list[dict]:
    """Punting `pos`: what did the wire hold? For each season, the
    rest-of-season top-N at the position, flagged undrafted (no ADP =
    free after the draft in a 12-team room), plus whether the best
    undrafted one had already shown itself by week `after`."""
    out = []
    for y, pool in _pools(years).items():
        ps = [p for p in pool if p.pos == pos]
        drafted = [p for p in ps if p.adp is not None]
        ros = sorted([p for p in ps if _games_after(p, after) >= MIN_GAMES],
                     key=lambda p: -_ros(p, after))
        topn = ros[:top_n]
        undrafted_top = [p for p in topn if p.adp is None]
        # the starter a drafter got by taking pos early: ~pos-slot 6 ADP
        early_pick = drafted[min(5, len(drafted) - 1)] if drafted else None
        best_un = undrafted_top[0] if undrafted_top else None
        shown = None
        if best_un is not None:
            early_ppg = _ppg(best_un, range(1, after + 1))
            all_early = sorted([p for p in ps], key=lambda p: -_ppg(p, range(1, after + 1)))
            shown = next((i + 1 for i, p in enumerate(all_early)
                          if p.pid == best_un.pid), None)
        out.append({
            "year": y,
            "ros_top_names": [(p.name, round(_ros(p, after), 1),
                               "FA" if p.adp is None else f"ADP{p.adp:.0f}")
                              for p in topn],
            "n_undrafted_in_top": len(undrafted_top),
            "best_undrafted": best_un.name if best_un else "-",
            "best_undrafted_ros": round(_ros(best_un, after), 1) if best_un else 0,
            "best_undrafted_rank_by_wk": shown,
            "early_pick": early_pick.name if early_pick else "-",
            "early_pick_ros": round(_ros(early_pick, after), 1) if early_pick else 0,
        })
    return out


def scarcity(years=SEASONS) -> dict[str, list[float]]:
    """Average season PPG by positional rank (rank by season PPG,
    min games), averaged across seasons: the value-curve chart."""
    from .config import POSITIONS
    acc: dict[str, list[list[float]]] = {pos: [] for pos in POSITIONS}
    for y, pool in _pools(years).items():
        for pos in POSITIONS:
            ranked = sorted([p for p in pool
                             if p.pos == pos and len(p.week_pts) >= MIN_GAMES],
                            key=lambda p: -_ppg(p, range(1, 18)))
            acc[pos].append([_ppg(p, range(1, 18)) for p in ranked[:40]])
    out = {}
    for pos, seasons in acc.items():
        depth = min(len(s) for s in seasons)
        out[pos] = [sum(s[i] for s in seasons) / len(seasons) for i in range(depth)]
    return out
