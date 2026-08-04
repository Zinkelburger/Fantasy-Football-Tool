"""Build the season player pool: ADP board joined to actual results.

The pool is every player who either appeared on the preseason ADP board
or recorded a regular-season stat line that year. ADP players with no
stats stay in the pool with zero-point seasons — drafting a bust or a
holdout is part of history and the sim should feel it.

`prior_ppg` is a leak-free preseason expectation: the realized PPG curve
by positional draft slot from the *previous* season, evaluated at each
player's slot this year. Lineup and waiver policies blend it with
observed points, so nobody peeks at the future.
"""

import polars as pl

from .config import POSITIONS, ScoringConfig
from .data import (load_adp, load_expected_points, load_injury_reports,
                   load_rookie_years, load_schedule_byes, load_weekly,
                   norm_name)
from .models import PlayerSeason


def _ppg_curve(prev: pl.DataFrame) -> dict[str, list[float]]:
    """position -> realized PPG by rank (rank 0 = best) last season."""
    totals = (prev.group_by(["player_id", "position"])
              .agg(pl.col("fpts").sum().alias("tot"), pl.len().alias("gp")))
    curve = {}
    for pos in POSITIONS:
        sub = (totals.filter(pl.col("position") == pos)
               .sort("tot", descending=True))
        curve[pos] = [(r["tot"] / max(r["gp"], 1)) for r in sub.iter_rows(named=True)]
    return curve


def build_pool(year: int, sc: ScoringConfig) -> list[PlayerSeason]:
    weekly = load_weekly(year, sc)
    prev = load_weekly(year - 1, sc)
    adp = load_adp(year)
    byes = load_schedule_byes(year)
    rookie_years = load_rookie_years()

    # Actual results, one entry per player who recorded stats this year.
    by_player: dict[str, dict] = {}
    for r in weekly.select(["player_id", "player_display_name", "position",
                            "team", "week", "fpts"]).iter_rows(named=True):
        d = by_player.setdefault(r["player_id"], {
            "name": r["player_display_name"], "pos": r["position"],
            "team": r["team"], "weeks": {}})
        d["weeks"][r["week"]] = float(r["fpts"])
        d["team"] = r["team"]  # keep latest team

    # Previous-season totals: fallback draft rank beyond the ADP board.
    prev_tot = {r["player_id"]: r["tot"] for r in
                prev.group_by("player_id").agg(pl.col("fpts").sum().alias("tot"))
                .iter_rows(named=True)}

    # Name index for ADP matching.
    name_pos: dict[tuple[str, str], str] = {}
    name_only: dict[str, list[str]] = {}
    for pid, d in by_player.items():
        name_pos.setdefault((norm_name(d["name"]), d["pos"]), pid)
        name_only.setdefault(norm_name(d["name"]), []).append(pid)

    pool: dict[str, PlayerSeason] = {}
    matched = set()
    for entry in adp:
        key = (norm_name(entry["name"]), entry["pos"])
        pid = name_pos.get(key)
        if pid is None:
            cands = [c for c in name_only.get(key[0], []) if c not in matched]
            pid = cands[0] if len(cands) == 1 else None
        if pid and pid not in matched:
            matched.add(pid)
            d = by_player[pid]
            pool[pid] = PlayerSeason(
                pid=pid, name=d["name"], pos=entry["pos"], team=d["team"],
                adp=entry["adp"], adp_sd=entry["stdev"],
                rookie=rookie_years.get(pid) == year,
                bye=byes.get(d["team"], 0), week_pts=d["weeks"])
        else:
            # On the board, never recorded a stat: a zero-point season.
            spid = f"adp:{norm_name(entry['name'])}:{entry['pos']}"
            pool[spid] = PlayerSeason(
                pid=spid, name=entry["name"], pos=entry["pos"],
                team=entry.get("team", ""), adp=entry["adp"],
                adp_sd=entry["stdev"], rookie=False,
                bye=byes.get(entry.get("team", ""), 0), week_pts={})

    # Everyone else who played this season (the waiver-wire universe).
    for pid, d in by_player.items():
        if d["pos"] not in POSITIONS:
            continue  # two-way defenders only enter via their ADP listing
        if pid not in pool:
            pool[pid] = PlayerSeason(
                pid=pid, name=d["name"], pos=d["pos"], team=d["team"],
                adp=None, adp_sd=3.0,
                rookie=rookie_years.get(pid) == year,
                bye=byes.get(d["team"], 0), week_pts=d["weeks"])

    players = list(pool.values())
    reports = load_injury_reports(year)
    epts = load_expected_points(year)
    for p in players:
        p.week_status = reports.get(p.pid, {})
        p.week_ep = epts.get(p.pid, {})
    players.sort(key=lambda p: (p.adp if p.adp is not None else 9999,
                                -prev_tot.get(p.pid, 0.0), p.name))
    curve = _ppg_curve(prev)
    pos_seen: dict[str, int] = {}
    for i, p in enumerate(players):
        p.draft_rank = i + 1
        k = pos_seen.get(p.pos, 0)
        pos_seen[p.pos] = k + 1
        p.pos_rank = k + 1
        c = curve[p.pos]
        p.prior_ppg = c[min(k, len(c) - 1)] if c else 0.0
    return players
