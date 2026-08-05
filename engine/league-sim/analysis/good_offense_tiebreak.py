"""Is "take the guy on the better offense" a real draft tiebreak?

The 2026 board shows a market-implied points-per-game for every offense
(implied_2026.csv, from the full-schedule betting lines). Before telling
people to break draft ties with it, test the idea on history.

No historical full-schedule line snapshots exist on the free tier, so
the preseason signal is the Vegas win-total line — the market's August
opinion of each team. Section 1 checks that the two are near-duplicates
on 2026 data (they are); sections 2-3 then backtest the win-total line:

  1. proxy check: implied PPG vs implied wins on the 2026 snapshot
  2. team level 2003-2025: does the August line predict which offenses
     actually score? (rho per season; 2025 called out, top/bottom 8)
  3. player level 2018-2025: the tiebreak itself. Same-position pairs
     drafted within 6 ADP slots of each other where the teams' lines
     sat >= 1.5 wins apart: how often did the better-offense player
     finish with more points? Plus per-season signs and a binomial p.
  4. robustness: the same pair test across window/gap/depth choices and
     on per-game scoring (8+ games) instead of season totals.

Data: win_totals_sos.csv (nfelo, 2003-2022) + win_totals_2023_2025.csv
(sportsoddshistory.com preseason lines), games.csv for actual scoring,
adp_<year>.json + weekly parquets (league-exact STD scoring) for players.

Run:  venv/bin/python analysis/good_offense_tiebreak.py
"""
import json
import re
import sys
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MKT = DATA / "market"
sys.path.insert(0, str(ROOT / "analysis"))
from adp import spearman                                 # noqa: E402
from player_model import league_pts, weekly_raw          # noqa: E402

YEARS = range(2018, 2026)          # player-level test (ADP files start 2018)
ADP_CUT = 180                      # 15 rounds x 12 teams
PAIR_ADP = 6                       # "close call": within half a round
PAIR_GAP = 1.5                     # "clearly better offense": line gap, wins
POSITIONS = ("QB", "RB", "WR", "TE")

# one franchise code per team across relocations, matching current nflverse
CANON = {"LAR": "LA", "OAK": "LV", "SD": "LAC", "STL": "LA"}
_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv|v)\.?$")


def canon(t):
    return CANON.get(t, t)


def norm(name):
    n = name.lower().strip().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", _SUFFIX.sub("", n))


def win_lines():
    """(season, team) -> preseason win-total line, 2003-2025."""
    old = pd.read_csv(MKT / "win_totals_sos.csv")[["season", "team", "line"]]
    new = pd.read_csv(MKT / "win_totals_2023_2025.csv")[
        ["season", "team", "line"]]
    df = pd.concat([old, new], ignore_index=True)
    df["team"] = df.team.map(canon)
    return {(r.season, r.team): r.line for r in df.itertuples()}


def team_ppg():
    """(season, team) -> actual points per game, regular season."""
    g = pd.read_csv(MKT / "games.csv", low_memory=False)
    g = g[(g.game_type == "REG") & g.home_score.notna()]
    pts, n = {}, {}
    for r in g.itertuples():
        for t, s in ((canon(r.home_team), r.home_score),
                     (canon(r.away_team), r.away_score)):
            k = (r.season, t)
            pts[k] = pts.get(k, 0) + s
            n[k] = n.get(k, 0) + 1
    return {k: pts[k] / n[k] for k in pts}


def roster_pids(year):
    """normalized name -> gsis_id."""
    r = pd.read_parquet(MKT / f"roster_{year}.parquet")[
        ["full_name", "gsis_id"]].dropna()
    out = {}
    for x in r.itertuples():
        out.setdefault(norm(x.full_name), x.gsis_id)
    return out


def season_pts(year):
    """player_id -> season total, league-exact STD scoring."""
    w = weekly_raw(year)
    pts = league_pts(w, 0.0)
    return pd.DataFrame({"player_id": w.player_id, "pts": pts}) \
        .groupby("player_id").pts.sum().to_dict()


def sec1_proxy():
    imp = pd.read_csv(MKT / "implied_2026.csv")
    rho = spearman(imp.imp_ppg.to_numpy(), imp.imp_wins.to_numpy())
    pear = np.corrcoef(imp.imp_ppg, imp.imp_wins)[0, 1]
    print("1. proxy check, 2026 snapshot: implied PPG vs implied wins")
    print(f"   Spearman {rho:.3f}   Pearson {pear:.3f}   "
          "(win totals carry the same information)\n")


def sec2_team(lines, ppg):
    print("2. preseason win-total line -> actual offense PPG, by season")
    rhos = {}
    for season in range(2003, 2026):
        pairs = [(lines[k], ppg[k]) for k in lines
                 if k[0] == season and k in ppg]
        if len(pairs) < 30:
            continue
        rhos[season] = spearman(np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs]))
    for s, r in rhos.items():
        print(f"   {s}  rho {r:+.2f}" + ("   <- the season asked about"
                                         if s == 2025 else ""))
    vals = list(rhos.values())
    print(f"   mean rho {np.mean(vals):+.2f}   "
          f"range {min(vals):+.2f} to {max(vals):+.2f}   "
          f"negative seasons: {sum(v < 0 for v in vals)}/{len(vals)}\n")

    season = 2025
    rows = sorted(((lines[k], ppg[k], k[1]) for k in lines
                   if k[0] == season and k in ppg), reverse=True)
    ranks = {t: i + 1 for i, (_, p, t) in enumerate(
        sorted(rows, key=lambda x: -x[1]))}
    top, bot = rows[:8], rows[-8:]
    print("   2025 top-8 offenses by August line (actual PPG, PPG rank):")
    for ln, p, t in top:
        print(f"     {t:4s} line {ln:4.1f}   {p:5.1f} ppg   #{ranks[t]}")
    print(f"   top-8 avg {np.mean([p for _, p, _ in top]):.1f} ppg vs "
          f"bottom-8 avg {np.mean([p for _, p, _ in bot]):.1f} ppg\n")


def player_rows(lines):
    """Every drafted player-season: ADP, team win line, points, games."""
    all_rows = []
    for year in YEARS:
        pids = roster_pids(year)
        w = weekly_raw(year)
        per = pd.DataFrame({"player_id": w.player_id,
                            "pts": league_pts(w, 0.0)}) \
            .groupby("player_id").agg(total=("pts", "sum"),
                                      games=("pts", "size"))
        for e in json.load(open(DATA / f"adp_{year}.json")):
            if (e.get("pos") not in POSITIONS or not e.get("adp")
                    or float(e["adp"]) > ADP_CUT or not e.get("team")):
                continue
            line = lines.get((year, canon(e["team"])))
            pid = pids.get(norm(e["name"]))
            if line is None or pid is None:
                continue
            # a drafted player with no season row scored zero, not missing
            played = pid in per.index
            all_rows.append(dict(
                year=year, pos=e["pos"], adp=float(e["adp"]), line=line,
                pts=per.loc[pid, "total"] if played else 0.0,
                games=int(per.loc[pid, "games"]) if played else 0))
    return pd.DataFrame(all_rows)


def tally(sel, pair_adp=PAIR_ADP, gap=PAIR_GAP, col="pts"):
    """Close-ADP pairs decided by the win-line gap: (better-offense
    player outscored, pairs)."""
    wins = n = 0
    for a, b in combinations(sel.itertuples(), 2):
        if abs(a.adp - b.adp) > pair_adp:
            continue
        hi, lo = (a, b) if a.line > b.line else (b, a)
        if hi.line - lo.line < gap \
                or getattr(hi, col) == getattr(lo, col):
            continue
        n += 1
        wins += getattr(hi, col) > getattr(lo, col)
    return wins, n


def by_group(df, **kw):
    w = n = 0
    for year in YEARS:
        for pos in POSITIONS:
            dw, dn = tally(df[(df.year == year) & (df.pos == pos)], **kw)
            w += dw
            n += dn
    return w, n


def sec3_pairs(df):
    print("3. the tiebreak: same position, drafted within "
          f"{PAIR_ADP} ADP slots, line gap >= {PAIR_GAP} wins")
    print(f"   {len(df)} drafted player-seasons matched")
    total_w = total_n = 0
    for pos in POSITIONS:
        w = n = 0
        for year in YEARS:
            dw, dn = tally(df[(df.year == year) & (df.pos == pos)])
            w += dw
            n += dn
        total_w += w
        total_n += n
        print(f"   {pos}: better offense won {w}/{n}  ({w / n:.0%})")
    # anti-conservative (overlapping pairs share players) — the
    # per-season signs below are the honest robustness read
    p = sum(comb(total_n, k) for k in range(total_w, total_n + 1)) \
        / 2 ** total_n
    print(f"   ALL: {total_w}/{total_n}  ({total_w / total_n:.0%})   "
          f"binomial p {p:.4f} vs coin flip")
    per_season = []
    for year in YEARS:
        w = n = 0
        for pos in POSITIONS:
            dw, dn = tally(df[(df.year == year) & (df.pos == pos)])
            w += dw
            n += dn
        per_season.append((year, w, n))
        print(f"     {year}: {w}/{n}  ({w / n:.0%})")
    print(f"   seasons above 50%: "
          f"{sum(w / n > .5 for _, w, n in per_season)}/{len(per_season)}\n")


def sec4_robustness(df):
    print("4. robustness: same test, other reasonable choices")
    for pair_adp, gap, cut in [(12, 1.5, ADP_CUT), (6, 2.5, ADP_CUT),
                               (12, 2.5, ADP_CUT), (3, 3.0, ADP_CUT),
                               (6, 1.5, 100), (12, 2.5, 100)]:
        w, n = by_group(df[df.adp <= cut], pair_adp=pair_adp, gap=gap)
        print(f"   window {pair_adp:2d} slots, gap >= {gap}, "
              f"ADP <= {cut}: {w}/{n}  ({w / n:.0%})")
    df8 = df[df.games >= 8].assign(ppg=lambda d: d.pts / d.games)
    w, n = by_group(df8, col="ppg")
    print(f"   per-game scoring, 8+ games:      {w}/{n}  ({w / n:.0%})")


def main():
    lines = win_lines()
    ppg = team_ppg()
    sec1_proxy()
    sec2_team(lines, ppg)
    df = player_rows(lines)
    sec3_pairs(df)
    sec4_robustness(df)


if __name__ == "__main__":
    main()
