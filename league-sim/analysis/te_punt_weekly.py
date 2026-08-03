"""The punt-TE question with real names and real weeks.

If you skip TE in the draft and shop the wire instead: who is the best
waiver TE you could actually identify after week 1, week 2, ... (the
undrafted-in-Sumfun TE with the most points so far — i.e. the guy at
the top of the waiver sort), and what did he score rest-of-season?

And on the other side of the ledger: for every TE the league actually
drafted in rounds 2-8, who was the next RB taken after that pick, and
what did HE score?  That's the player you gave up to own the TE.
"""

import polars as pl

from common import ROOT, SEASONS, league_drafted, season_totals
from simfl.data import norm_name

FINAL_WEEK = 17


def waiver_te_by_week(max_week: int = 6):
    """Best undrafted TE by cumulative points through week W, then his
    rest-of-season line.  Also the hindsight-best undrafted TE (ceiling)."""
    for y in SEASONS:
        undrafted = ~pl.col("nname").is_in(list(league_drafted(y)))
        print(f"\n== {y}: best waiver TE if you pick him up after week W ==")
        rows = []
        for w in range(1, max_week + 1):
            sofar = (season_totals(y, weeks=(1, w))
                     .filter(pl.col("position") == "TE", undrafted)
                     .sort("total", descending=True))
            hot = sofar.row(0, named=True)
            ros = season_totals(y, weeks=(w + 1, FINAL_WEEK)).filter(
                pl.col("position") == "TE")
            r = ros.filter(pl.col("player_id") == hot["player_id"])
            rows.append({
                "after wk": w,
                "top waiver TE": hot["player_display_name"],
                "pts so far": round(hot["total"], 1),
                "ros ppg": round(r["ppg"].item(), 1) if len(r) else 0.0,
                "ros TE rank": r["pos_rank"].item() if len(r) else None,
            })
        # hindsight ceiling: the undrafted TE with the best wk4-17 ppg
        best = (season_totals(y, weeks=(4, FINAL_WEEK))
                .filter(pl.col("position") == "TE", undrafted,
                        pl.col("games") >= 6)
                .sort("ppg", descending=True).row(0, named=True))
        print(pl.DataFrame(rows))
        print(f"   hindsight-best undrafted TE wk4-17: "
              f"{best['player_display_name']} {best['ppg']:.1f} ppg "
              f"(TE{best['pos_rank']})")


def te_pick_vs_next_rb():
    """Every TE drafted in rounds 2-8 in the family league vs the next
    RB taken after him in the same draft: full-season totals and wk4-17
    ppg for both."""
    picks = pl.read_parquet(ROOT / "data" / "espn" / "picks.parquet").with_columns(
        pl.col("player").map_elements(norm_name, return_dtype=pl.String)
        .alias("nname"))
    print("\n\n== The other side: early TE pick vs the next RB off the board ==")
    for y in SEASONS:
        yp = picks.filter(pl.col("year") == y).sort("overall")
        tes = yp.filter(pl.col("pos") == "TE", pl.col("round") <= 8)
        if not len(tes):
            continue
        season = season_totals(y, weeks=(1, FINAL_WEEK))
        ros = season_totals(y, weeks=(4, FINAL_WEEK))
        rows = []
        for te in tes.iter_rows(named=True):
            nxt_rb = yp.filter(pl.col("pos") == "RB",
                               pl.col("overall") > te["overall"]).head(1)
            def line(nname):
                s = season.filter(pl.col("nname") == nname)
                r = ros.filter(pl.col("nname") == nname)
                tot = round(s["total"].item(), 0) if len(s) else 0.0
                ppg = round(r["ppg"].item(), 1) if len(r) else 0.0
                return tot, ppg
            te_tot, te_ppg = line(te["nname"])
            rb = nxt_rb.row(0, named=True) if len(nxt_rb) else None
            rb_tot, rb_ppg = line(rb["nname"]) if rb else (0.0, 0.0)
            rows.append({
                "pick": te["overall"], "TE": te["player"],
                "TE season": te_tot, "TE ros ppg": te_ppg,
                "next RB (pick)": f"{rb['player']} ({rb['overall']})" if rb else "-",
                "RB season": rb_tot, "RB ros ppg": rb_ppg,
            })
        print(f"\n{y}:")
        print(pl.DataFrame(rows))


if __name__ == "__main__":
    pl.Config.set_tbl_rows(30)
    pl.Config.set_fmt_str_lengths(28)
    pl.Config.set_tbl_width_chars(140)
    waiver_te_by_week()
    te_pick_vs_next_rb()
