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
import pathlib
from collections import Counter

from mcp.server.mcpserver import MCPServer

import adjudicate as A
import claims as C
import resolve_names as R

HERE = pathlib.Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
POSTS, COMMENTS = CORPUS / "posts.jsonl", CORPUS / "comments.jsonl"
DOSSIERS = CORPUS / "dossiers"

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
                    min_comments: int = 1, replace_more: int = 12) -> str:
    """Sweep a subreddit's top/hot/new listings into the corpus.

    Reddit search never indexes comment bodies, which is why this pulls whole
    threads instead of searching per player. Resumable: already-cached posts
    are skipped. Budget roughly 2-5 API requests per post at 100 req/min."""
    import time
    from datetime import datetime, timedelta

    r = _reddit()
    sub = r.reddit.subreddit(subreddit)
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()

    cands = {}
    for listing in (sub.top(time_filter="month", limit=top),
                    sub.hot(limit=hot), sub.new(limit=new)):
        for s in listing:
            if s.created_utc >= cutoff and s.num_comments >= min_comments:
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
            f"{len(todo)} newly fetched, +{added_c} comments\n"
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
def write_note(player_name: str, markdown: str) -> str:
    """Save a finished draft note. This is where your summary of a dossier goes.

    Writes corpus/dossiers/<Player Name>.md — the same layout the draft tool
    reads from the season's analysis directory."""
    names = {p.player_name.lower(): p.player_name for p in pool()[0]}
    canon = names.get(player_name.strip().lower())
    if not canon:
        return f"{player_name!r} is not in the player pool; note not written."
    DOSSIERS.mkdir(parents=True, exist_ok=True)
    path = DOSSIERS / f"{canon}.md"
    path.write_text(markdown, encoding="utf-8")
    return f"wrote {path.relative_to(HERE)} ({len(markdown)} chars)"


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
                  min_score: int = None) -> str:
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
    exactly once, versus once per player mentioned in it."""
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
    out += ["", "The index is a retrieval aid, not an answer. It is about 98% right on",
            "which player a name refers to, but it cannot tell whether a sentence is",
            "*about* that player, and it silently maps players outside the 337-man",
            "pool onto whoever shares their name. Trust the thread text over it.",
            "", "=" * 74, "", "COMMENTS", "-" * 74]

    used = len("\n".join(out))
    truncated = [0]

    def walk(parent_key, depth):
        for c in tree.get(parent_key, []):
            nonlocal used
            if min_score is not None and (c.get("score") or 0) < min_score:
                continue
            pad = "  " * depth
            head = f"{pad}[{c['id']} · {c.get('score', 0)} pts]"
            body = "\n".join(pad + "  " + ln
                             for ln in (c.get("body") or "").strip().splitlines())
            block = f"{head}\n{body}\n"
            if used + len(block) > max_chars:
                truncated[0] += 1
                continue
            out.append(block)
            used += len(block)
            walk(c["id"], depth + 1)

    walk(None, 0)
    if truncated[0]:
        out.append(f"... {truncated[0]} further comments omitted at max_chars="
                   f"{max_chars}; raise it or set min_score to prune.")
    return "\n".join(out)


@mcp.tool()
def distill_thread(post_id: str = "", max_chars: int = 60000) -> str:
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

    body = thread_digest(pid, max_chars=max_chars)
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

Rules that matter:

  - Record what the thread SAYS, not what you believe. A wrong consensus is
    still a fact about the market.
  - Do not let one sentence become a claim for every player it names. "Gibbs,
    Chase and CeeDee are safe barring an injury to Goff/Burrow/Allen" is one
    claim about three players being safe and a different claim about three
    others being risks — never the same claim six times.
  - Bare-name votes ("Jeremiyah Love." in a bust thread) are ONE sentiment
    claim per player with a count, not one claim per comment.
  - People who are not in the pool — Pop Douglas, Calvin Austin, Matt Nagy,
    Andy Reid — get no claims. The index will sometimes have mapped them onto
    a pool player who shares a name; ignore it when the thread disagrees.
  - Nothing worth saying about a player means no claim for that player. An
    empty distillation of a thin thread is a correct answer.

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
                f"him first — corpus_stats or thread_digest will point you at them.")

    p = {x.player_name: x for x in pool()[0]}[canon]
    out = [f"{canon} — {p.team_name} {p.player_depth} — ADP {p.player_adp}", "=" * 74]
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
            "Weight by basis: team_official > beat_report > consensus > single_commenter.",
            "sentiment is what the market thinks, which is worth recording and worth",
            "trusting less than the rest — the 2025 backtest found tone added no edge."]
    return "\n".join(out)


@mcp.tool()
def claims_stats() -> str:
    """What has been distilled, what is left, and where the claims came from."""
    all_c = C.load()
    if not all_c:
        return "No claims stored yet. Start with distill_thread()."
    posts = {p["id"]: p for p in _read_jsonl(POSTS)}
    done = C.distilled_threads()
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
