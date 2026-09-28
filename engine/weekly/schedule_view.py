"""Schedule, results, byes and implied totals from saved files. No network.

Implied totals come from, in order: the weekly lines file (posted game
lines), then the nflverse schedule's spread/total when it has one, then
the preseason season-average implied points per team saved in August
(engine/league-sim/data/market/implied_2026.csv). Each value is labelled
with its source; a preseason average is a team-strength prior, not a
game line, and never substitutes for one in a published ranking.
"""
from __future__ import annotations

import csv

from common import CACHE, DATA, ROOT, TEAMS, norm_team

PRESEASON = ROOT / "engine" / "league-sim" / "data" / "market"


def _read(path):
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def games(season: int) -> list[dict]:
    import polars as pl
    p = CACHE / f"schedules_{season}.parquet"
    if not p.exists():
        return []
    return (pl.read_parquet(p).filter(pl.col("game_type") == "REG")
            .sort("week", "gameday", "gametime").to_dicts())


def preseason_implied(season: int) -> dict[str, dict]:
    """team -> {imp_ppg, imp_opp_ppg} from the August market snapshot."""
    rows = _read(PRESEASON / f"implied_{season}.csv")
    by_nick = {nick.lower(): abbr for abbr, nick in TEAMS.items()}
    out = {}
    for r in rows:
        nick = r["team"].split()[-1].lower()
        abbr = by_nick.get(nick)
        if abbr:
            out[abbr] = {"imp_ppg": float(r["imp_ppg"]), "imp_opp_ppg": float(r["imp_opp_ppg"])}
    return out


def _lines(season: int) -> dict[tuple[int, str], dict]:
    return {(int(r["week"]), r["team"]): r for r in _read(DATA / f"lines_{season}.csv")}


def implied(season: int, week: int, team: str, opp: str, home: bool, game: dict | None,
            lines=None, pre=None) -> tuple[float | None, float | None, str]:
    """(own implied, opponent implied, source label)."""
    lines = _lines(season) if lines is None else lines
    ln = lines.get((week, team))
    if ln and ln.get("imp_own") not in ("", None):
        return float(ln["imp_own"]), float(ln["imp_opp"]), "line"
    if game and game.get("spread_line") is not None and game.get("total_line") is not None:
        # nflverse spread_line is the home margin.
        margin = game["spread_line"] if home else -game["spread_line"]
        own = (game["total_line"] + margin) / 2
        return round(own, 1), round(game["total_line"] - own, 1), "nflverse line"
    pre = preseason_implied(season) if pre is None else pre
    if team in pre and opp in pre:
        # Average of own offence and opponent defence, both season-long priors.
        own = (pre[team]["imp_ppg"] + pre[opp]["imp_opp_ppg"]) / 2
        against = (pre[opp]["imp_ppg"] + pre[team]["imp_opp_ppg"]) / 2
        return round(own, 1), round(against, 1), "preseason prior"
    return None, None, "none"


def team_weeks(season: int, team: str, first: int = 1, last: int = 18) -> list[dict]:
    """One row per week for a team, byes included."""
    team = norm_team(team)
    sched = games(season)
    lines, pre = _lines(season), preseason_implied(season)
    out = []
    for w in range(first, last + 1):
        g = next((g for g in sched if g["week"] == w and team in (g["home_team"], g["away_team"])), None)
        if g is None:
            if any(x["week"] == w for x in sched):
                out.append({"week": w, "bye": True})
            continue
        home = g["home_team"] == team
        opp = g["away_team"] if home else g["home_team"]
        own, against, src = implied(season, w, team, opp, home, g, lines, pre)
        scored = g["home_score"] if home else g["away_score"]
        allowed = g["away_score"] if home else g["home_score"]
        out.append({"week": w, "bye": False, "opp": opp, "home": home,
                    "gameday": g["gameday"], "weekday": g["weekday"], "gametime": g["gametime"],
                    "roof": g.get("roof"), "stadium": g.get("stadium"),
                    "score": None if scored is None else (scored, allowed),
                    "imp_own": own, "imp_opp": against, "imp_source": src})
    return out


def team_text(season: int, team: str, first: int, last: int) -> str:
    rows = team_weeks(season, team, first, last)
    if not rows:
        return f"no {season} schedule cached for {team}"
    t = norm_team(team)
    out = [f"{t} {season} schedule, weeks {first}-{last} (times ET; implied = expected points)"]
    for r in rows:
        if r["bye"]:
            out.append(f"  wk{r['week']:>2}  BYE")
            continue
        res = ""
        if r["score"]:
            a, b = r["score"]
            res = f"  {'W' if a > b else 'L' if a < b else 'T'} {a}-{b}"
        imp = (f"  implied {r['imp_own']:.1f}-{r['imp_opp']:.1f} ({r['imp_source']})"
               if r["imp_own"] is not None else "")
        out.append(f"  wk{r['week']:>2}  {'vs' if r['home'] else '@ '} {r['opp']:3}  "
                   f"{r['weekday'][:3]} {r['gameday']} {r['gametime']}  {r['roof'] or ''}{res}{imp}")
    if any(r.get("imp_source") == "preseason prior" for r in rows):
        out.append("  preseason prior = August season-average implied points (team strength), not a game line")
    return "\n".join(out)


def week_text(season: int, week: int) -> str:
    sched = [g for g in games(season) if g["week"] == week]
    if not sched:
        return f"no {season} week {week} games cached"
    out = [f"{season} week {week} slate (times ET)"]
    for g in sched:
        score = (f"  {g['away_team']} {g['away_score']} - {g['home_team']} {g['home_score']}"
                 if g["home_score"] is not None else "")
        out.append(f"  {g['away_team']:3} @ {g['home_team']:3}  {g['weekday'][:3]} {g['gameday']} "
                   f"{g['gametime']}  {g.get('roof') or ''}{score}")
    playing = {g["home_team"] for g in sched} | {g["away_team"] for g in sched}
    byes = sorted(set(TEAMS) - playing)
    if byes:
        out.append("  bye: " + ", ".join(byes))
    return "\n".join(out)


def week_progress(season: int, week: int) -> tuple[int, int, list[dict]]:
    """(final games, scheduled games, unplayed games) for one week."""
    sched = [g for g in games(season) if g["week"] == week]
    left = [g for g in sched if g["home_score"] is None]
    return len(sched) - len(left), len(sched), left


def completed_weeks(season: int) -> list[int]:
    """Weeks whose every scheduled game has a final score."""
    weeks: dict[int, list] = {}
    for g in games(season):
        weeks.setdefault(g["week"], []).append(g["home_score"] is not None)
    return sorted(w for w, done in weeks.items() if done and all(done))


def usage_gap(season: int) -> str | None:
    """A note when a finished game is missing from the usage file."""
    usage = _read(DATA / f"advanced_usage_{season}_weekly.csv")
    have = {(int(r["week"]), r["team"]) for r in usage}
    have_weeks = {w for w, _ in have}
    missing = []
    for g in games(season):
        if g["home_score"] is None:
            continue
        if not any((g["week"], t) in have for t in (g["home_team"], g["away_team"])):
            missing.append(g)
    if not missing:
        return None
    weeks = sorted({g["week"] for g in missing})
    teams = ", ".join(f"{g['away_team']}@{g['home_team']}" for g in missing[:6])
    return (f"STALE: {len(missing)} finished game(s) not in the usage file "
            f"(week {', '.join(map(str, weeks))}: {teams}{'...' if len(missing) > 6 else ''}); "
            f"usage weeks on file {sorted(have_weeks)}. refresh_week(week=N) adds them.")


def decision_week_hint(season: int, state_week: int) -> str:
    """Plain statement of where the current week stands, for Monday questions."""
    final, total, left = week_progress(season, state_week)
    if not total:
        return f"week {state_week}: no schedule cached"
    if not left:
        return (f"week {state_week}: all {total} games final. Pickups and lineups now target "
                f"week {state_week + 1}; pass week={state_week + 1}.")
    rest = ", ".join(f"{g['away_team']}@{g['home_team']} {g['weekday'][:3]} {g['gametime']}" for g in left[:4])
    return (f"week {state_week}: {final}/{total} games final; still to play: {rest}. "
            f"Waiver/pickup questions after Sunday usually target week {state_week + 1}; "
            f"lineup questions for the remaining games stay week {state_week}.")
