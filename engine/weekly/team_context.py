"""Team-week offensive context: how an offense actually played, in percentiles.

    python team_context.py fit          # rebuild the 2021-2025 baseline (once a season)
    python team_context.py --season 2026

Every number here is computed locally from the nflverse play-by-play we
already cache. Nothing is fetched from a rankings site and nothing here
feeds the expected-points model; this is matchup context to read beside a
projection, the way finding 26 frames the team environment as real but
small next to a player's own usage.

The metrics are the ones the public advanced-stats writers use, so their
articles can be checked against this rather than taken on trust:

  proe       pass rate over expected, in points of pass rate (nflfastR
             `pass_oe`, the model's own expectation given down/distance/
             score/clock). Positive = passed more than the situation asked.
  epa_pass   EPA per dropback, scrambles and sacks included.
  epa_rush   EPA per designed rush, scrambles excluded.
  sr_*       success rate (EPA > 0) passing, rushing, and on 1st down.
  cpoe       completion percentage over expected, per pass attempt.
  expl_*     explosive rate: 20+ yard dropbacks, 10+ yard designed rushes.
  sack_rate  sacks per dropback.
  aypa       air yards per pass attempt.
  deep_rate  share of pass attempts thrown 20+ yards in the air.
  plays      pass and rush plays, kneels/spikes/two-point tries excluded.

Every metric also stores `<metric>_n`, the number of plays that actually
carried a value, so several weeks pool exactly as a weighted mean rather
than an average of averages — which would let a 12-play week count as
much as a 70-play one. The count is per metric and not reused, because
nflfastR leaves `cpoe` and `air_yards` null on some attempts: dividing
those by the attempt count quietly gives the wrong answer.

A raw EPA is unreadable on its own, so each metric also gets a percentile
against every team-game from 2021-2025 (`model/team_context_baseline.json`,
committed, 101 breakpoints per metric) and a rank within its own week.
"Bears 95th percentile passing" is the percentile; "Steelers 1st in PROE"
is the rank.

One game is one game. Week 1 percentiles are a description of what
happened, not a forecast, and the module says so in its own output.
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys

import polars as pl

from common import CACHE, DATA, MODEL, now_iso

BASELINE = MODEL / "team_context_baseline.json"
BASELINE_SEASONS = [2021, 2022, 2023, 2024, 2025]
# Metric -> is a higher value better for the offense? sack_rate is the one
# that runs the other way; plays and proe are neither, they are style.
METRICS = {"proe": None, "epa_pass": True, "epa_rush": True, "sr_pass": True,
           "sr_rush": True, "sr_first": True, "cpoe": True, "expl_pass": True,
           "expl_rush": True, "sack_rate": False, "aypa": None,
           "deep_rate": None, "plays": None}
# Percentiles are only meaningful on a full game's worth of plays.
MIN_PLAYS = 20

# nflfastR counts a scramble as a dropback, which is what we want for
# passing-game efficiency and what makes the designed-rush filter explicit.
_DROP = pl.col("qb_dropback") == 1
_RUSH = (pl.col("rush") == 1) & (pl.col("qb_dropback") != 1)
# nflfastR's pass_attempt flag also includes sacks; official attempts do not.
_ATT = (pl.col("pass_attempt") == 1) & (pl.col("sack") != 1)
# One definition per metric: the mean is taken over this series and the
# pooling weight is this same series' non-null count.
_SERIES = {
    "proe": pl.col("pass_oe"),
    "epa_pass": pl.col("epa").filter(_DROP),
    "epa_rush": pl.col("epa").filter(_RUSH),
    "sr_pass": pl.col("success").filter(_DROP),
    "sr_rush": pl.col("success").filter(_RUSH),
    "sr_first": pl.col("success").filter(pl.col("down") == 1),
    "cpoe": pl.col("cpoe").filter(_ATT),
    "expl_pass": (pl.col("yards_gained").filter(_DROP) >= 20),
    "expl_rush": (pl.col("yards_gained").filter(_RUSH) >= 10),
    "sack_rate": (pl.col("sack").filter(_DROP) == 1),
    "aypa": pl.col("air_yards").filter(_ATT),
    "deep_rate": (pl.col("air_yards").filter(_ATT) >= 20),
}
_EXPR = {k: v.mean() for k, v in _SERIES.items()}


def team_game(pbp: pl.DataFrame) -> pl.DataFrame:
    """One row per team per game: the offense's own plays, aggregated."""
    p = pbp.filter(
        (pl.col("season_type") == "REG") & pl.col("posteam").is_not_null()
        & (pl.col("qb_kneel") != 1) & (pl.col("qb_spike") != 1)
        & (pl.col("two_point_attempt") != 1)
        & ((pl.col("pass") == 1) | (pl.col("rush") == 1)))
    # nflfastR counts a scramble as a dropback, which is what we want for
    # passing-game efficiency and what makes the rush filter explicit.
    return p.group_by(["season", "week", "game_id", "posteam"]).agg(
        pl.len().alias("plays"),
        _DROP.sum().alias("dropbacks"),
        _RUSH.sum().alias("rushes"),
        _ATT.sum().alias("attempts"),
        *[e.alias(name) for name, e in _EXPR.items()],
        # Each metric's own non-null count: its exact pooling weight.
        *[e.count().alias(f"{name}_n") for name, e in _SERIES.items()],
    ).rename({"posteam": "team"}).sort(["season", "week", "team"])


# ------------------------------------------------------------- the baseline
def fit(seasons: list[int] | None = None) -> dict:
    """101 breakpoints per metric from every 2021-2025 team-game.

    Needs those seasons' play-by-play in the cache (gitignored, ~20MB
    each); the breakpoints themselves are committed so the weekly build
    never has to hold five seasons of it.
    """
    seasons = seasons or BASELINE_SEASONS
    frames = []
    for s in seasons:
        path = CACHE / f"pbp_{s}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing. Fetch it first: "
                "python engine/league-sim/analysis/ingame_model.py --fetch")
        frames.append(team_game(pl.read_parquet(path)))
    base = pl.concat(frames, how="vertical_relaxed").filter(pl.col("plays") >= MIN_PLAYS)
    qs = [i / 100 for i in range(101)]
    out = {"fit_seasons": seasons, "fitted": now_iso(), "team_games": base.height,
           "min_plays": MIN_PLAYS, "higher_is_better": METRICS,
           "breakpoints": {}}
    for m in METRICS:
        col = base[m].drop_nulls()
        out["breakpoints"][m] = [round(col.quantile(q, "linear"), 6) for q in qs]
    return out


def load_baseline() -> dict:
    if not BASELINE.exists():
        raise FileNotFoundError(f"{BASELINE} missing; run: python team_context.py fit")
    return json.loads(BASELINE.read_text())


def percentile(breakpoints: list[float], value: float | None) -> int | None:
    """Where this game sits among 2021-2025 team-games, 0-100."""
    if value is None:
        return None
    return min(100, bisect.bisect_left(breakpoints, value))


# ------------------------------------------------------------------- output
def build(season: int, baseline: dict | None = None) -> pl.DataFrame:
    path = CACHE / f"pbp_{season}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run build_week.py --season {season}")
    base = (baseline or load_baseline())["breakpoints"]
    tg = team_game(pl.read_parquet(path))
    # Percentile against history, then rank within the week, which is how
    # these get quoted ("24th in PROE" is a rank, "95th percentile" is not).
    for m in METRICS:
        bp = base[m]
        tg = tg.with_columns(
            pl.col(m).map_elements(lambda v, bp=bp: percentile(bp, v),
                                   return_dtype=pl.Int16, skip_nulls=False)
            .alias(f"{m}_pctl"),
            pl.col(m).rank("min", descending=METRICS[m] is not False)
            .over(["season", "week"]).cast(pl.Int16).alias(f"{m}_rk"))
    # Below the play floor the rates are noise; blank the percentiles rather
    # than publish a number the sample cannot support.
    thin = pl.col("plays") < MIN_PLAYS
    tg = tg.with_columns([pl.when(thin).then(None).otherwise(pl.col(f"{m}_pctl"))
                          .alias(f"{m}_pctl") for m in METRICS])
    cols = ["season", "week", "game_id", "team", "plays", "dropbacks", "rushes", "attempts"]
    cols += [m for m in METRICS if m != "plays"]
    cols += [f"{m}_n" for m in _SERIES]
    return tg.select(*cols, *[f"{m}_{s}" for m in METRICS for s in ("pctl", "rk")])


def write(season: int) -> tuple[pl.DataFrame, dict]:
    baseline = load_baseline()
    out = build(season, baseline)
    path = DATA / f"team_context_{season}.csv"
    out.write_csv(path, float_precision=6)
    manifest = {
        "season": season, "generated_at": now_iso(),
        "source": "nflverse play-by-play (nflfastR), computed locally",
        "baseline": {"fit_seasons": baseline["fit_seasons"],
                     "team_games": baseline["team_games"],
                     "fitted": baseline["fitted"]},
        "definitions": {
            "proe": "mean nflfastR pass_oe over pass/rush plays, in points of pass rate",
            "epa_pass": "EPA per dropback (scrambles and sacks included)",
            "epa_rush": "EPA per designed rush (scrambles excluded)",
            "sr_first": "success rate on 1st down",
            "expl_pass": "share of dropbacks gaining 20+ yards",
            "expl_rush": "share of designed rushes gaining 10+ yards",
            "deep_rate": "share of pass attempts thrown 20+ air yards",
            "*_pctl": f"percentile among {baseline['team_games']} team-games "
                      f"{baseline['fit_seasons'][0]}-{baseline['fit_seasons'][-1]}",
            "*_rk": "rank among the 32 teams within that week (1 = best, "
                    "or most for proe/aypa/plays, fewest for sack_rate)",
            "<metric>_n": "plays carrying a value for that metric; its exact "
                "weight when pooling weeks. Not the same as attempts: "
                "nflfastR leaves cpoe and air_yards null on some attempts",
            "excluded": "kneels, spikes, two-point tries, and all non-REG games",
            "purpose": "descriptive matchup context; never an input to the "
                       "expected-points model"},
        "coverage_by_week": out.group_by("week").agg(
            pl.len().alias("teams"), pl.col("plays").sum().alias("plays"),
            pl.col("epa_pass_pctl").count().alias("teams_above_play_floor")
        ).sort("week").to_dicts()}
    path.with_suffix(".sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return out, manifest


def main(argv=None):
    if argv is None and len(sys.argv) > 1 and sys.argv[1] == "fit":
        res = fit()
        BASELINE.write_text(json.dumps(res, indent=1) + "\n")
        print(f"wrote {BASELINE}: {res['team_games']} team-games "
              f"{res['fit_seasons'][0]}-{res['fit_seasons'][-1]}")
        for m in ("epa_pass", "epa_rush", "proe"):
            b = res["breakpoints"][m]
            print(f"  {m:9} p10 {b[10]:+.3f}  median {b[50]:+.3f}  p90 {b[90]:+.3f}")
        return 0
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, required=True)
    a = ap.parse_args(argv)
    out, manifest = write(a.season)
    print(f"wrote data/weekly/team_context_{a.season}.csv: {out.height} team-weeks")
    print(json.dumps(manifest["coverage_by_week"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
