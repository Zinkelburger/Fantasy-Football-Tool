"""Step 2: does note tone predict outcomes beyond the market rank?

Reads data/joined_{year}.csv (prep_data.py) and data/sentiment_scores.csv
(LLM scoring step, see scoring_prompt.md). Writes the full merged dataset
to data/final_dataset.csv and prints the statistics that back README.md:
  ../../../engine/league-sim/venv/bin/python analyze.py > ../results/correlation_output.txt

Core design: 'value' = positional market rank minus positional finish
rank, so value > 0 means the player BEAT his draft cost. Any real edge
in the notes must show up as corr(sentiment, value) > 0. p-values are
two-sided permutation tests (5000 shuffles, fixed seed).
"""
import pandas as pd, numpy as np
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
rng = np.random.default_rng(7)

TEAMS = {"Bills", "Quarterbacks", "Underdogs to Draft"}
TEAM_WORDS = ("Cardinals","Ravens","Bills","Bears","Bengals","Browns","Cowboys","Broncos",
    "Lions","Packers","Texans","Colts","Jaguars","Chiefs","Raiders","Chargers","Rams",
    "Dolphins","Vikings","Patriots","Saints","Giants","Jets","Eagles","Steelers","49ers",
    "Seahawks","Buccaneers","Titans","Commanders","Falcons","Panthers")

def is_meta(name):
    return name in TEAMS or any(name.endswith(w) or name == w for w in TEAM_WORDS)

# scores are keyed by (year, note_name): same-named files exist in both years
sc = pd.read_csv(DATA / "sentiment_scores.csv")

frames = []
for y in (2024, 2025):
    d = pd.read_csv(DATA / f"joined_{y}.csv")
    d = d[~d.note_name.map(is_meta)].copy()
    d = d.merge(sc[sc.year == y][["note_name", "s", "has_negative"]],
                on="note_name", how="left")
    frames.append(d)
df = pd.concat(frames, ignore_index=True)
print("scored:", df.s.notna().sum(), "/", len(df), "player-files")

df["position"] = df.position.fillna(df.pos.astype(str).str.extract(r"([A-Z]+)")[0])
df = df[df.position.isin(["QB", "RB", "WR", "TE", "K"])]

# players with a note + market rank but no stat line all season = true busts
df["total_pts"] = df.total_pts.fillna(0)
df["games"] = df.games.fillna(0)

m = df[df.market_rank.notna()].copy()
m["pos_mkt_rank"] = m.groupby(["year", "position"]).market_rank.rank(method="min")
m["pos_act_rank"] = m.groupby(["year", "position"]).total_pts.rank(ascending=False, method="min")
m["value"] = m.pos_mkt_rank - m.pos_act_rank        # + = beat the market
m["beat"] = (m.value > 0).astype(int)

def spear(a, b):
    x = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(x) < 8: return np.nan, np.nan, len(x)
    ra, rb = x.a.rank().values, x.b.rank().values
    r = np.corrcoef(ra, rb)[0, 1]
    null = np.array([np.corrcoef(rng.permutation(ra), rb)[0, 1] for _ in range(5000)])
    return r, (np.abs(null) >= abs(r)).mean(), len(x)

print("\n=== Sentiment distribution (glazing check) ===")
for y in (2024, 2025):
    d = df[df.year == y]
    counts = d.s.value_counts().reindex([-2, -1, 0, 1, 2], fill_value=0)
    n = d.s.notna().sum()
    print(f"{y}: n={n}  " + "  ".join(f"[{k:+d}] {v} ({v/n:.0%})" for k, v in counts.items())
          + f"  | has_negative: {d.has_negative.mean():.0%}")

print("\n=== Baseline: how good is the market alone? (pos mkt rank vs pos finish) ===")
for y in (2024, 2025):
    r, p, n = spear(m[m.year == y].pos_mkt_rank, m[m.year == y].pos_act_rank)
    print(f"{y}: spearman={r:.3f} (p={p:.4f}, n={n})")

print("\n=== Does sentiment predict finish at all? ===")
for y in (2024, 2025):
    r, p, n = spear(m[m.year == y].s, -m[m.year == y].pos_act_rank)
    print(f"{y}: sentiment vs finish: r={r:.3f} (p={p:.4f}, n={n})")

print("\n=== THE EDGE TEST: sentiment vs beating the market (value = mkt rank - finish rank) ===")
for y in (2024, 2025):
    d = m[m.year == y]
    r, p, n = spear(d.s, d.value)
    print(f"{y}: r={r:.3f} (p={p:.4f}, n={n})")
r, p, n = spear(m.s, m.value)
print(f"pooled: r={r:.3f} (p={p:.4f}, n={n})")

print("\n=== Mean outcome by sentiment bucket (pooled, market players) ===")
g = m.dropna(subset=["s"]).groupby("s").agg(n=("value", "size"), mean_value=("value", "mean"),
        med_value=("value", "median"), beat_rate=("beat", "mean"))
print(g.round(2).to_string())

print("\n=== Same, top-120 market only (where draft picks actually happen) ===")
t = m[m.market_rank <= 120]
for y in (2024, 2025):
    d = t[t.year == y]
    r, p, n = spear(d.s, d.value)
    print(f"{y}: r={r:.3f} (p={p:.4f}, n={n})")
g = t.dropna(subset=["s"]).groupby("s").agg(n=("value", "size"), mean_value=("value", "mean"), beat_rate=("beat", "mean"))
print(g.round(2).to_string())

print("\n=== PPG robustness (>=6 games, injury-insensitive) ===")
pp = m[m.games >= 6].copy()
pp["pos_ppg_rank"] = pp.groupby(["year", "position"]).ppg.rank(ascending=False, method="min")
pp["value_ppg"] = pp.pos_mkt_rank - pp.pos_ppg_rank
for y in (2024, 2025):
    d = pp[pp.year == y]
    r, p, n = spear(d.s, d.value_ppg)
    print(f"{y}: sentiment vs PPG-value: r={r:.3f} (p={p:.4f}, n={n})")

print("\n=== Is sentiment just tracking ADP? (sentiment vs market rank) ===")
for y in (2024, 2025):
    d = m[m.year == y]
    r, p, n = spear(d.s, -d.market_rank)
    print(f"{y}: r={r:.3f} (p={p:.4f}, n={n})")

print("\n=== has_negative flag: do 'no concerns mentioned' players do better? ===")
g = m.dropna(subset=["has_negative"]).groupby("has_negative").agg(
    n=("value", "size"), mean_value=("value", "mean"), beat_rate=("beat", "mean"))
print(g.round(2).to_string())

m2 = m.dropna(subset=["s"])
cols = ["year", "note_name", "position", "market_rank", "total_pts", "value"]
print("\n=== Where strong bullish notes (+2) landed ===")
hits = m2[m2.s == 2].sort_values("value", ascending=False)
print(hits[cols].head(8).to_string(index=False))
print("...worst:")
print(hits[cols].tail(8).to_string(index=False))
print("\n=== Where bearish notes (<=-1) landed ===")
fades = m2[m2.s <= -1].sort_values("value")
print(fades[cols].head(10).to_string(index=False))
print("...and bearish calls that were wrong (player smashed):")
print(fades[cols].tail(5).to_string(index=False))

m.to_csv(DATA / "final_dataset.csv", index=False)
