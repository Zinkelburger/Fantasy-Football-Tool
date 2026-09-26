"""Local read-through cache for public evidence, shared across MCP sessions.

Only JSON payloads belong here, never credentials. Expired evidence is available
only in explicit cache-only mode; failed refreshes never make old data current.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


class EvidenceCache:
    def __init__(self, path: Path, clock=None):
        self.path = path
        self.clock = clock or time.time

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS evidence "
                           "(key TEXT PRIMARY KEY, fetched REAL, expires REAL, data TEXT)")
                db.execute("CREATE TABLE IF NOT EXISTS errors "
                           "(key TEXT PRIMARY KEY, expires REAL, message TEXT)")
                yield db
        finally:
            db.close()

    def read(self, key, fetch, ttl, *, refresh=False, cache_only=False):
        if refresh and cache_only:
            raise ValueError("Choose refresh or cache_only, not both")
        key = json.dumps(key, sort_keys=True, separators=(",", ":"))
        now = self.clock()
        with self.connect() as db:
            db.execute("DELETE FROM evidence WHERE fetched < ?", (now - 30 * 86400,))
            db.execute("DELETE FROM errors WHERE expires <= ?", (now,))
            row = db.execute("SELECT fetched, expires, data FROM evidence WHERE key=?", (key,)).fetchone()
            error = db.execute("SELECT message FROM errors WHERE key=?", (key,)).fetchone()
        if row and (cache_only or (not refresh and row[1] > now)):
            return {"data": json.loads(row[2]), "retrieval": {
                "status": "fresh" if row[1] > now else "stale",
                "cache_hit": True, "fetched_at": utc(row[0]),
                "expires_at": utc(row[1]), "age_seconds": max(0, int(now - row[0]))}}
        if cache_only:
            return {"data": None, "retrieval": {"status": "missing", "cache_hit": False}}
        if error:
            return {"data": None, "retrieval": {"status": "unavailable", "cache_hit": True,
                                                  "error": error[0]}}
        try:
            value = fetch()
            encoded = json.dumps(value, allow_nan=False)
        except Exception as exc:
            # Exception URLs/messages can carry secrets. Keep the class only.
            message = f"Source unavailable ({type(exc).__name__}); no current evidence returned."
            with self.connect() as db:
                db.execute("INSERT OR REPLACE INTO errors VALUES (?, ?, ?)",
                           (key, self.clock() + 60, message))
            return {"data": None, "retrieval": {"status": "unavailable", "cache_hit": False,
                                                  "error": message}}
        now = self.clock()
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?)",
                       (key, now, now + ttl, encoded))
            db.execute("DELETE FROM errors WHERE key=?", (key,))
        return {"data": value, "retrieval": {"status": "fresh", "cache_hit": False,
                "fetched_at": utc(now), "expires_at": utc(now + ttl), "age_seconds": 0}}
