"""Score the pasted FantasyPoints WR/CB matchup table (wayback snapshot
2025-10-02, previewing a 14-game slate) against actual results.

Columns kept per WR: route%, TGT/RR, FP/RR (their skill baseline),
MATCHUP (pure matchup quality), ADVANTAGE (skill+matchup blend).
Test: do MATCHUP / ADVANTAGE correlate with that week's actual points,
and does MATCHUP add anything beyond the player's own baseline?
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/anbernal/Documents/Fantasy-Football-Tool/league-sim")
sys.path.insert(0, "/home/anbernal/Documents/Fantasy-Football-Tool/league-sim/analysis")
from player_model import league_pts

T = {"ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU"}
ROWS = [
    ("ARZ","Marvin Harrison",87.6,20.2,0.34,0.11,1.08),
    ("ARZ","Michael Wilson",79.7,11.4,0.18,0.10,0.83),
    ("ARZ","Greg Dortch",36.5,15.7,0.31,0.17,1.08),
    ("BLT","Rashod Bateman",74.7,16.1,0.41,-0.09,1.09),
    ("BLT","Zay Flowers",82.8,26.1,0.49,0.02,1.27),
    ("BLT","Tylan Wallace",28.6,12.4,0.32,0.08,1.03),
    ("BUF","Keon Coleman",71.4,20.7,0.39,-0.21,0.99),
    ("BUF","Josh Palmer",66.7,17.7,0.29,-0.14,0.88),
    ("BUF","Khalil Shakir",73.2,25.4,0.46,-0.06,1.20),
    ("CAR","Tetairoa McMillan",89.0,22.6,0.33,0.20,1.10),
    ("CAR","Brycen Tremayne",29.7,15.9,0.33,0.10,1.06),
    ("CAR","Hunter Renfrow",69.5,17.5,0.32,-0.01,0.99),
    ("CIN","Ja'Marr Chase",96.7,27.3,0.57,-0.05,1.36),
    ("CIN","Tee Higgins",81.9,20.1,0.42,-0.06,1.12),
    ("CIN","Andrei Iosivas",70.0,9.9,0.19,-0.13,0.73),
    ("CLV","Jamari Thrash",21.6,9.3,0.33,0.01,1.01),
    ("CLV","Jerry Jeudy",88.2,24.5,0.32,-0.07,0.96),
    ("CLV","Isaiah Bond",46.3,16.0,0.32,0.02,1.00),
    ("DAL","George Pickens",89.8,19.9,0.37,0.06,1.10),
    ("DAL","Jalen Tolbert",65.8,15.1,0.26,-0.05,0.89),
    ("DAL","KaVontae Turpin",37.7,18.0,0.40,-0.13,1.05),
    ("DEN","Courtland Sutton",77.7,26.4,0.57,-0.09,1.34),
    ("DEN","Marvin Mims",32.7,26.6,0.63,-0.05,1.45),
    ("DEN","Troy Franklin",51.6,20.2,0.32,-0.09,0.95),
    ("DET","Jameson Williams",83.4,19.9,0.36,0.01,1.07),
    ("DET","Kalif Raymond",36.5,18.8,0.39,-0.04,1.08),
    ("DET","Amon-Ra St. Brown",86.3,26.0,0.61,-0.02,1.45),
    ("HST","Nico Collins",69.8,28.7,0.57,-0.10,1.34),
    ("HST","Xavier Hutchinson",55.0,9.9,0.13,-0.13,0.63),
    ("HST","Christian Kirk",71.8,23.1,0.32,0.02,1.01),
    ("IND","Alec Pierce",75.4,17.1,0.37,-0.10,1.02),
    ("IND","Michael Pittman",84.9,25.7,0.47,-0.13,1.16),
    ("IND","Josh Downs",68.8,27.9,0.47,-0.18,1.15),
    ("JAX","Brian Thomas",84.9,25.9,0.48,-0.13,1.17),
    ("JAX","Parker Washington",70.8,18.8,0.32,-0.16,0.92),
    ("JAX","Travis Hunter",63.2,21.9,0.32,0.15,1.07),
    ("KC","Xavier Worthy",64.9,22.3,0.33,-0.10,0.97),
    ("KC","Marquise Brown",63.6,28.3,0.42,-0.09,1.11),
    ("KC","JuJu Smith-Schuster",52.2,12.8,0.27,-0.14,0.84),
    ("LA","Davante Adams",88.6,28.9,0.57,0.12,1.45),
    ("LA","Puka Nacua",78.7,39.8,0.76,-0.00,1.68),
    ("LA","Jordan Whittington",42.3,19.2,0.35,-0.02,1.04),
    ("LAC","Quentin Johnston",80.2,25.0,0.46,-0.25,1.09),
    ("LAC","Keenan Allen",81.7,24.2,0.48,-0.11,1.19),
    ("LAC","Ladd McConkey",88.2,21.4,0.41,0.04,1.16),
    ("LV","Tre Tucker",91.7,16.7,0.47,0.23,1.33),
    ("LV","Dont'e Thornton",68.1,14.3,0.25,0.14,0.96),
    ("LV","Jakobi Meyers",93.0,23.4,0.38,0.09,1.14),
    ("MIA","Jaylen Waddle",74.8,20.5,0.39,-0.10,1.05),
    ("MIA","Nick Westbrook-Ikhine",65.4,14.2,0.28,-0.14,0.87),
    ("MIA","Malik Washington",44.6,17.4,0.21,-0.13,0.76),
    ("MIN","Justin Jefferson",93.2,25.4,0.54,0.29,1.48),
    ("MIN","Jordan Addison",86.2,19.7,0.43,0.22,1.28),
    ("MIN","Jalen Nailor",59.8,12.0,0.23,0.14,0.93),
    ("NE","Kayshon Boutte",79.5,16.7,0.32,0.19,1.08),
    ("NE","Mack Hollins",53.9,13.7,0.32,0.18,1.09),
    ("NE","Stefon Diggs",67.3,26.0,0.47,0.09,1.28),
    ("NO","Chris Olave",69.7,26.0,0.32,-0.08,0.96),
    ("NO","Rashid Shaheed",82.4,19.0,0.30,-0.04,0.94),
    ("NO","Brandin Cooks",70.9,17.7,0.25,-0.05,0.87),
    ("NYG","Darius Slayton",71.6,10.1,0.25,-0.04,0.87),
    ("NYG","Jalin Hyatt",23.7,9.9,0.15,-0.03,0.71),
    ("NYG","Wan'Dale Robinson",83.0,22.7,0.40,-0.06,1.10),
    ("NYJ","Garrett Wilson",93.6,23.8,0.46,0.26,1.34),
    ("NYJ","Josh Reynolds",59.3,12.3,0.18,0.31,0.93),
    ("NYJ","Arian Smith",52.2,5.6,0.16,0.19,0.85),
    ("PHI","Jahan Dotson",70.1,8.9,0.14,0.02,0.72),
    ("PHI","A.J. Brown",90.3,26.8,0.50,-0.17,1.19),
    ("PHI","DeVonta Smith",92.3,21.0,0.51,-0.11,1.24),
    ("SEA","Jaxon Smith-Njigba",84.6,28.1,0.59,0.03,1.42),
    ("SEA","Tory Horton",51.4,17.5,0.43,0.04,1.18),
    ("SEA","Cooper Kupp",78.3,25.2,0.47,-0.02,1.22),
    ("SF","Jauan Jennings",73.3,26.0,0.42,-0.39,0.97),
    ("SF","Demarcus Robinson",69.7,9.9,0.20,-0.39,0.61),
    ("SF","Kendrick Bourne",59.8,15.5,0.25,-0.40,0.69),
    ("TB","Emeka Egbuka",84.3,23.1,0.52,-0.10,1.26),
    ("TB","Chris Godwin",81.4,27.1,0.56,-0.10,1.31),
    ("TB","Sterling Shepard",59.6,16.2,0.24,-0.09,0.83),
    ("TEN","Elic Ayomanor",68.7,22.3,0.38,-0.01,1.08),
    ("TEN","Calvin Ridley",79.1,21.7,0.33,-0.02,1.00),
    ("TEN","Tyler Lockett",71.8,10.2,0.16,-0.07,0.72),
    ("WAS","Chris Moore",45.6,12.2,0.28,-0.02,0.92),
    ("WAS","Jaylin Lane",39.4,17.9,0.25,-0.27,0.76),
    ("WAS","Deebo Samuel",78.8,20.3,0.36,-0.28,0.92),
]

df = pd.DataFrame(ROWS, columns=["team", "name", "route", "tgt_rr",
                                 "fp_rr", "matchup", "advantage"])
df["team"] = df.team.map(lambda t: T.get(t, t))

# which 2025 week is this slate?
g = pd.read_csv("/home/anbernal/Documents/Fantasy-Football-Tool/league-sim"
                "/data/market/games.csv")
g = g[(g.season == 2025) & (g.game_type == "REG")]
pairs = {frozenset(p) for p in
         zip(df.team.unique(), df.team.unique())}  # placeholder
slate = {frozenset({r.home_team, r.away_team}): r.week
         for r in g.itertuples()}
want = [frozenset(x) for x in
        [("ARI","TEN"),("BAL","HOU"),("BUF","NE"),("CAR","MIA"),
         ("CIN","DET"),("CLE","MIN"),("DAL","NYJ"),("DEN","PHI"),
         ("IND","LV"),("JAX","KC"),("LA","SF"),("LAC","WAS"),
         ("NO","NYG"),("SEA","TB")]]
weeks = [slate.get(w) for w in want]
from collections import Counter
week = Counter(w for w in weeks if w).most_common(1)[0][0]
print(f"slate identified as 2025 week {week} "
      f"({sum(1 for w in weeks if w == week)}/14 games match)")

# actual points that week
w = pd.read_parquet("/home/anbernal/Documents/Fantasy-Football-Tool/"
                    "league-sim/data/weekly_2025.parquet")
w = w[(w.week == week) & (w.position == "WR")].copy()
w["pts"] = league_pts(w)


def norm(s):
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    for suf in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s.strip()


w["key"] = w.player_display_name.map(norm)
df["key"] = df.name.map(norm)
merged = df.merge(w[["key", "team", "pts"]], on=["key", "team"],
                  how="left")
# fallback: match by key only (team code drift)
miss = merged.pts.isna()
fb = df[miss.values].merge(w[["key", "pts"]], on="key", how="left")
merged.loc[miss, "pts"] = fb.pts.values
print(f"matched {merged.pts.notna().sum()}/{len(merged)} WRs "
      f"(unmatched = inactive that week)")
d = merged.dropna(subset=["pts"])


def spear(a, b):
    return np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1]


print(f"\nn = {len(d)}   (detection floor at this n: |r| ~ 0.21)")
print(f"{'predictor':12s} {'pearson':>8s} {'spearman':>9s}")
for col in ("matchup", "advantage", "fp_rr", "tgt_rr", "route"):
    print(f"{col:12s} {np.corrcoef(d[col], d.pts)[0,1]:8.3f} "
          f"{spear(d[col], d.pts):9.3f}")

# does MATCHUP add anything beyond the player's own baseline?
X = np.column_stack([np.ones(len(d)), d.fp_rr, d.tgt_rr, d.route])
Xm = np.column_stack([X, d.matchup])
for label, Xd in (("baseline (fp_rr+tgt_rr+route)", X),
                  ("+ matchup", Xm)):
    beta, res, *_ = np.linalg.lstsq(Xd, d.pts.values, rcond=None)
    pred = Xd @ beta
    r2 = 1 - ((d.pts.values - pred) ** 2).sum() / \
        ((d.pts.values - d.pts.mean()) ** 2).sum()
    print(f"{label:32s} R2 = {r2:.3f}"
          + (f"   matchup coef = {beta[-1]:+.1f} pts per unit"
             if Xd is Xm else ""))

# top-vs-bottom matchup quartile, the practical read
q1 = d[d.matchup <= d.matchup.quantile(0.25)]
q4 = d[d.matchup >= d.matchup.quantile(0.75)]
print(f"\nworst-matchup quartile actual pts: {q1.pts.mean():.1f}   "
      f"best-matchup quartile: {q4.pts.mean():.1f}")
