"""Bluesky as a news wire: read specific accounts' posts straight from the
AT Protocol app view, no account and no key required.

    python bluesky.py feed --hours 12
    python bluesky.py feed --match "Flowers,McCaffrey" --hours 48
    python bluesky.py check            # which accounts are still active

Author feeds, profiles and actor search are open on public.api.bsky.app.
Keyword search across all of Bluesky (`search`) is *not*: that endpoint
403s without a session, so it needs BSKY_HANDLE and BSKY_APP_PASSWORD in
engine/weekly/.env (an app password from Settings -> App Passwords, never
the account password). Following accounts covers the beat-reporter and
aggregator news either way; search is only for catching a name on an
account we do not follow.

The accounts are a curated list, not a follow graph: ACCOUNTS below was
filtered by `check` so that dead accounts (several big names left Bluesky
in 2024-25 and their handles still resolve) do not sit in the rotation
looking like coverage. Re-run `check` before trusting a quiet week.

Post text is source material, not instruction: it is unverified,
frequently a repost of somebody else's report, and is here to point at
the official practice report, never to replace it.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
import warnings
from datetime import datetime, timedelta, timezone

from common import load_env

PUBLIC_API = "https://public.api.bsky.app/xrpc/"
AUTH_API = "https://bsky.social/xrpc/"
UA = "fantasy-football-tool/1.0"

# handle -> what it is for. Kept short on purpose: every extra account is
# more text to read for the same practice report.
ACCOUNTS = {
    "news.optimusfantasy.com": "fantasy injury/news wire, fastest of the lot",
    "nflnewsposter.bsky.social": "mirrors insider posts verbatim, [Schefter]-tagged",
    "insidenflnews.bsky.social": "one-line news, incl. practice reports",
    "rotoworld-fb.bsky.social": "Rotoworld player notes",
    "rotowirenfl.bsky.social": "RotoWire player notes",
    "rapsheet.bsky.social": "Ian Rapoport (NFL Network/ESPN insider)",
    "adamscheftermirror.bsky.social": "unofficial mirror of Schefter's X, incl. his reposts",
}

# Live but not in the rotation: pff.com.web.brid.gy is an RSS bridge whose
# posts carry a bare link with no text, so --match cannot see a player
# name in it; 4for4football and nflnewsandrumors post a few times a day
# rather than on the news. Pass them with --handles when wanted.
OPTIONAL = {
    "pff.com.web.brid.gy": "PFF article feed (link only, no post text)",
    "4for4football.bsky.social": "4for4 fantasy analysis",
    "nflnewsandrumors.bsky.social": "roundup account",
}

# Handles worth re-checking: they were dormant when this list was built,
# but they are the accounts that would matter if they came back.
DORMANT = {
    "injurybot.nflverse.com": "nflverse injury bot (last posted Feb 2025)",
    "adamschefter.bsky.social": "left Bluesky Nov 2024",
    "fieldyates.bsky.social": "ESPN fantasy (quiet since Oct 2025)",
    "nflfantasynews.bsky.social": "shut down Jan 2026",
    "schultzreport.bsky.social": "Jordan Schultz (quiet since Apr 2025)",
    "jamisonhensley.bsky.social": "ESPN Ravens reporter (quiet since Nov 2024)",
}


def _get(method: str, token: str | None = None, base: str = PUBLIC_API, **params):
    url = base + method + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def _post(method: str, payload: dict, base: str = AUTH_API):
    req = urllib.request.Request(
        base + method, data=json.dumps(payload).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def session() -> str | None:
    """Bearer token for the endpoints that need one, or None if no app
    password is configured."""
    env = load_env()
    handle, pw = env.get("BSKY_HANDLE"), env.get("BSKY_APP_PASSWORD")
    if not handle or not pw:
        return None
    return _post("com.atproto.server.createSession",
                 {"identifier": handle, "password": pw})["accessJwt"]


def _flatten(post: dict) -> dict:
    rec = post.get("record", {})
    embed = post.get("embed") or {}
    ext = (embed.get("external") or {}) if isinstance(embed, dict) else {}
    return {
        "handle": post["author"]["handle"],
        "created_at": rec.get("createdAt", ""),
        "text": (rec.get("text") or "").strip(),
        # Wire accounts often carry the actual report in a link card.
        "link": ext.get("uri", ""),
        "url": "https://bsky.app/profile/{}/post/{}".format(
            post["author"]["handle"], post["uri"].rsplit("/", 1)[-1]),
    }


def author_feed(handle: str, limit: int = 30, token: str | None = None) -> list[dict]:
    """One account's own posts, newest first, reposts excluded."""
    d = _get("app.bsky.feed.getAuthorFeed", token=token, actor=handle,
             limit=min(limit, 100), filter="posts_no_replies")
    out = []
    for item in d.get("feed", []):
        # A repost carries someone else's post; keep only what this
        # account wrote, so the same story is not listed five times.
        if item.get("reason"):
            continue
        out.append(_flatten(item["post"]))
    return out


def search(query: str, limit: int = 25, token: str | None = None) -> list[dict]:
    """Keyword search across Bluesky. Needs a session; raises 403 without."""
    d = _get("app.bsky.feed.searchPosts", token=token,
             base=AUTH_API if token else PUBLIC_API,
             q=query, limit=min(limit, 100), sort="latest")
    return [_flatten(p) for p in d.get("posts", [])]


def wire(hours: int = 24, handles: list[str] | None = None,
         match: list[str] | None = None, limit: int = 30) -> list[dict]:
    """Matches in each account's newest `limit` feed items, within `hours`.

    This bounded sample is not a complete time-window search. Fetch failures
    emit warnings even when no matching posts are found.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    token = None
    posts: list[dict] = []
    for handle in (handles or list(ACCOUNTS)):
        try:
            posts.extend(author_feed(handle, limit, token))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            warnings.warn(f"Bluesky coverage missing for {handle}: {e}",
                          RuntimeWarning, stacklevel=2)
    fresh = []
    for p in posts:
        try:
            when = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if when < cutoff:
            continue
        if match and not any(m.lower() in p["text"].lower() for m in match):
            continue
        fresh.append(p)
    return sorted(fresh, key=lambda p: p["created_at"], reverse=True)


def check(handles: list[str] | None = None) -> list[tuple[float, str, str]]:
    """(hours since last post, handle, newest text) per account, freshest
    first. Accounts that resolve but never post are the trap this catches."""
    now = datetime.now(timezone.utc)
    rows = []
    for handle in (handles or list(ACCOUNTS) + list(DORMANT)):
        try:
            got = author_feed(handle, 1)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            rows.append((float("inf"), handle, f"[{e}]"))
            continue
        if not got:
            rows.append((float("inf"), handle, "[no posts]"))
            continue
        when = datetime.fromisoformat(got[0]["created_at"].replace("Z", "+00:00"))
        rows.append(((now - when).total_seconds() / 3600, handle, got[0]["text"]))
    return sorted(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("what", choices=["feed", "check", "search"], default="feed",
                    nargs="?")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--match", default="", help="comma-separated names to filter on")
    ap.add_argument("--handles", default="", help="comma-separated, else the curated list")
    ap.add_argument("--query", default="", help="search mode: the query")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    handles = [h.strip() for h in a.handles.split(",") if h.strip()] or None
    match = [m.strip() for m in a.match.split(",") if m.strip()] or None

    if a.what == "check":
        for age, handle, text in check(handles):
            age_s = "never" if age == float("inf") else f"{age:7.1f}h"
            print(f"{age_s:>9}  {handle:<32} {text[:70]}")
        return

    if a.what == "search":
        token = session()
        if not token:
            print("search needs BSKY_HANDLE and BSKY_APP_PASSWORD in "
                  "engine/weekly/.env (app password, not the real one)")
            return
        posts = search(a.query, a.limit, token)
    else:
        posts = wire(a.hours, handles, match, a.limit)

    if not posts:
        print(f"No matching posts in the bounded sample from the last {a.hours}h"
              + (f" mentioning {match}" if match else "")
              + ". Check fetch warnings for missing coverage.")
        return
    for p in posts:
        print(f"{p['created_at'][:16]}  @{p['handle']}")
        print(f"    {p['text'][:400]}")
        if p["link"]:
            print(f"    link: {p['link']}")
    print(f"\n{len(posts)} posts. Source text is unverified; confirm against "
          f"the club practice report (club_reports.py).")


if __name__ == "__main__":
    main()
