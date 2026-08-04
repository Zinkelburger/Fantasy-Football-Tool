"""Findings 15-18: what season-N stats predict season-N+1 fantasy PPG.

Reproduces every number in findings/15-late-season-momentum-myth.md,
16-td-luck-regresses.md, 17-buy-targets-not-efficiency.md,
18-injury-prone-is-mostly-myth.md.

Data: cached weeklies (data/weekly_*.parquet, family scoring via simfl),
plus nflreadpy pulls cached as data/{adv_weekly,ff_opportunity,injuries}
_2017_2025.parquet (re-downloaded automatically if missing).

Run:  venv/bin/python scripts/next_season_signal.py [--quick]
--quick skips the permutation/bootstrap significance suite (~4 min).

Stats notes: p-values are two-sided permutation tests (5,000 perms;
Freedman-Lane residual permutation for partial correlations). CIs are
95% cluster bootstraps resampling PLAYERS (2,000 draws) because the
same player contributes multiple season-pairs. "partial r beyond PPG"
= correlation of X and next-season PPG after linearly residualizing
both on current-season PPG.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simfl.config import ScoringConfig
from simfl.scoring import add_fantasy_points

DATA = ROOT / "data"
YEARS = list(range(2017, 2026))
POS = ["QB", "RB", "WR", "TE"]
KS = [1, 2, 3, 4, 5]
TOPN = {"QB": 24, "RB": 50, "WR": 60, "TE": 24}  # rosterable in 12-team
B_PERM, B_BOOT = 5000, 2000
rng = np.random.default_rng(42)


# ---------------- data loading ----------------
def load_or_fetch():
    paths = {
        "adv": DATA / "adv_weekly_2017_2025.parquet",
        "opp": DATA / "ff_opportunity_2017_2025.parquet",
        "inj": DATA / "injuries_2017_2025.parquet",
    }
    if not all(p.exists() for p in paths.values()):
        import nflreadpy as nfl
        stats = nfl.load_player_stats(YEARS)
        keep = ["player_id", "player_display_name", "position", "season",
                "season_type", "week", "team", "targets", "receptions",
                "receiving_yards", "receiving_yards_after_catch",
                "receiving_tds", "rushing_tds", "rushing_yards", "carries",
                "target_share", "receiving_air_yards"]
        stats.select([c for c in keep if c in stats.columns]).write_parquet(paths["adv"])
        nfl.load_ff_opportunity(YEARS).write_parquet(paths["opp"])
        nfl.load_injuries(YEARS).write_parquet(paths["inj"])
    return (pd.read_parquet(paths["adv"]), pd.read_parquet(paths["opp"]),
            pd.read_parquet(paths["inj"]))


def build_player_seasons():
    """Per player-season: full/last-K/first-K PPG plus next-season PPG."""
    sc = ScoringConfig()
    frames = []
    for y in YEARS:
        df = add_fantasy_points(pl.read_parquet(DATA / f"weekly_{y}.parquet"), sc)
        frames.append(df.select(["player_id", "player_display_name", "position",
                                 "season", "week", "fpts"]).to_pandas())
    wk = pd.concat(frames, ignore_index=True)
    wk = wk[wk.position.isin(POS)]
    wk["mw"] = wk.groupby("season")["week"].transform("max")

    key = ["player_id", "season"]
    ps = wk.groupby(key).agg(
        name=("player_display_name", "first"), position=("position", "first"),
        gp=("fpts", "size"), total=("fpts", "sum"), ppg=("fpts", "mean")).reset_index()
    for k in KS:
        for tag, mask in [(f"last{k}", wk.week > wk.mw - k), (f"first{k}", wk.week <= k)]:
            sub = wk[mask].groupby(key).fpts.agg(["mean", "size"])
            sub.columns = [f"ppg_{tag}", f"gp_{tag}"]
            ps = ps.merge(sub.reset_index(), on=key, how="left")
            ps[f"gp_{tag}"] = ps[f"gp_{tag}"].fillna(0)

    nxt = ps[key + ["ppg", "gp"]].copy()
    nxt["season"] -= 1
    ps = ps.merge(nxt.rename(columns={"ppg": "ppg_next", "gp": "gp_next"}), on=key, how="left")
    ps["pos_rank"] = ps.groupby(["season", "position"])["total"].rank(ascending=False, method="first")
    ps["relevant"] = ps.pos_rank <= ps.position.map(TOPN)
    return ps


def build_merged(ps, adv, opp):
    adv = adv[adv.season_type == "REG"]
    adv_season = adv.groupby(["player_id", "season"]).agg(
        targets=("targets", "sum"), receptions=("receptions", "sum"),
        rec_yards=("receiving_yards", "sum"), yac=("receiving_yards_after_catch", "sum"),
        carries=("carries", "sum")).reset_index()

    opp = opp.copy()
    opp["season"] = opp.season.astype(int)
    opp["week"] = opp.week.astype(int)
    opp = opp[opp.week <= np.where(opp.season <= 2020, 17, 18)]  # REG only
    opp_season = opp.groupby(["player_id", "season"]).agg(
        x_rec_td=("rec_touchdown_exp", "sum"), x_rush_td=("rush_touchdown_exp", "sum"),
        x_pass_td=("pass_touchdown_exp", "sum"), a_rec_td=("rec_touchdown", "sum"),
        a_rush_td=("rush_touchdown", "sum"), a_pass_td=("pass_touchdown", "sum"),
        x_rec=("receptions_exp", "sum"), a_rec=("receptions", "sum")).reset_index()

    m = ps.merge(adv_season, on=["player_id", "season"], how="left")
    m = m.merge(opp_season, on=["player_id", "season"], how="left")
    m["td"] = m.a_rec_td + m.a_rush_td
    m["xtd"] = m.x_rec_td + m.x_rush_td
    m["tdoe"] = m.td - m.xtd
    m["tdoe_pg"] = m.tdoe / m.gp
    nxt = m[["player_id", "season", "td", "xtd", "yac", "receptions", "targets"]].copy()
    nxt["season"] -= 1
    nxt.columns = ["player_id", "season"] + [c + "_nx" for c in nxt.columns[2:]]
    return m.merge(nxt, on=["player_id", "season"], how="left")


def build_injuries(ps, inj):
    outs = inj[(inj.game_type == "REG") & inj.report_status.isin(["Out", "Doubtful"])]
    osn = outs.groupby(["gsis_id", "season"]).size().rename("wk_out").reset_index()
    osn["season"] = osn.season.astype(int)
    osn = osn.rename(columns={"gsis_id": "player_id"})
    im = ps[["player_id", "season", "position", "name", "ppg", "gp",
             "ppg_next", "gp_next", "relevant"]].merge(osn, on=["player_id", "season"], how="left")
    im["wk_out"] = im.wk_out.fillna(0)
    nxto = osn.copy()
    nxto["season"] -= 1
    im = im.merge(nxto.rename(columns={"wk_out": "wk_out_nx"}), on=["player_id", "season"], how="left")
    im["wk_out_nx"] = im.wk_out_nx.fillna(0)
    return im


# ---------------- stats helpers ----------------
def resid(y, x):
    return y - np.polyval(np.polyfit(x, y, 1), x)


def perm_p_corr(x, y, quick=False):
    x, y = np.asarray(x, float), np.asarray(y, float)
    obs = np.corrcoef(x, y)[0, 1]
    if quick:
        return obs, np.nan
    hits = sum(abs(np.corrcoef(x, rng.permutation(y))[0, 1]) >= abs(obs)
               for _ in range(B_PERM))
    return obs, (hits + 1) / (B_PERM + 1)


def perm_p_partial(x, y, z, quick=False):
    return perm_p_corr(resid(np.asarray(x, float), np.asarray(z, float)),
                       resid(np.asarray(y, float), np.asarray(z, float)), quick)


def cboot(df, stat, quick=False):
    est = stat(df)
    if quick:
        return est, np.nan, np.nan
    idx = df.groupby("player_id").indices
    players = list(idx.keys())
    arr = df.reset_index(drop=True)
    vals = []
    for _ in range(B_BOOT):
        pick = rng.choice(len(players), size=len(players), replace=True)
        try:
            vals.append(stat(arr.iloc[np.concatenate([idx[players[i]] for i in pick])]))
        except Exception:
            continue
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return est, lo, hi


def partial_stat(xcol):
    return lambda dd: np.corrcoef(resid(dd[xcol].values, dd.ppg.values),
                                  resid(dd.ppg_next.values, dd.ppg.values))[0, 1]


def line(label, est, p=None, ci=(np.nan, np.nan), n=None):
    s = f"{label:<58} {est:+.3f}"
    if p is not None and not np.isnan(p):
        s += f"  p={p:.4f}"
    if not np.isnan(ci[0]):
        s += f"  CI[{ci[0]:+.3f},{ci[1]:+.3f}]"
    if n:
        s += f"  n={n}"
    print(s)


# ---------------- analyses ----------------
def late_season(ps, quick):
    print("\n===== 15. LATE-SEASON MOMENTUM =====")
    rel = ps[ps.relevant & ps.season.lt(2025) & (ps.gp >= 8) & (ps.gp_next >= 6)]

    print("Raw Pearson r with next-season PPG (per position):")
    cols = ["ppg"] + [f"ppg_last{k}" for k in KS] + [f"ppg_first{k}" for k in KS]
    for pos in ["ALL"] + POS:
        sub = rel if pos == "ALL" else rel[rel.position == pos]
        out = [pos]
        for c in cols:
            k = int(c[-1]) if c[-1].isdigit() else 0
            d = sub.dropna(subset=[c, "ppg_next"])
            if k:
                d = d[d[c.replace("ppg_", "gp_")] >= max(1, (k + 1) // 2)]
            out.append(f"{d[c].corr(d.ppg_next):.3f}")
        print("  " + " ".join(f"{v:>7}" for v in out))

    d = rel.dropna(subset=["ppg_last3", "ppg_next"]).query("gp_last3 >= 2")
    obs, p = perm_p_partial(d.ppg_last3, d.ppg_next, d.ppg, quick)
    _, lo, hi = cboot(d, partial_stat("ppg_last3"), quick)
    line("pooled last3 partial beyond season PPG", obs, p, (lo, hi), len(d))

    for pos, k in [("RB", 1), ("RB", 3)]:
        d = rel[rel.position == pos].dropna(subset=[f"ppg_last{k}", "ppg_next"])
        d = d[d[f"gp_last{k}"] >= max(1, (k + 1) // 2)]
        obs, p = perm_p_partial(d[f"ppg_last{k}"], d.ppg_next, d.ppg, quick)
        _, lo, hi = cboot(d, partial_stat(f"ppg_last{k}"), quick)
        line(f"{pos} last{k} partial beyond season PPG", obs, p, (lo, hi), len(d))

    d = rel.dropna(subset=["ppg_last5", "ppg_first5", "ppg_next"])
    d = d[(d.gp_last5 >= 3) & (d.gp_first5 >= 3)]
    est, lo, hi = cboot(d, lambda dd: dd.ppg_last5.corr(dd.ppg_next)
                        - dd.ppg_first5.corr(dd.ppg_next), quick)
    line("recency: r(last5,next) - r(first5,next)", est, None, (lo, hi), len(d))

    for pos in ["RB", "TE"]:  # fader asymmetry (suggestive only)
        d = rel[rel.position == pos].dropna(subset=["ppg_last3", "ppg_next"]).query("gp_last3 >= 2").copy()
        d["surge"] = d.ppg_last3 - d.ppg
        d["chg"] = d.ppg_next - d.ppg

        def fade(dd):
            q = dd.surge.quantile(0.25)
            return dd.loc[dd.surge <= q, "chg"].mean() - dd.loc[dd.surge > q, "chg"].mean()

        est, lo, hi = cboot(d, fade, quick)
        p = np.nan
        if not quick:
            hits = 0
            for _ in range(B_PERM):
                dd = d.copy()
                dd["surge"] = rng.permutation(d.surge.values)
                hits += abs(fade(dd)) >= abs(est)
            p = (hits + 1) / (B_PERM + 1)
        line(f"{pos} faders (bottom-quartile surge) next-yr chg vs rest", est, p, (lo, hi), len(d))


def td_luck(m, quick):
    print("\n===== 16. TD LUCK =====")
    mm = m[m.relevant & m.season.lt(2025) & (m.gp >= 8) & (m.gp_next >= 6)]
    sk = mm[mm.position.isin(["RB", "WR", "TE"])].copy()
    sk["tdoe_nx"] = sk.td_nx - sk.xtd_nx
    sk["chg"] = sk.ppg_next - sk.ppg

    d = sk.dropna(subset=["tdoe_pg", "ppg_next"])
    obs, p = perm_p_partial(d.tdoe_pg, d.ppg_next, d.ppg, quick)
    _, lo, hi = cboot(d, partial_stat("tdoe_pg"), quick)
    line("skill TDOE/gm partial vs next-yr PPG", obs, p, (lo, hi), len(d))

    d = sk.dropna(subset=["tdoe", "tdoe_nx"])
    est, lo, hi = cboot(d, lambda dd: dd.tdoe.corr(dd.tdoe_nx), quick)
    line("TDOE year-over-year persistence", est, None, (lo, hi), len(d))
    est, lo, hi = cboot(d, lambda dd: dd.xtd.corr(dd.td_nx) - dd.td.corr(dd.td_nx), quick)
    line("r(xTD,nextTD) - r(TD,nextTD)", est, None, (lo, hi), len(d))

    d = sk.dropna(subset=["tdoe", "ppg_next"])

    def gap(dd):
        return (dd.loc[dd.tdoe >= dd.tdoe.quantile(0.8), "chg"].mean()
                - dd.loc[dd.tdoe <= dd.tdoe.quantile(0.2), "chg"].mean())

    est, lo, hi = cboot(d, gap, quick)
    line("lucky-vs-unlucky next-yr PPG gap (quintiles)", est, None, (lo, hi), len(d))
    per = [gap(d[d.season == s]) for s in range(2017, 2025)]
    print(f"   gap negative in {sum(g < 0 for g in per)}/8 season-pairs "
          f"(sign test one-sided p=0.5^8=0.0039): " + " ".join(f"{g:+.1f}" for g in per))

    qb = mm[mm.position == "QB"].copy()
    qb["tdoe_pg"] = (qb.a_pass_td - qb.x_pass_td) / qb.gp
    d = qb.dropna(subset=["tdoe_pg", "ppg_next"])
    obs, p = perm_p_partial(d.tdoe_pg, d.ppg_next, d.ppg, quick)
    _, lo, hi = cboot(d, partial_stat("tdoe_pg"), quick)
    line("QB pass-TDOE/gm partial vs next-yr PPG", obs, p, (lo, hi), len(d))


def efficiency(m, quick):
    print("\n===== 17. TARGETS vs EFFICIENCY =====")
    mm = m[m.relevant & m.season.lt(2025) & (m.gp >= 8) & (m.gp_next >= 6)]

    wr = mm[mm.position == "WR"].dropna(subset=["targets", "ppg_next"]).copy()
    wr["tpg"] = wr.targets / wr.gp
    obs, p = perm_p_partial(wr.tpg, wr.ppg_next, wr.ppg, quick)
    _, lo, hi = cboot(wr, partial_stat("tpg"), quick)
    line("WR targets/gm partial vs next-yr PPG", obs, p, (lo, hi), len(wr))
    signs = [np.sign(partial_stat("tpg")(wr[wr.season == s])) for s in range(2017, 2025)]
    print(f"   positive in {sum(s > 0 for s in signs)}/8 season-pairs")
    for pos, vol in [("RB", "carries"), ("TE", "targets")]:
        d = mm[mm.position == pos].dropna(subset=[vol, "ppg_next"]).copy()
        d["vpg"] = d[vol] / d.gp
        obs, p = perm_p_partial(d.vpg, d.ppg_next, d.ppg, quick)
        line(f"{pos} {vol}/gm partial vs next-yr PPG", obs, p, n=len(d))

    tg = mm[mm.position.isin(["WR", "TE", "RB"]) & (mm.targets >= 50)].copy()
    tg["yac_pr"] = tg.yac / tg.receptions
    tg["yac_pr_nx"] = tg.yac_nx / tg.receptions_nx
    d = tg[tg.position == "WR"].dropna(subset=["yac_pr", "yac_pr_nx"])
    obs, p = perm_p_corr(d.yac_pr, d.yac_pr_nx, quick)
    line("WR YAC/rec y/y stability (real skill)", obs, p, n=len(d))
    d = tg.dropna(subset=["yac_pr", "ppg_next"])
    obs, p = perm_p_partial(d.yac_pr, d.ppg_next, d.ppg, quick)
    _, lo, hi = cboot(d, partial_stat("yac_pr"), quick)
    line("YAC/rec partial vs next-yr PPG (50+ tgt)", obs, p, (lo, hi), len(d))

    hv = mm[mm.position.isin(["WR", "TE"]) & (mm.targets >= 70)].copy()
    hv["cr"] = hv.receptions / hv.targets
    hv["croe"] = (hv.a_rec - hv.x_rec) / hv.targets
    for col, lbl in [("cr", "catch rate"), ("croe", "catch rate over expected")]:
        d = hv.dropna(subset=[col, "ppg_next"])
        obs, p = perm_p_partial(d[col], d.ppg_next, d.ppg, quick)
        _, lo, hi = cboot(d, partial_stat(col), quick)
        line(f"{lbl} partial vs next-yr PPG (70+ tgt)", obs, p, (lo, hi), len(d))


def injuries(im, quick):
    print("\n===== 18. INJURY PERSISTENCE =====")
    imr = im[im.relevant & im.season.lt(2025) & im.ppg_next.notna() & (im.gp >= 8)].copy()
    obs, p = perm_p_corr(imr.wk_out, imr.wk_out_nx, quick)
    _, lo, hi = cboot(imr, lambda dd: dd.wk_out.corr(dd.wk_out_nx), quick)
    line("weeks-Out y/y correlation (all pos)", obs, p, (lo, hi), len(imr))
    for pos in POS:
        d = imr[imr.position == pos].copy()
        obs, p = perm_p_corr(d.wk_out, d.wk_out_nx, quick)
        d["g2n"] = (d.wk_out_nx >= 2).astype(int)
        a, b = d[d.wk_out >= 2], d[d.wk_out == 0]
        diff = a.g2n.mean() - b.g2n.mean()
        pp = np.nan
        if not quick:
            hits = 0
            for _ in range(B_PERM):
                sh = rng.permutation(d.wk_out.values)
                aa, bb = d.g2n.values[sh >= 2], d.g2n.values[sh == 0]
                hits += len(aa) > 0 and abs(aa.mean() - bb.mean()) >= abs(diff)
            pp = (hits + 1) / (B_PERM + 1)
        print(f"  {pos}: r={obs:+.3f} (p={p:.4f})  P(2+wk Out next|2+ now)={a.g2n.mean():.1%} (n={len(a)}) "
              f"vs P(2+|0)={b.g2n.mean():.1%} (n={len(b)}), diff={diff:+.1%} (p={pp:.4f})")
    obs, p = perm_p_partial(imr.wk_out, imr.ppg_next, imr.ppg, quick)
    line("weeks-Out partial vs next-yr PPG", obs, p, n=len(imr))


def lists_2026(m):
    print("\n===== 2026 DRAFT LISTS (from 2025 stats) =====")
    d = m[m.relevant & (m.season == 2025) & m.position.isin(["RB", "WR", "TE"])].dropna(subset=["tdoe"])
    cols = ["name", "position", "gp", "ppg", "td", "xtd", "tdoe"]
    fmt = dict(index=False, float_format=lambda x: f"{x:.1f}")
    print("TD-lucky (fade at cost):")
    print(d.nlargest(12, "tdoe")[cols].to_string(**fmt))
    print("\nTD-unlucky (buy):")
    print(d.nsmallest(12, "tdoe")[cols].to_string(**fmt))
    q = m[m.relevant & (m.season == 2025) & (m.position == "QB")].dropna(subset=["a_pass_td"]).copy()
    q["tdoe"] = q.a_pass_td - q.x_pass_td
    print("\nQB pass-TD luck (top/bottom 5):")
    print(pd.concat([q.nlargest(5, "tdoe"), q.nsmallest(5, "tdoe")])[
        ["name", "gp", "ppg", "a_pass_td", "x_pass_td", "tdoe"]].to_string(**fmt))
    wr = m[m.relevant & (m.season == 2025) & (m.position == "WR")].dropna(subset=["targets"]).copy()
    wr["tpg"] = wr.targets / wr.gp
    wr["tgt_excess"] = resid(wr.tpg.values, wr.ppg.values)
    print("\nWR volume buys (targets >> PPG):")
    print(wr.nlargest(10, "tgt_excess")[["name", "gp", "ppg", "tpg", "tgt_excess"]].to_string(**fmt))
    print("\nWR efficiency-dependent (fade):")
    print(wr.nsmallest(8, "tgt_excess")[["name", "gp", "ppg", "tpg", "tgt_excess"]].to_string(**fmt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip permutation/bootstrap suite")
    args = ap.parse_args()

    adv, opp, inj = load_or_fetch()
    ps = build_player_seasons()
    m = build_merged(ps, adv, opp)
    im = build_injuries(ps, inj)
    n_rel = len(ps[ps.relevant & ps.season.lt(2025) & ps.ppg_next.notna()])
    print(f"relevant player-season pairs with next-year data: {n_rel}")

    late_season(ps, args.quick)
    td_luck(m, args.quick)
    efficiency(m, args.quick)
    injuries(im, args.quick)
    lists_2026(m)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    main()
