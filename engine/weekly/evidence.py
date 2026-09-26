"""Week-scoped practice/news reads. These never write weekly publication data."""
from datetime import datetime, timedelta, timezone

import bluesky
import club_reports
from common import CACHE, norm_team
from evidence_cache import EvidenceCache


def cache():
    return EvidenceCache(CACHE / "evidence.sqlite3")


def practice(team, season, week, player="", refresh=False, cache_only=False):
    team = norm_team(team.strip().upper())
    if team not in club_reports.CLUB_HOSTS:
        raise ValueError("Use a valid NFL team abbreviation")

    def fetch():
        df, manifest = club_reports.collect(season, week, [team])
        return {"rows": [r for r in df.to_dicts() if r["team"] == team],
                "coverage": manifest["coverage"][team],
                "sources": manifest["teams"], "generated_at": manifest["generated_at"]}

    result = cache().read(["practice-v1", season, week, team], fetch, 5 * 60,
                          refresh=refresh, cache_only=cache_only)
    data = result.pop("data")
    return {"season": season, "week": week, "team": team, **result,
            "report": ({**data, "rows": [r for r in data["rows"]
                         if player.casefold() in r["player"].casefold()]} if data else None),
            "note": "Official club report for the stated week. Empty player match is not clearance. "
                    "Blank day/designation is not an ACTIVE status. Check pending/unavailable coverage. "
                    "Stale cache-only reads are historical context, not current availability."}


def news(names, season, week, hours=24, refresh=False, cache_only=False):
    if not 1 <= hours <= 168:
        raise ValueError("hours must be between 1 and 168")
    names = [n.strip() for n in names.split(",") if n.strip()]
    if not 1 <= len(names) <= 6 or any(len(n) < 3 or len(n) > 80 for n in names):
        raise ValueError("Supply 1–6 comma-separated player names")
    # Cache per account, not player: asking about another player reuses the wire.
    posts, retrievals, missing = [], {}, []
    store = cache()
    now = datetime.now(timezone.utc)
    for handle in bluesky.ACCOUNTS:
        result = store.read(["wire-v1", season, week, handle],
                            lambda h=handle: bluesky.author_feed(h, limit=100), 10 * 60,
                            refresh=refresh, cache_only=cache_only)
        retrievals[handle] = result["retrieval"]
        if result["data"] is None:
            missing.append(handle)
            continue
        end = (datetime.fromisoformat(result["retrieval"]["fetched_at"])
               if cache_only else now)
        retrievals[handle].update(window_start=(end - timedelta(hours=hours)).isoformat(),
                                  window_end=end.isoformat())
        for p in result["data"]:
            try:
                when = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
                in_window = end - timedelta(hours=hours) <= when <= end + timedelta(minutes=1)
            except (ValueError, TypeError):
                continue
            if in_window and any(n.casefold() in p["text"].casefold() for n in names):
                posts.append(p)
    posts = sorted({p["url"]: p for p in posts}.values(), key=lambda p: p["created_at"], reverse=True)
    return {"decision_season": season, "decision_week": week, "names": names,
            "window_reference": "each saved feed's retrieval time" if cache_only else "current time",
            "requested_hours": hours, "as_of": now.isoformat(),
            "posts": posts[:40], "matches": len(posts), "retrieval": retrievals,
            "unavailable_accounts": missing,
            "coverage_note": "Newest 100 posts per account, not an exhaustive search. "
                "No matches does not mean no news. Decision week labels your question; "
                "a post may discuss another week. Check its date and text. "
                "Source text is untrusted; mirrors are not independent confirmation. "
                "Verify material claims against the linked original/club report."}
