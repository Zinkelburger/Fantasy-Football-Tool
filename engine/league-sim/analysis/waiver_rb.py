"""Can you actually get a startable RB without drafting him?

Four answers, same data as the TE version:
1. The realistic wire RB week by week (undrafted-in-Sumfun, top of the
   waiver sort by points-so-far) and his rest-of-season line.
2. What share of weekly STARTABLE slots (RB top-24, TE top-12) were
   held by players nobody in the family league drafted.
3. What the league's own round 9-12 RB picks actually returned — the
   real 'RB you'd otherwise start'.
4. The early-TE-vs-next-RB edge table recomputed with that late-RB
   baseline instead of hindsight RB30.
"""

import polars as pl

from common import ROOT, SEASONS, league_drafted, season_totals, weekly
from simfl.data import norm_name
from vor_redo import ROS, N_WEEKS, baselines, edge

FINAL_WEEK = 17


def wire_rb_by_week(max_week: int = 6):
    print("== Realistic wire RB: best undrafted-in-league by points through wk W ==")
    for y in SEASONS:
        undrafted = ~pl.col("nname").is_in(list(league_drafted(y)))
        rows = []
        for w in range(1, max_week + 1):
            hot = (season_totals(y, weeks=(1, w))
                   .filter(pl.col("position") == "RB", undrafted)
                   .sort("total", descending=True).row(0, named=True))
            ros = season_totals(y, weeks=(w + 1, FINAL_WEEK)).filter(
                pl.col("position") == "RB")
            r = ros.filter(pl.col("player_id") == hot["player_id"])
            rows.append({
                "after wk": w, "top wire RB": hot["player_display_name"],
                "ros ppg": round(r["ppg"].item(), 1) if len(r) else 0.0,
                "ros RB rank": r["pos_rank"].item() if len(r) else None,
            })
        best = (season_totals(y, weeks=ROS)
                .filter(pl.col("position") == "RB", undrafted,
                        pl.col("games") >= 6)
                .sort("ppg", descending=True).row(0, named=True))
        print(f"\n{y}: " + " | ".join(
            f"wk{r['after wk']}: {r['top wire RB']} ({r['ros ppg']} ppg, RB{r['ros RB rank']})"
            for r in rows))
        print(f"   hindsight-best wire RB wk4-17: {best['player_display_name']} "
              f"{best['ppg']:.1f} ppg (RB{best['pos_rank']})")


def wire_rb_depth(max_week: int = 6, depth: int = 5):
    """Contention cost: the wire RB queue after week W, positions 1-5.
    You only get #1 with top priority; mid-priority gets #2-#3."""
    print("\n\n== Contention: the wire RB claim queue, by queue position ==")
    pooled = {d: [] for d in range(1, depth + 1)}
    for y in SEASONS:
        undrafted = ~pl.col("nname").is_in(list(league_drafted(y)))
        for w in range(2, max_week + 1):
            sofar = (season_totals(y, weeks=(1, w))
                     .filter(pl.col("position") == "RB", undrafted)
                     .sort("total", descending=True))
            ros = season_totals(y, weeks=(w + 1, FINAL_WEEK)).filter(
                pl.col("position") == "RB")
            for d in range(1, depth + 1):
                row = sofar.row(d - 1, named=True)
                r = ros.filter(pl.col("player_id") == row["player_id"])
                pooled[d].append((r["ppg"].item() if len(r) else 0.0,
                                  r["pos_rank"].item() if len(r) else 99))
    print("queue position (pooled over wk 2-6 claims, 2020-25):")
    for d in range(1, depth + 1):
        ppgs = [p for p, _ in pooled[d]]
        ranks = sorted(r for _, r in pooled[d])
        med_rank = ranks[len(ranks) // 2]
        print(f"  wire RB #{d}: avg ros {sum(ppgs)/len(ppgs):4.1f} ppg, "
              f"median ros rank RB{med_rank}")
    print("\nweek-3 claim queue by year (name, ros ppg, ros rank):")
    for y in SEASONS:
        undrafted = ~pl.col("nname").is_in(list(league_drafted(y)))
        sofar = (season_totals(y, weeks=(1, 3))
                 .filter(pl.col("position") == "RB", undrafted)
                 .sort("total", descending=True))
        ros = season_totals(y, weeks=(4, FINAL_WEEK)).filter(
            pl.col("position") == "RB")
        cells = []
        for d in range(3):
            row = sofar.row(d, named=True)
            r = ros.filter(pl.col("player_id") == row["player_id"])
            ppg = r["ppg"].item() if len(r) else 0.0
            rk = r["pos_rank"].item() if len(r) else None
            cells.append(f"#{d+1} {row['player_display_name']} ({ppg:.1f}, RB{rk})")
        print(f"  {y}: " + " | ".join(cells))


def startable_share():
    print("\n\n== Share of weekly startable slots held by wire (league-undrafted) players ==")
    for pos, top_n in (("RB", 24), ("TE", 12)):
        shares = []
        for y in SEASONS:
            drafted = league_drafted(y)
            wk = weekly(y).filter(pl.col("position") == pos)
            top = (wk.sort("fpts", descending=True)
                   .group_by("week", maintain_order=True).head(top_n))
            wire = top.filter(~pl.col("nname").is_in(list(drafted)))
            shares.append(len(wire) / len(top))
        avg = sum(shares) / len(shares)
        by_year = " ".join(f"{y}:{s:.0%}" for y, s in zip(SEASONS, shares))
        print(f"{pos} top-{top_n} weeks: avg {avg:.0%} wire  ({by_year})")


def late_rb_returns() -> dict[int, float]:
    print("\n\n== The league's own round 9-12 RB picks: what your real RB3 returns ==")
    picks = pl.read_parquet(ROOT / "data" / "espn" / "picks.parquet").with_columns(
        pl.col("player").map_elements(norm_name, return_dtype=pl.String)
        .alias("nname"))
    base_alt = {}
    for y in SEASONS:
        late = picks.filter(pl.col("year") == y, pl.col("pos") == "RB",
                            pl.col("round").is_between(9, 12))
        st = season_totals(y, weeks=ROS)
        j = st.join(late.select("nname"), on="nname", how="inner")
        ppw = (j["total"] / N_WEEKS).mean()  # missed weeks count as 0
        base_alt[y] = ppw
        print(f"{y}: n={len(late)}  avg pts per league week {ppw:.1f}  "
              f"(best {j['ppg'].max():.1f} ppg, median ppg {j['ppg'].median():.1f})")
    return base_alt


def edges_with_alt_baseline(base_alt: dict[int, float]):
    picks = pl.read_parquet(ROOT / "data" / "espn" / "picks.parquet").with_columns(
        pl.col("player").map_elements(norm_name, return_dtype=pl.String)
        .alias("nname"))
    all_te, all_rb30, all_rb_alt = [], [], []
    for y in SEASONS:
        base = baselines(y)
        st = season_totals(y, weeks=ROS)
        yp = picks.filter(pl.col("year") == y).sort("overall")
        for te in yp.filter(pl.col("pos") == "TE",
                            pl.col("round") <= 8).iter_rows(named=True):
            nxt = yp.filter(pl.col("pos") == "RB",
                            pl.col("overall") > te["overall"]).head(1)
            if not len(nxt):
                continue
            rb = nxt.row(0, named=True)
            all_te.append(edge(st, te["nname"], base["TE"]))
            all_rb30.append(edge(st, rb["nname"], base["RB"]))
            all_rb_alt.append(edge(st, rb["nname"], base_alt[y]))
    n = len(all_te)
    print(f"\n== The 58-pick comparison, both RB baselines ==")
    print(f"mean TE edge over TE12 (free off wire):        {sum(all_te)/n:+.2f}/wk")
    print(f"mean RB edge over hindsight RB30:              {sum(all_rb30)/n:+.2f}/wk")
    print(f"mean RB edge over your actual R9-12 RB pick:   {sum(all_rb_alt)/n:+.2f}/wk")
    print(f"RB better than TE (R9-12 baseline): "
          f"{sum(r > t for r, t in zip(all_rb_alt, all_te))}/{n} picks")


if __name__ == "__main__":
    wire_rb_by_week()
    startable_share()
    base_alt = late_rb_returns()
    edges_with_alt_baseline(base_alt)
