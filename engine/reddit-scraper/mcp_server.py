#!/usr/bin/env python3
"""MCP server exposing the Reddit scrape + name-resolution pipeline as tools.

Lets a Claude Code session drive the whole pipeline without an OpenAI key: the
session itself is the LLM. Reddit credentials are still required (there is no
unauthenticated way to read Reddit at volume — the public .json endpoints 403),
but they're free and live in .env.

The division of labour:

    deterministic, here          model's job, in the session
    ------------------------     --------------------------------
    fetch posts + comments       adjudicate the ~6% of mentions that
    build the alias table        resolve_names flags as review/ambiguous
    resolve names to players     write the per-player markdown notes
    assemble per-player dossiers

Run standalone:  python mcp_server.py
Register:        see .mcp.json at the repo root

Tools are read-only against Reddit and write only inside this directory
(corpus/, dossiers/). Raw comment text stays local — see API-TOS.md; it may
not be republished, and this repo is public.
"""

import json
import os
import pathlib
import re
import time
from collections import Counter, defaultdict
from datetime import datetime

from mcp.server.mcpserver import MCPServer

import adjudicate as A
import claims as C
import resolve_names as R

HERE = pathlib.Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
POSTS, COMMENTS = CORPUS / "posts.jsonl", CORPUS / "comments.jsonl"
DOSSIERS = CORPUS / "dossiers"
# Where the site actually reads notes from. corpus/dossiers is a staging area;
# write_note(publish=True) copies a finished note here.
SHIPPED_NOTES = HERE.parent.parent / "data" / "notes"
LEASES = CORPUS / "leases.json"
INDEX_CACHE = CORPUS / "index_cache.json"
SKIPPED = CORPUS / "skipped.json"
NOTE_LOG = CORPUS / "notes_written.json"
LEASE_MINUTES = 45

mcp = MCPServer("ff-reddit-scraper", version="1.0.0")

_pool = None


def pool():
    """Alias table is ~2.4k keys over 337 players; build once per process."""
    global _pool
    if _pool is None:
        _pool = R.load_pool(str(HERE / "combined_with_depth.csv"))
    return _pool


def _reddit():
    from RedditQuery import RedditQuery
    return RedditQuery()


def _read_jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# --------------------------------------------------------------------- fetch

@mcp.tool()
def fetch_thread(url_or_id: str, replace_more: int = 20) -> str:
    """Fetch one Reddit thread's post and comments into the local corpus.

    Accepts a full permalink or a bare submission id. Appends to the corpus,
    deduped by id, so calling it twice is harmless. Returns a summary; use
    match_thread or player_dossier to read the content back."""
    sid = url_or_id.strip().rstrip("/").split("/comments/")[-1].split("/")[0]
    r = _reddit()
    s = r.reddit.submission(id=sid)
    s.comment_sort = "top"
    s.comments.replace_more(limit=replace_more)
    comments = s.comments.list()

    CORPUS.mkdir(exist_ok=True)
    seen_p = {row["id"] for row in _read_jsonl(POSTS)}
    seen_c = {row["id"] for row in _read_jsonl(COMMENTS)}

    added_p = 0
    if s.id not in seen_p:
        with open(POSTS, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": s.id, "title": s.title, "selftext": s.selftext,
                "score": s.score, "num_comments": s.num_comments,
                "created_utc": s.created_utc, "permalink": s.permalink}) + "\n")
        added_p = 1

    added_c = 0
    with open(COMMENTS, "a", encoding="utf-8") as f:
        for c in comments:
            if c.id in seen_c:
                continue
            f.write(json.dumps({
                "id": c.id, "post_id": s.id, "parent_id": c.parent_id,
                "score": c.score, "body": c.body,
                "created_utc": c.created_utc}) + "\n")
            added_c += 1

    return (f"{s.title!r}\nscore {s.score}, {s.num_comments} comments, id {s.id}\n"
            f"added {added_p} post, {added_c} new comments "
            f"({len(comments) - added_c} already cached)")


@mcp.tool()
def sweep_subreddit(subreddit: str = "fantasyfootball", top: int = 50,
                    hot: int = 50, new: int = 50, days: int = 60,
                    min_comments: int = 1, replace_more: int = 12,
                    require_relevance: bool = False) -> str:
    """Sweep a subreddit's top/hot/new listings into the corpus.

    Reddit search never indexes comment bodies, which is why this pulls whole
    threads instead of searching per player. Resumable: already-cached posts
    are skipped. Budget roughly 2-5 API requests per post at 100 req/min.

    require_relevance keeps only posts whose title names a draftable player or
    reads like a report. Leave it off for r/fantasyfootball. Turn it on for a
    team subreddit, which is mostly game threads, open threads and memes with
    the beat reporting scattered through — and that reporting names the player
    in the title. It is also worth turning on for r/fantasyfootballadvice and
    r/Fantasy_Football, which are largely personal rate-my-team posts: swept
    without it they contributed 233 posts of which almost none rank."""
    import time
    from datetime import datetime, timedelta

    r = _reddit()
    sub = r.reddit.subreddit(subreddit)
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()

    def relevant(post):
        if not require_relevance:
            return True
        title = post.title or ""
        return bool(_names_in(title, title) or C._BEAT.match(title)
                    or C._ATTRIB.search(title))

    cands, skipped = {}, 0
    for listing in (sub.top(time_filter="month", limit=top),
                    sub.hot(limit=hot), sub.new(limit=new)):
        for s in listing:
            if s.created_utc >= cutoff and s.num_comments >= min_comments:
                if not relevant(s):
                    skipped += 1
                    continue
                cands.setdefault(s.id, s)

    CORPUS.mkdir(exist_ok=True)
    seen_p = {row["id"] for row in _read_jsonl(POSTS)}
    seen_c = {row["id"] for row in _read_jsonl(COMMENTS)}
    todo = [s for pid, s in cands.items() if pid not in seen_p]

    added_c = 0
    with open(POSTS, "a", encoding="utf-8") as pf, \
            open(COMMENTS, "a", encoding="utf-8") as cf:
        for s in todo:
            try:
                s.comment_sort = "top"
                s.comments.replace_more(limit=replace_more)
                comments = s.comments.list()
            except Exception:
                continue
            pf.write(json.dumps({
                "id": s.id, "title": s.title, "selftext": s.selftext,
                "score": s.score, "num_comments": s.num_comments,
                "created_utc": s.created_utc, "permalink": s.permalink}) + "\n")
            for c in comments:
                if c.id in seen_c:
                    continue
                seen_c.add(c.id)
                cf.write(json.dumps({
                    "id": c.id, "post_id": s.id, "parent_id": c.parent_id,
                    "score": c.score, "body": c.body,
                    "created_utc": c.created_utc}) + "\n")
                added_c += 1
            pf.flush(); cf.flush()
            time.sleep(0.2)

    return (f"swept r/{subreddit}: {len(cands)} candidate posts, "
            f"{len(todo)} newly fetched, +{added_c} comments"
            + (f", {skipped} skipped off-topic" if skipped else "") + "\n"
            f"corpus now {len(_read_jsonl(POSTS))} posts, "
            f"{len(_read_jsonl(COMMENTS))} comments")


# ------------------------------------------------------------------ resolve

def _scan_corpus():
    """Corpus mentions with adjudicated verdicts applied."""
    for row, post, m in A.resolved_mentions(pool()):
        yield row, post.get("title", "?"), m


@mcp.tool()
def corpus_stats() -> str:
    """Mention counts per player across the whole local corpus, plus the tier
    breakdown showing how much needs LLM adjudication."""
    per, tiers = Counter(), Counter()
    for _, _, m in _scan_corpus():
        per[m.player.player_name] += 1
        tiers[m.tier] += 1
    players = pool()[0]
    zero = sum(1 for p in players if per.get(p.player_name, 0) == 0)
    lines = [f"corpus: {len(_read_jsonl(POSTS))} posts, "
             f"{len(_read_jsonl(COMMENTS))} comments",
             f"tiers: {dict(tiers)}",
             f"players with mentions: {len(per)}/{len(players)} ({zero} with none)",
             "", "busiest:"]
    lines += [f"  {n:26s} {c}" for n, c in per.most_common(25)]
    return "\n".join(lines)


@mcp.tool()
def player_dossier(player_name: str, max_chars: int = 12000,
                   include_uncertain: bool = False) -> str:
    """Every corpus sentence resolved to one player, highest-scoring first.

    This is the raw material for a draft note. By default only confidently
    resolved mentions are included; set include_uncertain to also see the ones
    review_queue would hand you."""
    target = player_name.strip().lower()
    hits = []
    for row, title, m in _scan_corpus():
        if m.player.player_name.lower() != target:
            continue
        if m.tier in ("review", "ambiguous") and not include_uncertain:
            continue
        hits.append((row.get("score", 0), title, m))
    if not hits:
        names = {p.player_name for p in pool()[0]}
        close = [n for n in names if target in n.lower()]
        return (f"No mentions for {player_name!r}."
                + (f" Did you mean: {', '.join(sorted(close)[:5])}?" if close else ""))

    p = hits[0][2].player
    out = [f"PLAYER: {p.player_name} ({p.team_name}, {p.player_depth}) — "
           f"ADP {p.player_adp} — {len(hits)} mentions", "=" * 70, ""]
    seen, used = set(), 0
    for score, title, m in sorted(hits, key=lambda h: -h[0]):
        key = m.sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        line = f"[{title[:60]!r} | score {score} | {m.tier}] {m.sentence}"
        if used + len(line) > max_chars:
            out.append(f"... truncated at {max_chars} chars "
                       f"({len(hits) - len(seen)} more mentions)")
            break
        out.append(line)
        used += len(line)
    return "\n".join(out)


@mcp.tool()
def adjudication_stats() -> str:
    """How many mentions resolved themselves, how many await your judgement."""
    return json.dumps(A.stats(pool()), indent=1)


@mcp.tool()
def next_batch(size: int = 20, chain_depth: int = 3) -> str:
    """The next batch of mentions needing adjudication, with full context.

    Each item carries the sentence with the token marked, the whole comment,
    the reply chain above it, the thread title, every candidate player's 2026
    team / position / ADP, and the players already identified in that same
    comment. Decide each one and pass your verdicts to submit_verdicts.

    The heuristic_guess field is a hint, not an answer — it leans on ADP, which
    is wrong exactly when a cheaper player shares the name."""
    items = A.build_batch(pool(), size=size, chain_depth=chain_depth)
    if not items:
        return "Nothing pending — every mention is either auto-resolved or decided."
    return A.INSTRUCTIONS + "\n" + json.dumps(items, indent=1)


@mcp.tool()
def submit_verdicts(verdicts: str) -> str:
    """Record adjudications from next_batch.

    JSON list of {"oid", "player", "note"}, where player is a full name, null
    for "not a player", or "unsure" to leave it pending. Verdicts are pinned to
    the occurrence, so the same surname can resolve differently in different
    threads. A token decided the same way three times with no contradiction is
    promoted to a global default and stops being asked about."""
    try:
        rows = json.loads(verdicts)
    except json.JSONDecodeError as e:
        return f"Could not parse verdicts as JSON: {e}"
    if isinstance(rows, dict):
        rows = [rows]
    recorded, promoted, bad = A.record(rows, pool())
    out = [f"recorded {len(recorded)} verdict(s)"]
    if promoted:
        out.append("promoted to global defaults:\n  " + "\n  ".join(promoted))
    if bad:
        out.append("rejected:\n  " + "\n  ".join(bad))
    out.append(json.dumps(A.stats(pool()), indent=1))
    return "\n".join(out)


@mcp.tool()
def roster_context(team: str = "", position: str = "", name_contains: str = "") -> str:
    """Look up players in the 2026 pool by team, position, or name fragment.

    For checking a hunch while adjudicating — whether a candidate is actually
    on the team the comment is discussing, or who a thread's other names are."""
    players = pool()[0]
    t, pos, frag = team.strip().upper(), position.strip().upper(), name_contains.strip().lower()
    hits = [p for p in players
            if (not t or p.team_name.upper() == t)
            and (not pos or str(p.player_depth).upper().startswith(pos))
            and (not frag or frag in p.player_name.lower())]
    if not hits:
        return "No players match."
    hits.sort(key=lambda p: p.player_adp)
    return "\n".join(f"{p.player_name:26s} {p.team_name:4s} {str(p.player_depth):6s} "
                      f"ADP {p.player_adp:6.1f}" for p in hits[:60])


@mcp.tool()
def resolve_text(text: str, thread_title: str = "") -> str:
    """Run the resolver over an arbitrary string. Useful for spot-checking why
    a mention did or didn't match without touching the corpus."""
    players, aliases, keys, cap, defaults, firsts = pool()
    ms = list(R.scan(text, aliases, keys, thread_title=thread_title,
                     cap_required=cap, defaults=defaults, first_names=firsts))
    if not ms:
        return "No player mentions resolved."
    return "\n".join(
        f"{m.raw!r:16s} -> {m.player.player_name:24s} [{m.tier}/{m.score}] {m.why}"
        for m in ms)


@mcp.tool()
def write_note(player_name: str, markdown: str, publish: bool = False) -> str:
    """Save a finished draft note written from player_claims.

    Writes corpus/dossiers/<Player Name>.md as a staging copy. With
    publish=True it also overwrites data/notes/<Player Name>.md, which is the
    file the site bundles — build_deploy.py picks it up on the next build."""
    names = {p.player_name.lower(): p.player_name for p in pool()[0]}
    canon = names.get(player_name.strip().lower())
    if not canon:
        return f"{player_name!r} is not in the player pool; note not written."
    DOSSIERS.mkdir(parents=True, exist_ok=True)
    path = DOSSIERS / f"{canon}.md"
    path.write_text(markdown, encoding="utf-8")
    def _log():
        log = _read_note_log()
        log[canon] = {"ts": time.time(),
                      "claims": len([c for c in C.load() if c.get("player") == canon])}
        NOTE_LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    _with_lock(_log)
    msg = f"wrote {path.relative_to(HERE)} ({len(markdown)} chars)"
    if publish:
        SHIPPED_NOTES.mkdir(parents=True, exist_ok=True)
        (SHIPPED_NOTES / f"{canon}.md").write_text(markdown, encoding="utf-8")
        msg += f"\npublished to data/notes/{canon}.md"
    if "as of" not in markdown[:300]:
        msg += "\nwarning: no 'as of <date>' in the header — readers cannot tell how stale it is"
    return msg


def _with_lock(fn, retries=60):
    """Run fn under a crude exclusive lock so parallel agents can claim work.

    A fleet of subagents all calling next_threads at once will otherwise read
    the same file, pick the same threads, and distil them twice. O_EXCL on a
    lockfile is enough here: single machine, short critical section."""
    lock = CORPUS / ".lease.lock"
    CORPUS.mkdir(exist_ok=True)
    for _ in range(retries):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 120:
                    lock.unlink(missing_ok=True)      # stale, holder died
            except OSError:
                pass
            time.sleep(0.1)
            continue
        try:
            os.close(fd)
            return fn()
        finally:
            lock.unlink(missing_ok=True)
    return fn()          # lock never came free; better to race than to hang


def _read_note_log():
    try:
        return json.loads(NOTE_LOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_skipped():
    try:
        return json.loads(SKIPPED.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _done_threads():
    """Threads that need no more reading: distilled, or read and found empty."""
    return C.distilled_threads() | set(_read_skipped())


def _read_leases():
    try:
        return json.loads(LEASES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _live_leases(now=None, leases=None, done=None):
    """Leases still worth honouring: not expired, and not on finished work.

    A lease on a thread that has since been distilled or released is dead
    whatever its timestamp — an agent that crashed after submitting would
    otherwise keep the thread out of the queue for the rest of its 45 minutes."""
    now = now or time.time()
    done = _done_threads() if done is None else done
    return {k: v for k, v in (_read_leases() if leases is None else leases).items()
            if now - v.get("ts", 0) < LEASE_MINUTES * 60 and k not in done}


def _mention_index(rebuild=False):
    """Returns (index, chars): per post, who is mentioned how often with their
    ADP, and how many characters of comment text the thread holds.

    Counts, not presence. Whether a thread is *about* a player is a question
    about concentration, and presence cannot answer it: a bust megathread names
    forty early-round players once each and says nothing about any of them.

    Cached per post, because this is the hot path for the whole fleet. The
    corpus reached 116k comments and a full resolver pass crossed two minutes —
    paid again by every worker on every next_threads call. Comments are
    append-only and a post is fetched whole, so a post already in the cache
    never needs rescanning; only new posts are resolved.

    The cache is keyed by the alias table's own size so that editing
    non_players.json or the player pool invalidates it. Registering a coach has
    to change the counts, or the index would keep recommending threads on the
    strength of mentions the resolver no longer makes."""
    players, aliases, keys, cap, defaults, firsts = pool()
    # The resolver's own source is part of the key: a rule change alters the
    # counts just as surely as a pool change, and a cache that survived an edit
    # would keep recommending threads on mentions the resolver no longer makes.
    src = HERE / "resolve_names.py"
    # "v2" is the cache layout. Bump it whenever the stored shape changes: a
    # stale cache in the previous shape reads as every post having no mentions
    # and no text, which does not error, it just silently ranks everything zero.
    # The non-player registry is deliberately NOT in the key. Workers register
    # dozens of coaches and linemen while reading, and rebuilding a 95-second
    # index after each one made next_threads block for minutes — the exact
    # stall the cache was added to remove. Registering shifts a handful of
    # counts; the index is a ranking aid, and a ranking does not need to be
    # exact. Force a refresh with _mention_index(rebuild=True) or by deleting
    # the file.
    stamp = (f"v3:{len(players)}:{len(aliases)}:"
             f"{int(src.stat().st_mtime) if src.exists() else 0}")
    cached = {}
    if not rebuild:
        try:
            blob = json.loads(INDEX_CACHE.read_text(encoding="utf-8"))
            if blob.get("stamp") == stamp:
                cached = blob.get("posts", {})
        except (OSError, json.JSONDecodeError):
            cached = {}

    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    todo = {pid for pid in posts if pid not in cached}
    if todo:
        fresh, size = defaultdict(Counter), Counter()
        for c in _read_jsonl(COMMENTS):
            pid = c.get("post_id")
            if pid not in todo:
                continue
            body = c.get("body") or ""
            size[pid] += len(body)
            for m in R.scan(body, aliases, keys,
                            thread_title=posts[pid].get("title", ""),
                            cap_required=cap, defaults=defaults, first_names=firsts):
                if m.tier not in ("review", "ambiguous"):
                    fresh[pid][m.player.player_name] += 1
        # The title is the most authoritative statement of what a thread is
        # about, and it was not being read at all: "Ravens WR Zay Flowers
        # didn't practice today" indexed as Ja'Kobi Lane and Mark Andrews,
        # because those are who the comments mention. Two workers reported the
        # same shape independently. A title mention counts double — a beat
        # report names its subject once and the room then argues about
        # somebody else.
        for pid in todo:
            head = f"{posts[pid].get('title', '')}\n{posts[pid].get('selftext', '')[:600]}"
            for m in R.scan(head, aliases, keys,
                            thread_title=posts[pid].get("title", ""),
                            cap_required=cap, defaults=defaults, first_names=firsts):
                if m.tier not in ("review", "ambiguous"):
                    fresh[pid][m.player.player_name] += 2
        for pid in todo:
            cached[pid] = {"n": dict(fresh.get(pid, {})), "c": size.get(pid, 0)}
        try:
            INDEX_CACHE.write_text(json.dumps({"stamp": stamp, "posts": cached}),
                                   encoding="utf-8")
        except OSError:
            pass

    by_name = {p.player_name: p for p in players}
    index, chars = {}, {}
    for pid, row in cached.items():
        names = row.get("n") or {}
        chars[pid] = row.get("c", 0)
        if names:
            index[pid] = (Counter(names),
                          {n: getattr(by_name.get(n), "player_adp", 999) for n in names})
    return index, chars


def _thread_priority(post, comment_chars, mention_index, explain=False):
    """What is this thread worth reading? Higher is sooner.

    Not all 272 undistilled threads deserve equal attention, and a fleet that
    starts at the top of an arbitrary list spends its first hour on rate-my-team
    dailies. Ranked by: reporting over opinion, players people actually draft,
    recency (a September practice report supersedes an August one), and size —
    with size capped, because an 800-comment joke thread carries less than a
    100-comment beat report."""
    title = post.get("title", "")
    why = []
    if re.match(r"^Official:\s*\[", title):
        # The daily rate-my-team / who-do-I-draft / trade threads. They are 6%
        # of the corpus by text and almost none of it is a claim: roster dumps
        # and one-line verdicts on them. thread_kind even calls the Trade
        # thread "news", because the word trade is in it. Sink them below
        # everything real rather than nudging — they are still claimable once
        # the 264 genuine threads are done.
        return (-1000.0, ["daily churn thread"]) if explain else -1000.0
    score = 0.0
    if _ADVICE.search(title):
        score -= 55; why.append("somebody's own roster question")
    # A transaction report about an offensive lineman reads exactly like one
    # about a running back — "waived", "cut", "trading", "designated to IR" are
    # the same words either way. What separates them is whether the title names
    # somebody draftable. "Saints waived RB Devin Neal" does; "The Eagles
    # waived both Uar Bernard and Joshua Weru" does not, and neither does "On
    # this day in 1995, Jimmy Smith was released by the Eagles".
    #
    # This test only became usable once the resolver stopped reading a surname
    # wearing someone else's first name as a player; before that every one of
    # those titles resolved to a real player and the check would have passed
    # them all.
    named = _names_in(title, title)
    if _REPORTING.search(title) or C._BEAT.match(title):
        if named:
            score += 40
            why.append("beat report on " + ", ".join(sorted(named)[:3]))
        else:
            score -= 25
            why.append("reports a move, but names nobody draftable")
    elif C.thread_kind(title, post.get("selftext", "")) == "news":
        score += 8; why.append("news vocabulary, no attribution")
    elif named:
        score += 12; why.append("title names " + ", ".join(sorted(named)[:3]))
    if re.search(r"\bAMA\b|ask me anything|ask us anything|we host", title, re.I):
        # An AMA is labelled discussion and reads like a goldmine — a named
        # analyst answering questions all day. Measured over the first 27
        # distilled threads it is the worst value in the corpus: the Ringer AMA
        # produced ONE team-official-or-beat-report claim from 149k characters,
        # and three other AMAs produced none at all from 130k more. What they
        # generate is opinion, in volume, which the 2025 backtest priced at zero.
        score -= 45; why.append("AMA — measured near-zero hard claims")
    # Size is a cost, not a benefit. Hard claims (team_official or beat_report)
    # per 10k characters, over the first 27 threads distilled:
    #
    #   Crod getting the nod over Tuten     16k chars   3.64
    #   Chase not practicing today           4k chars   2.23
    #   Puka left practice early            20k chars   2.02
    #   ...
    #   Ringer Fantasy Football Show AMA   149k chars   0.07
    #   Who are you fading for no reason   115k chars   0.00
    #   punting TE is the way to go        100k chars   0.00
    #
    # A thread needs enough substance to be worth opening, and past that every
    # extra character is reading labour buying sentiment. So: a bonus for
    # clearing a floor, then a penalty that grows with length.
    score += 8 if comment_chars >= 3000 else comment_chars / 400.0
    over = max(comment_chars - 25000, 0) / 6000.0
    if over > 3:
        score -= over; why.append(f"long ({comment_chars//1000}k chars) — costs reading, yields opinion")
    else:
        score -= over
    score += min(post.get("score", 0), 3000) / 400.0
    # players in it that people actually draft
    # Focus, not breadth. The threads that produced hard claims were about one
    # or two players — "Crod getting the nod over Tuten" (16k chars, 3.64 hard
    # per 10k), "Chase not practicing today" (4k, 2.23). The threads that
    # produced none named forty players once each. Counting distinct players
    # ranks the second kind top, which is backwards, so score the share of the
    # thread's mentions held by its top three names.
    counts, adps = mention_index.get(post.get("id"), (Counter(), {}))
    total = sum(counts.values())
    if total >= 5:
        top3 = counts.most_common(3)
        focus = sum(k for _, k in top3) / total
        score += 26 * focus
        lead, lead_n = top3[0]
        if adps.get(lead, 999) <= 60:
            score += 8
        elif adps.get(lead, 999) <= 150:
            score += 4
        names = ", ".join(n for n, _ in top3)
        if focus >= 0.45:
            why.append(f"focused on {names} ({focus:.0%} of mentions)")
        else:
            why.append(f"spread over {len(counts)} players, no focus ({focus:.0%} top three)")
        score -= min(len(counts), 60) / 5.0
    ts = post.get("created_utc") or 0
    age_days = max((time.time() - ts) / 86400.0, 0)
    score += max(12 - age_days, -10)
    if age_days <= 3:
        why.append("fresh")
    return (score, why) if explain else score


# Somebody's own roster question. These are the dominant form on
# r/fantasyfootballadvice and r/Fantasy_Football, and they defeat both halves of
# the score: they are short, and they are maximally focused, because a trade
# question names exactly the two or three players being traded. They also trip
# the news test, since thread_kind counts the word "trade" as reporting. What
# they contain is one person's league and a dozen one-line verdicts on it —
# nothing that generalises to a draft note.
_ADVICE = re.compile(
    r"^\s*(should|would|who|which|what|is|are|am|do|does|can|could|help|"
    r"thoughts?|rate|need|any)\b.*\?|"
    r"\b(should i|would you|who do i|who should i|rate my|my team|my league|"
    r"help me|thoughts on my|am i|did i|worth it|i just (got|drafted|traded)|"
    r"trade\s+\w+\s+for\b|for\s+\w+\?|start\s+\w+\s+or\b|\bor\b.*\?)",
    re.I)

# A beat report, not merely a title containing injury or transaction words.
# thread_kind is deliberately loose because erring toward "news" only costs a
# careful read; ranking cannot afford that, so it asks for the shape.
_REPORTING = re.compile(
    r"\bper\s+@?[A-Z]|\baccording to\s+[A-Z]|\breport(s|ed|edly)\b|"
    r"\bsources?\s+(say|said|tell)|\b(returned?|placed|activated|waived|"
    r"released|signed|claimed|ruled)\b|\b(did not|didn't|limited|full)\s+"
    r"practic\w*|\bpractice (today|report|participation)\b|"
    r"\b(questionable|doubtful|out for|season-ending|IR|PUP)\b", re.I)


_BOARD = {}


def _board_row(name):
    """Bye week and board rank, read from the half-PPR board the site ships.

    The note header carries both, and looking them up by hand is a step that
    invites a wrong number in a file nothing validates."""
    if not _BOARD:
        import csv
        f = HERE.parent.parent / "data" / "ranks" / "0.5_ppr_with_depth.csv"
        if f.exists():
            with open(f, encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    _BOARD[row["Player"]] = (row.get("Rank"), row.get("Bye"))
    return _BOARD.get(name, (None, None))


def _names_in(text, title=""):
    """Confidently resolved player names in one piece of text."""
    players, aliases, keys, cap, defaults, firsts = pool()
    return {m.player.player_name
            for m in R.scan(text or "", aliases, keys, thread_title=title,
                            cap_required=cap, defaults=defaults, first_names=firsts)
            if m.tier not in ("review", "ambiguous")}


def _vote_tally(post_id, title):
    """Per-player count of TOP-LEVEL comments naming them, plus their upvotes.

    "Call your shot" threads are show-of-hands threads: 305 top-level replies
    to the biggest-bust prompt, 186 of them naming exactly one player. A model
    cannot count those from a digest that had to truncate at 60k chars, and
    counting is not a job that needs a model anyway. Upvotes are the part the
    count alone hides — Jeremiyah Love drew 14 nominations carrying 1,324
    upvotes, McCaffrey 18 carrying 29. The room agreed with one and shrugged at
    the other.

    It is a tally of *mentions in a nomination slot*, not of agreement: a reply
    that says "not Achane" counts for Achane. Label it as such."""
    votes, ups = Counter(), Counter()
    top_level = singles = 0
    for c in _read_jsonl(COMMENTS):
        if c.get("post_id") != post_id or not (c.get("parent_id") or "").startswith("t3_"):
            continue
        top_level += 1
        names = _names_in(c.get("body") or "", title)
        if len(names) == 1:
            singles += 1
        for n in names:
            votes[n] += 1
            ups[n] += max(c.get("score") or 0, 0)

    # Only a show-of-hands thread has a meaningful tally. An AMA does not: its
    # top-level comments are questions, and greetings resolve to players —
    # "Love the show" gave Jeremiyah Love ten nominations in the Ringer AMA,
    # and "Hey Brandon" reached Brandon Aubrey. The shape tells them apart. In
    # the biggest-bust thread 187 of 305 top-level comments name exactly one
    # player (61%); in the AMA it is 111 of 649 (17%).
    if top_level < 25 or singles / max(top_level, 1) < 0.35:
        return []
    return [(n, k, ups[n]) for n, k in votes.most_common()]


def _threads_for(player_name):
    """Threads mentioning one player: (post, confident mentions, uncertain)."""
    per = {}
    for row, post, m in A.resolved_mentions(pool()):
        if m.player.player_name != player_name:
            continue
        pid = post.get("id") or row.get("post_id")
        sure, unsure = per.get(pid, (0, 0))
        if m.tier in ("review", "ambiguous"):
            per[pid] = (sure, unsure + 1)
        else:
            per[pid] = (sure + 1, unsure)
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    return [(posts.get(pid, {"id": pid}), k, q) for pid, (k, q) in per.items()]


def _thread_tree(post_id):
    """Comments of one post, nested under their parents, chronological."""
    kids = {}
    for c in _read_jsonl(COMMENTS):
        if c.get("post_id") != post_id:
            continue
        parent = (c.get("parent_id") or "")
        key = parent[3:] if parent.startswith("t1_") else None
        kids.setdefault(key, []).append(c)
    for v in kids.values():
        v.sort(key=lambda c: float(c.get("created_utc") or 0))
    return kids


@mcp.tool()
def thread_digest(post_id: str = "", max_chars: int = 60000,
                  min_score: int = None, page: int = 1,
                  prune: bool = True) -> str:
    """One whole thread — title, body, and the full reply tree — plus the
    resolver's index of which players appear in it.

    This is the thread-first path, and it is the one to reach for when writing
    notes. player_dossier hands over isolated sentences, which strips exactly
    the context that decides what they mean: "Gibbs, Chase and CeeDee are safe
    barring an injury to Goff/Burrow/Allen" is reassuring for the first three
    and a warning about the last three, and a lone sentence in six dossiers
    cannot say which. Whole threads also show a bare "Jeremiyah Love" in a
    call-your-shot thread for what it is — a vote, not an argument — and let
    you recognise people who are not in the draft pool at all, where the
    resolver can only shred them into whoever shares their name (Pop Douglas
    becoming Isiah Pacheco plus Caleb Douglas).

    Call with no post_id to list what the corpus holds. Reading whole threads
    costs about twice what the sentence extracts do and reads each comment
    exactly once, versus once per player mentioned in it.

    A thread longer than max_chars is paged: page=2 returns the next slice of
    the same reply tree, and the footer says how many pages there are. prune
    drops downvoted comments and short nameless leaves — joke chains, "water
    is wet", "who?" — but keeps any comment with a substantive descendant. On
    this corpus that removes 10-20% of characters and almost no claims."""
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    if not post_id:
        counts = Counter(c.get("post_id") for c in _read_jsonl(COMMENTS))
        out = ["threads in corpus (id | comments | title)", "=" * 70]
        for pid, p in sorted(posts.items(), key=lambda kv: -counts.get(kv[0], 0)):
            out.append(f"{pid}  {counts.get(pid, 0):>4}  {p.get('title', '')[:88]}")
        return "\n".join(out)

    post_id = post_id.strip().rsplit("/", 1)[-1] if "/" in post_id else post_id.strip()
    post = posts.get(post_id)
    if not post:
        return (f"No thread {post_id!r} in corpus. Call thread_digest() with no "
                f"arguments to list what is here, or fetch_thread first.")

    players, aliases, keys, cap, defaults, firsts = pool()
    tree = _thread_tree(post_id)

    # index first: who is in here, and how sure are we
    seen = Counter()
    uncertain = Counter()
    for c in _read_jsonl(COMMENTS):
        if c.get("post_id") != post_id:
            continue
        for m in R.scan(c.get("body") or "", aliases, keys,
                        thread_title=post.get("title", ""), cap_required=cap,
                        defaults=defaults, first_names=firsts):
            if m.tier in ("review", "ambiguous"):
                uncertain[m.player.player_name] += 1
            else:
                seen[m.player.player_name] += 1

    by_name = {p.player_name: p for p in players}
    out = [f"THREAD {post_id} — {post.get('title', '')}",
           f"score {post.get('score', 0)} · {post.get('num_comments', 0)} comments "
           f"· https://reddit.com{post.get('permalink', '')}", "=" * 74]
    if post.get("selftext", "").strip():
        out += ["", post["selftext"].strip(), "=" * 74]

    out += ["", "PLAYERS THE RESOLVER FOUND HERE (name · team · pos · ADP · mentions)",
            "-" * 74]
    for n, k in seen.most_common():
        p = by_name.get(n)
        q = uncertain.get(n, 0)
        out.append(f"  {n:26} {getattr(p, 'team_name', '?'):4} "
                   f"{getattr(p, 'player_depth', '?'):5} ADP {getattr(p, 'player_adp', 0):>6.1f}  "
                   f"x{k}" + (f" (+{q} uncertain)" if q else ""))
    only_q = [n for n in uncertain if n not in seen]
    if only_q:
        out.append("  -- uncertain only, treat as unconfirmed: " + ", ".join(sorted(only_q)))
    tally = _vote_tally(post_id, post.get("title", ""))
    if len(tally) >= 5 and sum(k for _, k, _ in tally) >= 20:
        out += ["", "TOP-LEVEL NOMINATIONS (player · top-level comments naming him · their upvotes)",
                "-" * 74,
                "  Counted by the resolver, not read. A reply saying 'not X' still counts",
                "  for X. Use these as the counts for bare-name sentiment claims instead of",
                "  tallying by hand; use the upvotes to tell what the room agreed with."]
        out += [f"  {n:26} x{k:<4} ↑{u}" for n, k, u in tally[:25]]

    out += ["", "The index is a retrieval aid, not an answer. It is about 98% right on",
            "which player a name refers to, but it cannot tell whether a sentence is",
            "*about* that player, and it silently maps players outside the 337-man",
            "pool onto whoever shares their name. Trust the thread text over it.",
            "", "=" * 74, "", "COMMENTS", "-" * 74]

    # Which comments survive pruning: a comment stays if it is not downvoted
    # and either names a player or has something to say (length), or if any
    # reply under it stays — context for a kept reply is worth keeping.
    keep = {}
    title = post.get("title", "")

    def decide(c):
        body = (c.get("body") or "").strip()
        own = (c.get("score") or 0) >= 1 and (len(body) >= 100 or bool(_names_in(body, title)))
        kids_kept = [decide(k) for k in tree.get(c["id"], [])]
        keep[c["id"]] = own or any(kids_kept)
        return keep[c["id"]]

    if prune:
        for c in tree.get(None, []):
            decide(c)

    blocks = []

    def walk(parent_key, depth):
        for c in tree.get(parent_key, []):
            if prune and not keep.get(c["id"]):
                continue
            if min_score is not None and (c.get("score") or 0) < min_score:
                continue
            pad = "  " * depth
            head = f"{pad}[{c['id']} · {c.get('score', 0)} pts]"
            body = "\n".join(pad + "  " + ln
                             for ln in (c.get("body") or "").strip().splitlines())
            blocks.append(f"{head}\n{body}\n")
            walk(c["id"], depth + 1)

    walk(None, 0)

    # Page the reply tree by character budget, header excluded, so a 117k-char
    # thread is three calls rather than one truncated one.
    budget = max(max_chars - len("\n".join(out)), 5000)
    pages, cur, used = [], [], 0
    for b in blocks:
        if cur and used + len(b) > budget:
            pages.append(cur); cur, used = [], 0
        cur.append(b); used += len(b)
    if cur:
        pages.append(cur)
    n_pages = max(len(pages), 1)
    page = min(max(page, 1), n_pages)
    if pages:
        out += pages[page - 1]
    dropped = sum(1 for c in tree.values() for x in c) - len(blocks)
    foot = [f"-- page {page} of {n_pages} · {len(blocks)} comments shown"
            + (f" · {dropped} pruned (prune=False to see them)" if dropped else "")]
    if page < n_pages:
        foot.append(f"   call again with page={page + 1} for the rest before distilling.")
    out += [""] + foot
    return "\n".join(out)


@mcp.tool()
def distill_thread(post_id: str = "", max_chars: int = 60000, page: int = 1,
                   prune: bool = True) -> str:
    """Hand over one thread plus the contract for turning it into claims.

    This is step one of the two-step note pipeline: distil each thread into
    typed claims, then merge a player's claims into a note. Reading whole
    threads is what makes the claims trustworthy — the sentence extracts
    player_dossier returns cannot tell you that "Rodriguez got the nod" and
    "LeQuint Allen is out for camp" are the same fact, and a note written from
    them will report a permanent role change that is actually a temporary
    vacancy.

    Distil the thread, then call submit_claims. Skip anything you would not
    want to read back in a draft room."""
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    if not post_id:
        done = C.distilled_threads()
        counts = Counter(c.get("post_id") for c in _read_jsonl(COMMENTS))
        out = ["threads (id | comments | kind | distilled | title)", "=" * 76]
        for pid, p in sorted(posts.items(), key=lambda kv: -counts.get(kv[0], 0)):
            t = p.get("title", "")
            out.append(f"{pid}  {counts.get(pid, 0):>4}  {C.thread_kind(t, p.get('selftext', '')):<10} "
                       f"{'yes' if pid in done else '--':<9} {t[:60]}")
        out.append("")
        out.append("news threads go deep on a few players; discussion threads spread")
        out.append("thin opinion over many. Weight what you take out accordingly.")
        return "\n".join(out)

    pid = post_id.strip().rstrip("/").rsplit("/", 1)[-1]
    post = posts.get(pid)
    if not post:
        return f"No thread {pid!r} in corpus. Call distill_thread() to list, or fetch_thread first."

    already = [c for c in C.load() if c.get("thread") == pid]
    warn = ""
    if already:
        who = Counter(c["player"] for c in already)
        warn = (f"\n*** ALREADY DISTILLED: {len(already)} claims from this thread are "
                f"stored, covering {', '.join(n for n, _ in who.most_common(8))}"
                + ("..." if len(who) > 8 else "") + ".\n"
                f"    Distilling it again produces near-duplicates — the dedupe key is "
                f"the exact\n    claim text, so a reworded version of the same fact is "
                f"stored twice. Only\n    continue if you are deliberately adding what "
                f"the first pass missed.\n")
    body = warn + thread_digest(pid, max_chars=max_chars, page=page, prune=prune)
    types = "\n".join(f"      {k:<10} {v}" for k, v in C.CLAIM_TYPES.items())
    basis = "\n".join(f"      {k:<18} {v}" for k, v in C.BASIS.items())
    return f"""{body}

{'=' * 74}
YOUR JOB: turn this thread into typed claims, then call submit_claims.

thread kind: {C.thread_kind(post.get('title', ''), post.get('selftext', ''))}   date: {C.thread_date(post)}

Each claim is one assertion about one player:

  player           exact pool name (the index above lists them)
  type             one of:
{types}
  claim            the assertion, under 400 chars, in your words
  basis            one of:
{basis}
  thread           "{pid}"
  comment          optional comment id, for traceability
  conditional_on   optional — what would make this stop being true.
                   This field is why whole threads are worth reading:
                   "Rodriguez is the pass-protection back" is misleading
                   without "while LeQuint Allen is out for camp".
  supersedes       optional — what this claim overtakes. A thread id when the
                   earlier report is its own thread, or a short phrase when
                   the correction sits inside this one ("the practice-exit
                   report earlier in this thread"). Swift leaving practice and
                   Schefter calling it a cramp the next day is one story with a
                   direction; without this the note reports both as live. You
                   will sometimes read the later thread first — say so in the
                   phrase rather than leaving the pair unordered.

Rules that matter:

  - Record what the thread SAYS, not what you believe. A wrong consensus is
    still a fact about the market.
  - Do not let one sentence become a claim for every player it names. "Gibbs,
    Chase and CeeDee are safe barring an injury to Goff/Burrow/Allen" is one
    claim about three players being safe and a different claim about three
    others being risks — never the same claim six times.
  - Bare-name votes ("Jeremiyah Love." in a bust thread) are ONE sentiment
    claim per player with a count, not one claim per comment. The TOP-LEVEL
    NOMINATIONS block above has the counts and upvotes; cite them.
  - If the footer says there are more pages, read every page before
    submitting — the second half of a thread is where the replies to the
    prompt turn into arguments.
  - People who are not in the pool — Pop Douglas, Calvin Austin, Matt Nagy,
    Andy Reid — get no claims. The index will sometimes have mapped them onto
    a pool player who shares a name; ignore it when the thread disagrees, and
    call report_non_player so the next reader does not have to notice it
    again. That registry is the only part of the resolver that learns.
  - Nothing worth saying about a player means no claim for that player. An
    empty distillation of a thin thread is a correct answer — give it with
    release_thread(id, reason), which frees the lease and stops the thread
    coming back. Never invent a filler claim to have something to submit.
  - A claim is about ONE player. When a thread argues that two players
    cannibalize each other, that is two claims, and the other name belongs in
    conditional_on — each player's note has to stand on its own.
  - Strategy is not a claim. "Punt TE", "TE1 to TE12 is only four points a
    week", "take RBs in the first three rounds" are about the draft, not about
    a player, and forcing them into sentiment claims for whoever got named
    loses the argument and pollutes the player. Skip them; that work lives in
    engine/league-sim/findings/.
  - An AMA host, a national ranker or a podcaster is basis "analyst" — he has
    no access a beat writer has, but the room weights him more than one
    commenter.

Return them through submit_claims as a JSON array."""


@mcp.tool()
def submit_claims(claims_json: str) -> str:
    """Validate and store claims produced by distill_thread.

    Rejects the whole batch if any claim is malformed, so a typo cannot half-
    write a thread's distillation."""
    try:
        batch = json.loads(claims_json)
    except json.JSONDecodeError as e:
        return f"not valid JSON: {e}"
    if isinstance(batch, dict):
        batch = [batch]
    if not isinstance(batch, list) or not batch:
        return "expected a non-empty JSON array of claims"

    names = {p.player_name for p in pool()[0]}
    threads = {p["id"] for p in _read_jsonl(POSTS)}
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    problems = []
    for i, c in enumerate(batch):
        for msg in C.validate(c, names, threads):
            problems.append(f"  [{i}] {msg}")
    if problems:
        return ("nothing stored — fix these and resubmit:\n" + "\n".join(problems[:25])
                + (f"\n  ... and {len(problems) - 25} more" if len(problems) > 25 else ""))

    for c in batch:
        c.setdefault("date", C.thread_date(posts.get(c["thread"], {})))
    added, dupes = C.append(batch)
    def _release():
        leases = _read_leases()
        for t in {c["thread"] for c in batch}:
            leases.pop(t, None)
        LEASES.write_text(json.dumps(leases, indent=1), encoding="utf-8")
    _with_lock(_release)
    by_type = Counter(c["type"] for c in batch)
    return (f"stored {added} claims"
            + (f" ({dupes} already present)" if dupes else "")
            + " — " + ", ".join(f"{k}:{v}" for k, v in by_type.most_common())
            + f"\ncorpus now holds {len(C.load())} claims across "
              f"{len(C.distilled_threads())} threads")


@mcp.tool()
def player_claims(player_name: str) -> str:
    """Everything distilled about one player, newest first, grouped by type.

    This is the input to the note — step two. Order matters: "left practice"
    and "just a hyperextension, could have kept playing" are the same story
    two days apart, and only the dates say which one still stands.

    Write the note from these, not from player_dossier."""
    names = {p.player_name.lower(): p.player_name for p in pool()[0]}
    canon = names.get(player_name.strip().lower())
    if not canon:
        return f"{player_name!r} is not in the player pool."
    grouped = C.for_player(canon)
    if not grouped:
        return (f"No claims for {canon} yet. Distil the threads that mention "
                f"him first:\n" + player_threads(canon))

    p = {x.player_name: x for x in pool()[0]}[canon]
    rank, bye = _board_row(canon)
    today = datetime.now().date().isoformat()
    header = (f"**{canon}** ({p.team_name}, {str(p.player_depth)[:2]}, bye {bye or '?'})"
              f" — board rank {rank or '?'} · as of {today}")
    out = [f"{canon} — {p.team_name} {p.player_depth} — ADP {p.player_adp}", "=" * 74,
           "", f"Header line for the note, ready to paste (the date is today, "
           f"generated now):", "  " + header]
    for t in C.CLAIM_TYPES:
        rows = grouped.get(t)
        if not rows:
            continue
        out += ["", f"{t.upper()}  ({len(rows)})", "-" * 74]
        for c in rows:
            out.append(f"  {c.get('date', '?')} [{c.get('basis', '?')}] {c['claim']}")
            if c.get("conditional_on"):
                out.append(f"           ^ only while: {c['conditional_on']}")
            out.append(f"           ^ thread {c.get('thread', '?')}")
    out += ["", "=" * 74,
            "Newest first within each block. A later injury/role claim supersedes",
            "an earlier one; say so in the note rather than reporting both as live.",
            "Weight by basis: " + " > ".join(C.BASIS) + ".",
            "A later claim supersedes an earlier one on the same fact ONLY if its",
            "basis is at least as strong. A weaker later mention is usually lag —",
            "a commenter repeating a hamstring two days after the beat writer",
            "reported full practice is not news, it is someone who missed the news.",
            "sentiment is what the market thinks, which is worth recording and worth",
            "trusting less than the rest — the 2025 backtest found tone added no edge.",
            "",
            "NOTE FORMAT (what write_note expects; the site reads data/notes/*.md):",
            "  the header line printed at the top of this output, verbatim",
            "  **Room sentiment:** one line of substance, no superlatives.",
            "  - bullets: injury and role first, with basis ('per beat report',",
            "    'one commenter'), dates when a status changed, and what it is",
            "    conditional on. Market and sentiment last. Quote the thread where",
            "    the wording is the evidence. No invented stat ranges.",
            "  **Draft take:** one sentence. The site previews a note by its last",
            "  line, so this is the line people see on the board.",
            "  Say 'nothing new since <date>' rather than padding a thin player.",
            "", "Undistilled threads that mention him are listed by player_threads."]
    return "\n".join(out)


@mcp.tool()
def player_threads(player_name: str) -> str:
    """Every corpus thread that mentions one player, busiest first, with
    whether it has been distilled yet.

    This is the retrieval step for refreshing a note: it says which threads
    still need reading before player_claims is complete for him. Only
    confidently resolved mentions count toward the order; uncertain ones are
    shown separately."""
    names = {p.player_name.lower(): p.player_name for p in pool()[0]}
    canon = names.get(player_name.strip().lower())
    if not canon:
        return f"{player_name!r} is not in the player pool."
    rows = _threads_for(canon)
    if not rows:
        return f"No thread in the corpus mentions {canon}."
    done = C.distilled_threads()
    out = [f"{canon}: {sum(k for _, k, _ in rows)} mentions across {len(rows)} threads",
           "id       date        kind        distilled  mentions  title", "-" * 78]
    for post, k, q in sorted(rows, key=lambda r: -r[1]):
        pid = post.get("id", "?")
        out.append(f"{pid:8} {C.thread_date(post):11} "
                   f"{C.thread_kind(post.get('title', ''), post.get('selftext', '')):11} "
                   f"{'yes' if pid in done else '--':10} x{k:<3}"
                   + (f"(+{q}?) " if q else "      ")
                   + f" {post.get('title', '')[:44]}")
    todo = [p for p, _, _ in rows if p.get("id") not in done]
    if todo:
        out.append(f"\n{len(todo)} thread(s) not yet distilled — distill_thread them, "
                   f"then player_claims.")
    return "\n".join(out)


@mcp.tool()
def note_queue(limit: int = 40, include_silent: bool = False) -> str:
    """Which players need a note written or rewritten, most urgent first.

    A note is stale when a claim newer than the note exists. Injury and role
    claims from a beat report or the team outrank everything else — they are
    the facts the 2025 backtest says matter, and the ones that change daily in
    late August. Sentiment-only players go last.

    include_silent adds the players the corpus never mentioned. They still need
    a note for a complete pass, and "nobody is talking about this player" is
    itself the finding — no hype, no reported role change, no injury chatter.
    Writing that honestly is the job; padding it is not."""
    all_c = C.load()
    if not all_c:
        return "No claims yet — distill_thread first."
    by_p = defaultdict(list)
    for c in all_c:
        by_p[c["player"]].append(c)
    if include_silent:
        for p in pool()[0]:
            by_p.setdefault(p.player_name, [])
    basis_rank = {b: i for i, b in enumerate(C.BASIS)}
    logged = _read_note_log()
    type_rank = {t: i for i, t in enumerate(C.CLAIM_TYPES)}

    def note_date(name):
        """The 'as of' date in the note header. A note without one is
        'undated' — file mtime is a git-checkout time, not a writing time, and
        the shipped Chase note carried an mtime two days after a knee injury
        it knew nothing about."""
        best = None
        for d in (SHIPPED_NOTES, DOSSIERS):
            f = d / f"{name}.md"
            if f.exists():
                m = re.search(r"as of (\d{4}-\d{2}-\d{2})",
                              f.read_text(encoding="utf-8", errors="ignore")[:300])
                best = max(best or "", m.group(1) if m else "undated")
        return best

    rows = []
    for name, cs in by_p.items():
        newest = max([c.get("date") or "" for c in cs], default="")
        strongest = min([(type_rank.get(c["type"], 9), basis_rank.get(c["basis"], 9))
                         for c in cs], default=(9, 9))
        nd = note_date(name)
        # Dates alone are too coarse for an unattended pass: a note written at
        # noon and three claims stored at three o'clock are the same calendar
        # day, so the note reads as current when it never saw them. The log
        # records how many claims each note was actually written from.
        seen = logged.get(name, {}).get("claims")
        if nd is None:
            status = "missing"
        elif nd == "undated":
            status = "undated"
        elif seen is None:
            # A note with no log entry predates the log. Unknown is treated as
            # stale rather than current: the cost is one rewrite, and the cost
            # of the other guess is shipping a note nobody checked.
            status = "unverified"
        elif seen < len(cs):
            status = f"stale +{len(cs) - seen}"
        else:
            status = "stale" if newest > nd else "current"
        rows.append((not status.startswith("current"), strongest, -len(cs),
                     name, status, nd, newest, len(cs)))
    rows.sort()
    out = [f"{sum(1 for r in rows if not r[4].startswith('current'))} of {len(rows)} players need a note"
           + (" (including those the corpus never mentioned)" if include_silent else
              " (players with claims only; pass include_silent for the whole board)"),
           "player                     status   note-as-of  newest-claim  claims",
           "-" * 74]
    for _, _, _, name, status, nd, newest, n in rows[:limit]:
        out.append(f"{name:26} {status:8} {nd or '--':11} {newest:13} {n}")
    out += ["",
            "Ordered by: needs work first, then the strongest claim type and basis",
            "the player has, then claim count. So an injury claim from a beat",
            "report outranks a pile of sentiment.",
            "",
            "status:  missing    no note file at all",
            "         undated    a note with no 'as of' header — provenance unknown",
            "         unverified a note written before write_note kept a log; it may",
            "                    be fine, but nothing records what it was written from",
            "         stale +N   N claims arrived after the note was written",
            "         current    written from every claim now stored",
            "Rewrite everything except current.",
            "",
            "player_claims(name) -> write_note(name, md, publish=True) for each."]
    return "\n".join(out)


@mcp.tool()
def next_threads(count: int = 1, worker: str = "") -> str:
    """Claim the next undistilled threads to work on, highest value first.

    This is the entry point for a fleet. Each call leases the threads it hands
    back for 45 minutes, so N agents running at once get disjoint work instead
    of all starting at the top of the same list. Call it, distil what it gives
    you with distill_thread, submit_claims, then call it again for more.

    Threads are ranked by whether they report or opine, how many draftable
    players are in them, recency, and size with size capped — an 800-comment
    joke thread is worth less than a 100-comment beat report. Daily
    rate-my-team and who-do-I-draft posts sort to the bottom.

    Pass `worker` (any string naming yourself) so a stuck lease can be traced.
    A lease expires on its own; submitting claims for a thread releases it."""
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    index, chars = _mention_index()

    def claim():
        done = _done_threads()
        # Rewrite from the live set, not the stored one: dead leases otherwise
        # accumulate in the file forever, and a reader cannot tell which of
        # them still mean anything.
        live = _live_leases(done=done)
        todo = [p for pid, p in posts.items() if pid not in done and pid not in live]
        todo.sort(key=lambda p: -_thread_priority(p, chars.get(p["id"], 0), index))
        picked = todo[:max(1, min(count, 25))]
        for p in picked:
            live[p["id"]] = {"worker": worker or "?", "ts": time.time()}
        LEASES.write_text(json.dumps(live, indent=1), encoding="utf-8")
        return picked, len(todo), len(live) - len(picked)

    picked, remaining, held = _with_lock(claim)
    if not picked:
        return (f"Nothing left to claim: every thread is distilled or leased "
                f"({held} leases live). claims_stats() for the state.")
    out = [f"leased {len(picked)} thread(s) to {worker or 'you'} for {LEASE_MINUTES} min "
           f"· {remaining - len(picked)} unclaimed, {held} held by others", "=" * 74]
    for p in picked:
        out.append(f"{p['id']}  {C.thread_kind(p.get('title',''), p.get('selftext','')):10} "
                   f"{C.thread_date(p):11} {chars.get(p['id'],0):>7,}ch  {p.get('title','')[:52]}")
    out += ["", "For each: distill_thread(id) -> read every page -> submit_claims(json).",
            "Then call next_threads again. Report any coach, reporter or retired",
            "player you see mis-resolved with report_non_player."]
    return "\n".join(out)


@mcp.tool()
def thread_shortlist(count: int = 25, undistilled_only: bool = True) -> str:
    """The threads most likely to be worth reading, with the reason for each.

    Same ranking next_threads hands out, but printed rather than claimed, so you
    can see what the queue thinks is valuable and why before spending agents on
    it. Reasons come from the score itself, not a separate explanation."""
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    index, chars = _mention_index()
    done = _done_threads()
    rows = []
    for pid, p in posts.items():
        if undistilled_only and pid in done:
            continue
        sc, why = _thread_priority(p, chars.get(pid, 0), index, explain=True)
        rows.append((sc, pid, p, why))
    rows.sort(key=lambda r: -r[0])
    out = [f"top {min(count, len(rows))} of {len(rows)} "
           f"{'undistilled ' if undistilled_only else ''}threads", "=" * 76]
    for sc, pid, p, why in rows[:count]:
        out.append(f"{sc:6.0f}  {pid}  {C.thread_date(p):11} {p.get('title','')[:60]}")
        out.append(f"        {' · '.join(why) if why else 'no strong signal'}")
    out.append("")
    out.append("next_threads(n) claims from the top of exactly this list.")
    return "\n".join(out)


@mcp.tool()
def release_thread(post_id: str, reason: str = "") -> str:
    """Mark a thread read but empty, releasing its lease without storing claims.

    The brief says an empty distillation of a thin thread is a correct answer,
    and until this existed there was no way to give that answer: submit_claims
    rejects an empty batch, and only submitting released a lease. A worker who
    read an offensive-line trade thread and correctly found nothing had to
    either sit on the lease for 45 minutes or invent a filler claim. The second
    is what a queue with no skip path quietly trains for.

    Use it when the thread genuinely carries nothing about a draftable player —
    the index found only name collisions, it is memorabilia or a game thread,
    or the fantasy content is one passing comparison you would not read back in
    a draft room. Threads released this way do not come back."""
    pid = post_id.strip().rstrip("/").rsplit("/", 1)[-1]
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    if pid not in posts:
        return f"No thread {pid!r} in the corpus."
    if pid in C.distilled_threads():
        return f"{pid} already has claims stored; nothing to release."

    def go():
        skipped = _read_skipped()
        skipped[pid] = {"reason": reason.strip() or "nothing about a draftable player",
                        "ts": time.time()}
        SKIPPED.write_text(json.dumps(skipped, indent=1), encoding="utf-8")
        leases = _read_leases()
        leases.pop(pid, None)
        LEASES.write_text(json.dumps(leases, indent=1), encoding="utf-8")
        return len(skipped)

    n = _with_lock(go)
    return (f"released {pid} — {posts[pid].get('title','')[:60]!r}\n"
            f"recorded as read-and-empty ({n} total); it will not be handed out again.")


@mcp.tool()
def report_non_player(name: str, role: str = "", note: str = "") -> str:
    """Record someone who is NOT a draftable player: a coach, a beat writer, a
    retired player, anyone outside the 337-man pool.

    This is the fix for the resolver's last real error class. The pool cannot
    represent a person it does not contain, so every such person gets shredded
    onto whoever shares his name — "the ghost of Nick Chubb" became Chuba
    Hubbard, "Pop Douglas" became Caleb Douglas, and "Andy" reached a kicker 31
    times when it meant Andy Reid.

    Once registered, the full name is blocked outright and the bare first name
    stops resolving unless the pool player is corroborated elsewhere in the
    comment. If you are reading a thread and see a name treated as a player who
    plainly is not one, report it here — that is knowledge only a reader has."""
    name = " ".join(name.split())
    if len(name.split()) < 2:
        return ("Give the full name — a single token would block a surname the "
                "pool legitimately owns.")
    names = {p.player_name.lower() for p in pool()[0]}
    if name.lower() in names:
        return f"{name!r} IS in the draft pool; not registering."
    path = HERE / R.NON_PLAYERS_FILE
    try:
        reg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        reg = {}
    if name in reg:
        return f"{name!r} already registered as {reg[name].get('role','?')}."
    reg[name] = {k: v for k, v in (("role", role.strip()), ("note", note.strip())) if v}
    path.write_text(json.dumps(reg, indent=1, sort_keys=True), encoding="utf-8")
    R.NON_PLAYER_NAMES, R.NON_PLAYER_FIRSTS = R.load_non_players()
    global _pool
    _pool = None
    return (f"registered {name!r}" + (f" ({role})" if role else "")
            + f"; registry now {len(reg)} names. Resolver reloaded.")


@mcp.tool()
def sweep_many(subreddits: str = "fantasyfootball,DynastyFF,fantasyfootballadvice",
               top: int = 60, hot: int = 60, new: int = 120, days: int = 30,
               min_comments: int = 10, replace_more: int = 12,
               require_relevance: bool = False) -> str:
    """Sweep several subreddits in one call, comma-separated.

    r/fantasyfootball is the main room, but team subreddits carry the beat
    reporting first and the other fantasy subs argue differently. Every listing
    is deduped into the same corpus, so overlap costs nothing but a skip."""
    out = []
    for sub in [x.strip() for x in subreddits.split(",") if x.strip()]:
        try:
            out.append(f"--- r/{sub}\n" + sweep_subreddit(
                sub, top=top, hot=hot, new=new, days=days,
                min_comments=min_comments, replace_more=replace_more,
                require_relevance=require_relevance))
        except Exception as e:
            out.append(f"--- r/{sub}\n  failed: {type(e).__name__}: {e}")
    return "\n".join(out)


@mcp.tool()
def claims_stats() -> str:
    """What has been distilled, what is left, and where the claims came from."""
    all_c = C.load()
    if not all_c:
        return "No claims stored yet. Start with distill_thread()."
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    done = _done_threads()
    todo = [p for i, p in posts.items() if i not in done]
    out = [f"{len(all_c)} claims · {len({c['player'] for c in all_c})} players · "
           f"{len(done)}/{len(posts)} threads distilled", "=" * 74, "",
           "by type:  " + ", ".join(f"{k}={v}" for k, v in
                                    Counter(c["type"] for c in all_c).most_common()),
           "by basis: " + ", ".join(f"{k}={v}" for k, v in
                                    Counter(c["basis"] for c in all_c).most_common())]
    if todo:
        out += ["", f"not yet distilled ({len(todo)}):"]
        for p in sorted(todo, key=lambda p: -(p.get("num_comments") or 0)):
            out.append(f"  {p['id']}  {C.thread_kind(p.get('title', ''), p.get('selftext', '')):<10} "
                       f"{p.get('title', '')[:58]}")
    top = Counter(c["player"] for c in all_c).most_common(12)
    out += ["", "most-claimed players:"] + [f"  {n:26} {k}" for n, k in top]
    return "\n".join(out)


if __name__ == "__main__":
    mcp.run()
