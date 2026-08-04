"""Redo two analyses in value-over-replacement terms.

Everything is expressed as points per league week ABOVE the last
starter you could otherwise field (this league's lineup: QB12, RB30
incl. flex, WR30, TE12, over wk 4-17, ppg-ranked with min 6 games).
Weeks a player missed count as zero edge — you'd start the baseline
guy those weeks — so edge_ppw = (total - games * base) / n_weeks.

Part 1: every TE the family league drafted in rounds 2-8, vs the next
RB off the board: edge over TE12 vs edge over RB30.  The pick is only
right if the TE's edge over his baseline beats the RB's edge over his.

Part 2: the bench-lottery redo: bench-round (ADP 96-180) RB vs WR,
but instead of counting top-24 weeks, sum the points above baseline
captured during 3+ week consecutive startable runs — EXCLUDING each
run's first week, since you only start him after he shows something.
"""

import polars as pl

from common import ROOT, SEASONS, season_totals
from simfl.config import DEFAULT_SCORING
from simfl.data import norm_name
from simfl.pool import build_pool

ROS = (4, 17)
N_WEEKS = ROS[1] - ROS[0] + 1
LAST_STARTER = {"QB": 12, "RB": 30, "WR": 30, "TE": 12}


def baselines(y: int) -> dict[str, float]:
    """PPG of the last starter at each position, wk 4-17, min 6 games."""
    st = season_totals(y, weeks=ROS).filter(pl.col("games") >= 6)
    out = {}
    for pos, rank in LAST_STARTER.items():
        d = (st.filter(pl.col("position") == pos)
             .sort("ppg", descending=True))
        out[pos] = d["ppg"][rank - 1]
    return out


def edge(st: pl.DataFrame, nname: str, base: float) -> float:
    """Points per league week above baseline, missed weeks = 0 edge."""
    r = st.filter(pl.col("nname") == nname)
    if not len(r):
        return round(-0.0, 2)
    return round((r["total"].item() - r["games"].item() * base) / N_WEEKS, 2)


def te_vs_rb_vor():
    picks = pl.read_parquet(ROOT / "data" / "espn" / "picks.parquet").with_columns(
        pl.col("player").map_elements(norm_name, return_dtype=pl.String)
        .alias("nname"))
    print("== Early TE picks in VOR terms: edge/wk over TE12 vs next RB's edge/wk over RB30 ==")
    all_te, all_rb = [], []
    for y in SEASONS:
        base = baselines(y)
        st = season_totals(y, weeks=ROS)
        yp = picks.filter(pl.col("year") == y).sort("overall")
        tes = yp.filter(pl.col("pos") == "TE", pl.col("round") <= 8)
        rows = []
        for te in tes.iter_rows(named=True):
            nxt = yp.filter(pl.col("pos") == "RB",
                            pl.col("overall") > te["overall"]).head(1)
            rb = nxt.row(0, named=True) if len(nxt) else None
            te_e = edge(st, te["nname"], base["TE"])
            rb_e = edge(st, rb["nname"], base["RB"]) if rb else 0.0
            all_te.append(te_e)
            all_rb.append(rb_e)
            rows.append({"pick": te["overall"], "TE": te["player"],
                         "TE edge/wk": te_e,
                         "next RB": rb["player"] if rb else "-",
                         "RB edge/wk": rb_e,
                         "RB - TE": round(rb_e - te_e, 2)})
        print(f"\n{y}  (baselines: TE12 {base['TE']:.1f} ppg, RB30 {base['RB']:.1f} ppg)")
        print(pl.DataFrame(rows))
    n = len(all_te)
    print(f"\nALL {n} early-TE picks 2020-25: mean TE edge {sum(all_te)/n:+.2f}/wk, "
          f"mean next-RB edge {sum(all_rb)/n:+.2f}/wk, "
          f"RB better in {sum(r > t for r, t in zip(all_rb, all_te))}/{n} picks")


def bench_lottery_vor():
    print("\n\n== Bench lottery in points, not week-counts ==")
    print("ADP 96-180 picks; value captured = pts above baseline during 3+wk")
    print("consecutive top-24 runs, excluding each run's first week.\n")
    for pos in ("RB", "WR"):
        players = []
        for y in SEASONS:
            base = baselines(y)[pos]
            pool = [p for p in build_pool(y, DEFAULT_SCORING) if p.pos == pos]
            top = {}
            for w in range(1, 18):
                wk = sorted(((p.week_pts.get(w, None), p.pid) for p in pool
                             if w in p.week_pts), reverse=True)[:24]
                top[w] = {pid for _, pid in wk}
            for p in pool:
                if p.adp is None or not (96 <= p.adp <= 180):
                    continue
                good = sorted(w for w in p.week_pts
                              if w <= 17 and p.pid in top[w])
                runs, cur = [], []
                for w in good:
                    if cur and w == cur[-1] + 1:
                        cur.append(w)
                    else:
                        if len(cur) >= 3:
                            runs.append(cur)
                        cur = [w]
                if len(cur) >= 3:
                    runs.append(cur)
                cap = sum(p.week_pts[w] - base
                          for r in runs for w in r[1:])
                run_wks = sum(len(r) - 1 for r in runs)
                players.append({"year": y, "name": p.name, "cap": cap,
                                "run_wks": run_wks, "had_run": bool(runs)})
        n = len(players)
        hits = [p for p in players if p["had_run"]]
        cap_all = sum(p["cap"] for p in players) / n
        cap_hit = sum(p["cap"] for p in hits) / len(hits) if hits else 0.0
        ppw_hit = (sum(p["cap"] for p in hits) / max(1, sum(p["run_wks"] for p in hits)))
        print(f"{pos}: n={n}  P(any 3+wk run) {len(hits)/n:.0%}  "
              f"captured pts/player (all) {cap_all:+.1f}  "
              f"(hitters only) {cap_hit:+.1f}  edge/startable-wk {ppw_hit:+.1f}")
        top5 = sorted(players, key=lambda p: -p["cap"])[:5]
        print("   best: " + "; ".join(
            f"{p['year']} {p['name']} ({p['cap']:+.0f} pts over {p['run_wks']}wk)"
            for p in top5))


if __name__ == "__main__":
    pl.Config.set_tbl_rows(30)
    pl.Config.set_fmt_str_lengths(26)
    pl.Config.set_tbl_width_chars(120)
    te_vs_rb_vor()
    bench_lottery_vor()
