#!/usr/bin/env python3
"""Match all players against the local corpus (zero API calls) and build
per-player dossiers for the LLM summarizer.

Matching tiers per DESIGN-2026.md:
- exact: full-name variants, auto-generated initialisms (ARSB, JSN, MHJ),
  and nicknames — single-word aliases only when they pass the safety guard
- guarded: surname or first name alone, ONLY when the token is not an
  English word, is unique across every token of every player's name, and
  is 4+ characters (Nacua/Achane/Bijan pass; Chase/Hill/Brown fail)

No truncation: dossiers carry everything found. Garbage control is
dedup, a comment-score floor, and sentence-level matching — precision
beyond that is the summarizer LLM's job (its prompt says to ignore
same-name people).

Usage:
    python match_players.py            # all players, write dossiers + stats
    python match_players.py --stats    # stats only, no files
"""

import argparse
import json
import pathlib
import re
from collections import defaultdict

from FootballPlayer import FootballPlayer
from main_scrape_reddit_api import normalize_name_for_matching

CORPUS_DIR = pathlib.Path(__file__).resolve().parent / "corpus"
DOSSIER_DIR = CORPUS_DIR / "dossiers"
MIN_COMMENT_SCORE = 1       # below this, the community already downvoted it
GUARD_MIN_LEN = 4           # single guarded tokens must be at least this long
ALIAS_MIN_LEN = 3           # initialisms/nicknames must be at least this long

try:
    ENGLISH_WORDS = {w.strip().lower() for w in open("/usr/share/dict/words")}
except FileNotFoundError:
    ENGLISH_WORDS = set()
    print("warning: no /usr/share/dict/words — guarded tier will be too permissive")


def name_tokens(player) -> list:
    return normalize_name_for_matching(player.player_name).split()


def initialism(player) -> str:
    """First letters of name parts, hyphens split ('Amon-Ra St. Brown'->'arsb')."""
    parts = re.split(r"[\s\-]+", player.player_name.lower())
    return "".join(p[0] for p in parts if p and p[0].isalpha())


def build_alias_tables(players):
    """Returns (phrase_map, token_map): normalized phrase/token -> (slug, tier)."""
    # every name token across the pool, to test uniqueness
    token_owners = defaultdict(set)
    for p in players:
        for tok in name_tokens(p):
            token_owners[tok].add(p.slug)

    phrase_map = {}   # multi-word normalized phrases -> (slug, tier)
    token_map = {}    # single normalized tokens -> (slug, tier)
    claimed = set()   # single tokens already used as aliases (avoid collisions)

    def claim_token(tok, slug, tier):
        if tok in claimed or len(token_owners.get(tok, set()) - {slug}) > 0:
            return
        claimed.add(tok)
        token_map[tok] = (slug, tier)

    for p in players:
        toks = name_tokens(p)
        full = " ".join(toks)
        if len(toks) >= 2:
            phrase_map[full] = (p.slug, "exact")
            # initials written with spaces: "a j brown"
            if len(toks[0]) == 2:
                phrase_map[f"{toks[0][0]} {toks[0][1]} " + " ".join(toks[1:])] = (p.slug, "exact")

        ini = initialism(p)
        if len(ini) >= ALIAS_MIN_LEN and ini not in ENGLISH_WORDS:
            claim_token(ini, p.slug, "exact")

        nick = normalize_name_for_matching(str(p.player_nickname or ""))
        if nick:
            if " " in nick:
                phrase_map[nick] = (p.slug, "exact")
            elif len(nick) >= ALIAS_MIN_LEN and nick not in ENGLISH_WORDS:
                claim_token(nick, p.slug, "exact")

    # guarded single tokens (surname / first name) — after all exact aliases
    for p in players:
        toks = name_tokens(p)
        for tok in {toks[0], toks[-1]}:
            if (len(tok) >= GUARD_MIN_LEN
                    and tok not in ENGLISH_WORDS
                    and len(token_owners[tok]) == 1):
                claim_token(tok, p.slug, "guarded")

    return phrase_map, token_map


# Split on sentence enders, but not after an abbreviation or initial —
# "Amon-Ra St. Brown" and "A.J. Brown" must survive as one sentence.
SENT_SPLIT = re.compile(
    r"(?<!\b[A-Z]\.)(?<!\b(?:St|Jr|Sr|Mr|Dr|vs|No)\.)(?<=[.!?])\s+|\n+")


def sentences(text):
    for s in SENT_SPLIT.split(text):
        s = s.strip()
        if s:
            yield s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stats", action="store_true", help="print stats only, write nothing")
    ap.add_argument("--players", nargs="*", help="limit to these player names")
    args = ap.parse_args()

    players = FootballPlayer.from_csv(
        str(pathlib.Path(__file__).resolve().parent / "combined_with_depth.csv"))
    if args.players:
        wanted = {n.lower() for n in args.players}
        players_out = [p for p in players if p.player_name.lower() in wanted]
    else:
        players_out = players
    by_slug = {p.slug: p for p in players}

    phrase_map, token_map = build_alias_tables(players)
    print(f"alias tables: {len(phrase_map)} phrases, {len(token_map)} single tokens "
          f"({sum(1 for v in token_map.values() if v[1]=='guarded')} guarded)")

    # one alternation regex over all phrases, longest first so 'aj brown' wins over 'brown'
    phrases = sorted(phrase_map, key=len, reverse=True)
    phrase_re = re.compile(r"\b(" + "|".join(re.escape(p) for p in phrases) + r")\b")

    post_titles, comment_bodies = {}, {}
    with open(CORPUS_DIR / "posts.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            post_titles[row["id"]] = row["title"]
    rows = []
    with open(CORPUS_DIR / "comments.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            comment_bodies[row["id"]] = row["body"]
            rows.append(row)
    # post selftext participates as a pseudo-comment
    with open(CORPUS_DIR / "posts.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["selftext"].strip():
                rows.append({"id": f"post_{row['id']}", "post_id": row["id"],
                             "parent_id": "", "score": row["score"],
                             "body": row["selftext"], "created_utc": row["created_utc"]})
    print(f"corpus: {len(post_titles)} posts, {len(rows)} texts")

    hits = defaultdict(lambda: defaultdict(list))  # slug -> tier -> [(score, title, sent, parent)]
    for row in rows:
        if row["score"] < MIN_COMMENT_SCORE:
            continue
        title = post_titles.get(row["post_id"], "?")
        parent = ""
        if row["parent_id"].startswith("t1_"):
            parent = comment_bodies.get(row["parent_id"][3:], "")[:150]
        for sent in sentences(row["body"]):
            norm = normalize_name_for_matching(sent)
            found = {}
            for m in phrase_re.finditer(norm):
                slug, tier = phrase_map[m.group(1)]
                found[slug] = tier
            for w in set(norm.split()):
                if w in token_map:
                    slug, tier = token_map[w]
                    if slug not in found:      # exact phrase beats token tier
                        found[slug] = tier
            for slug, tier in found.items():
                hits[slug][tier].append((row["score"], title, sent, parent))

    # ---- stats over the full pool ----
    counts = {p.slug: sum(len(v) for v in hits.get(p.slug, {}).values()) for p in players}
    buckets = {"0": 0, "1-5": 0, "6-20": 0, "21-100": 0, "100+": 0}
    for n in counts.values():
        buckets["0" if n == 0 else "1-5" if n <= 5 else "6-20" if n <= 20
                else "21-100" if n <= 100 else "100+"] += 1
    print(f"\nmention distribution over {len(players)} players: {buckets}")
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:12]
    print("busiest players:")
    for slug, n in top:
        chars = sum(len(s) for v in hits[slug].values() for _, _, s, _ in v)
        print(f"  {by_slug[slug].player_name:24s} {n:5d} mentions  ≈{chars//4:6d} tokens")

    if args.stats:
        return

    DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for p in players_out:
        tiers = hits.get(p.slug, {})
        total = sum(len(v) for v in tiers.values())
        out = [f"PLAYER: {p.player_name} ({p.team_name}, {p.player_depth}) — "
               f"ADP {p.player_adp} — {total} mentions in corpus", "=" * 80, ""]
        for tier, label in [("exact", "FULL-NAME / ALIAS MENTIONS"),
                            ("guarded", "SINGLE-NAME MENTIONS (verify these refer to the player)")]:
            rows_t = tiers.get(tier, [])
            seen_sents = set()
            block = []
            for score, title, sent, parent in sorted(rows_t, key=lambda r: -r[0]):
                key = sent.lower()
                if key in seen_sents:
                    continue
                seen_sents.add(key)
                ctx = f' (replying to: "{parent}")' if parent else ""
                block.append(f"[thread: {title!r} | score {score}]{ctx} {sent}")
            if block:
                out += [f"== {label} ==", ""] + block + [""]
        if total == 0:
            out.append("No discussion found in corpus window.")
        (DOSSIER_DIR / f"{p.slug}.txt").write_text("\n".join(out), encoding="utf-8")
        written += 1
    print(f"\nwrote {written} dossiers to {DOSSIER_DIR}")


if __name__ == "__main__":
    main()
