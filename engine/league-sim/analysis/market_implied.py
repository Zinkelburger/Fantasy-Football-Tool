"""Market-implied projections from The Odds API (free tier, key in .env).

Two tools:

  market_implied.py season [snapshot.json]
      The full 2026 schedule already has spreads/totals/h2h from ~9
      books (fetched Aug 2026). Consensus (median) lines -> implied
      team totals per game -> the market's 2026 team scoring
      environment, TODAY — the live version of the preseason
      win-total prior that finding 26 found beats every stat-based
      signal (0.458 vs 0.421 for lag PF), and that the historical
      dataset only covered through 2022. Writes
      data/market/implied_2026.csv. Without a snapshot file, fetches
      fresh (costs 3 credits of the 500/month).

  market_implied.py props
      In-season weekly tool (props post during game week; empty in
      August). Fetches player props for this week's games and converts
      to implied fantasy points under LEAGUE scoring (STD: receptions
      are worthless, so markets = pass yds/TDs, rush yds, rec yds,
      anytime TD). Yard lines ~ medians -> pts directly; anytime-TD
      odds -> devigged prob -> expected TDs ~ 1.15 * p. Budget: 5
      markets x ~16 games = ~80 credits/week, fits free tier.
      Output: data/market/props_implied_wkN.csv for comparison against
      the weekly model (finding 26's M4) — the paper-trade plan.

Historical odds (the backtest we'd want) are locked to paid plans
(~$30/mo for 20k credits; a 3-week props backtest ~ 2-3k credits).
"""
import json
import os
import sys
import urllib.request
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MKT = ROOT / "data" / "market"
BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
PROP_MARKETS = ("player_pass_yds,player_pass_tds,player_rush_yds,"
                "player_reception_yds,player_anytime_td")


def api_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("ODDS_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("ODDS_API_KEY not in .env")


def get(path, **params):
    params["apiKey"] = api_key()
    q = "&".join(f"{k}={v}" for k, v in params.items())
    with urllib.request.urlopen(f"{BASE}/{path}?{q}") as r:
        remaining = r.headers.get("x-requests-remaining")
        print(f"  [credits remaining: {remaining}]", file=sys.stderr)
        return json.load(r)


def devig(p_a, p_b):
    return p_a / (p_a + p_b)


def american_prob(o):
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def season(snapshot=None):
    if snapshot:
        events = json.load(open(snapshot))
    else:
        events = get(f"sports/{SPORT}/odds", regions="us",
                     markets="h2h,spreads,totals", oddsFormat="american")
    rows = []
    for e in events:
        home, away = e["home_team"], e["away_team"]
        spreads, totals, ph, pa = [], [], [], []
        for b in e["bookmakers"]:
            for m in b["markets"]:
                if m["key"] == "spreads":
                    for o in m["outcomes"]:
                        if o["name"] == home:
                            spreads.append(o["point"])
                elif m["key"] == "totals":
                    totals.append(m["outcomes"][0]["point"])
                elif m["key"] == "h2h":
                    probs = {o["name"]: american_prob(o["price"])
                             for o in m["outcomes"]}
                    if home in probs and away in probs:
                        ph.append(devig(probs[home], probs[away]))
        if not spreads or not totals:
            continue
        sp, tot = median(spreads), median(totals)
        wp = median(ph) if ph else 0.5
        rows.append((e["commence_time"][:10], home, away,
                     tot / 2 - sp / 2, tot / 2 + sp / 2, wp))
    g = pd.DataFrame(rows, columns=["date", "home", "away",
                                    "imp_home", "imp_away", "wp_home"])
    print(f"{len(g)} games with consensus lines")
    team = {}
    for r in g.itertuples():
        for t, pts, opp, w in ((r.home, r.imp_home, r.imp_away, r.wp_home),
                               (r.away, r.imp_away, r.imp_home, 1 - r.wp_home)):
            d = team.setdefault(t, {"pts": [], "opp": [], "w": []})
            d["pts"].append(pts); d["opp"].append(opp); d["w"].append(w)
    out = pd.DataFrame([
        dict(team=t, games=len(d["pts"]),
             imp_ppg=np.mean(d["pts"]), imp_opp_ppg=np.mean(d["opp"]),
             imp_wins=np.sum(d["w"]))
        for t, d in team.items()]).sort_values("imp_ppg", ascending=False)
    out.to_csv(MKT / "implied_2026.csv", index=False)
    print("\nmarket-implied 2026 environment (top 8 / bottom 5):")
    for r in out.head(8).itertuples():
        print(f"  {r.team:24s} {r.imp_ppg:5.1f} implied ppg   "
              f"{r.imp_wins:4.1f} wins")
    print("  ...")
    for r in out.tail(5).itertuples():
        print(f"  {r.team:24s} {r.imp_ppg:5.1f} implied ppg   "
              f"{r.imp_wins:4.1f} wins")
    print(f"\n-> {MKT/'implied_2026.csv'}")


def props():
    events = get(f"sports/{SPORT}/events", )
    soon = [e for e in events][:16]
    rows = []
    for e in soon:
        od = get(f"sports/{SPORT}/events/{e['id']}/odds", regions="us",
                 markets=PROP_MARKETS, oddsFormat="american")
        lines = {}
        for b in od.get("bookmakers", []):
            for m in b["markets"]:
                for o in m["outcomes"]:
                    key = (o.get("description", o["name"]), m["key"])
                    lines.setdefault(key, []).append(
                        (o.get("point"), o["price"], o["name"]))
        players = {}
        for (player, mkt), vals in lines.items():
            d = players.setdefault(player, {})
            if mkt == "player_anytime_td":
                probs = [american_prob(p) for _, p, _ in vals]
                d["e_td"] = 1.15 * (np.mean(probs) * 0.93)  # devig approx
            else:
                pts = [pt for pt, _, side in vals
                       if pt is not None and side == "Over"]
                if pts:
                    d[mkt] = median(pts)
        for player, d in players.items():
            fp = (d.get("player_pass_yds", 0) / 25
                  + d.get("player_pass_tds", 0) * 4
                  + d.get("player_rush_yds", 0) / 10
                  + d.get("player_reception_yds", 0) / 10
                  + d.get("e_td", 0) * 6)
            if fp > 0:
                rows.append(dict(game=f"{e['away_team']}@{e['home_team']}",
                                 player=player, implied_fp=round(fp, 1),
                                 **{k: v for k, v in d.items()}))
    if not rows:
        print("no props posted yet (books post them during game week)")
        return
    out = pd.DataFrame(rows).sort_values("implied_fp", ascending=False)
    wk = out_path = MKT / "props_implied_latest.csv"
    out.to_csv(out_path, index=False)
    print(f"{len(out)} players with implied fantasy points -> {wk}")
    print(out.head(15).to_string(index=False))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "season"
    if mode == "season":
        season(sys.argv[2] if len(sys.argv) > 2 else None)
    elif mode == "props":
        props()
