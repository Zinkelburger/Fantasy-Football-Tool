#!/usr/bin/env python3
"""Sweep r/fantasyfootball once into a local corpus (posts + comments as JSONL).

Reddit search never indexes comments, so instead of per-player searches this
pulls top/hot/new posts and expands their comment trees. Matching happens
offline (match_players.py) against the cached corpus — re-matching costs zero
API calls.

Rate-limit friendly: PRAW self-throttles from Reddit's rate headers (free tier
is 100 requests/min), replace_more is capped per post, and the corpus is
append-only keyed by id, so an interrupted sweep resumes where it left off.
"""

import argparse
import json
import os
import pathlib
import time
from datetime import datetime, timedelta

from RedditQuery import RedditQuery

SUBREDDIT = "fantasyfootball"
CORPUS_DIR = pathlib.Path(__file__).resolve().parent / "corpus"
POSTS_FILE = CORPUS_DIR / "posts.jsonl"
COMMENTS_FILE = CORPUS_DIR / "comments.jsonl"


def load_seen_ids(path: pathlib.Path, key: str) -> set:
    seen = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line)[key])
                except (json.JSONDecodeError, KeyError):
                    continue
    return seen


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=150, help="posts from top(month)")
    ap.add_argument("--hot", type=int, default=100, help="posts from hot")
    ap.add_argument("--new", type=int, default=200, help="posts from new")
    ap.add_argument("--days", type=int, default=60, help="ignore posts older than this")
    ap.add_argument("--replace-more", type=int, default=12,
                    help="max 'load more comments' expansions per post (~100 comments each)")
    args = ap.parse_args()

    CORPUS_DIR.mkdir(exist_ok=True)
    seen_posts = load_seen_ids(POSTS_FILE, "id")
    seen_comments = load_seen_ids(COMMENTS_FILE, "id")
    print(f"corpus already has {len(seen_posts)} posts, {len(seen_comments)} comments")

    reddit = RedditQuery()
    sub = reddit.reddit.subreddit(SUBREDDIT)
    cutoff = (datetime.now() - timedelta(days=args.days)).timestamp()

    # Gather candidate posts from three listings, dedupe by id
    candidates = {}
    for label, listing in [("top", sub.top(time_filter="month", limit=args.top)),
                           ("hot", sub.hot(limit=args.hot)),
                           ("new", sub.new(limit=args.new))]:
        n = 0
        for s in listing:
            if s.created_utc >= cutoff and s.num_comments > 0:
                candidates.setdefault(s.id, s)
                n += 1
        print(f"listing {label}: {n} usable posts (running unique: {len(candidates)})")

    todo = [s for pid, s in candidates.items() if pid not in seen_posts]
    print(f"{len(todo)} new posts to fetch ({len(candidates) - len(todo)} already cached)")

    posts_f = open(POSTS_FILE, "a", encoding="utf-8")
    comments_f = open(COMMENTS_FILE, "a", encoding="utf-8")

    t0 = time.time()
    new_comments = 0
    for i, s in enumerate(todo, 1):
        try:
            s.comment_sort = "top"
            s.comments.replace_more(limit=args.replace_more)
            comments = s.comments.list()
        except Exception as e:
            print(f"  ! failed on post {s.id} ({s.title[:50]}): {e}")
            continue

        posts_f.write(json.dumps({
            "id": s.id, "title": s.title, "selftext": s.selftext,
            "score": s.score, "num_comments": s.num_comments,
            "created_utc": s.created_utc, "permalink": s.permalink,
        }) + "\n")

        for c in comments:
            if c.id in seen_comments:
                continue
            seen_comments.add(c.id)
            comments_f.write(json.dumps({
                "id": c.id, "post_id": s.id, "parent_id": c.parent_id,
                "score": c.score, "body": c.body, "created_utc": c.created_utc,
            }) + "\n")
            new_comments += 1

        posts_f.flush()
        comments_f.flush()
        if i % 20 == 0 or i == len(todo):
            elapsed = time.time() - t0
            print(f"  [{i}/{len(todo)}] {new_comments} comments so far, "
                  f"{elapsed/60:.1f} min elapsed")
        time.sleep(0.2)  # gentle pacing on top of PRAW's own throttling

    posts_f.close()
    comments_f.close()
    print(f"\ndone: +{len(todo)} posts, +{new_comments} comments "
          f"in {(time.time()-t0)/60:.1f} min")
    print(f"corpus: {POSTS_FILE} / {COMMENTS_FILE}")


if __name__ == "__main__":
    main()
