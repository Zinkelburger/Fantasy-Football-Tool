#!/usr/bin/env python3
"""Typed claims — the intermediate representation between threads and notes.

The pipeline used to go thread -> per-player sentences -> prose note, and the
prose was where everything went wrong. Prose cannot be merged across threads,
cannot be date-ordered, cannot be deduped, and cannot be tested: once "Rodriguez
got the nod" and "twelve people called Tuten a bust" are the same paragraph,
nothing downstream can tell a beat report from a show of hands.

So a thread distils into claims instead, and claims carry the four things prose
loses:

    type          what kind of assertion this is
    basis         who is asserting it
    date          when, so a status claim can be superseded
    conditional_on  what would make it stop being true

`type` is the one that earns its keep. The 2025 backtest (../reddit-notes-study/)
found note *tone* added no draft edge over ADP and that hyped players mildly
underperformed — but it measured notes where a snap-count observation and a pile
of bust nominations were fused into one string. Splitting them makes the real
question askable: do usage facts beat ADP even though sentiment does not? That
is not answerable while both live in the same sentence.
"""

import json
import pathlib
import re
from collections import defaultdict
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
CLAIMS = HERE / "corpus" / "claims.jsonl"

# Ordered most to least durable. injury outranks role only in the sense that it
# expires faster, not that it matters more.
CLAIM_TYPES = {
    "injury":    "health, availability, practice participation, IR/suspension",
    "role":      "usage, snap share, depth chart, committee split, scheme fit",
    "market":    "ADP, where he actually goes, cost relative to ranking",
    "sentiment": "what the community thinks, including bare-name votes",
}

# Ordered strongest to weakest. The distinction the old pipeline could not draw.
BASIS = {
    "team_official":   "the team, a coach, or the official depth chart",
    "beat_report":     "a named beat writer or insider quoted in the thread",
    "consensus":       "several commenters independently agreeing",
    "single_commenter": "one person's opinion",
}

REQUIRED = ("player", "type", "claim", "basis", "thread")
OPTIONAL = ("conditional_on", "comment", "date", "supersedes")

# A title like "... Per Adam Schefter." or "Colts WR Josh Downs is dealing with
# a calf injury." is reporting; "Call your shot: ..." is a conversation. Thread
# kind is not decoration — news threads went deep on few players while the
# discussion threads spread thin opinion over many.
_NEWS = re.compile(r"\b(per\s+[A-Z]|report(s|ed|ing|edly)?|accord\w+ to|announc\w+|"
                   r"activat\w+|placed on|questionable|doubtful|out for|season-ending|"
                   r"injur\w+|acl|mcl|achilles|hamstring|groin|quad|calf|ankle|knee|"
                   r"shoulder|concussion|hyperextension|torn|sprain\w*|suspen\w+|"
                   r"practic\w+|depth chart|first team|1st team|reps?\b|snap counts?|"
                   r"sign(s|ed|ing)?\b|releas\w+|waiv\w+|trad(e|ed|ing)\b|"
                   r"expected to|is dealing with|said|says)\b", re.I)

# Beat-style headlines name the team and position before the player: "Colts WR
# Josh Downs is dealing with a calf injury." Nobody writes a discussion prompt
# that way, so the shape alone is a reliable tell.
_BEAT = re.compile(r"^[A-Z][A-Za-z.'-]+(\s+[A-Z][A-Za-z.'-]+)?\s+"
                   r"(QB|RB|WR|TE|K|DST|GM|HC|OC|DC)\b")

# The body gets a much narrower test than the title. Injury vocabulary is
# everywhere in a fantasy thread — the biggest-bust prompt opens "*non injury
# related preferably*" — so only an actual attribution counts as reporting.
_ATTRIB = re.compile(r"(\bper\s+[A-Z]|\baccording to\s+[A-Z]|"
                     r"\breport(s|ed|edly)\b|\bsources?\s+(say|said|tell)|"
                     r"\b(ESPN|NFL Network|The Athletic|Sports Illustrated|"
                     r"PFF|Rotoworld|Yahoo|CBS|Fox Sports)\b)")

def thread_kind(title, selftext=""):
    """'news' or 'discussion' — used to weight what comes out of a thread.

    Reads the body too, because a thread can be a bare editorial headline over
    a quoted beat report: "Crod getting the nod at RB over Tuten in key
    situations" says nothing, while the blurb underneath it is Sports
    Illustrated. Erring toward 'news' is the cheaper mistake — it only means
    reading a thread more carefully than it deserved."""
    title = title or ""
    if _BEAT.match(title) or _NEWS.search(title):
        return "news"
    head = (selftext or "")[:600]
    return "news" if _ATTRIB.search(head) else "discussion"


def thread_date(post):
    ts = post.get("created_utc")
    if not ts:
        return ""
    return datetime.fromtimestamp(float(ts), timezone.utc).date().isoformat()


def validate(claim, pool_names, known_threads=None):
    """Return a list of problems; empty means the claim is well-formed."""
    bad = []
    if not isinstance(claim, dict):
        return ["not an object"]
    for k in REQUIRED:
        if not str(claim.get(k) or "").strip():
            bad.append(f"missing {k}")
    if bad:
        return bad
    if claim["player"] not in pool_names:
        bad.append(f"{claim['player']!r} is not in the player pool")
    if claim["type"] not in CLAIM_TYPES:
        bad.append(f"type must be one of {', '.join(CLAIM_TYPES)}")
    if claim["basis"] not in BASIS:
        bad.append(f"basis must be one of {', '.join(BASIS)}")
    if known_threads is not None and claim["thread"] not in known_threads:
        bad.append(f"thread {claim['thread']!r} is not in the corpus")
    if len(str(claim["claim"])) > 400:
        bad.append("claim is over 400 chars; split it or tighten it")
    for k in claim:
        if k not in REQUIRED and k not in OPTIONAL:
            bad.append(f"unknown field {k!r}")
    return bad


def load(path=CLAIMS):
    if not pathlib.Path(path).exists():
        return []
    out = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def append(claims, path=CLAIMS):
    """Append, skipping exact duplicates already stored for the same thread."""
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    seen = {_key(c) for c in load(path)}
    fresh = [c for c in claims if _key(c) not in seen]
    if fresh:
        with open(path, "a", encoding="utf-8") as fh:
            for c in fresh:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    return len(fresh), len(claims) - len(fresh)


def _key(c):
    return (c.get("thread"), c.get("player"), c.get("type"),
            str(c.get("claim", "")).strip().lower())


def distilled_threads(path=CLAIMS):
    return {c.get("thread") for c in load(path)}


def for_player(name, path=CLAIMS):
    """One player's claims, newest first, grouped by type.

    Newest first because status claims supersede: "left practice" on the 25th
    and "just a hyperextension, could have kept playing" on the 26th are the
    same story, and only the order says which one still holds."""
    mine = [c for c in load(path) if c.get("player") == name]
    out = defaultdict(list)
    for c in sorted(mine, key=lambda c: (c.get("date") or "", c.get("thread") or ""),
                    reverse=True):
        out[c.get("type", "?")].append(c)
    return out
