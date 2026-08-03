#!/usr/bin/env python3
"""Season checklist step 1: turn a FantasyPros overall-ADP export into

  1. combined_with_depth.csv  — input for the scraper/matcher (this dir)
  2. ../data/ranks/{std,0.5_ppr,ppr}_with_depth.csv — board CSVs for the
     draft tool (columns: Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank)

FantasyPros 2026 format: Rank,"Player (Bye)",POS,Sleeper,RTSports,AVG,Real-Time
The player cell is "Jahmyr Gibbs   DET (6)"; free agents are a bare name.
Depth (RB1, WR2...) = ADP order within (team, position).

Usage:
    python build_player_csv.py FantasyPros_2026_Overall_ADP_Rankings.csv
    python build_player_csv.py FP.csv --no-board   # scraper CSV only
"""

import argparse
import glob
import pathlib
import re

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
BOARD_DIR = HERE.parent / "data" / "ranks"
OUT = HERE / "combined_with_depth.csv"

# board file -> the JuiceBoxOne scoring-format label used in its filename
BOARD_FILES = {
    "std_with_depth.csv": "Standard",
    "0.5_ppr_with_depth.csv": "Half PPR",
    "ppr_with_depth.csv": "PPR",
}

SUFFIX_RE = re.compile(r"\s+(?:Jr\.|Sr\.|II|III|IV|V)$", re.IGNORECASE)
PLAYER_RE = re.compile(r"^(?P<name>.+?)\s{2,}(?P<team>[A-Z]{2,3})\s+\((?P<bye>\d+)\)$")


def clean_name(name: str) -> str:
    return SUFFIX_RE.sub("", str(name)).strip()


def parse_players(df: pd.DataFrame, player_col: str):
    names, teams, byes = [], [], []
    for raw in df[player_col]:
        m = PLAYER_RE.match(str(raw).strip())
        if m:
            names.append(clean_name(m.group("name")))
            teams.append(m.group("team"))
            byes.append(m.group("bye"))
        else:  # free agent: bare name, no team/bye
            names.append(clean_name(raw))
            teams.append("")
            byes.append("")
    return names, teams, byes


def juicebox_ranks(directory: str) -> dict:
    """Read JuiceBoxOne per-platform ranking CSVs -> {(site, format): {name: rank}}.

    Filenames look like "...Draft Rankings - ESPN Half PPR.csv"; the rank column
    is 'ESPN' or 'Sleeper ADP' depending on the platform.
    """
    found = {}
    for path in glob.glob(str(pathlib.Path(directory) / "*.csv")):
        # handles both the hand-downloaded "... - ESPN Half PPR.csv" and the
        # fetch_juicebox.py "juicebox_rankings_ESPN_Half_PPR.csv" naming
        stem = pathlib.Path(path).stem.replace("_", " ")
        site = "ESPN" if "ESPN" in stem else "Sleeper" if "Sleeper" in stem else None
        if not site:
            continue
        fmt = next((f for f in ("Half PPR", "PPR", "Standard") if stem.endswith(f)), None)
        if not fmt:
            continue
        df = pd.read_csv(path)
        col = next((c for c in df.columns if c.strip() in (site, f"{site} ADP")), None)
        if col is None or "Name" not in df.columns:
            continue
        ranks = {}
        for _, row in df.iterrows():
            val = pd.to_numeric(row[col], errors="coerce")
            if pd.notna(row["Name"]) and pd.notna(val):
                ranks[clean_name(row["Name"]).lower()] = int(val)
        found[(site, fmt)] = ranks
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fantasypros_csv")
    ap.add_argument("--no-board", action="store_true", help="skip the board CSVs")
    ap.add_argument("--juicebox", metavar="DIR",
                    help="directory of JuiceBoxOne per-platform ranking CSVs "
                         "(supplies the ESPN_Rank/Sleeper_Rank comparison columns)")
    args = ap.parse_args()

    df = pd.read_csv(args.fantasypros_csv)
    player_col = next(c for c in df.columns if c.startswith("Player"))
    names, teams, byes = parse_players(df, player_col)

    out = pd.DataFrame({
        "Player": names,
        "Team": teams,
        "Bye": byes,
        "POS": df["POS"].fillna("UNK"),
        "Average_ADP": pd.to_numeric(df["AVG"], errors="coerce"),
        # site ranks: the 2026 export carries Sleeper but no ESPN column
        "Sleeper_Rank": pd.to_numeric(df.get("Sleeper"), errors="coerce"),
    })
    out = (out.dropna(subset=["Average_ADP"])
              .sort_values("Average_ADP")
              .reset_index(drop=True))

    out["Base_POS"] = out["POS"].str.replace(r"\d+", "", regex=True)
    out["Depth_Rank"] = out.groupby(["Team", "Base_POS"]).cumcount() + 1
    out.loc[out["Team"] == "", "Depth_Rank"] = 0
    out["Depth_Rank"] = out["Depth_Rank"].astype(int)
    out["Depth"] = out["Base_POS"] + out["Depth_Rank"].astype(str)

    # carry nicknames over from the previous season's file
    nicknames = {}
    if OUT.exists():
        prev = pd.read_csv(OUT)
        for _, row in prev.iterrows():
            nick = row.get("Nickname")
            if isinstance(nick, str) and nick.strip():
                nicknames[clean_name(row["Player"]).lower()] = nick.strip()
    out["Nickname"] = [nicknames.get(n.lower(), "") for n in out["Player"]]

    scraper_cols = ["Player", "Team", "Bye", "POS", "Average_ADP",
                    "Depth", "Depth_Rank", "Nickname"]
    out[scraper_cols].to_csv(OUT, index=False)
    print(f"wrote {len(out)} players to {OUT}")
    print(f"  free agents (no team/bye): {(out['Team'] == '').sum()}")
    print(f"  nicknames carried over: {(out['Nickname'] != '').sum()}")

    if args.no_board:
        return

    # Board CSVs: skill positions only, matching the 2025 go/ files (no K/DST).
    board = out[~out["Base_POS"].isin(["K", "DST"])].copy()
    board.insert(0, "Rank", range(1, len(board) + 1))
    board["ESPN_Rank"] = ""  # filled from JuiceBoxOne below when available
    board["Sleeper_Rank"] = board["Sleeper_Rank"].apply(
        lambda v: "" if pd.isna(v) else str(int(v)))
    board["POS"] = board["Base_POS"]
    board_cols = ["Rank", "Player", "Team", "Bye", "POS", "ESPN_Rank", "Sleeper_Rank"]

    jb = juicebox_ranks(args.juicebox) if args.juicebox else {}
    for fname, fmt_label in BOARD_FILES.items():
        b = board.copy()
        for site, col in (("ESPN", "ESPN_Rank"), ("Sleeper", "Sleeper_Rank")):
            ranks = jb.get((site, fmt_label))
            if ranks:
                b[col] = [str(ranks.get(clean_name(n).lower(), "")) for n in b["Player"]]
        b[board_cols].to_csv(BOARD_DIR / fname, index=False)

    print(f"wrote {len(board)} players to {len(BOARD_FILES)} board CSVs in {BOARD_DIR}")
    if jb:
        for (site, fmt), ranks in sorted(jb.items()):
            print(f"  merged {len(ranks)} {site} ranks for {fmt}")
    else:
        print("  NOTE: all three formats are identical and ESPN_Rank is blank.")
        print("  Pass --juicebox <dir> with the JuiceBoxOne per-platform ranking CSVs")
        print("  to restore the ESPN/Sleeper comparison columns (see README).")


if __name__ == "__main__":
    main()
