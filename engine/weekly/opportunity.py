"""Weekly opportunity table for a season.

Per player-week: usage counts, expected points (ep_<fmt>) from the
fitted model, actual points, and a leak-free EWMA of expected points
that stands for "what this player's role is worth right now".

    ewma_ep[w] = a * ep[w] + (1 - a) * ewma_ep[w-1],   a = 0.35

The EWMA is seeded with the player's prior-season expected points per
game (shrunk toward the position's replacement level by how few games
he played), so week 1 of a season is not blank and a player coming off
a 17-game role does not read the same as a rookie. `ewma_ep_pre` is the
value going INTO the week (uses only earlier weeks), which is what a
start/sit decision should use; `ewma_ep` includes the week itself.

Outputs (data/weekly/):
  opportunity_<season>_weekly.csv   one row per player-week
  opportunity_<season>.csv          one row per player, season to date
"""
from __future__ import annotations

import sys

import polars as pl

from common import DATA, FORMATS, SKILL
import ep_model
import nfl_data

ALPHA = 0.35
PRIOR_GAMES = 4          # prior-season games at which the seed is trusted fully
REPLACEMENT = {           # half-PPR points/game a free agent is worth; the
    "QB": 8.0, "RB": 4.0, "WR": 4.0, "TE": 3.0}   # shrinkage target for seeds
# Standard/PPR seeds scale from the half-PPR level; close enough for a
# prior that fades after four games.
REPL_SCALE = {"std": 0.85, "half": 1.0, "ppr": 1.15}


def season_ep(season: int, refresh: bool) -> pl.DataFrame:
    """Per player-game rows with ep_<fmt> and pts_<fmt>."""
    coef = ep_model.load_coef()
    df = ep_model.panel(season, refresh)
    parts = []
    for pos in SKILL:
        sub = df.filter(pl.col("position") == pos)
        if not sub.height:
            continue
        cols = {f"ep_{fmt}": ep_model.predict(sub, coef, pos, fmt) for fmt in FORMATS}
        parts.append(sub.with_columns([pl.Series(k, v) for k, v in cols.items()]))
    out = pl.concat(parts) if parts else df
    return out.with_columns([pl.col(f"ep_{f}").clip(lower_bound=0.0) for f in FORMATS])


def prior_seeds(prev: pl.DataFrame) -> dict[str, dict[str, float]]:
    """player_id -> {fmt: seed} from the previous season's per-game EP,
    shrunk toward replacement level by games played / PRIOR_GAMES."""
    g = prev.group_by(["player_id", "position"]).agg(
        [pl.len().alias("games")] + [pl.col(f"ep_{f}").mean().alias(f) for f in FORMATS])
    seeds = {}
    for r in g.iter_rows(named=True):
        w = min(1.0, r["games"] / PRIOR_GAMES)
        repl = REPLACEMENT.get(r["position"], 3.0)
        seeds[r["player_id"]] = {f: w * r[f] + (1 - w) * repl * REPL_SCALE[f]
                                 for f in FORMATS}
    return seeds


def build(season: int, refresh: bool = True) -> tuple[pl.DataFrame, pl.DataFrame]:
    cur = season_ep(season, refresh)
    try:
        prev = season_ep(season - 1, refresh=False)
    except Exception:  # noqa: BLE001 - first season of data
        prev = cur.clear()
    seeds = prior_seeds(prev) if prev.height else {}

    rows = []
    cur = cur.sort(["player_id", "week"])
    for pid, grp in cur.group_by("player_id", maintain_order=True):
        pid = pid[0]
        pos = grp["position"][0]
        state = seeds.get(pid) or {f: REPLACEMENT.get(pos, 3.0) * REPL_SCALE[f] for f in FORMATS}
        seeded = pid in seeds
        for r in grp.iter_rows(named=True):
            row = dict(r)
            for f in FORMATS:
                pre = state[f]
                post = ALPHA * r[f"ep_{f}"] + (1 - ALPHA) * pre
                row[f"ewma_ep_pre_{f}"] = pre
                row[f"ewma_ep_{f}"] = post
                state[f] = post
            row["seeded_from_prior"] = seeded
            rows.append(row)
    weekly = pl.DataFrame(rows) if rows else cur.clear()

    if weekly.height:
        aggs = [pl.len().cast(pl.Int64).alias("games"), pl.col("team").last().alias("team"),
                pl.col("name").last().alias("name"), pl.col("position").first().alias("pos"),
                pl.col("week").max().alias("last_week")]
        for f in FORMATS:
            aggs += [pl.col(f"ep_{f}").mean().alias(f"ep_{f}"),
                     pl.col(f"pts_{f}").mean().alias(f"pts_{f}"),
                     pl.col(f"ewma_ep_{f}").last().alias(f"ewma_ep_{f}"),
                     pl.col(f"ep_{f}").last().alias(f"last_ep_{f}"),
                     pl.col(f"pts_{f}").last().alias(f"last_pts_{f}")]
        for c in ("rush_att", "tgt", "rush_rz", "tgt_rz", "tgt_ez", "air_yds", "pass_att"):
            aggs.append(pl.col(c).mean().alias(f"{c}_pg"))
        season_tbl = weekly.group_by("player_id").agg(aggs)
        for f in FORMATS:
            season_tbl = season_tbl.with_columns(
                (pl.col(f"pts_{f}") - pl.col(f"ep_{f}")).alias(f"gap_{f}"))
        season_tbl = season_tbl.sort("ewma_ep_half", descending=True)
    else:
        season_tbl = weekly

    # Players with a prior-season seed but no game yet this season still
    # deserve a row (week 1 before their game, injured players): their
    # EWMA is the seed.
    if seeds:
        seen = set(weekly["player_id"].to_list()) if weekly.height else set()
        meta = (prev.group_by("player_id").agg([pl.col("name").last(), pl.col("position").first().alias("pos"),
                                                pl.col("team").last().alias("team")]))
        extra = []
        for r in meta.iter_rows(named=True):
            if r["player_id"] in seen:
                continue
            e = {"player_id": r["player_id"], "name": r["name"], "pos": r["pos"],
                 "team": r["team"], "games": 0, "last_week": None}
            for f in FORMATS:
                e[f"ewma_ep_{f}"] = seeds[r["player_id"]][f]
            extra.append(e)
        if extra:
            ex = pl.DataFrame(extra)
            for c in season_tbl.columns:
                if c not in ex.columns:
                    ex = ex.with_columns(pl.lit(None).cast(season_tbl.schema[c]).alias(c))
            season_tbl = pl.concat([season_tbl, ex.select(season_tbl.columns)]).sort(
                "ewma_ep_half", descending=True)
    return weekly, season_tbl


def write(season: int, refresh: bool = True) -> tuple[pl.DataFrame, pl.DataFrame]:
    weekly, tbl = build(season, refresh)
    wcols = ["season", "week", "player_id", "name", "position", "team"] + ep_model.ALL_FEATURES
    for f in FORMATS:
        wcols += [f"ep_{f}", f"pts_{f}", f"ewma_ep_pre_{f}", f"ewma_ep_{f}"]
    wcols.append("seeded_from_prior")
    weekly.select([c for c in wcols if c in weekly.columns]).write_csv(
        DATA / f"opportunity_{season}_weekly.csv", float_precision=2)
    tbl.write_csv(DATA / f"opportunity_{season}.csv", float_precision=2)
    return weekly, tbl


if __name__ == "__main__":
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    w, t = write(season)
    print(f"{season}: {w.height} player-weeks, {t.height} players")
    print(t.head(12).select(["name", "pos", "team", "games", "ewma_ep_half", "ep_half", "pts_half"]))
