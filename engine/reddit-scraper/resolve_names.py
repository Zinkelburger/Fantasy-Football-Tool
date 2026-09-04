#!/usr/bin/env python3
"""Resolve bare-name mentions to players — surnames, first names, initialisms,
nicknames and misspellings — replacing the dictionary guard in match_players.py.

The guard being replaced tested each name token against /usr/share/dict/words
and dropped anything found there. On Fedora that dict is 480k entries and
includes proper nouns, so it blocked 360 of the pool's 525 name tokens:
Burrow, Hurts, Herbert, Stroud, Jackson, Daniels, Maye and Purdy all failed,
leaving 9 of 39 QBs with any single-token alias at all. Measured against one
r/fantasyfootball QB thread, that cost ~85% of the human-visible mentions.

The replacement rests on a different observation: a surname being an English
word says nothing about whether it's ambiguous *in a fantasy football
context*. What matters is how many draftable players own it. 235 of the pool's
271 surnames have exactly one owner, so they need no disambiguation at all.
The remaining ~36 get a scored resolution pass, and only genuinely contested
ones are handed to an LLM.

Resolution tiers, in the order they're tried:

    exact       full name, or initial+surname ("J Allen"), present in the text
    unique      alias has exactly one owner in the draftable pool
    context     several owners, but team / position / a nearby full-name
                mention picks one out
    presumptive several owners, one is far cheaper by ADP (Josh Allen ADP 18
                vs Braelon Allen 174) and nothing contradicts it
    ambiguous   genuinely contested -> emit for LLM adjudication
    rejected    score too low (a lowercase common word with no support)

Case is a signal and is deliberately preserved: "love him this year" is a verb,
"Love is a top 5 QB" is a player. match_players.py lowercased before matching
and threw that away.

Self-test:  python resolve_names.py --selftest
"""

import argparse
import difflib
import json
import pathlib
import re
from collections import defaultdict

from FootballPlayer import FootballPlayer
from main_scrape_reddit_api import normalize_name_for_matching as _norm

# ---------------------------------------------------------------- team context

# Abbreviation -> the words a redditor would actually type for that team.
# Used only as a disambiguation signal, so partial coverage is harmless.
TEAM_WORDS = {
    "ARI": "arizona cardinals cards", "ATL": "atlanta falcons",
    "BAL": "baltimore ravens", "BUF": "buffalo bills",
    "CAR": "carolina panthers", "CHI": "chicago bears",
    "CIN": "cincinnati bengals", "CLE": "cleveland browns",
    "DAL": "dallas cowboys", "DEN": "denver broncos",
    "DET": "detroit lions", "GB": "green bay packers gb",
    "HOU": "houston texans", "IND": "indianapolis colts",
    "JAC": "jacksonville jaguars jags", "KC": "kansas city chiefs kc",
    "LAC": "chargers lac bolts", "LAR": "rams lar",
    "LV": "las vegas raiders lv", "MIA": "miami dolphins fins",
    "MIN": "minnesota vikings vikes", "NE": "new england patriots pats",
    "NO": "new orleans saints", "NYG": "giants nyg",
    "NYJ": "jets nyj", "PHI": "philadelphia eagles birds",
    "PIT": "pittsburgh steelers", "SEA": "seattle seahawks hawks",
    "SF": "san francisco 49ers niners", "TB": "tampa bay buccaneers bucs",
    "TEN": "tennessee titans", "WAS": "washington commanders commies",
}
# Spelled-out names match ordinary lowercase text; bare abbreviations must be
# written as abbreviations. "WAS", "NO", "GB", "SF", "NE" and "TB" are all
# common English words, and "I was originally going to target Williams" scored
# a Washington match that handed the mention to Antonio Williams (WAS) instead
# of Caleb.
TEAM_TOKENS = {abbr: set(words.split()) for abbr, words in TEAM_WORDS.items()}
TEAM_ABBRS = {abbr: abbr.lower() for abbr in TEAM_WORDS}

POSITION_WORDS = {
    "QB": {"qb", "qbs", "quarterback", "quarterbacks", "qb1", "qb2", "superflex"},
    "RB": {"rb", "rbs", "runningback", "running", "rb1", "rb2", "rb3", "handcuff"},
    "WR": {"wr", "wrs", "receiver", "receivers", "wr1", "wr2", "wr3"},
    "TE": {"te", "tes", "tightend", "te1", "te2"},
    "K": {"k", "kicker", "kickers"},
    "DST": {"dst", "def", "defense", "dline"},
}

# Words that carry fantasy intent. Their presence near a bare surname is weak
# evidence the token is a player and not the English word it collides with.
FANTASY_WORDS = {
    "adp", "draft", "drafted", "drafting", "pick", "picked", "round", "rounds",
    "start", "sit", "starting", "bench", "flex", "trade", "traded", "roster",
    "rostered", "waiver", "waivers", "stack", "keeper", "target", "targeting",
    "value", "sleeper", "bust", "upside", "floor", "ceiling", "league", "tier",
    "ppr", "reach", "fell", "falls", "grab", "grabbed", "took", "take", "snagged",
    "points", "fantasy", "mock", "mocks", "turn", "punt", "punted", "injury",
}

# Initialisms and short tokens that are football jargon, never a player. The
# thread had "WR" resolving to Wan'Dale Robinson, "TD" to Tank Dell, "OC"
# (offensive coordinator) to Omar Cooper, "RB" to Rashod Bateman.
JARGON = {
    "qb", "rb", "wr", "te", "dst", "def", "st", "ol", "dl", "lb", "cb", "db",
    "td", "tds", "int", "ints", "fg", "yac", "adp", "ppr", "bpa", "fa", "ir",
    "oc", "dc", "hc", "gm", "nfl", "nfc", "afc", "sf", "wk", "gb", "sos", "bye",
    "rz", "ay", "mvp", "roy", "dpoy", "opoy", "pff", "espn", "cbs", "lol", "imo",
    "imho", "fwiw", "idk", "tbh", "ngl", "smh", "afaik", "eta", "ot", "op",
}

# Two different kinds of collision, which need two different rules.
#
# STOPWORDS are ordinary high-frequency English. Lowercase, they are never a
# player — "i'd love to take the Dak tier" is the verb, and no amount of
# candidate ambiguity changes that. These are dropped outright rather than
# queued, because asking a model about them wastes its attention on a question
# with a known answer.
STOPWORDS = set("""
the be to of and in that have it for not on with he as you do at this but his
by from they we say her she or an will my one all would there their what so up
out if about who get which go me when make can like time no just him know take
people into year your good some could them see other than then now look only
come its over think also back after use two how our work first well way even
new want because any these give day most us is was are been has had were said
did may part run play pass catch need hope hate miss hit deep top best
worst big huge great solid fine sure right left high low late early last next
full half free hard easy long short wait watch start end keep lose win drop add
cut hold move feel seem guess mean matter chance shot room board spot line side
front here more much many own same still too very put ask try call leave might
must never off point really show tell thing week month game team season night
down ball green price likely little young pick
am pm im ive ill id dont doesnt didnt cant wont isnt arent wasnt werent hasnt
havent wouldnt couldnt shouldnt thats theres heres whats lets gonna wanna gotta
yeah yep nope ok okay guy guys man dude bro thanks thank please sorry
""".split())

# WEAK_NAMES are dictionary words that are, in a football context, mostly
# surnames. Lowercase they are genuinely ambiguous, so they are gated out of
# auto-acceptance but still queued for adjudication when several players share
# them: "my washington pick" really is Parker Washington.
# Deliberately short. A surname only belongs here if the lowercase word is
# genuinely common English *in a football conversation* — which "burrow",
# "hurts", "chase", "brown", "smith" and "jackson" are not, whatever the
# dictionary says. Listing those would re-create the bug this module exists to
# fix, gating the very surnames the redesign was meant to rescue and losing
# "i took burrow in the 6th" all over again.
WEAK_NAMES = set("""
white black blue strange swift hall hunt fields mason cook bell lane rice reed
dell branch marks max noel rome tate tracy warren washington worthy wright jack
james justice lamb lemon london loop love
""".split())

# Both tiers demand a capital before a mention is auto-accepted. Unlike the
# 480k dictionary this replaces, neither blocks anything outright at match
# time — "at the right price" is dropped while "Price is a sleeper" survives.
# "love" belongs to the stopword tier, not this one, even though two players
# are named Love: as a verb it is far too common for a lowercase occurrence to
# mean the player, so it takes a capital L to count at all.
assert not (STOPWORDS & WEAK_NAMES), sorted(STOPWORDS & WEAK_NAMES)
COMMON_WORDS = STOPWORDS | WEAK_NAMES

SCORE_ACCEPT = 5    # >= this: take it, no LLM
SCORE_REVIEW = 2    # >= this: hand to the LLM; below: drop


def _key(s):
    """Lookup key: the pipeline's normalizer plus apostrophe folding.

    normalize_name_for_matching strips periods and hyphens but keeps
    apostrophes, so "Wan'Dale Robinson" and the "Wandale Robinson" people
    actually type never met. Same for De'Von, Ja'Marr, Amon-Ra."""
    return _norm(s).replace("'", "").replace("’", "")


def _tok(s):
    return _key(s).split()


def _strip(word):
    """Normalize one raw word for lookup, keeping the original for case tests."""
    word = re.sub(r"[’']s$", "", word.strip("“”\"'’`.,!?;:()[]{}*_~/\\"))
    return _key(word)


def _strip_keep_s(word):
    """Same, but folding the possessive apostrophe instead of dropping the s.

    A surname ending in s, written as a possessive, is ambiguous with a
    different player's first name: "Adam's" strips to "adam" (Adam Randall)
    when every occurrence in the corpus meant Davante Adams, and "Jayden
    Daniel's" strips to "daniel" (Daniel Jones) while also blocking the
    "jayden daniels" full-name match. Callers try this form first and fall
    back to _strip when the pool does not know it — "Cook's" folds to "cooks",
    which owns nothing, so it correctly falls back to James Cook."""
    return _key(word.strip("“”\"'’`.,!?;:()[]{}*_~/\\").replace("’", "").replace("'", ""))


def tokenize(sentence):
    """Split a sentence into raw tokens, breaking on slashes.

    Redditors list players slash-separated — "TLaw/Dak/Purdy/Nix tier",
    "Goff/Baker", "Allen/Jackson/Burrow/Hurts/Maye". Plain whitespace splitting
    made those a single unmatchable token and lost most of the misses in the
    QB-thread benchmark."""
    return [t for t, _ in tokenize_spans(sentence)]


def tokenize_spans(sentence):
    """tokenize(), but each token carries whether a separator preceded it.

    "Puka/Jamaar" and "Puka Jamaar" tokenize identically, yet only the second
    could be one person's name. Adjacency tests need to tell them apart, so the
    flag records that this token began a new list item rather than continuing a
    phrase."""
    out = []
    for w in sentence.split():
        for k, t in enumerate(x for x in re.split(r"[/|]", w) if x):
            out.append((t, k > 0))
    return out


# ------------------------------------------------------------- alias building

def build_aliases(players):
    """Returns (aliases, cap_required).

    aliases maps an alias string to every player owning it — multi-owner keys
    are kept, unlike the old guard which discarded anything non-unique, because
    disambiguation now happens at resolve time with context.

    cap_required maps a key to how much capitalization it demands:

        "cap"     a capital anywhere, sentence-initial included. For surnames
                  that happen to be dictionary words — Love, Price, Washington.
                  "Love in the 9th" is the player; "i love him" is not.
        "strict"  a capital that is NOT sentence-initial, since at the start of
                  a sentence every word is capitalized and the capital proves
                  nothing. For ordinary English (Will, Just, Take)."""
    aliases = defaultdict(list)
    cap_required = {}
    first_names, other_names = set(), set()

    def add(key, p):
        if not key or len(key) < 2 or key in JARGON:
            return
        if p not in aliases[key]:
            aliases[key].append(p)
        if key in STOPWORDS:
            cap_required[key] = "strict"
        elif key in WEAK_NAMES:
            cap_required.setdefault(key, "cap")

    for p in players:
        # A DST's "name" is "Green Bay Packers DST   (11)" — the bye week in
        # parens became an alias, and the city alone matched any mention of the
        # city. Register the full string only.
        if str(p.player_depth or "").startswith("DST"):
            add(_key(re.sub(r"\s*\(\d+\)\s*$", "", p.player_name)), p)
            continue
        toks = _tok(p.player_name)
        if len(toks) < 2:
            add(" ".join(toks), p)
            continue
        first, last = toks[0], toks[-1]
        add(" ".join(toks), p)                       # "josh allen"
        add(f"{first[0]} {last}", p)                 # "j allen"
        add(f"{first[0]}{last}", p)                  # "jallen"
        add(last, p)                                 # "allen"
        add(first, p)                                # "josh"
        first_names.add(first)
        other_names.update((" ".join(toks), last))

        # Abbreviations are deliberately NOT generated. Initialisms (CMC, JSN),
        # initial+surname-prefix forms (TLaw, CRod) and truncations (Skat,
        # Monty) are all real, but deriving them mechanically costs far more
        # than it earns. Measured over 2,960 r/fantasyfootball comments, the
        # three generators together produced 79 good mentions against 2,451
        # junk candidates: "it" for Isaac TeSlaa (496 hits), "me" for Mike
        # Evans, "by" for Bryce Young, "then" for TreVeyon Henderson, "ball"
        # for Braelon Allen, "dont" for Dontayvion Wicks. Only the lowercase
        # gate held those back, and it leaked the moment the word was
        # capitalized — "she gives off Lavar Ball vibes" resolved to Braelon
        # Allen at unique tier, no adjudication. Over the same corpus the
        # hand-written Nickname column scored 147 good to 2 junk.
        #
        # So abbreviations come from the CSV, not from a rule. Pipe-separate to
        # give one player several: "Sun God|ARSB".
        for nick in str(p.player_nickname or "").split("|"):
            add(_key(nick), p)

    # Keys reachable ONLY as somebody's first name. Bijan, Puka, Saquon and
    # Rhamondre are how people actually write those players; Matt, Adam, Mike
    # and Andy are how they write Matt Nagy, Adam Schefter, Mike McDaniel and
    # Andy Reid. scan() tells them apart by what sits next to the token.
    # Each player carries the alias keys that reach him, so a fuzzy hit can ask
    # whether he is also named here by a key that did not need fuzzing.
    owned = defaultdict(set)
    for k, ps in aliases.items():
        for p in ps:
            owned[id(p)].add(k)
    for ps in aliases.values():
        for p in ps:
            p._alias_keys = owned[id(p)]
    return dict(aliases), cap_required, (first_names - other_names)


# Words a fuzzy match must never start from. The system dictionary when it is
# there, plus a floor list so the resolver behaves the same on a machine
# without one — resolution quality that varies by host is not worth the extra
# recall.
#
# This is the opposite of the call made for *exact* surname matching, where the
# dictionary was thrown out because it blocked Burrow, Hurts and Herbert. The
# calculus inverts for fuzzy: an exact hit on "Burrow" is evidence, while an
# edit-distance hop from "Maybe" to "Maye" is not. A misspelling is not a word.
# That single rule is worth ~1,050 false positives per 47k comments.
_FUZZY_STOP_FLOOR = frozenset("""
maybe thank bench though christ browns cleveland randy shough tank brown daniels
thanks thought through their there these those where when what which while
should would could about above after again against because before being below
between both during each further having into itself more most other over same
some such than that then they this under until very were will with your
""".split())


def _load_dict_words():
    for path in ("/usr/share/dict/words", "/usr/dict/words"):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                # Floor of 2, not 4: fuzzy matching only ever tests tokens of
                # 5+, so short entries are inert there, but the surname rule
                # needs them — "Got Herbert" turns on knowing "got" is a word.
                return {w.strip().lower() for w in fh
                        if w.strip() and "'" not in w and len(w.strip()) >= 2}
        except OSError:
            continue
    return set()


_DICT_WORDS = _load_dict_words() | _FUZZY_STOP_FLOOR


NON_PLAYERS_FILE = "non_players.json"


def load_non_players(path=NON_PLAYERS_FILE):
    """People who turn up constantly and are not draftable: coaches, beat
    writers, retired players, anyone outside the 337-man pool.

    The resolver's remaining error class, and the one an audit kept finding.
    Two of three misses over 84 blind-judged mentions were this: "the ghost of
    Nick Chubb" became Chuba Hubbard, "Pop Douglas" became Caleb Douglas. The
    pool has no way to represent someone it does not contain, so every such
    person gets shredded onto whoever shares a name with him.

    Returns (full-name keys, first-name keys). Full names are blocked outright
    as spans. First names only demand corroboration, because "Andy" is Andy
    Reid far more often than Andy Borregales but "Josh" is usually a player."""
    try:
        with open(pathlib.Path(__file__).resolve().parent / path, encoding="utf-8") as fh:
            reg = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return frozenset(), frozenset()
    full, firsts = set(), set()
    for name in reg:
        k = _key(name)
        if " " in k:
            full.add(k)
            firsts.add(k.split()[0])
    return frozenset(full), frozenset(firsts)


NON_PLAYER_NAMES, NON_PLAYER_FIRSTS = load_non_players()


def fuzzy_alias(token, raw_token, alias_keys, cutoff=0.86,
                corroborated=lambda alias: False):
    """Catch the misspellings the threads are full of: Mahommes, Kiddle, Charbs.

    Gated on capitalization, and on the token not being an English word.
    Capitalization alone does not work, because at the start of a sentence
    every word is capitalized: "Maybe I'm biased" resolved to Drake Maye 336
    times, "Thank you" to Tank Bigsby 186, "Bench:" in a rate-my-team post to
    Jack Bech 146, and "to Cleveland lol" to Colston Loveland 51.

    A dictionary word can still match if `corroborated` says the same player is
    named elsewhere in the comment by an alias that did not need fuzzing. That
    is what keeps "Kyler Murry" — "Kyler" is sitting right next to it — while
    dropping "Maybe I'm just biased", where no Drake Maye appears anywhere in
    the comment. Misspellings travel with the name they misspell; ordinary
    words do not."""
    if len(token) < 5 or not raw_token[:1].isupper():
        return None
    hit = difflib.get_close_matches(token, alias_keys, n=1, cutoff=cutoff)
    if not hit:
        return None
    if token.lower() in _DICT_WORDS and not corroborated(hit[0]):
        return None
    return hit[0]


# ------------------------------------------------------------------ resolution

class Mention:
    __slots__ = ("player", "alias", "raw", "tier", "score", "why", "sentence",
                 "candidates", "sent_idx", "word_idx", "default")

    def __init__(self, player, alias, raw, tier, score, why, sentence, candidates,
                 sent_idx=0, word_idx=0, default=None):
        self.player, self.alias, self.raw = player, alias, raw
        self.tier, self.score, self.why = tier, score, why
        self.sentence, self.candidates = sentence, candidates
        # (sent_idx, word_idx) locate the mention inside its comment, so an
        # adjudication can be pinned to this occurrence rather than to the
        # token globally.
        self.sent_idx, self.word_idx = sent_idx, word_idx
        self.default = default

    def __repr__(self):
        name = self.player.player_name if self.player else "?"
        return f"<{self.raw!r} -> {name} [{self.tier}/{self.score}] {self.why}>"


DEFAULT_BONUS = 3


def _score_candidate(p, ctx):
    """Evidence that this specific candidate is the one meant.

    The adjudicated default is deliberately NOT counted here — see
    _apply_default, which folds it in only where it cannot outrank evidence."""
    s, why = 0, []
    if _norm(p.player_name) in ctx["comment_norm"]:
        s += 3; why.append("full name in comment")
    elif _norm(p.player_name) in ctx["thread_norm"]:
        s += 1; why.append("full name in thread")
    if (TEAM_TOKENS.get(p.team_name, set()) & ctx["sent_words"]
            or TEAM_ABBRS.get(p.team_name) in ctx["upper_words"]):
        s += 2; why.append(f"team {p.team_name}")
    pos = re.sub(r"\d+", "", str(p.player_depth or ""))
    if POSITION_WORDS.get(pos, set()) & ctx["sent_words"]:
        s += 2; why.append(f"pos {pos}")
    elif ctx["capitalized"] and POSITION_WORDS.get(pos, set()) & ctx["title_words"]:
        # Title hints are ambient — every comment in a QB thread gets them — so
        # they may sharpen a mention that already looks like a name, but must
        # not by themselves promote a lowercase common word ("i love him").
        s += 1; why.append(f"pos {pos} in title")
    return s, why


def _apply_default(scored, default):
    """Fold in an adjudicated default without letting it overrule evidence.

    A token answered the same way three times becomes a default, and the README
    calls that "a prior, not a collapse" — the other candidates stay reachable
    and context can still overturn it. Added as a flat bonus it could not: at +3
    against team evidence worth +2, `allen -> Josh Allen` beat LeQuint Allen
    four times in a thread about the Jacksonville backfield, at `context` tier,
    with the JAX running back sitting right there in the pool.

    So the bonus applies only where the default is already tied for best on
    evidence — deciding between candidates the context does not separate, which
    is the job it was promoted to do. Where another candidate has strictly
    better evidence, the prior yields."""
    if not default:
        return scored
    best = max((s for s, _, _ in scored), default=0)
    return [(s + DEFAULT_BONUS, p, w + ["adjudicated default"])
            if p.player_name == default and s >= best else (s, p, w)
            for s, p, w in scored]


def resolve(alias, raw_token, candidates, ctx, sentence, sent_idx=0, word_idx=0):
    """Pick a player for one alias occurrence, or mark it for the LLM."""
    multiword = " " in alias
    score, why = 0, []

    # --- shape of the alias itself
    if multiword:
        score += 4; why.append("multi-word")
    elif len(alias) <= 2:
        score += 1; why.append("2-letter initialism")
    else:
        score += 2

    # --- capitalization, the signal the old pipeline discarded
    if raw_token[:1].isupper():
        if ctx["sentence_initial"]:
            score += 1; why.append("capitalized (sentence-initial)")
        else:
            score += 2; why.append("capitalized")
    else:
        score -= 2; why.append("lowercase")

    if FANTASY_WORDS & ctx["sent_words"]:
        score += 1; why.append("fantasy context")

    # --- which candidate
    ctx = dict(ctx, capitalized=raw_token[:1].isupper())
    scored = []
    for p in candidates:
        cs, cwhy = _score_candidate(p, ctx)
        scored.append((cs, p, cwhy))
    scored = _apply_default(scored, ctx.get("default"))
    scored.sort(key=lambda t: (-t[0], t[1].player_adp))

    if len(candidates) == 1:
        best = scored[0]
        score += 2 + best[0]; why.append("unique in pool"); why += best[2]
        tier = "unique"
    else:
        top, second = scored[0], scored[1]
        if top[0] > second[0]:
            score += 2 + top[0]; why.append("context picks one"); why += top[2]
            tier = "context"
        else:
            # no contextual separation — fall back to draft cost
            ratio = second[1].player_adp / max(top[1].player_adp, 0.1)
            if ratio >= 2.5:
                score += 1
                why.append(f"ADP-dominant ({top[1].player_adp:.0f} vs "
                           f"{second[1].player_adp:.0f})")
                tier = "presumptive"
            else:
                score -= 1; why.append(f"{len(candidates)} plausible owners")
                tier = "ambiguous"

    player = scored[0][1]
    # The score floor applies to ambiguous mentions too: a contested surname
    # with no supporting evidence is noise, not work for the LLM.
    if score < SCORE_REVIEW:
        tier = "rejected"
    elif tier != "ambiguous" and score < SCORE_ACCEPT:
        tier = "review"
    return Mention(player, alias, raw_token, tier, score, ", ".join(why),
                   sentence, [p for _, p, _ in scored], sent_idx, word_idx,
                   ctx.get("default"))


# -------------------------------------------------------------------- scanning

SENT_SPLIT = re.compile(
    r"(?<!\b[A-Z]\.)(?<!\b(?:St|Jr|Sr|Mr|Dr|vs|No)\.)(?<=[.!?])\s+|\n+")


# Tokens that legitimately sit in front of a surname without being a first
# name. Beat reports are written this way constantly: "Bengals WR Chase",
# "RB Hubbard (hamstring)", "Coach Campbell".
_NAME_PREFIX = frozenset("""
qb rb wr te k dst def ol ot og c dl de dt lb cb s fs ss ils olb edge
coach hc oc dc gm rookie veteran star former ex sr jr saint
""".split()) | {t.lower() for words_ in TEAM_WORDS.values() for t in words_.split()} \
  | {a.lower() for a in TEAM_WORDS}


def _preceded_by_other_first_name(words, normed, after_sep, i, aliases):
    """True if a bare surname at i is preceded by somebody else's first name.

    Longer n-grams match first, so reaching a bare surname at all means the
    pair in front of it is not a name the pool owns. If that preceding token is
    a capitalized word that is not a position, a team, or an honorific, the two
    together are a different person's full name: "Jimmy Smith" is not DeVonta,
    "Landon Robinson" is not Bijan, "Nick Chubb" is not Chuba Hubbard.

    Sentence-initial position is excluded, because there the capital proves
    nothing — the same rule the exact-match path already applies to ordinary
    English words."""
    if i == 0 or after_sep[i]:
        return False
    prev_raw, prev = words[i - 1], normed[i - 1]
    if not prev_raw[:1].isupper() or not prev:
        return False
    if i - 1 == 0 and prev in _DICT_WORDS:
        # The preceding word opens the sentence, so its capital proves nothing,
        # and it is an ordinary English word: "Got Herbert in the 8th",
        # "Assuming Bijan", "Targeting Dak". A sentence-opening token that is
        # *not* a word is a given name — "Landon Robinson will make the 53" —
        # and that pair is somebody else.
        return False
    if prev in _NAME_PREFIX or prev_raw.isupper():
        return False              # "WR Chase", "JAX Allen"
    if prev_raw != prev_raw.rstrip(".,;:!?)]}-–—/\\\"'’"):
        return False              # punctuation between them: a list, not a name
    if aliases.get(f"{prev} {normed[i]}"):
        return False              # the pair itself is a pool name
    # Deliberately not exempting "prev is any alias the pool owns". Brandon
    # Aubrey is in the pool, which made "the Giants have cut QB Brandon Allen"
    # exempt and it resolved to Josh Allen. Owning the first name of somebody
    # else is not evidence that this surname is yours; only owning the pair is.
    return True


def _adjacent_to_other_name(words, normed, after_sep, i, aliases, cands):
    """True if words[i] abuts a capitalized token belonging to someone else.

    Only the immediate neighbours count, and only across whitespace: punctuation
    between the two means a list item ("Odunze, Evans, Watson"), a slash run
    ("Chase/Burrow") or a dash ("Puka- Chase"), not a name.

    The two directions take different evidence, because English capitalizes the
    start of every sentence:

    - *after* the token, an unfamiliar capitalized word is a surname. Nagy,
      Schefter, Damon and Gutekunst are not in the pool and never will be,
      which is exactly why "Matt Nagy" must not resolve to Matt Gay.
    - *before* it, an unfamiliar capitalized word is usually just a sentence
      opening — "Targeting Dak", "Assuming Bijan", "That Puka" — so only a name
      the pool actually knows counts, which still catches "Calvin Austin"."""
    def owned_by_other(j):
        owners = aliases.get(normed[j])
        return owners is not None and not any(c in owners for c in cands)

    def capped(j):
        return 0 <= j < len(words) and words[j][:1].isupper()

    SEP = ".,;:!?)]}-–—/\\\"'’"
    after_ok = (words[i].rstrip("’'s") == words[i].rstrip("’'s" + SEP)
                and not (i + 1 < len(after_sep) and after_sep[i + 1]))
    before_ok = (i > 0 and not after_sep[i]
                 and words[i - 1] == words[i - 1].rstrip(SEP + "([{"))

    after = capped(i + 1) and (aliases.get(normed[i + 1]) is None
                               or owned_by_other(i + 1))
    before = capped(i - 1) and owned_by_other(i - 1)
    return (after_ok and after) or (before_ok and before)


def scan(text, aliases, alias_keys, thread_title="", max_ngram=3, fuzzy=True,
         cap_required=frozenset(), keep_rejected=False, defaults=None,
         first_names=frozenset()):
    """Yield Mentions for every alias occurrence in one comment.

    keep_rejected surfaces what the gates would have discarded. Dropping a
    mention is itself a judgement call, so an adjudication pass needs to see
    those rather than trust the heuristic to have been right."""
    comment_norm = _norm(text)
    thread_norm = _norm(thread_title)
    title_words = set(thread_norm.split())

    for sent_idx, sentence in enumerate(
            s.strip() for s in SENT_SPLIT.split(text) if s.strip()):
        spans = tokenize_spans(sentence)
        words = [t for t, _ in spans]
        after_sep = [sep for _, sep in spans]
        normed = [_strip(w) for w in words]
        # A possessive that the pool knows verbatim beats the s-stripped form:
        # "Adam's" -> adams (Davante), not adam (Adam Randall).
        for j, w in enumerate(words):
            if re.search(r"[’']s\b", w):
                keep = _strip_keep_s(w)
                if keep in aliases and keep != normed[j]:
                    normed[j] = keep
        sent_words = set(w for w in normed if w)
        upper_words = {n for w, n in zip(words, normed)
                       if n and w.strip("'’").isupper()}
        ctx_base = {"comment_norm": comment_norm, "thread_norm": thread_norm,
                    "sent_words": sent_words, "title_words": title_words,
                    "upper_words": upper_words}
        consumed = set()
        # longest n-gram first so "josh allen" beats "allen"
        for n in range(max_ngram, 0, -1):
            for i in range(len(words) - n + 1):
                if any(j in consumed for j in range(i, i + n)):
                    continue
                key = " ".join(x for x in normed[i:i + n] if x)
                if not key:
                    continue
                if n > 1 and key in NON_PLAYER_NAMES:
                    # "Andy Reid", "Nick Chubb", "Pop Douglas" — consume the
                    # whole span so no shorter n-gram inside it can match
                    # either. Blocking the full name is what stops "Andy"
                    # reaching a kicker and "Chubb" reaching Chuba Hubbard.
                    consumed.update(range(i, i + n))
                    continue
                cands = aliases.get(key)
                matched_key = key
                gated = ""
                strictness = cap_required.get(key)
                if cands and strictness and not words[i][:1].isupper():
                    gated = "dictionary word, written lowercase"
                elif cands and strictness == "strict" and i == 0:
                    # Every word is capitalized at the start of a sentence, so
                    # the capital is no evidence at all: "Just the waiting
                    # sucks" is not Justice Hill.
                    gated = "sentence-initial capital proves nothing"
                elif (cands and n == 1 and key not in first_names
                      and any(key == _key(c.player_name).split()[-1] for c in cands)
                      and _preceded_by_other_first_name(words, normed, after_sep,
                                                        i, aliases)):
                    # A surname wearing somebody else's first name.
                    gated = "surname preceded by another person's first name"
                elif (cands and n == 1 and key in NON_PLAYER_FIRSTS
                      and key in first_names
                      and not any(a != key and (a in sent_words
                                                or f" {a} " in f" {comment_norm} ")
                                  for c in cands
                                  for a in getattr(c, "_alias_keys", ()) or ())):
                    # A bare first name shared with a known non-player, with
                    # the pool player nowhere else in the comment. "Andy loves
                    # good RBs" is Andy Reid; the adjacency rule below misses
                    # it because no capitalized surname follows.
                    gated = "first name of a known non-player, uncorroborated"
                elif (cands and n == 1 and key in first_names
                      and _adjacent_to_other_name(words, normed, after_sep, i,
                                                  aliases, cands)):
                    # A bare first name touching another capitalized name is
                    # somebody else's full name: Matt Nagy, Adam Schefter, Mike
                    # McDaniel, Andy Reid, Calvin Austin. Measured over 2,960
                    # comments this was wrong 42 times out of 42. Adjacency has
                    # to be literal — "Odunze, Evans, Watson" is a list, not a
                    # name, so a token carrying trailing punctuation is exempt.
                    gated = "bare first name adjacent to another name"
                elif cands and len(key) <= 2 and not words[i].strip("'’.,").isupper():
                    # Two-letter aliases are initialisms — JJ, QJ, CMC — and are
                    # written in caps. Lowercased, "I'd" folds to "id" and
                    # collides with Isaiah Davis.
                    gated = "two-letter alias not written in caps"
                if gated and not keep_rejected:
                    continue
                if not cands and n == 1 and fuzzy:
                    def _corroborated(alt_key, _cn=comment_norm, _sw=sent_words):
                        """Is this player already named here without fuzzing?

                        Any other alias of any candidate the fuzzy key points
                        at, present in the comment as an exact token."""
                        for p in aliases.get(alt_key) or ():
                            for a in getattr(p, "_alias_keys", ()) or ():
                                if a != alt_key and (a in _sw or f" {a} " in f" {_cn} "):
                                    return True
                        return False
                    alt = fuzzy_alias(key, words[i], alias_keys,
                                      corroborated=_corroborated)
                    if alt:
                        cands, matched_key = aliases.get(alt), alt
                if not cands:
                    continue
                ctx = dict(ctx_base, sentence_initial=(i == 0),
                           default=(defaults or {}).get(matched_key))
                m = resolve(matched_key, words[i], cands, ctx, sentence, sent_idx, i)
                if gated:
                    m.tier, m.why = "gated", gated
                if m.tier not in ("rejected", "gated"):
                    consumed.update(range(i, i + n))
                    yield m
                elif keep_rejected:
                    yield m


OVERRIDES_FILE = "alias_overrides.json"


def apply_overrides(aliases, cap_required, players, path=OVERRIDES_FILE):
    """Fold in adjudications recorded by a human or by the model.

    Returns the default map: token -> player name.

    A null verdict blacklists the token outright — "not a player" is a complete
    answer. A player verdict is only a *default*: the other candidates stay in
    the table and context can still overturn it. Collapsing the alias instead
    would make Braelon Allen permanently unreachable the moment "Allen" was
    settled as Josh once, and the surnames worth adjudicating are exactly the
    ones several players share."""
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = pathlib.Path(__file__).resolve().parent / p
    if not p.exists():
        return 0
    try:
        table = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    by_name = {pl.player_name: pl for pl in players}
    defaults = {}
    for tok, who in table.items():
        if who is None:
            aliases.pop(tok, None)
        elif who in by_name and tok in aliases:
            defaults[tok] = who
            cap_required.pop(tok, None)
        elif who in by_name:
            aliases[tok] = [by_name[who]]
            cap_required.pop(tok, None)
            defaults[tok] = who
    return defaults


def load_pool(csv_path="combined_with_depth.csv"):
    players = FootballPlayer.from_csv(csv_path)
    aliases, cap_required, first_names = build_aliases(players)
    defaults = apply_overrides(aliases, cap_required, players)
    # Fuzzy matching searches these keys; weak ones would turn every typo into a
    # nickname collision, so they are excluded from the search space.
    fuzzy_keys = [k for k in aliases if k not in cap_required and " " not in k]
    return players, aliases, fuzzy_keys, cap_required, defaults, first_names


# ------------------------------------------------------------------- self-test

SELFTEST = [
    # (sentence, expected player, note)
    ("Dak, Tlaw, Purdy, Nix, Shough for me.", "Dak Prescott", "bare first name"),
    ("Dak, Tlaw, Purdy, Nix, Shough for me.", "Trevor Lawrence", "TLaw nickname"),
    ("Dak, Tlaw, Purdy, Nix, Shough for me.", "Tyler Shough", "unique surname"),
    ("i took burrow in the 6th in a 12 team", "Joe Burrow", "lowercase, fantasy ctx"),
    ("Mahommes went right after I drafted Baker LOL", "Patrick Mahomes", "misspelling"),
    ("If I miss that I like Kyler Murry pretty late", "Kyler Murray", "misspelling"),
    ("I got Stafford in the 8th and Love in the 9th", "Jordan Love", "Love=QB via ctx"),
    ("Got Herbert in the 8th and pretty happy with it", "Justin Herbert", "dict word"),
    ("Yes it’s Davante Adam’s", "Davante Adams", "possessive of a plural surname"),
    ("Jayden Daniel's is a hard pass for me", "Jayden Daniels", "Daniel's != Daniel"),
    ("Cook's weekly output was closer to Swift", "James Cook", "possessive falls back"),
    ("I will continue with my theory that Matt Nagy is cursed", None,
     "first name + unknown surname is another person"),
    ("“We feel good,” ESPN’s Adam Schefter reported", None, "reporter, not Adam Randall"),
    ("When was Calvin Austin relevant?", None, "surname preceded by a known first name"),
    ("But Andy Reid does when he’s got the back", None, "coach, not Andy Borregales"),
    ("I had Chase, Kupp, and Mike Williams that year", "Ja'Marr Chase", "list survives"),
    ("Assuming Bijan and Gibbs go first", "Bijan Robinson",
     "sentence-initial capital is not a surname"),
    ("Consensus is Puka/Jamaar, without Jamaar 4 is a toss up", "Puka Nacua",
     "slash list is not a full name"),
    ("negative perception of him", None, "no false positive"),
    ("I love him this year", None, "lowercase 'love' is a verb"),
    ("Hoping for C Williams at 7.8", "Caleb Williams", "initial+surname"),
    ("threat of Achane only increases Willis' upside", "Malik Willis", "possessive"),
]


def selftest():
    players, aliases, keys, cap, defaults, firsts = load_pool()
    print(f"pool: {len(players)} players, {len(aliases)} alias keys "
          f"({len(cap)} need a capital)\n")
    ok = fail = 0
    for sentence, expect, note in SELFTEST:
        found = {m.player.player_name: m for m in
                 scan(sentence, aliases, keys, thread_title="How are you choosing QB in 2026?",
                      first_names=firsts,
                      cap_required=cap, defaults=defaults)
                 if m.tier != "rejected"}
        if expect is None:
            passed = not found
            got = ", ".join(found) or "(nothing)"
        else:
            passed = expect in found
            got = ", ".join(f"{k}[{v.tier}]" for k, v in found.items()) or "(nothing)"
        ok, fail = (ok + 1, fail) if passed else (ok, fail + 1)
        print(f"  {'PASS' if passed else 'FAIL'}  {note:28s} {sentence[:44]!r:48s} -> {got}")
    print(f"\n{ok} passed, {fail} failed")
    return fail


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--text", help="resolve names in an ad-hoc string")
    args = ap.parse_args()
    if args.selftest:
        raise SystemExit(1 if selftest() else 0)
    if args.text:
        players, aliases, keys, cap, defaults, firsts = load_pool()
        for m in scan(args.text, aliases, keys, cap_required=cap, defaults=defaults,
                      first_names=firsts):
            print(m)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
