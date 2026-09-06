"""How does the Sumfun League actually draft?

Joins the real ESPN draft picks (2020-2025) to FFC standard ADP and
rookie status, then reports each tendency we plan to encode in the
family opponent model: reach size, position preferences, rookie bias,
and when K/DST go.  Also writes the tidy pick table to
data/espn/picks.parquet for the simulator to fit against.
"""

import json
import random
import statistics as st
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simfl.config import DEFAULT_SCORING, SEASONS
from simfl.data import load_adp, load_weekly, load_rookie_years, norm_name

ESPN = ROOT / "data" / "espn"

# Round bands for the reach split. The pooled reach table hides the one
# real signal in it (see reach_by_round).
BANDS = ((1, 3), (4, 6), (7, 10), (11, 16))
BOOT_N = 4000


def player_map() -> dict:
    """ESPN player id -> {name, pos}, unioned across seasons (older
    season files carry retired players the newer ones drop)."""
    out = {}
    for f in sorted(ESPN.glob("players_*.json")):
        out.update(json.loads(f.read_text()))
    return out


def rookie_names() -> dict[str, int]:
    """normalized name -> rookie season, via nflverse ids."""
    by_id = load_rookie_years()
    out = {}
    for year in SEASONS:
        wk = load_weekly(year, DEFAULT_SCORING)
        for pid, name in wk.select("player_id", "player_display_name").unique().rows():
            if pid in by_id:
                out[norm_name(name)] = by_id[pid]
    return out


def build_picks() -> pl.DataFrame:
    pmap = player_map()
    rookies = rookie_names()
    rows = []
    for year in SEASONS:
        lg = json.loads((ESPN / f"league_{year}.json").read_text())
        teams = {t["id"]: (t.get("name") or f"{t.get('location','')} {t.get('nickname','')}".strip())
                 for t in lg["teams"]}
        adp = {norm_name(p["name"]): p["adp"] for p in load_adp(year)}
        for p in lg["draftDetail"]["picks"]:
            info = pmap.get(str(p["playerId"]), {"name": f"id:{p['playerId']}", "pos": "?"})
            n = norm_name(info["name"])
            rows.append({
                "year": year,
                "overall": p["overallPickNumber"],
                "round": p["roundId"],
                "team_id": p["teamId"],
                "team": teams.get(p["teamId"], "?"),
                "player": info["name"],
                "pos": info["pos"],
                "adp": adp.get(n),
                "rookie": rookies.get(n) == year,
            })
    return pl.DataFrame(rows).sort("year", "overall")


def _boot_median_ci(vals: list[float], n: int = BOOT_N) -> tuple[float, float, float]:
    """Median with a 95% bootstrap CI.

    Reach is skewed (a few huge reaches, a long tail of players who fell
    out of the top 200) and the per-cell n is small — 12 picks for early
    TEs. A mean +/- sd would imply precision that isn't there.
    """
    rng = random.Random(7)
    draws = sorted(st.median(rng.choices(vals, k=len(vals))) for _ in range(n))
    return st.median(vals), draws[int(0.025 * n)], draws[int(0.975 * n)]


def reach_by_round(with_adp: pl.DataFrame) -> None:
    """Reach split by round band, which the pooled table above hides.

    Pooled over 16 rounds the room looks neutral on TE (median -0.4).
    That is two opposite effects cancelling: it reaches for tight ends
    in rounds 1-6 and lets them rot after round 10. Splitting by band
    is what makes either one visible. Same sign convention as report():
    NEGATIVE = taken earlier than ADP (reached for).
    """
    print("\n== Reach by round band (negative = reached early), 95% bootstrap CI ==")
    print(f"{'band':>9} {'pos':>4} {'n':>5} {'median':>8}   {'95% CI':>16}")
    for lo, hi in BANDS:
        for pos in ("RB", "WR", "TE", "QB"):
            vals = (with_adp
                    .filter(pl.col("round").is_between(lo, hi), pl.col("pos") == pos)
                    .get_column("reach").to_list())
            if len(vals) < 5:
                continue
            med, l, u = _boot_median_ci(vals)
            # flag cells whose interval excludes zero
            star = " *" if (l > 0 or u < 0) else ""
            print(f"{f'rd {lo}-{hi}':>9} {pos:>4} {len(vals):>5} {med:>8.1f}   "
                  f"[{l:>6.1f},{u:>6.1f}]{star}")
        print()

    print("== Does the early reach repeat? (median reach, rounds 1-6, per year) ==")
    years = sorted(with_adp.get_column("year").unique().to_list())
    print(f"{'year':>6}" + "".join(f"{p:>8}" for p in ("TE", "QB", "RB", "WR")))
    for y in years:
        row = f"{y:>6}"
        for pos in ("TE", "QB", "RB", "WR"):
            vals = (with_adp
                    .filter(pl.col("year") == y, pl.col("round") <= 6,
                            pl.col("pos") == pos)
                    .get_column("reach").to_list())
            row += f"{st.median(vals):>8.1f}" if vals else f"{'-':>8}"
        print(row)

    print("\n== How often a position FELL 5+ picks past ADP (rounds 1-6) ==")
    for pos in ("RB", "WR", "TE", "QB"):
        vals = (with_adp
                .filter(pl.col("round") <= 6, pl.col("pos") == pos)
                .get_column("reach").to_list())
        fell = sum(1 for v in vals if v > 5)
        print(f"  {pos}: {fell}/{len(vals)} ({100 * fell / len(vals):.0f}%)")


def report(df: pl.DataFrame) -> None:
    skill = df.filter(pl.col("pos").is_in(["QB", "RB", "WR", "TE"]))
    with_adp = skill.filter(pl.col("adp").is_not_null()).with_columns(
        (pl.col("overall") - pl.col("adp")).alias("reach"))  # negative = reached early

    print(f"picks: {len(df)}  |  unmapped players: {len(df.filter(pl.col('pos') == '?'))}")
    print(f"skill picks with ADP: {len(with_adp)}/{len(skill)} "
          f"(rest were drafted despite no FFC ADP at all)\n")

    print("== Reach (overall pick minus ADP; negative = taken early) ==")
    print(with_adp.group_by("pos").agg(
        pl.col("reach").mean().round(1).alias("mean"),
        pl.col("reach").median().alias("median"),
        pl.col("reach").std().round(1).alias("std"),
        pl.len().alias("n"),
    ).sort("pos"))

    reach_by_round(with_adp)

    print("\n== Same, rookies vs veterans (rounds 1-10 only) ==")
    print(with_adp.filter(pl.col("round") <= 10).group_by("rookie").agg(
        pl.col("reach").mean().round(1).alias("mean"),
        pl.col("reach").median().alias("median"),
        pl.len().alias("n"),
    ).sort("rookie"))

    print("\n== Position share by round bucket (all picks) ==")
    buckets = df.with_columns(
        pl.when(pl.col("round") <= 3).then(pl.lit("R1-3"))
        .when(pl.col("round") <= 6).then(pl.lit("R4-6"))
        .when(pl.col("round") <= 10).then(pl.lit("R7-10"))
        .otherwise(pl.lit("R11-16")).alias("bucket"))
    shares = (buckets.group_by("bucket", "pos").agg(pl.len().alias("n"))
              .pivot(on="pos", index="bucket", values="n").fill_null(0)
              .sort("bucket"))
    print(shares)

    print("\n== When K and DST go (round of each team's first K / DST) ==")
    for pos in ["K", "DST"]:
        firsts = (df.filter(pl.col("pos") == pos)
                  .group_by("year", "team_id").agg(pl.col("round").min())
                  .get_column("round"))
        print(f"{pos}: median round {firsts.median():.0f}, "
              f"earliest {firsts.min()}, latest {firsts.max()}, "
              f"drafted {len(firsts)}/72 team-seasons")

    print("\n== Per-team reach profile (skill picks, rounds 1-10) ==")
    per_team = (with_adp.filter(pl.col("round") <= 10)
                .group_by("team_id", "team").agg(
                    pl.col("reach").mean().round(1).alias("mean_reach"),
                    pl.col("rookie").mean().round(2).alias("rookie_share"),
                    (pl.col("pos") == "RB").mean().round(2).alias("rb_share"),
                    pl.len().alias("n"))
                .sort("mean_reach"))
    print(per_team)


if __name__ == "__main__":
    df = build_picks()
    df.write_parquet(ESPN / "picks.parquet")
    report(df)
    print(f"\nwrote {ESPN / 'picks.parquet'}")
