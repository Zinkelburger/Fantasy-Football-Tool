#!/usr/bin/env python3
"""LLM adjudication of ambiguous player mentions, one occurrence at a time.

resolve_names.py can settle a mention two ways without help: the alias has
exactly one owner in the draftable pool, or context (team, position, a nearby
full-name mention) separates the candidates cleanly. Everything else it was
deciding by ADP — assume the cheapest player is the one meant — which is a
guess dressed up as an answer. "Love" is the case that shows why: Jeremiyah
Love (RB, ADP 20) now outranks Jordan Love (QB, ADP 141), so cost points at
the RB in a thread that is entirely about quarterbacks.

This module hands those to an LLM instead, with the context a person would
actually use:

    the sentence, with the token marked
    the full comment it sits in
    the parent chain up to the root comment
    the thread title
    every candidate's team, position, depth rank, bye and ADP
    the other players already resolved in the same comment

Decisions are pinned to an occurrence — comment id plus position — not to the
token, so "Allen" can be Josh in one thread and Braelon in another. A token
that keeps resolving the same way is promoted to a global default in
alias_overrides.json and stops being asked about.

Nothing here calls an API. The batches are built for whatever model is reading
them; in a Claude Code session that is the session itself, via mcp_server.py.

    python adjudicate.py --pending          # how much is waiting
    python adjudicate.py --batch 20         # print a batch as JSON
"""

import argparse
import hashlib
import json
import pathlib

import resolve_names as R

HERE = pathlib.Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
DECISIONS = CORPUS / "decisions.jsonl"

# What reaches the model, and what does not.
#
# Every mention with more than one candidate is asked about, whatever the
# heuristics concluded — that is the whole point, since "context picks one" is
# the heuristic marking its own homework, and the fallback beneath it is ADP.
#
# Single-candidate mentions are only asked about when the alias itself is
# shaky: a common English word, or a truncation the alias builder guessed at.
# "i took burrow in the 6th" has exactly one possible Burrow and needs no
# adjudication; "at the right price" and "my washington pick" do.
#
# Mentions the gates dropped are included only when a real decision survives —
# a name/word collision with several owners, or a non-obvious token. Without
# that filter the queue fills with "me", "it", "pick" and "don't", where the
# gate was plainly right and the model's attention is wasted.
MIN_GATED_LEN = 4

# Times a token must resolve to the same player, with no contradicting
# decision, before it becomes a global default and stops being asked about.
PROMOTE_AFTER = 3


def occurrence_id(comment_id, sent_idx, word_idx, alias):
    """Stable short id for one mention in one comment."""
    raw = f"{comment_id}:{sent_idx}:{word_idx}:{alias}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def load_decisions(path=DECISIONS):
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                row = json.loads(line)
                out[row["oid"]] = row
            except (json.JSONDecodeError, KeyError):
                continue
    return out


def append_decisions(rows, path=DECISIONS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def promote(decisions, players, overrides_path=None):
    """Turn repeated, consistent verdicts into global alias defaults.

    Only promotes a token whose decisions all agree. One dissent and it stays
    per-occurrence forever, which is the correct outcome for a genuinely
    context-dependent token like a shared surname."""
    overrides_path = overrides_path or (HERE / R.OVERRIDES_FILE)
    by_token = {}
    for row in decisions.values():
        by_token.setdefault(row["token"], []).append(row.get("player"))

    names = {p.player_name for p in players}
    table = {}
    if overrides_path.exists():
        try:
            table = json.loads(overrides_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            table = {}

    promoted = []
    for token, verdicts in by_token.items():
        if len(verdicts) < PROMOTE_AFTER or len(set(map(str, verdicts))) != 1:
            continue
        who = verdicts[0]
        if who is None:
            # "Not a player here" never generalizes to "not a player anywhere".
            # Promoting it would blacklist the token outright and take the real
            # mentions with it — every capital-L Love along with the verb.
            continue
        if who not in names:
            continue
        if table.get(token, "__unset__") != who:
            table[token] = who
            promoted.append(f"{token} -> {who or '(not a player)'}")
    if promoted:
        overrides_path.write_text(json.dumps(table, indent=1, sort_keys=True))
    return promoted


# ------------------------------------------------------------------- corpus

def _read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def load_corpus():
    posts = {p["id"]: p for p in _read_jsonl(CORPUS / "posts.jsonl")}
    comments = _read_jsonl(CORPUS / "comments.jsonl")
    by_id = {c["id"]: c for c in comments}
    rows = list(comments)
    for p in posts.values():
        if p.get("selftext", "").strip():
            rows.append({"id": f"post_{p['id']}", "post_id": p["id"],
                         "parent_id": "", "score": p.get("score", 0),
                         "body": p["selftext"]})
    return posts, by_id, rows


def parent_chain(row, by_id, depth=3):
    """The comments this one is replying to, root-most last. Bounded — a deep
    chain is mostly noise, but the immediate parent is often what makes a bare
    surname interpretable."""
    chain, cur = [], row
    for _ in range(depth):
        pid = str(cur.get("parent_id", ""))
        if not pid.startswith("t1_"):
            break
        parent = by_id.get(pid[3:])
        if not parent:
            break
        chain.append(parent["body"])
        cur = parent
    return chain


def scan_corpus(pool, keep_rejected=True):
    """Yield (row, post, mention) over the whole local corpus."""
    players, aliases, keys, cap, defaults, firsts = pool
    posts, by_id, rows = load_corpus()
    for row in rows:
        post = posts.get(row.get("post_id"), {})
        for m in R.scan(row["body"], aliases, keys,
                        thread_title=post.get("title", ""),
                        cap_required=cap, keep_rejected=keep_rejected,
                        defaults=defaults, first_names=firsts):
            yield row, post, m


def needs_adjudication(m, weak=frozenset()):
    """True when a real decision exists — see the note on MIN_GATED_LEN.

    A token with an adjudicated default stops being asked about only while the
    default keeps winning. If context points at a different candidate the
    mention comes back to the queue, which is how "Allen" can be settled as
    Josh without burying Braelon forever."""
    multi = len(m.candidates) > 1
    if multi and m.default and m.player.player_name == m.default:
        return False
    if m.tier == "gated":
        if m.alias in R.STOPWORDS:
            # Ordinary English typed in lowercase. Several players may share
            # the spelling, but that does not make it a question worth asking.
            return False
        return multi or (len(m.alias) >= MIN_GATED_LEN
                         and m.alias not in R.COMMON_WORDS)
    return multi or m.alias in weak


def resolved_mentions(pool, decisions=None):
    """Scan the corpus with recorded verdicts applied.

    This is what downstream consumers (dossiers, stats) should use rather than
    raw scan output: a verdict of "not a player" drops the mention entirely,
    and a verdict naming someone else reassigns it. Without this the
    adjudication pass would change nothing outside its own bookkeeping."""
    decisions = load_decisions() if decisions is None else decisions
    by_name = {p.player_name: p for p in pool[0]}
    for row, post, m in scan_corpus(pool, keep_rejected=False):
        oid = occurrence_id(row["id"], m.sent_idx, m.word_idx, m.alias)
        verdict = decisions.get(oid)
        if verdict is not None:
            who = verdict.get("player")
            if who is None:
                continue                       # adjudicated: not a player
            if who != m.player.player_name and who in by_name:
                m.player = by_name[who]
                m.tier = "adjudicated"
        yield row, post, m


# -------------------------------------------------------------------- batches

def _player_row(p):
    return {"name": p.player_name, "team": p.team_name,
            "pos": p.player_depth, "adp": p.player_adp}


def build_batch(pool, size=20, decisions=None, chain_depth=3):
    """Assemble the next `size` undecided mentions with full context."""
    players, aliases, keys, cap, defaults, firsts = pool
    decisions = load_decisions() if decisions is None else decisions
    posts, by_id, _ = load_corpus()

    items, seen = [], set()
    weak = pool[3]
    for row, post, m in scan_corpus(pool):
        if not needs_adjudication(m, weak):
            continue
        oid = occurrence_id(row["id"], m.sent_idx, m.word_idx, m.alias)
        if oid in decisions or oid in seen:
            continue
        seen.add(oid)

        # Players already resolved elsewhere in the same comment are strong
        # context: a comment about Herbert's receivers makes "QJ" Quentin
        # Johnston rather than Quinshon Judkins.
        nearby = sorted({
            o.player.player_name
            for o in R.scan(row["body"], aliases, keys,
                            thread_title=post.get("title", ""), cap_required=cap,
                            defaults=defaults, first_names=firsts)
            if len(o.candidates) == 1 and o.player.player_name != m.player.player_name})

        marked = m.sentence.replace(m.raw, f">>>{m.raw}<<<", 1)
        items.append({
            "oid": oid,
            "token": m.alias,
            "as_written": m.raw,
            "sentence": marked,
            "comment": row["body"][:1200],
            "reply_to": parent_chain(row, by_id, chain_depth),
            "thread_title": post.get("title", ""),
            "comment_score": row.get("score", 0),
            "candidates": [_player_row(p) for p in m.candidates[:8]],
            "also_in_comment": nearby[:12],
            "heuristic_guess": m.player.player_name,
            "heuristic_reason": m.why,
            "heuristic_tier": m.tier,
            "adjudicated_default": m.default,
        })
        if len(items) >= size:
            break
    return items


INSTRUCTIONS = """\
For each item decide which player, if any, the marked token refers to.

- `candidates` lists every draftable player owning that alias, with 2026 team,
  position/depth and ADP. The answer is usually but not always among them.
- `heuristic_guess` is what the matcher assumed. It is a hint, not an answer —
  it leans on ADP, which is wrong whenever a cheaper player shares the name.
- Use the thread title, the reply chain, and `also_in_comment` (players already
  identified in the same comment) as context. Position and team consistency
  matter more than draft cost.
- Answer `null` when the token is not a player at all: an ordinary English
  word, a coach, a team, a different sport, a player outside the pool.
- Answer "unsure" when the context genuinely does not settle it.

Return JSON: [{"oid": "...", "player": "Full Name" | null | "unsure",
               "note": "brief reason"}]
"""


def record(verdicts, pool):
    """Persist verdicts and promote anything now consistently decided."""
    players = pool[0]
    names = {p.player_name.lower(): p.player_name for p in players}
    rows, bad = [], []
    for v in verdicts:
        oid = v.get("oid")
        who = v.get("player")
        if not oid:
            continue
        if who in (None, "null", "none"):
            player = None
        elif str(who).lower() == "unsure":
            continue                      # leave it pending rather than guess
        elif str(who).lower() in names:
            player = names[str(who).lower()]
        else:
            bad.append(f"{oid}: {who!r} is not in the player pool")
            continue
        rows.append({"oid": oid, "token": v.get("token", ""),
                     "player": player, "note": v.get("note", "")})
    append_decisions(rows)
    promoted = promote(load_decisions(), players)
    return rows, promoted, bad


def stats(pool):
    decisions = load_decisions()
    weak = pool[3]
    total = auto = pending = 0
    seen = set()
    for row, _, m in scan_corpus(pool):
        total += 1
        if not needs_adjudication(m, weak):
            auto += 1
            continue
        oid = occurrence_id(row["id"], m.sent_idx, m.word_idx, m.alias)
        if oid in seen:
            continue
        seen.add(oid)
        if oid not in decisions:
            pending += 1
    return {"mentions": total, "auto_resolved": auto,
            "needing_adjudication": len(seen), "decided": len(decisions),
            "pending": pending}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pending", action="store_true")
    ap.add_argument("--batch", type=int, metavar="N")
    args = ap.parse_args()
    pool = R.load_pool(str(HERE / "combined_with_depth.csv"))
    if args.pending:
        print(json.dumps(stats(pool), indent=1))
    elif args.batch:
        print(INSTRUCTIONS)
        print(json.dumps(build_batch(pool, args.batch), indent=1))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
