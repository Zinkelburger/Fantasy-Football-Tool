"""Rookie-year projection model — fills the board's "veterans only" gap.

Rookies have no NFL season to read, so the veteran player model skips
them. This one reads what exists before Week 1, deliberately WITHOUT
absolute fantasy ADP (the point is an independent opinion):

- draft capital: log overall pick — the market that actually watched
  the film — plus draft age (an old rookie is a red flag by itself)
- combine: height, weight, 40, vertical, broad, cone, shuttle, bench
  (nflverse combine.parquet; missing tests mean-imputed, like every
  other NaN here)
- landing spot, no ADP needed: salary already committed to the same
  position room on his team (OTC contracts — a rookie behind a paid
  veteran waits), and the team's prior-season offense rating
- ONE relative-ADP read, allowed because it prices his path to the
  field, not the player: log of the best (earliest) veteran ADP at his
  position on his team. A rookie RB behind an ADP-15 back is blocked;
  behind an ADP-140 back he is a starter-in-waiting.

NOT included: college production. The free cfbfastR mirrors publish
college play-by-play only (no season stat tables, ~100MB/season to
aggregate, ESPN ids that don't join our sports-reference slugs), and
CollegeFootballData needs an API key. Draft capital carries most of
that signal anyway — teams drafted the production. v2 candidate.

Model: per-position ridge (standardized, lambda by nested
leave-one-class-out), mirroring player_model.py. Target = rookie-year
fantasy points per SCHEDULED game (16 before 2021, 17 after) — per
scheduled game, not per game played, so a Week-3 bust counts as the
bust it was. Drafted players who never signed/played score 0.

Evaluated leave-one-class-out on the 2017-2025 classes against two
benchmarks: draft order (rank by pick) and, for 2018+ where the FFC
snapshot exists, the fantasy market's rookie ADP. Metric: Spearman
rank correlation within class, per position.

Output: data/market/rookie_board_2026.csv with per-format projections
(standard / half / full PPR are separate fits, like the veteran model).

Usage: rookie_model.py [--list]   (--list prints the 2026 board only)
"""
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# all-NaN feature slices (e.g. team ratings before 2018) mean-impute to
# zero by design; numpy's empty-slice warnings are just noise here
warnings.filterwarnings("ignore", category=RuntimeWarning)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import player_model as pm                                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
POSITIONS = ("QB", "RB", "WR", "TE")
CLASSES = list(range(2017, 2026))        # rookie classes with weekly data
LAMS = (1.0, 10.0, 30.0, 100.0)

SCORINGS = (("standard", 0.0, "pred_std"),
            ("half PPR", 0.5, "pred_half"),
            ("full PPR", 1.0, "pred_ppr"))

FEATURES = [
    "ln_pick", "draft_age",
    "ht_in", "wt", "forty", "vertical", "broad", "cone", "shuttle", "bench",
    "room_cap", "ln_vet_adp", "team_off",
]

SUFFIX_RE = re.compile(r"\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$")

# roster/nflverse code <- other feeds' codes (PFR draft table, FFC ADP),
# so team joins line up
TEAM_CANON = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "SD": "LAC",
              "STL": "LA", "OAK": "OAK", "HST": "HOU", "BLT": "BAL",
              "ARZ": "ARI", "CLV": "CLE", "KAN": "KC", "LVR": "LV",
              "NOR": "NO", "NWE": "NE", "SFO": "SF", "TAM": "TB",
              "GNB": "GB"}


def canon(team):
    return TEAM_CANON.get(str(team or "").upper(), str(team or "").upper())


def _norm(name):
    n = str(name).lower().strip().replace(".", "").replace("'", "")
    return re.sub(r"\s+", " ", SUFFIX_RE.sub("", n))


def ht_inches(ht):
    """'6-4' -> 76.0; combine heights are feet-inches strings."""
    m = re.match(r"^(\d+)-(\d+)$", str(ht or ""))
    return float(m.group(1)) * 12 + float(m.group(2)) if m else np.nan


def draft_classes():
    d = pd.read_parquet(MKT / "draft_picks.parquet")
    d = d[d.position.isin(POSITIONS)].copy()
    d["ht_key"] = d.pfr_player_id
    return d


def combine_table():
    c = pd.read_parquet(MKT / "combine.parquet").dropna(subset=["pfr_id"])
    c = c.drop_duplicates("pfr_id").set_index("pfr_id")
    c["ht_in"] = [ht_inches(h) for h in c.ht]
    return c[["ht_in", "wt", "forty", "vertical", "broad_jump",
              "cone", "shuttle", "bench"]]


def adp_rows(year):
    p = DATA / f"adp_{year}.json"
    if p.exists():
        return json.loads(p.read_text())
    # 2026 has no sim cache yet; the tracked ADP snapshot carries the
    # same FFC numbers (engine/update_ranks.py writes it).
    snap = MKT / f"adp_{year}.csv"
    if snap.exists():
        df = pd.read_csv(snap)
        return [dict(name=r.player, pos=r.pos, team=r.team, adp=r.ffc_std)
                for r in df.itertuples() if pd.notna(r.ffc_std)]
    return []


def vet_adp_by_room(year, class_names):
    """(team, pos) -> best veteran ADP that season, rookies of that
    class excluded so the feature reads incumbents only."""
    best = {}
    for e in adp_rows(year):
        if _norm(e["name"]) in class_names or not e.get("team"):
            continue
        key = (canon(e["team"]), e["pos"])
        if e["adp"] is not None:
            best[key] = min(best.get(key, 999.0), float(e["adp"]))
    return best


def room_cap_by_team(year, cap, ros):
    """(team, pos) -> summed cap % already committed that season."""
    out = {}
    for gsis, r in ros.iterrows():
        pct = cap.get((gsis, year), (0.0, 0.0))[1]
        key = (r.team, r.position)
        out[key] = out.get(key, 0.0) + pct * 100
    return out


def sched_games(year):
    return 17 if year >= 2021 else 16


def build_class(t, drafts, comb, cap):
    """Feature rows for the class of year t (no target attached)."""
    cls = drafts[drafts.season == t]
    class_names = {_norm(n) for n in cls.pfr_player_name}
    ros = pm.roster(t)
    vet_adp = vet_adp_by_room(t, class_names)
    room = room_cap_by_team(t, cap, ros)
    try:
        team_off = {tm: pm.team_rating(t - 1, tm)[0]
                    for tm in ros.team.unique()} if t - 1 >= 2017 else {}
    except Exception:
        team_off = {}

    rows = []
    for r in cls.itertuples():
        gsis = r.gsis_id if pd.notna(r.gsis_id) else None
        team = (ros.loc[gsis].team if gsis in ros.index
                else canon(r.team))
        c = comb.loc[r.pfr_player_id] if r.pfr_player_id in comb.index else None
        va = vet_adp.get((team, r.position), np.nan)
        rows.append(dict(
            pid=gsis, name=r.pfr_player_name, pos=r.position, year=t,
            team=team, rnd=int(r.round), pick=int(r.pick),
            ln_pick=np.log(float(r.pick)),
            draft_age=float(r.age) if pd.notna(r.age) else np.nan,
            ht_in=c.ht_in if c is not None else np.nan,
            wt=float(c.wt) if c is not None and pd.notna(c.wt) else np.nan,
            forty=float(c.forty) if c is not None and pd.notna(c.forty) else np.nan,
            vertical=float(c.vertical) if c is not None and pd.notna(c.vertical) else np.nan,
            broad=float(c.broad_jump) if c is not None and pd.notna(c.broad_jump) else np.nan,
            cone=float(c.cone) if c is not None and pd.notna(c.cone) else np.nan,
            shuttle=float(c.shuttle) if c is not None and pd.notna(c.shuttle) else np.nan,
            bench=float(c.bench) if c is not None and pd.notna(c.bench) else np.nan,
            room_cap=room.get((team, r.position), 0.0),
            ln_vet_adp=np.log(va) if pd.notna(va) else np.nan,
            team_off=team_off.get(team, np.nan),
        ))
    return pd.DataFrame(rows)


def targets(t, ppr):
    """gsis_id -> rookie-year points per scheduled game."""
    s = pm.season_stats(t, ppr)
    return (s.pts / sched_games(t)).to_dict()


def market_adp_rank(t, cls):
    """Rookie ADP values for the class; NaN = the fantasy market never
    priced him.

    NaN, not a tied sentinel. Scoring unpriced rookies as one big tied
    block asks the model to sort a group ADP was never asked to sort,
    which silently hands it the win — the same mistake finding 25 made.
    Callers must mask on NaN."""
    adp = {}
    for e in adp_rows(t):
        adp[(_norm(e["name"]), e["pos"])] = float(e["adp"])
    return np.array([adp.get((_norm(r.name), r.pos), np.nan)
                     for r in cls.itertuples()])


def fit_predict(tr, te, lam):
    a, b = pm.standardize(tr[FEATURES].values, te[FEATURES].values)
    beta = pm.ridge_fit(a, tr.y.values, lam)
    return pm.ridge_pred(beta, b)


def pick_lam(tr):
    best = (30.0, -9)
    for lam in LAMS:
        scs = []
        for inner in sorted(tr.year.unique()):
            itr, ite = tr[tr.year != inner], tr[tr.year == inner]
            if len(ite) < 8:
                continue
            scs.append(pm.spearman(fit_predict(itr, ite, lam), ite.y.values))
        if scs and np.mean(scs) > best[1]:
            best = (lam, np.mean(scs))
    return best[0]


MIN_CELL = 8       # fewest players in a position-class cell worth scoring


def _paired(rows, a, b):
    """mean, se and win count of benchmark `a` minus benchmark `b`."""
    d = np.array([r[a] - r[b] for r in rows])
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else np.nan
    return d.mean(), se, int((d > 0).sum()), len(d)


def evaluate(data):
    """Two head-to-heads, each run only where the benchmark is defined.

    Draft order ranks the whole class, so the model can be graded
    against it on everybody. **Fantasy ADP cannot**: only ~26% of a
    drafted class is priced at all (185 of 721), and scoring the other
    74% as a tied block asks the model to sort a group ADP was never
    asked to sort. That is the finding-25 bug in a different costume,
    and it is what the original version of this script did.

    So the ADP head-to-head runs on priced rookies only, and only in
    cells with at least MIN_CELL of them. In practice that leaves RB and
    WR: the fantasy market prices 1-5 rookie QBs and 0-2 rookie TEs a
    class, which is far too few to rank against.
    """
    cells = {}
    for pos in POSITIONS:
        d = data[data.pos == pos]
        for hold in CLASSES:
            tr, te = d[d.year != hold], d[d.year == hold]
            if len(te) < MIN_CELL:
                continue
            pred = fit_predict(tr, te, pick_lam(tr))
            cells[(pos, hold)] = (te, pred, market_adp_rank(hold, te))

    print("A) every drafted rookie — draft order vs the model")
    print(f"{'pos':4s} {'class':>5s} {'n':>4s}   draft  model")
    per_pos = {}
    for pos in POSITIONS:
        rows = []
        for hold in CLASSES:
            if (pos, hold) not in cells:
                continue
            te, pred, _ = cells[(pos, hold)]
            r = dict(draft=pm.spearman(-te.pick.values, te.y.values),
                     model=pm.spearman(pred, te.y.values))
            rows.append(r)
            print(f"{pos:4s} {hold:5d} {len(te):4d}  {r['draft']:6.3f} "
                  f"{r['model']:6.3f}")
        if rows:
            per_pos[pos] = rows
            print(f"{pos:4s} {'mean':>5s}       "
                  f"{np.mean([r['draft'] for r in rows]):6.3f} "
                  f"{np.mean([r['model'] for r in rows]):6.3f}\n")
    allrows = [r for rows in per_pos.values() for r in rows]
    m, se, w, n = _paired(allrows, "model", "draft")
    print(f"model - draft order, paired: {m:+.3f} +/- {se:.3f}  "
          f"wins {w}/{n}\n")

    print("B) rookies the fantasy market actually priced — the ADP "
          "head-to-head")
    print(f"{'pos':4s} {'class':>5s} {'n':>4s}   draft    ADP  model")
    b_rows, skipped = {}, []
    for pos in POSITIONS:
        rows = []
        for hold in CLASSES:
            if (pos, hold) not in cells:
                continue
            te, pred, adp = cells[(pos, hold)]
            m_ = ~np.isnan(adp)
            if m_.sum() < MIN_CELL:
                skipped.append(f"{pos} {hold} (n={int(m_.sum())})")
                continue
            y = te.y.values[m_]
            r = dict(draft=pm.spearman(-te.pick.values[m_], y),
                     adp=pm.spearman(-adp[m_], y),
                     model=pm.spearman(pred[m_], y))
            rows.append(r)
            print(f"{pos:4s} {hold:5d} {int(m_.sum()):4d}  {r['draft']:6.3f} "
                  f"{r['adp']:6.3f} {r['model']:6.3f}")
        if rows:
            b_rows[pos] = rows
            print(f"{pos:4s} {'mean':>5s}       "
                  f"{np.mean([r['draft'] for r in rows]):6.3f} "
                  f"{np.mean([r['adp'] for r in rows]):6.3f} "
                  f"{np.mean([r['model'] for r in rows]):6.3f}\n")
    if skipped:
        print(f"  too few priced rookies to score ({MIN_CELL} needed): "
              + ", ".join(skipped) + "\n")
    allb = [r for rows in b_rows.values() for r in rows]
    if allb:
        for lab, a in (("model - ADP", "model"), ("draft - ADP", "draft")):
            m, se, w, n = _paired(allb, a, "adp")
            print(f"{lab:14s} paired: {m:+.3f} +/- {se:.3f}  wins {w}/{n}")

    print("\nstandardized ridge coefficients (lam=30), full panel:")
    print(f"{'feature':12s}" + "".join(f"{p:>8s}" for p in POSITIONS))
    betas = {}
    for pos in POSITIONS:
        d = data[data.pos == pos]
        a, _ = pm.standardize(d[FEATURES].values, d[FEATURES].values)
        betas[pos] = pm.ridge_fit(a, d.y.values, 30.0)[1:]
    for i, f in enumerate(FEATURES):
        print(f"{f:12s}" + "".join(f"{betas[p][i]:8.2f}" for p in POSITIONS))


def main():
    list_only = "--list" in sys.argv
    drafts = draft_classes()
    comb = combine_table()
    cap = pm.cap_table()

    panels = {t: build_class(t, drafts, comb, cap) for t in CLASSES}
    feat26 = build_class(2026, drafts, comb, cap)
    print(f"panel: {sum(len(p) for p in panels.values())} drafted skill "
          f"rookies 2017-25, {len(feat26)} in the 2026 class\n")

    board = feat26[["name", "pos", "team", "rnd", "pick"]].copy()

    for label, ppr, col in SCORINGS:
        data = pd.concat(panels.values(), ignore_index=True)
        y = {t: targets(t, ppr) for t in CLASSES}
        data["y"] = [y[r.year].get(r.pid, 0.0) for r in data.itertuples()]

        if not list_only and ppr == 0.0:
            evaluate(data)

        # 2026 board, this format
        preds = np.full(len(feat26), np.nan)
        for pos in POSITIONS:
            d = data[data.pos == pos]
            m = (feat26.pos == pos).values
            if not m.any():
                continue
            preds[m] = fit_predict(d, feat26[m], 30.0)
        board[col] = np.round(preds, 1)

    board = board.sort_values("pred_std", ascending=False)
    dst = MKT / "rookie_board_2026.csv"
    board.to_csv(dst, index=False)
    print(f"\n=== 2026 rookie board (top 25, standard) ===")
    for i, r in enumerate(board.head(25).itertuples(), 1):
        print(f"  {i:2d}. {r.name:24s} {r.pos:2s} {r.team:3s} "
              f"rd{r.rnd} pk{r.pick:3d}  {r.pred_std:4.1f}")
    print(f"\nfull board -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
