"""What hits, round by round — under all three scoring formats.

For every drafted player 2018-2025 (ADP boards, 12-team rounds), score
the season under STD / 0.5PPR / PPR and ask, per round band and
position: how often did the pick return a starter, and what did the
hits have in common that the busts didn't?

Sections printed:
  1. hit rates by round band x position x format
  2. late rounds (9+): RB vs WR starter-hit gap, per-season signs and a
     permutation p (is late-RB-over-WR real or luck?)
  3. per-round table (all formats) for the site/guide
  4. trait profile of hits vs busts inside each band (age, rookie,
     prior-year usage), per position
  5. does the 0.5/full-PPR world change any of it

Definitions (12-team, documented in finding 29):
  round     = ceil(overall ADP / 12), capped at 15
  finish    = rank by season TOTAL points at the position (volume and
              health count — that's what wins leagues)
  starter   = finish <= 12 (QB/TE) or <= 24 (RB/WR)
  usable    = finish <= 18 (QB/TE) or <= 36 (RB/WR)
  smash     = finish <= 6  (QB/TE) or <= 12 (RB/WR)

Run:  venv/bin/python analysis/round_profile.py
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
sys.path.insert(0, str(ROOT / "analysis"))
from player_model import league_pts, weekly_raw          # noqa: E402

YEARS = range(2018, 2026)
FORMATS = {"std": 0.0, "half": 0.5, "ppr": 1.0}
STARTER = {"QB": 12, "TE": 12, "RB": 24, "WR": 24}
USABLE = {"QB": 18, "TE": 18, "RB": 36, "WR": 36}
SMASH = {"QB": 6, "TE": 6, "RB": 12, "WR": 12}
BANDS = [(1, 2), (3, 5), (6, 8), (9, 11), (12, 15)]
LATE = (9, 15)
_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv|v)\.?$")
rng = np.random.default_rng(42)

ROOKIE_YEAR = {k: int(v) for k, v in
               json.load(open(DATA / "rookie_years.json")).items()}


def norm(name):
    n = name.lower().strip().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", _SUFFIX.sub("", n))


def roster_ids(year):
    """normalized name -> (gsis_id, age at Sept 1)."""
    r = pd.read_parquet(MKT / f"roster_{year}.parquet")[
        ["full_name", "gsis_id", "birth_date"]].dropna(subset=["full_name",
                                                               "gsis_id"])
    out = {}
    for x in r.itertuples():
        age = None
        if pd.notna(x.birth_date):
            y, mo, dy = str(x.birth_date)[:10].split("-")
            age = year - int(y) - (1 if (int(mo), int(dy)) > (9, 1) else 0)
        out.setdefault(norm(x.full_name), (x.gsis_id, age))
    return out


def finishes(year):
    """format -> {player_id: positional finish}, plus pos of each id."""
    w = weekly_raw(year)
    out = {}
    for fmt, ppr in FORMATS.items():
        pts = league_pts(w, ppr)
        g = pd.DataFrame({"player_id": w.player_id, "pos": w.position,
                          "pts": pts}).groupby("player_id").agg(
            pos=("pos", "first"), total=("pts", "sum"))
        g["fin"] = g.groupby("pos").total.rank(ascending=False,
                                               method="first")
        out[fmt] = {pid: int(f) for pid, f in g.fin.items()}
    return out


def prior_usage(year):
    """player_id -> per-game targets/carries in year-1."""
    a = pd.read_parquet(DATA / "adv_weekly_2017_2025.parquet")
    a = a[(a.season == year - 1) & (a.season_type == "REG")]
    g = a.groupby("player_id").agg(tgt=("targets", "sum"),
                                   car=("carries", "sum"),
                                   gwk=("week", "nunique"))
    return {pid: (r.tgt / r.gwk, r.car / r.gwk) for pid, r in g.iterrows()}


def build():
    rows = []
    for year in YEARS:
        ids = roster_ids(year)
        fin = finishes(year)
        usage = prior_usage(year)
        unmatched = 0
        for e in json.load(open(DATA / f"adp_{year}.json")):
            if e.get("pos") not in STARTER or not e.get("adp"):
                continue
            hit = ids.get(norm(e["name"]))
            if hit is None:
                unmatched += 1
                continue
            pid, age = hit
            tgt, car = usage.get(pid, (None, None))
            row = dict(year=year, name=e["name"], pos=e["pos"],
                       adp=float(e["adp"]),
                       rnd=min(15, math.ceil(float(e["adp"]) / 12)),
                       pid=pid, age=age,
                       rookie=ROOKIE_YEAR.get(pid) == year,
                       tgt_pg=tgt, car_pg=car)
            for fmt in FORMATS:
                row[f"fin_{fmt}"] = fin[fmt].get(pid)
            rows.append(row)
        if unmatched:
            print(f"  ({year}: {unmatched} ADP names unmatched to rosters)")
    return pd.DataFrame(rows)


def rate(sel, fmt, cut):
    """share of picks finishing at/above `cut` for their position."""
    ok = sel[f"fin_{fmt}"].notna()
    if not ok.any():
        return None, 0
    hits = sum(1 for r in sel[ok].itertuples()
               if getattr(r, f"fin_{fmt}") <= cut[r.pos])
    n = int(ok.sum())
    # a drafted player with no season row is a zero, not missing data
    n_all = len(sel)
    hits_all = hits
    return hits_all / n_all, n_all


def section_bands(df):
    print("\n== 1. starter-hit rate by band x position x format ==")
    print("   (starter = top-12 QB/TE, top-24 RB/WR by season total; "
          "no-season = bust)")
    for lo, hi in BANDS:
        band = df[(df.rnd >= lo) & (df.rnd <= hi)]
        line = [f"R{lo}-{hi:<2}"]
        for pos in ("QB", "RB", "WR", "TE"):
            sel = band[band.pos == pos]
            if not len(sel):
                line.append(f"{pos}: --")
                continue
            cells = []
            for fmt in FORMATS:
                r, n = rate(sel, fmt, STARTER)
                cells.append(f"{r:4.0%}" if r is not None else "  --")
            line.append(f"{pos} n={len(sel):3d} " + "/".join(cells))
        print("  " + "   ".join(line))
    print("   (cells are std/half/ppr)")


def section_late(df):
    print("\n== 2. late rounds (9-15): RB vs WR ==")
    late = df[(df.rnd >= LATE[0]) & (df.rnd <= LATE[1])
              & df.pos.isin(["RB", "WR"])]
    for fmt in FORMATS:
        rb = late[late.pos == "RB"]
        wr = late[late.pos == "WR"]
        r_rb, n_rb = rate(rb, fmt, STARTER)
        r_wr, n_wr = rate(wr, fmt, STARTER)
        u_rb, _ = rate(rb, fmt, USABLE)
        u_wr, _ = rate(wr, fmt, USABLE)
        s_rb, _ = rate(rb, fmt, SMASH)
        s_wr, _ = rate(wr, fmt, SMASH)
        diff = r_rb - r_wr
        # permutation: shuffle pos labels within each year (numpy).
        # NOTE the null keeps each pick's own finish-at-its-own-position
        # hit flag and only permutes which label it counts under — it
        # tests "are late-RB picks likelier to hit than late-WR picks",
        # not anything about the positions' scales.
        hit_flag = np.array([
            (not pd.isna(getattr(r, f"fin_{fmt}")))
            and getattr(r, f"fin_{fmt}") <= STARTER[r.pos]
            for r in late.itertuples()])
        is_rb = (late.pos == "RB").values
        year_idx = [np.where((late.year == y).values)[0]
                    for y in late.year.unique()]
        perms = np.empty(5000)
        for i in range(5000):
            lab = is_rb.copy()
            for idx in year_idx:
                lab[idx] = rng.permutation(lab[idx])
            perms[i] = hit_flag[lab].mean() - hit_flag[~lab].mean()
        p = (np.sum(np.abs(perms) >= abs(diff)) + 1) / 5001
        print(f"  {fmt:>4}: RB starter {r_rb:.1%} (n={n_rb}) vs WR "
              f"{r_wr:.1%} (n={n_wr}), diff {diff:+.1%} p={p:.3f} | "
              f"usable {u_rb:.1%} vs {u_wr:.1%} | smash {s_rb:.1%} vs "
              f"{s_wr:.1%}")
    print("  per-season RB-minus-WR starter gap (std):")
    for y, g in late.groupby("year"):
        rb = g[g.pos == "RB"]
        wr = g[g.pos == "WR"]
        if not len(rb) or not len(wr):
            continue
        r1, _ = rate(rb, "std", STARTER)
        r2, _ = rate(wr, "std", STARTER)
        print(f"    {y}: {r1 - r2:+.1%}  (RB n={len(rb)}, WR n={len(wr)})")


def section_perround(df):
    print("\n== 3. per-round starter-hit table (std | half | ppr, "
          "all positions pooled + RB/WR split) ==")
    for rnd in range(1, 16):
        sel = df[df.rnd == rnd]
        if not len(sel):
            continue
        cells = []
        for fmt in FORMATS:
            r, n = rate(sel, fmt, STARTER)
            cells.append(f"{r:4.0%}")
        rb, _ = rate(sel[sel.pos == "RB"], "std", STARTER) \
            if len(sel[sel.pos == "RB"]) else (None, 0)
        wr, _ = rate(sel[sel.pos == "WR"], "std", STARTER) \
            if len(sel[sel.pos == "WR"]) else (None, 0)
        print(f"  R{rnd:<2} n={len(sel):3d}  all {'/'.join(cells)}   "
              f"RB {rb if rb is None else format(rb, '4.0%')} | "
              f"WR {wr if wr is None else format(wr, '4.0%')}")


def section_traits(df):
    print("\n== 4. what separates hits from busts (starter cut, std) ==")
    for lo, hi in [(6, 8), (9, 11), (12, 15)]:
        band = df[(df.rnd >= lo) & (df.rnd <= hi)]
        print(f"  R{lo}-{hi}:")
        for pos in ("RB", "WR", "TE", "QB"):
            sel = band[band.pos == pos].copy()
            if len(sel) < 20:
                continue
            sel["hit"] = [
                (not pd.isna(getattr(r, "fin_std")))
                and r.fin_std <= STARTER[pos] for r in sel.itertuples()]
            h = sel[sel.hit]
            b = sel[~sel.hit]
            if not len(h):
                continue
            vol = "tgt_pg" if pos in ("WR", "TE") else "car_pg"

            def m(s, col):
                v = s[col].dropna()
                return f"{v.mean():.1f}" if len(v) else "--"

            print(f"    {pos}: hit {len(h):3d}/{len(sel):3d}  "
                  f"age {m(h, 'age')} vs {m(b, 'age')}  "
                  f"rookie {h.rookie.mean():.0%} vs {b.rookie.mean():.0%}  "
                  f"prior {vol} {m(h, vol)} vs {m(b, vol)}")


def section_formats(df):
    print("\n== 5. who moves between formats (top-24 RB/WR std vs ppr) ==")
    moved = 0
    for r in df.itertuples():
        if r.pos not in ("RB", "WR"):
            continue
        a, b = r.fin_std, r.fin_ppr
        if pd.isna(a) or pd.isna(b):
            continue
        if (a <= 24) != (b <= 24):
            moved += 1
    both = len(df[df.pos.isin(["RB", "WR"])
                  & df.fin_std.notna() & df.fin_ppr.notna()])
    print(f"  {moved}/{both} drafted RB/WR seasons flip top-24 status "
          f"between std and full PPR ({moved / both:.1%})")
    late = df[(df.rnd >= LATE[0]) & df.pos.isin(["RB", "WR"])]
    for fmt in ("std", "ppr"):
        for pos in ("RB", "WR"):
            sel = late[late.pos == pos]
            r, n = rate(sel, fmt, STARTER)
            print(f"    late {pos} {fmt}: starter {r:.1%}")


def main():
    df = build()
    print(f"picks matched: {len(df)} over {df.year.nunique()} drafts")
    section_bands(df)
    section_late(df)
    section_perround(df)
    section_traits(df)
    section_formats(df)
    out = MKT / "round_profile.csv"
    df.drop(columns=["pid"]).to_csv(out, index=False)
    print(f"\n{out} written ({len(df)} rows) — feeds finding 29 tables")


if __name__ == "__main__":
    main()
