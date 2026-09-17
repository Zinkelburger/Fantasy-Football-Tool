"""Boris Chen's fftiers: FantasyPros expert consensus, clustered into tiers.

The public S3 bucket behind borischen.co and fantasyfootballtiers.com
(that site is static PNGs; it has no data layer of its own). It carries
the same FantasyPros ECR that fantasypros.py needs an API key for, plus
the tier assignment, and it needs no key:

    https://s3-us-west-1.amazonaws.com/fftiers/out/weekly-<POS>[-HALF|-PPR].csv
    "Rank","Player.Name","Matchup","Best.Rank","Worst.Rank","Avg.Rank","Std.Dev","Tier"

Output: data/weekly/ecr_<season>_wk<NN>.csv — the same path and the same
columns fantasypros.py writes, plus `tier` and `source`, so every
consumer keeps working whichever fetcher filled the file. The paid API
wins when a key is configured; this is the keyless fallback. Read the
file back with fantasypros.load(), which owns that path either way.

What the tiers are for: a rank gap inside a tier is noise the experts
disagree about, a tier gap is a real ordering. `rank_std` says how much
they disagree, which is the signal for "go read the news on this one".

What the bucket does not give us and the API does: a team abbreviation
per player (only the opponent, via `Matchup`) and `start_sit_grade`.
Those are written empty, except D/ST, where the team is the player.

The files carry no week number — there is one live copy per position,
rewritten in place. `fetch()` therefore takes the set of teams playing
in the week being built and refuses to write a week's file from another
week's rankings.

Coverage is shallow on purpose (QB 26, RB 40, WR 60, TE 24, K 20,
D/ST 20, FLX ranks 20-95): startable players, not the waiver tail.
Unofficial bucket, no terms and no SLA — a failure here is logged and
skipped, never fatal.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys

from common import DATA, TEAMS, http_text, nfl_state, norm_team, now_iso, week_key

BASE = "https://s3-us-west-1.amazonaws.com/fftiers/out"
SUFFIX = {"std": "", "half": "-HALF", "ppr": "-PPR"}
# True where the bucket splits the file by scoring format. QB, K and
# D/ST tiers do not move with receptions, so those are single files.
POSITIONS = {"QB": False, "RB": True, "WR": True, "TE": True, "FLX": True,
             "K": False, "DST": False}
# The ecr_*.csv contract, in fantasypros.py's order, then our two extras.
FIELDS = ["pos", "rank_ecr", "name", "team", "opp", "rank_min", "rank_max",
          "rank_ave", "rank_std", "start_sit_grade", "fp_id", "tier", "source"]

MATCHUP = re.compile(r"^(at|vs\.?)\s+([A-Z]{2,3})$", re.I)
# "Philadelphia Eagles" -> PHI, so a D/ST row can join on its team.
NICKNAMES = {v.lower(): k for k, v in TEAMS.items()}


def url(pos: str, fmt: str = "std") -> str:
    return f"{BASE}/weekly-{pos}{SUFFIX[fmt] if POSITIONS[pos] else ''}.csv"


def parse_matchup(s: str | None) -> tuple[str | None, bool | None]:
    """'at BUF' -> ('BUF', False); 'vs. CAR' -> ('CAR', True)."""
    m = MATCHUP.match((s or "").strip())
    if not m:
        return None, None
    return norm_team(m.group(2)), m.group(1).lower().startswith("vs")


def dst_name(name: str) -> tuple[str, str | None]:
    """'Philadelphia Eagles' -> ('Eagles D/ST', 'PHI'), ESPN's spelling,
    so the roster join by name lands. The team is carried too, because
    D/ST naming differs between every source that has ever existed."""
    abbr = NICKNAMES.get((name or "").rsplit(" ", 1)[-1].lower())
    return (f"{TEAMS[abbr]} D/ST", abbr) if abbr else (name, None)


def parse(text: str, pos: str) -> list[dict]:
    """One position's CSV -> ecr_*.csv rows. Pure; no network."""
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        name = (r.get("Player.Name") or "").strip()
        if not name or not (r.get("Rank") or "").strip():
            continue
        team = None
        if pos == "DST":
            name, team = dst_name(name)
        opp, _home = parse_matchup(r.get("Matchup"))
        rows.append({"pos": pos, "rank_ecr": r["Rank"], "name": name,
                     "team": team or "", "opp": opp or "",
                     "rank_min": r.get("Best.Rank", ""), "rank_max": r.get("Worst.Rank", ""),
                     "rank_ave": r.get("Avg.Rank", ""), "rank_std": r.get("Std.Dev", ""),
                     "start_sit_grade": "", "fp_id": "",
                     "tier": (r.get("Tier") or "").strip(), "source": "fftiers"})
    return rows


def off_week(rows: list[dict], schedule: dict[str, str] | None) -> list[str]:
    """Rankings that disagree with the week's schedule, as readable lines.

    The bucket has no week in its filenames, so comparing matchups is the
    only way to tell a stale or lookahead copy from the right one. Before
    the byes start every team plays every week, so "is this opponent
    playing" proves nothing; the pairing has to match. D/ST rows are the
    lever — they are the only ones that name both sides — and 20 teams
    checked exactly is a real test. `schedule` is {team: opponent}.
    """
    if not schedule:
        return []
    bad = []
    for r in rows:
        if not r["opp"]:
            continue
        if r["opp"] not in schedule:
            bad.append(f"{r['name']} ({r['pos']}) faces {r['opp']}, who are not playing")
        elif r["team"] and schedule.get(r["team"]) != r["opp"]:
            bad.append(f"{r['name']} ({r['pos']}) is down to face {r['opp']}, "
                       f"but {r['team']} play {schedule.get(r['team'], 'BYE')}")
    return bad


def fetch(season: int, week: int, fmt: str = "std",
          schedule: dict[str, str] | None = None) -> list[dict] | None:
    """Pull every position, write ecr_<season>_wkNN.csv and its manifest.

    `schedule` is the week's {team: opponent}; when omitted it is loaded
    from nflverse. Only the current regular-season week is accepted, and
    D/ST matchups must be available to verify it. Returns rows, or None if the bucket gave
    us nothing at all. Raises if the rankings are for another week.
    """
    state = nfl_state()
    if (season, week) != (state["season"], state["week"]) or state.get("season_type") != "regular":
        raise ValueError("fftiers only serves the current regular-season week")
    if schedule is None:
        import nfl_data
        import polars as pl
        games = nfl_data.schedules(season).filter(
            (pl.col("week") == week) & (pl.col("game_type") == "REG"))
        schedule = {}
        for game in games.iter_rows(named=True):
            schedule[game["home_team"]] = game["away_team"]
            schedule[game["away_team"]] = game["home_team"]
    if not schedule:
        raise ValueError("Cannot verify fftiers rankings without this week's schedule")
    rows: list[dict] = []
    sources: dict[str, dict] = {}
    for pos in POSITIONS:
        u = url(pos, fmt)
        try:
            text, modified = http_text(u)
            got = parse(text, pos)
        except Exception as e:  # noqa: BLE001 - one position failing is not fatal
            sources[pos] = {"status": "unavailable", "error": str(e), "url": u,
                            "rows": 0, "last_modified": None}
            print(f"fftiers {pos} unavailable: {e}", file=sys.stderr)
            continue
        rows += got
        sources[pos] = {"status": "available" if got else "empty", "error": None, "url": u,
                        "rows": len(got), "last_modified": modified}
    if not rows:
        return None
    if not any(r["pos"] == "DST" and r["team"] and r["opp"] for r in rows):
        raise RuntimeError("Cannot verify fftiers week: no D/ST matchups available")
    bad = off_week(rows, schedule)
    if bad:
        raise RuntimeError(
            f"fftiers rankings do not match {season} week {week} "
            f"({len(bad)} mismatches, e.g. {bad[0]}). The bucket publishes "
            "one live copy per position and cannot be asked for another "
            "week, so this is a stale or lookahead fetch.")

    path = DATA / f"ecr_{week_key(season, week)}.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    manifest = {"season": season, "week": week, "scoring": fmt,
                "generated_at": now_iso(), "source": "fftiers",
                "provider": "Boris Chen (borischen.co), from FantasyPros ECR",
                "note": "Keyless fallback for fantasypros.py. Adds `tier`; "
                        "has no team (except D/ST) and no start_sit_grade. "
                        "Shallow by design: startable players only.",
                "rows": len(rows), "schedule_checked": bool(schedule),
                "sources": sources}
    path.with_suffix(".sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--fmt", choices=sorted(SUFFIX), default="std")
    a = ap.parse_args(argv)
    st = nfl_state()
    season, week = a.season or st["season"], a.week or st["week"]
    rows = fetch(season, week, a.fmt)
    if rows is None:
        print("fftiers unreachable; nothing written", file=sys.stderr)
        return 1
    per = {}
    for r in rows:
        per[r["pos"]] = per.get(r["pos"], 0) + 1
    print(f"{len(rows)} rows -> data/weekly/ecr_{week_key(season, week)}.csv "
          f"({a.fmt}): " + ", ".join(f"{k} {v}" for k, v in per.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
