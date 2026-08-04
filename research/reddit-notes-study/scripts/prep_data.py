"""Step 1: join every reddit-note file with market rank and actual results.

Inputs (already in the repo):
  archive/2024/analysis/*.md         raw reddit comment pastes, one player per file
  archive/2025/go/analysis/*.md      LLM-summarized outlooks, one player per file
  archive/2024/ADR.csv               2024 preseason ADP board
  archive/2025/go/std_with_depth.csv 2025 preseason consensus rank (ESPN+Sleeper)
  engine/league-sim/data/weekly_{y}.parquet  actual weekly stat lines (nflverse)

Output: data/joined_{year}.csv - one row per note file with market rank,
actual season points (ESPN standard scoring, weeks 1-17), and positional
finish. Run with league-sim's venv (needs pandas + pyarrow):
  ../../../engine/league-sim/venv/bin/python prep_data.py
"""
import pandas as pd, os, re, unicodedata
from pathlib import Path

STUDY = Path(__file__).resolve().parent.parent
ROOT = STUDY.parent.parent  # research/reddit-notes-study -> repo root
DATA = STUDY / "data"

def norm(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    n = n.lower().replace(".", "").replace("'", "").replace("-", " ")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()

def season_points(year):
    w = pd.read_parquet(ROOT / f"engine/league-sim/data/weekly_{year}.parquet")
    w = w[w["week"] <= 17].copy()
    fg_pts = (3*(w.fg_made_0_19 + w.fg_made_20_29 + w.fg_made_30_39)
              + 4*w.fg_made_40_49 + 5*(w.fg_made_50_59 + w.fg_made_60_)
              + w.pat_made - w.fg_missed)
    w["pts"] = (0.04*w.passing_yards + 4*w.passing_tds - 2*w.passing_interceptions
                + 0.1*w.rushing_yards + 6*w.rushing_tds
                + 0.1*w.receiving_yards + 6*w.receiving_tds
                - 2*w.fumbles_lost_total
                + 2*(w.passing_2pt_conversions + w.rushing_2pt_conversions + w.receiving_2pt_conversions)
                + 6*w.special_teams_tds + fg_pts.fillna(0))
    g = (w.groupby(["player_display_name", "position"], as_index=False)
           .agg(total_pts=("pts", "sum"), games=("week", "nunique")))
    g["ppg"] = g.total_pts / g.games
    g = g.sort_values("total_pts", ascending=False)
    g["pos_finish"] = g.groupby("position")["total_pts"].rank(ascending=False, method="min")
    g["key"] = g.player_display_name.map(norm)
    g = g.sort_values("total_pts", ascending=False).drop_duplicates("key")
    return g

def market_2024():
    adr = pd.read_csv(ROOT / "archive/2024/ADR.csv")
    adr = adr.rename(columns={"Name": "player", "Pos": "pos", "ADP": "market_rank"})
    adr = adr[["player", "pos", "market_rank"]].dropna(subset=["player"])
    adr["key"] = adr.player.map(norm)
    return adr.drop_duplicates("key")

def market_2025():
    m = pd.read_csv(ROOT / "archive/2025/go/std_with_depth.csv")
    m = m.rename(columns={"Player": "player", "POS": "pos", "Rank": "market_rank"})
    m = m[["player", "pos", "market_rank"]]
    m["key"] = m.player.map(norm)
    return m.drop_duplicates("key")

ALIAS = {  # note-filename key -> nflverse display-name key
    "hollywood brown": "marquise brown",
    "chigoziem okonkwo": "chig okonkwo",
    "joshua palmer": "josh palmer",
    "kenneth gainwell": "kenny gainwell",
    "cameron ward": "cam ward",
    "keon colemand": "keon coleman",   # filename typo
    "mitch trubisky": "mitchell trubisky",
}

def build(year, notes_dir, market):
    files = sorted(f for f in os.listdir(notes_dir) if f.endswith(".md"))
    rows = []
    for f in files:
        name = f[:-3]
        key = ALIAS.get(norm(name), norm(name))
        rows.append({"file": str(notes_dir / f), "note_name": name, "key": key})
    n = pd.DataFrame(rows)
    acts = season_points(year)
    df = n.merge(market, on="key", how="left", suffixes=("", "_m"))
    df = df.merge(acts[["key", "position", "total_pts", "games", "ppg", "pos_finish"]],
                  on="key", how="left")
    df["year"] = year
    df.to_csv(DATA / f"joined_{year}.csv", index=False)
    print(f"{year}: {len(df)} note files | market match {df.market_rank.notna().sum()}"
          f" | actuals match {df.total_pts.notna().sum()}")
    print("  no stat line (DST/meta files or true zero-point busts):",
          ", ".join(df[df.total_pts.isna()].note_name.tolist()))

build(2024, ROOT / "archive/2024/analysis", market_2024())
build(2025, ROOT / "archive/2025/go/analysis", market_2025())
