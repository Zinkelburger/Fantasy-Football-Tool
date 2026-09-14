"""The Reddit places worth reading for player information, and how to name them.

One catalogue, used by every tool that takes a `subreddits` argument. Agents
should not need to know that Green Bay's subreddit is r/GreenBayPackers or
that Jacksonville is JAC in the pool and JAX in nflverse: they can say a team
code, a group keyword, or a player, and `expand()` turns it into the real
subreddit names.

    expand("MIA,fantasyfootballadvice")   -> ["miamidolphins", "fantasyfootballadvice"]
    expand("fantasy")                     -> the four fantasy rooms
    expand("teams")                       -> all 32 team subreddits
    expand("all")                         -> everything in the catalogue

Every name below was checked against the live API on 2026-09-14 (subscriber
counts are from that day). `python sources.py` prints the catalogue and runs
the self-test; `python sources.py --check` re-verifies each name via PRAW.
"""

from collections import OrderedDict

# --------------------------------------------------------------- fantasy rooms
# name -> (group, subscribers, what it is good for)
FANTASY_SUBS = OrderedDict([
    ("fantasyfootball", ("fantasy", 3_452_636,
        "the main room; official weekly megathreads (start/sit, waivers, injuries), "
        "beat news reposted within minutes, the biggest sample of opinion")),
    ("fantasyfootballadvice", ("fantasy", 152_763,
        "individual roster questions: 'panic on Achane?', trade and start/sit asks. "
        "Small threads, but the fastest read on what managers are worried about")),
    ("DynastyFF", ("fantasy", 211_177,
        "long-horizon takes: rookies, contracts, age curves, who a team is building "
        "around. Best sub for 'is this player's role real beyond this week'")),
    ("Fantasy_Football", ("fantasy", 211_960,
        "second general room, mostly rate-my-team and trade posts; overlaps "
        "r/fantasyfootballadvice")),
    ("FantasyFootballers", ("fantasy", 88_455,
        "listeners of the Fantasy Footballers podcast; echoes the show's rankings "
        "and start/sit calls")),
    ("FFCommish", ("fantasy", 26_837,
        "league management, not players; rarely worth searching")),
    ("nfl", ("news", 12_839_915,
        "every real NFL news item (injury, trade, signing, suspension) lands here as "
        "a post with the beat report in the title; too big to sweep, good to search")),
    ("NFL_Draft", ("news", 791_755,
        "rookie scouting and draft-capital context; useful for first-year players")),
])

# --------------------------------------------------------------- team rooms
# Team code -> subreddit. Codes are the ones the pool (combined_with_depth.csv)
# uses; nflverse / ESPN spellings are added as aliases below.
TEAM_SUBS = OrderedDict([
    ("ARI", "AZCardinals"),      ("ATL", "falcons"),
    ("BAL", "ravens"),           ("BUF", "buffalobills"),
    ("CAR", "panthers"),         ("CHI", "CHIBears"),
    ("CIN", "bengals"),          ("CLE", "Browns"),
    ("DAL", "cowboys"),          ("DEN", "DenverBroncos"),
    ("DET", "detroitlions"),     ("GB", "GreenBayPackers"),
    ("HOU", "Texans"),           ("IND", "Colts"),
    ("JAC", "Jaguars"),          ("KC", "KansasCityChiefs"),
    ("LV", "raiders"),           ("LAC", "Chargers"),
    ("LAR", "LosAngelesRams"),   ("MIA", "miamidolphins"),
    ("MIN", "minnesotavikings"), ("NE", "Patriots"),
    ("NO", "Saints"),            ("NYG", "NYGiants"),
    ("NYJ", "nyjets"),           ("PHI", "eagles"),
    ("PIT", "steelers"),         ("SF", "49ers"),
    ("SEA", "Seahawks"),         ("TB", "buccaneers"),
    ("TEN", "Tennesseetitans"),  ("WAS", "Commanders"),
])
assert len(TEAM_SUBS) == 32

TEAM_NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAC": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LV": "Las Vegas Raiders", "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers", "SEA": "Seattle Seahawks", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}

# Other spellings of a team code that show up in nflverse, ESPN, Sleeper and
# in people's heads. Nicknames too, so "dolphins" and "Patriots" both work.
TEAM_ALIASES = {
    "JAX": "JAC", "LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC",
    "STL": "LAR", "GNB": "GB", "KAN": "KC", "NWE": "NE", "NOR": "NO",
    "SFO": "SF", "TAM": "TB", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE",
    "HST": "HOU",
}
for _code, _full in TEAM_NAMES.items():
    _nick = _full.split()[-1].lower()          # cardinals, 49ers, ...
    TEAM_ALIASES[_nick.upper()] = _code
    TEAM_ALIASES[_full.upper()] = _code
    TEAM_ALIASES[_full.replace(" ", "").upper()] = _code
TEAM_ALIASES["NINERS"] = "SF"
TEAM_ALIASES["BUCS"] = "TB"
TEAM_ALIASES["PATS"] = "NE"
TEAM_ALIASES["FINS"] = "MIA"
TEAM_ALIASES["SKINS"] = "WAS"
TEAM_ALIASES["JAGS"] = "JAC"

# lowercase subreddit name -> canonical spelling, so "patriots" -> "Patriots"
_CANON = {s.lower(): s for s in list(FANTASY_SUBS) + list(TEAM_SUBS.values())}
_SUB_TO_TEAM = {s.lower(): code for code, s in TEAM_SUBS.items()}

GROUPS = {
    "fantasy": [n for n, (g, _, _) in FANTASY_SUBS.items() if g == "fantasy"],
    "news": [n for n, (g, _, _) in FANTASY_SUBS.items() if g == "news"],
    "teams": list(TEAM_SUBS.values()),
}
GROUPS["all"] = GROUPS["fantasy"] + GROUPS["news"] + GROUPS["teams"]

# Weekly discovery uses focused player queries in the main fantasy/news rooms.
# Broad draft corpus groups remain separate and require explicit selection.
WEEKLY_SEARCH = ["fantasyfootball", "nfl"]
DEFAULT_SEARCH = ["fantasyfootball", "fantasyfootballadvice", "DynastyFF", "Fantasy_Football"]
DEFAULT_SWEEP = ["fantasyfootball", "DynastyFF", "fantasyfootballadvice", "Fantasy_Football"]
NEWS_SEARCH = DEFAULT_SEARCH + ["nfl"]


def team_code(text):
    """'MIA', 'jax', 'dolphins', 'Miami Dolphins', 'r/miamidolphins' -> 'MIA'.
    None if it is not a team."""
    if not text:
        return None
    t = str(text).strip()
    if t.lower().startswith("r/"):
        t = t[2:]
    if t.lower() in _SUB_TO_TEAM:
        return _SUB_TO_TEAM[t.lower()]
    u = t.upper()
    if u in TEAM_SUBS:
        return u
    return TEAM_ALIASES.get(u)


def team_subreddit(text):
    """Subreddit for a team however it was named, or None."""
    code = team_code(text)
    return TEAM_SUBS.get(code) if code else None


def expand(subreddits, default=None):
    """Turn a comma-separated string of subreddit names, team codes, team
    nicknames and group keywords into a deduped list of real subreddit names.

    Unknown names pass through untouched (they may be real subreddits the
    catalogue does not know), so this never refuses; it only translates."""
    if isinstance(subreddits, (list, tuple)):
        tokens = list(subreddits)
    else:
        tokens = [x.strip() for x in str(subreddits or "").split(",")]
    tokens = [t for t in tokens if t]
    if not tokens:
        tokens = list(default or DEFAULT_SEARCH)
    out = []
    for tok in tokens:
        raw = tok[2:] if tok.lower().startswith("r/") else tok
        if raw.lower() in GROUPS:
            names = GROUPS[raw.lower()]
        elif raw.lower() in _CANON:
            names = [_CANON[raw.lower()]]
        else:
            ts = team_subreddit(raw)
            names = [ts] if ts else [raw]
        for n in names:
            if n.lower() not in {o.lower() for o in out}:
                out.append(n)
    return out


def catalogue():
    """Human-readable listing for the reddit_sources tool and the docs."""
    lines = ["FANTASY / NEWS SUBREDDITS  (use the name, or a group: fantasy, news, teams, all)", ""]
    for name, (group, subs, note) in FANTASY_SUBS.items():
        lines.append(f"  r/{name:24} {group:8} {subs:>11,}  {note}")
    lines += ["", "TEAM SUBREDDITS  (use the code, the nickname, or the name: MIA, dolphins, miamidolphins)", ""]
    for code, sub in TEAM_SUBS.items():
        lines.append(f"  {code:4} r/{sub:20} {TEAM_NAMES[code]}")
    lines += ["",
              "Defaults:",
              f"  research_brief / search_reddit   {','.join(WEEKLY_SEARCH)}",
              f"  player_news     {','.join(WEEKLY_SEARCH)} + the player's team sub (from the pool)",
              f"  sweep_many      {','.join(DEFAULT_SWEEP)}",
              "",
              "Tips:",
              "  - Team subs carry beat reporting first (practice reports, snap counts,",
              "    coach quotes). Search them by the player's surname; sweep them with",
              "    require_relevance=True or you get game threads and memes.",
              "  - r/fantasyfootballadvice threads are one manager's question;",
              "    use only for a manager-opinion question, not weekly news discovery.",
              "  - r/DynastyFF is where role and contract questions get argued out.",
              "  - Reddit search only indexes titles and post bodies, never comments.",
              "    Weekly: research_brief -> verify sources -> read_research_thread if needed.",
              "    Draft corpus only: fetch_thread(id) then thread_digest(id)."]
    return "\n".join(lines)


def _selftest():
    assert expand("MIA,fantasyfootballadvice") == ["miamidolphins", "fantasyfootballadvice"]
    assert expand("teams") == list(TEAM_SUBS.values())
    assert expand("fantasy")[0] == "fantasyfootball"
    assert expand("r/ravens") == ["ravens"]
    assert expand("ravens,BAL,Baltimore Ravens") == ["ravens"]
    assert expand("JAX") == ["Jaguars"] and expand("LA") == ["LosAngelesRams"]
    assert expand("dolphins,Patriots,pats") == ["miamidolphins", "Patriots"]
    assert expand("") == DEFAULT_SEARCH
    assert expand("somethingelse") == ["somethingelse"]
    assert expand("all") and len(expand("all")) == len(FANTASY_SUBS) + 32
    assert team_code("r/Commanders") == "WAS" and team_code("WSH") == "WAS"
    assert team_code("Achane") is None
    print("sources selftest ok")


def _check_live():
    from RedditQuery import RedditQuery
    r = RedditQuery().reddit
    bad = 0
    for name in GROUPS["all"]:
        try:
            s = r.subreddit(name)
            print(f"  r/{s.display_name:24} {s.subscribers:>11,}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"  r/{name:24} FAIL {type(e).__name__}")
    print("all names resolve" if not bad else f"{bad} names failed")


if __name__ == "__main__":
    import sys
    _selftest()
    if "--check" in sys.argv:
        _check_live()
    else:
        print(catalogue())
