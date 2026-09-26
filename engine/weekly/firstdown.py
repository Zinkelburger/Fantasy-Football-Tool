"""First Down Studio's weekly Vegas rankings, read from a page you saved.

    https://www.firstdown.studio/rankings/rb   (also /wr /te /flex /k)

A third projection beside the FantasyPros consensus (fftiers.py) and our
usage model: each player's points are built from **sportsbook player
props** (rushing/receiving yards, attempts, receptions, anytime-TD
probability, passing lines, kicking points), in standard, half and full
PPR. Where a book has no prop for a stat, First Down fills it with its
own estimate and lists the stat in `projected_fields`; a row with none of
those is fully market-based. Players with no props at all are absent, so
a missing name is not a low ranking.

**No fetching, by design.** First Down's terms of service prohibit
"automated tools, scrapers, or bots without our written permission" and
reproducing their content. So nothing here touches their site: you open
any of the weekly rankings pages in a browser (Thursday evening and
Sunday morning is plenty; the snapshot rarely changes more often) and
save it (Ctrl+S, either "HTML only" or "complete") into
engine/weekly/cache/firstdown/ or ~/Downloads. Every weekly rankings page
embeds the same snapshot of every position, so one save covers
QB/RB/WR/TE/K.

The page is a Next.js app; the snapshot is JSON inside its
`self.__next_f.push([1,"..."])` script chunks. `parse()` decodes those,
checks season/week and the matchups against the schedule, and refuses
another week's page. Parsed rows go to engine/weekly/cache/ (gitignored),
never to data/weekly/, which is public and feeds the website.

    python firstdown.py                  # import the newest save, print RBs
    python firstdown.py --pos FLEX --top 60
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from common import CACHE, nfl_state, norm_team, now_iso, week_key

URL = "https://www.firstdown.studio/rankings/rb"
SAVE_DIRS = [CACHE / "firstdown", Path.home() / "Downloads"]
TERMS_NOTE = ("First Down Studio's terms forbid scrapers and reproduction: read only "
              "from pages the user saved; kept in the gitignored cache, never "
              "committed, published or quoted anywhere public.")
ET = ZoneInfo("America/New_York")
# When a fresh save is worth asking for: Thursday from noon ET (the Week 3
# snapshot was generated Thu 16:57 ET, so anything older than Thursday is
# due) and Sunday 09:00 ET, before the early games lock.
CHECKPOINTS = [(3, 12), (6, 9)]          # (weekday Mon=0, hour ET)
MAX_SCAN = 200                            # newest candidate files looked at

SNAP = re.compile(r'"snapshot"\s*:\s*\{')
CHUNK = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', re.S)
KEEP = ["rushing_attempts", "rushing_yards", "receptions", "receiving_yards",
        "expected_touchdowns", "passing_yards", "passing_touchdowns",
        "interceptions", "kicking_points"]
POSITIONS = ("QB", "RB", "WR", "TE", "K")


def path(season: int, week: int) -> Path:
    return CACHE / f"firstdown_{week_key(season, week)}.json"


def _snapshot_text(page: str) -> str | None:
    """The decoded RSC stream, or the raw page if it already holds plain
    JSON (some browsers' "save complete" re-serializes the scripts)."""
    parts = []
    for raw in CHUNK.findall(page):
        try:
            parts.append(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            continue
    text = "".join(parts)
    if SNAP.search(text):
        return text
    return page if SNAP.search(page) else None


def parse(page: str) -> dict | None:
    """Saved page HTML -> {season, week, generated_at, rows}. Pure; None
    when the page holds no First Down weekly snapshot."""
    text = _snapshot_text(page)
    if text is None:
        return None
    i = SNAP.search(text).end() - 1          # at the object's opening brace
    try:
        snap, _ = json.JSONDecoder().raw_decode(text, i)
    except json.JSONDecodeError:
        return None
    rows = []
    for r in snap.get("rows") or []:
        pos = r.get("position")
        if pos not in POSITIONS or r.get("standard") is None:
            continue
        details = r.get("game_details") or ""
        filled = [f for f in (r.get("projected_fields") or []) if f != "projected_points"]
        rows.append({
            "name": r.get("name"), "pos": pos, "team": norm_team(r.get("team")),
            "opp": norm_team(r.get("opponent")), "home": " vs " in details,
            "kickoff": r.get("kickoff_at"), "injury": r.get("injury_status"),
            "points_std": round(float(r["standard"]), 2),
            "points_half": round(float(r.get("halfppr") or 0), 2),
            "points_ppr": round(float(r.get("ppr") or 0), 2),
            "rank_std": r.get("standard_erc"), "sleeper_id": r.get("sleeper_id"),
            "not_from_props": filled,
            **{k: round(float(r[k]), 2) for k in KEEP if r.get(k) is not None},
        })
    if not rows:
        return None
    return {"season": snap.get("season"), "week": snap.get("week"),
            "generated_at": snap.get("generated_at"),
            "snapshot_id": snap.get("snapshot_id"),
            "scoring_version": snap.get("scoring_version"), "rows": rows}


def _schedule(season: int, week: int) -> dict[str, str]:
    import nfl_data
    import polars as pl
    games = nfl_data.schedules(season).filter(
        (pl.col("week") == week) & (pl.col("game_type") == "REG"))
    out = {}
    for g in games.iter_rows(named=True):
        out[g["home_team"]] = g["away_team"]
        out[g["away_team"]] = g["home_team"]
    return out


def _candidates(dirs=None) -> list[Path]:
    files = []
    for d in dirs or SAVE_DIRS:
        if d.is_dir():
            files += [p for p in d.iterdir() if p.suffix.lower() in (".html", ".htm")]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:MAX_SCAN]


def import_saved(season: int, week: int, dirs=None,
                 schedule: dict[str, str] | None = None) -> dict | None:
    """Newest saved page for this season/week -> cache. None if there is
    no such save. Raises when the newest matching save disagrees with the
    schedule (a wrong-season page must never pass as this week's)."""
    best, best_src = None, None
    for p in _candidates(dirs):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "firstdown" not in text.lower() and "first down studio" not in text.lower():
            continue
        snap = parse(text)
        if not snap or (snap["season"], snap["week"]) != (season, week):
            continue
        if best is None or (snap["generated_at"] or "") > (best["generated_at"] or ""):
            best, best_src = snap, p
    if best is None:
        return None
    schedule = _schedule(season, week) if schedule is None else schedule
    bad = [f"{r['name']} ({r['team']}) vs {r['opp']}" for r in best["rows"]
           if r["team"] and r["opp"] and schedule and schedule.get(r["team"]) != r["opp"]]
    if bad:
        raise RuntimeError(f"First Down matchups disagree with the {season} week {week} "
                           f"schedule ({len(bad)}, e.g. {bad[0]}); not importing {best_src}")
    cached = path(season, week)
    if cached.exists():
        old = json.loads(cached.read_text())
        if (old.get("generated_at") or "") >= (best["generated_at"] or ""):
            return old
    payload = {**best, "source_file": str(best_src), "imported_at": now_iso(),
               "url": URL, "terms": TERMS_NOTE}
    cached.write_text(json.dumps(payload, indent=1))
    return payload


def due_since(now: datetime | None = None) -> datetime:
    """The most recent refresh checkpoint (Thu evening / Sun morning ET)."""
    now = (now or datetime.now(timezone.utc)).astimezone(ET)
    best = None
    for back in range(8):
        day = (now - timedelta(days=back)).date()
        for wd, hour in CHECKPOINTS:
            if day.weekday() == wd:
                t = datetime(day.year, day.month, day.day, hour, tzinfo=ET)
                if t <= now and (best is None or t > best):
                    best = t
    return best


def freshness(data: dict, now: datetime | None = None) -> str | None:
    """A note when the snapshot predates the latest checkpoint, else None."""
    gen = data.get("generated_at")
    if not gen:
        return "snapshot has no generation time"
    g = datetime.fromisoformat(gen.replace("Z", "+00:00"))
    since = due_since(now)
    if since and g < since:
        return (f"snapshot generated {g.astimezone(ET):%a %b %d %H:%M} ET, before the "
                f"{since:%a %H:%M} ET checkpoint: a newer one may exist. Ask the user to "
                f"open {URL} and save it into {SAVE_DIRS[0]} or ~/Downloads.")
    return None


def load(season: int, week: int, dirs=None) -> dict:
    """Import the newest save (cheap, local only), else the cached copy.
    Raises FileNotFoundError with instructions when there is neither."""
    data = import_saved(season, week, dirs=dirs)
    if data is None and path(season, week).exists():
        data = json.loads(path(season, week).read_text())
    if data is None:
        raise FileNotFoundError(
            f"no saved First Down page for {season} week {week}. Open {URL} in a browser "
            f"and save it (Ctrl+S) into {SAVE_DIRS[0]} or ~/Downloads. (Their terms "
            f"forbid automated fetching, so this tool never downloads it.)")
    return data


def select(rows: list[dict], position: str) -> list[dict]:
    pos = position.upper()
    if pos == "FLEX":
        keep = [r for r in rows if r["pos"] in ("RB", "WR", "TE")]
    else:
        keep = [r for r in rows if r["pos"] == pos]
    return sorted(keep, key=lambda r: -r["points_std"])


def line(r: dict, rank: int) -> str:
    stats = []
    if "passing_yards" in r:
        stats.append(f"{r['passing_yards']:.0f} pass yd, {r.get('passing_touchdowns', 0):.1f} pass TD")
    if "rushing_yards" in r:
        att = f"{r['rushing_attempts']:.0f} att " if "rushing_attempts" in r else ""
        stats.append(f"{att}{r['rushing_yards']:.0f} rush yd")
    if "receiving_yards" in r:
        stats.append(f"{r.get('receptions', 0):.1f} rec {r['receiving_yards']:.0f} rec yd")
    if "expected_touchdowns" in r:
        stats.append(f"{r['expected_touchdowns']:.2f} TD")
    if "kicking_points" in r and r["pos"] == "K":
        stats.append("kicking props")
    flag = f"  [not from props: {', '.join(r['not_from_props'])}]" if r["not_from_props"] else ""
    inj = f"  [{r['injury']}]" if r["injury"] else ""
    return (f"  {rank:>3} {r['name']:24} {r['pos']:2} {r['team'] or '?':3} "
            f"{'vs' if r['home'] else '@ '} {r['opp'] or '?':3} {r['points_std']:5.1f} std  "
            + "; ".join(stats) + inj + flag)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pos", default="RB")
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args(argv)
    st = nfl_state()
    data = load(st["season"], st["week"])
    print(f"First Down Vegas {a.pos.upper()} week {data['week']}, generated "
          f"{data['generated_at']} (from {data.get('source_file')})")
    note = freshness(data)
    if note:
        print("  STALE: " + note)
    for i, r in enumerate(select(data["rows"], a.pos)[:a.top], 1):
        print(line(r, i))
    return 0


if __name__ == "__main__":
    sys.exit(main())
