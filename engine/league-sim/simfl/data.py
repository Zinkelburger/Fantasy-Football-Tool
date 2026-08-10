"""Data acquisition and caching.

Sources:
- ADP 2020-2024: FantasyFootballCalculator API (12-team standard),
  which includes per-player pick stdev from real drafts.
- ADP 2025: FantasyPros standard consensus ADP, recovered from a
  Wayback Machine snapshot dated 2025-09-03 (FFC purged its 2025 data).
  Stdev is imputed from a linear fit of stdev-vs-ADP on the FFC years.
- Weekly stats & player metadata: nflreadpy (nflverse).

Everything is cached under league-sim/data/ so repeat runs are offline.
"""

import json
import re
import urllib.request
from pathlib import Path

import polars as pl

from .config import POSITIONS, ScoringConfig
from .scoring import STAT_COLS, add_fantasy_points

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

FFC_URL = "https://fantasyfootballcalculator.com/api/v1/adp/{fmt}?teams=12&year={year}"
FP_2025_WAYBACK = ("http://web.archive.org/web/20250903050817/"
                   "https://www.fantasypros.com/nfl/adp/overall.php")

# Points-per-reception -> the draft board real drafters used in that
# format. A PPR season simulated off a standard board measures the wrong
# thing: half the story of PPR is that the room itself reprices
# receivers, so the board has to move with the scoring.
ADP_FORMATS = {0.0: "standard", 0.5: "half-ppr", 1.0: "ppr"}

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?$")

# ADP-site name -> nflverse name (applied post-normalization).
ALIASES = {
    "hollywood brown": "marquise brown",
    "joshua palmer": "josh palmer",
    "michael badgley": "mike badgley",
    "kenneth gainwell": "kenny gainwell",
}


def norm_name(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"[.'\-]", "", n)
    n = _SUFFIXES.sub("", n).strip()
    return ALIASES.get(n, n)


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "league-sim/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------- ADP

def _fetch_ffc(year: int, fmt: str = "standard") -> list[dict]:
    raw = json.loads(_get(FFC_URL.format(year=year, fmt=fmt)))
    out = []
    for p in raw["players"]:
        pos = {"PK": "K"}.get(p["position"], p["position"])
        if pos not in POSITIONS:
            continue  # drops DEF
        out.append({
            "name": p["name"], "pos": pos, "team": p["team"],
            "adp": float(p["adp"]), "stdev": float(p["stdev"]),
            "source": f"ffc-{fmt}",
        })
    return out


def _fetch_fp_2025() -> list[dict]:
    """Parse the archived FantasyPros standard-ADP table (top ~330)."""
    html = _get(FP_2025_WAYBACK)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for row in rows:
        m = re.search(r'fp-player-name="([^"]+)"', row)
        if not m:
            continue
        name = m.group(1)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        # Layout: rank | player | POS# | per-source ADPs ... | AVG
        posm = None
        for td in tds:
            posm = posm or re.fullmatch(r"([A-Z]{1,3})\d+", td.strip())
        if not posm:
            continue
        pos = {"DST": None, "PK": "K"}.get(posm.group(1), posm.group(1))
        if pos not in POSITIONS:
            continue
        team_m = re.search(r"<small>([A-Z]{2,3})</small>", row)
        # Layout ends: ... | AVG | rank-change badge. AVG is tds[-2]; fall
        # back to the last decimal-looking cell if the layout shifts.
        avg = None
        for td in [tds[-2]] + tds[::-1]:
            txt = re.sub(r"<[^>]+>", "", td).strip()
            if re.fullmatch(r"\d+(\.\d+)?", txt):
                avg = float(txt)
                break
        if avg is None:
            continue
        out.append({
            "name": name, "pos": pos,
            "team": team_m.group(1) if team_m else "",
            "adp": avg, "stdev": None, "source": "fantasypros-wayback",
        })
    out.sort(key=lambda p: p["adp"])
    return out


def _impute_stdev(players: list[dict], ffc_years: list[list[dict]]) -> None:
    """Fill missing stdev using a linear fit of stdev vs ADP on FFC data."""
    xs, ys = [], []
    for yr in ffc_years:
        for p in yr:
            xs.append(p["adp"])
            ys.append(p["stdev"])
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = my - b * mx
    for p in players:
        if p["stdev"] is None:
            p["stdev"] = round(max(0.5, a + b * p["adp"]), 2)


def load_adp(year: int, fmt: str | None = None) -> list[dict]:
    """The preseason draft board for one season.

    `fmt` is None for the historical default: FantasyFootballCalculator
    standard, except 2025, which comes from an archived FantasyPros
    board (~330 players deep, where FFC's 2025 standard is only ~150).
    Every published standard-scoring finding rests on that board, so it
    stays the default.

    Pass an explicit FFC format ("standard", "half-ppr", "ppr") to get a
    board straight from FFC. The format sweep uses those for all three
    arms, because comparing formats needs one board source across them —
    a deeper board in one arm changes what the late rounds even see.
    """
    if fmt is None:
        cache = DATA_DIR / f"adp_{year}.json"
        if cache.exists():
            return json.loads(cache.read_text())
        if year == 2025:
            players = _fetch_fp_2025()
            ffc = [load_adp(y) for y in range(2020, 2025)]
            _impute_stdev(players, ffc)
        else:
            players = _fetch_ffc(year)
        cache.write_text(json.dumps(players, indent=1))
        return players

    cache = DATA_DIR / f"adp_{fmt}_{year}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    players = _fetch_ffc(year, fmt)
    cache.write_text(json.dumps(players, indent=1))
    return players


# ------------------------------------------------------- weekly stats

KEEP_COLS = ["player_id", "player_display_name", "position", "team",
             "season", "week"] + STAT_COLS


def load_weekly(year: int, sc: ScoringConfig) -> pl.DataFrame:
    """Regular-season weekly rows with an 'fpts' column, cached raw."""
    cache = DATA_DIR / f"weekly_{year}.parquet"
    if cache.exists():
        df = pl.read_parquet(cache)
    else:
        import nflreadpy as nfl
        df = nfl.load_player_stats([year])
        df = df.filter(pl.col("season_type") == "REG")
        # Keep offense positions, plus anyone with offensive touches —
        # two-way players (e.g. Travis Hunter, listed as CB) draft as WRs.
        df = df.filter(
            pl.col("position").is_in(list(POSITIONS))
            | (pl.col("carries").fill_null(0) + pl.col("targets").fill_null(0)
               + pl.col("attempts").fill_null(0) + pl.col("receptions").fill_null(0) > 0))
        df = df.select([c for c in KEEP_COLS if c in df.columns])
        df.write_parquet(cache)
    return add_fantasy_points(df, sc)


def load_schedule_byes(year: int) -> dict[str, int]:
    """team -> bye week (regular season)."""
    cache = DATA_DIR / f"byes_{year}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    import nflreadpy as nfl
    sched = nfl.load_schedules([year]).filter(pl.col("game_type") == "REG")
    weeks = sched.select("week").unique().to_series().to_list()
    teams = set(sched["home_team"].to_list()) | set(sched["away_team"].to_list())
    playing = {w: set() for w in weeks}
    for r in sched.iter_rows(named=True):
        playing[r["week"]].update([r["home_team"], r["away_team"]])
    byes = {}
    for t in teams:
        off = [w for w in sorted(weeks) if t not in playing[w]]
        byes[t] = off[0] if off else 0
    cache.write_text(json.dumps(byes))
    return byes


def load_injury_reports(year: int) -> dict[str, dict[int, str]]:
    """gsis player_id -> {week: Friday game status} for one season,
    statuses Questionable/Doubtful/Out only. Real report data, so the
    sim's managers read the same news the family did."""
    inj = (pl.read_parquet(DATA_DIR / "injuries_2017_2025.parquet")
           .filter(pl.col("season") == year,
                   pl.col("report_status").is_in(["Questionable", "Doubtful", "Out"]))
           .select("gsis_id", pl.col("week").cast(pl.Int64), "report_status"))
    out: dict[str, dict[int, str]] = {}
    for r in inj.iter_rows(named=True):
        if r["gsis_id"]:
            out.setdefault(r["gsis_id"], {})[r["week"]] = r["report_status"]
    return out


def load_expected_points(year: int, ppr: float = 0.0) -> dict[str, dict[int, float]]:
    """gsis player_id -> {week: expected points} from nflverse
    ff_opportunity, rescored under league rules (pass 1/25 + 4TD − 2INT,
    rush/rec 1/10 + 6TD, 2pt = 2). Opportunity-based: what the week's
    usage was worth, before the TD/long-play dice landed.

    `ppr` adds the reception term. It has to be here and not only in
    scoring.py: expected points drive the lineup and waiver projections,
    and in a PPR league a 90-catch possession receiver's usage is worth
    far more than the standard-scored version of the same week says."""
    df = (pl.read_parquet(DATA_DIR / "ff_opportunity_2017_2025.parquet")
          .filter(pl.col("season") == str(year),
                  pl.col("position").is_in(["QB", "RB", "WR", "TE"])))
    ep = (pl.col("pass_yards_gained_exp") / 25
          + pl.col("pass_touchdown_exp") * 4
          + pl.col("pass_interception_exp") * -2
          + pl.col("rush_yards_gained_exp") / 10
          + pl.col("rush_touchdown_exp") * 6
          + pl.col("rec_yards_gained_exp") / 10
          + pl.col("rec_touchdown_exp") * 6
          + pl.col("receptions_exp").fill_null(0.0) * ppr
          + (pl.col("pass_two_point_conv_exp") + pl.col("rec_two_point_conv_exp")
             + pl.col("rush_two_point_conv_exp")) * 2)
    df = df.with_columns(ep.fill_null(0.0).alias("ep"))
    out: dict[str, dict[int, float]] = {}
    for pid, week, val in df.select("player_id", "week", "ep").iter_rows():
        if pid:
            out.setdefault(pid, {})[int(week)] = val
    return out


def load_rookie_years() -> dict[str, int]:
    """gsis player_id -> entry year."""
    cache = DATA_DIR / "rookie_years.json"
    if cache.exists():
        return json.loads(cache.read_text())
    import nflreadpy as nfl
    players = nfl.load_players()
    col = next(c for c in ("entry_year", "rookie_year", "draft_year")
               if c in players.columns)
    out = {r["gsis_id"]: r[col]
           for r in players.select(["gsis_id", col]).drop_nulls().iter_rows(named=True)}
    cache.write_text(json.dumps(out))
    return out


def fetch_all(years: list[int], sc: ScoringConfig) -> None:
    """Warm every cache (network needed only the first time)."""
    for y in years:
        load_adp(y)
        load_weekly(y, sc)
        load_weekly(y - 1, sc)  # previous season, for fallback draft ranks
        load_schedule_byes(y)
    load_rookie_years()
