"""Build the static site's data files from repo outputs.

Inputs (all tracked in the repo):
- engine/league-sim/data/market/model_board_2026{,_half,_ppr}.csv
                                                      -> board.json
- engine/league-sim/data/market/opportunity_2025.csv  -> board.json
  (usage-based expected points; analysis/export_opportunity.py)
- engine/league-sim/data/market/implied_2026.csv      -> market.json
- engine/league-sim/data/market/games.csv (2026 wk1)  -> weekly.json (DST + K)
- site/posts/NN-*.md                                  -> blog.json

site/posts/ holds the reader-facing rewrites of the research findings in
engine/league-sim/findings/ (same filenames; the research docs are the
record, the posts are the articles). A finding without a post is skipped
with a warning.

Run: python3 site/build_site.py   (stdlib only; re-run after any model
refresh or new finding)
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MKT = ROOT / "engine" / "league-sim" / "data" / "market"
FINDINGS = ROOT / "engine" / "league-sim" / "findings"
POSTS = SITE / "posts"

TEAMS = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}


# ------------------------------------------------------- markdown -> html
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s


def md2html(md):
    out, para, table, ul, ol, code = [], [], [], False, False, False

    def flush_para():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_table():
        if not table:
            return
        head, *rows = [r for r in table
                       if not re.match(r"^\|[\s:|-]+\|$", r)]
        def cells(r):
            return [c.strip() for c in r.strip("|").split("|")]
        h = "".join(f"<th>{inline(c)}</th>" for c in cells(head))
        b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>"
                                     for c in cells(r)) + "</tr>"
                    for r in rows)
        out.append(f'<div class="tbl"><table><thead><tr>{h}</tr></thead>'
                   f"<tbody>{b}</tbody></table></div>")
        table.clear()

    def close_lists():
        nonlocal ul, ol
        if ul:
            out.append("</ul>"); ul = False
        if ol:
            out.append("</ol>"); ol = False

    for raw in md.splitlines():
        line = esc(raw.rstrip())
        if line.startswith("```"):
            flush_para(); flush_table(); close_lists()
            out.append("<pre>" if not code else "</pre>")
            code = not code
            continue
        if code:
            out.append(raw if raw == esc(raw) else esc(raw))
            continue
        if line.startswith("|"):
            flush_para(); close_lists()
            table.append(line)
            continue
        flush_table()
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush_para(); close_lists()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            continue
        if re.match(r"^-{3,}$", line):
            flush_para(); close_lists()
            out.append("<hr>")
            continue
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            flush_para()
            if not ul:
                if ol:
                    out.append("</ol>"); ol = False
                out.append("<ul>"); ul = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            flush_para()
            if not ol:
                if ul:
                    out.append("</ul>"); ul = False
                out.append("<ol>"); ol = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        if not line.strip():
            flush_para(); close_lists()
            continue
        if (ul or ol) and out and out[-1].endswith("</li>"):
            # a wrapped bullet continues on the next line
            out[-1] = f"{out[-1][:-5]} {inline(line.strip())}</li>"
            continue
        para.append(line.strip())
    flush_para(); flush_table(); close_lists()
    return "\n".join(out)


# ------------------------------------------------ plain-English tooltips
# First occurrence of each stat term in a post gets a hover definition
# (dotted underline). Definitions must not contain double quotes — they
# land in a title="..." attribute.
GLOSSARY = [
    (r"Spearman", "How well two rankings agree, from -1 to 1 "
     "(1 = identical order). Only the order matters, not the gaps."),
    (r"Pearson", "How closely two sets of numbers move together, from "
     "-1 to 1 (1 = perfectly in step). Unlike Spearman, gap sizes matter."),
    (r"rank correlations?", "How well two rankings agree, from -1 to 1. "
     "0 = no relationship, 1 = identical order."),
    (r"all-play", "Your record if you played every team every week - "
     "team strength with schedule luck stripped out."),
    (r"LOYO", "Leave-one-year-out: train the model on every season "
     "except one, test on the held-out season, repeat. The model never "
     "grades its own homework."),
    (r"leave-one-(?:year|season)-out", "Train the model on every season "
     "except one, test on the held-out season, repeat. The model never "
     "grades its own homework."),
    (r"MAE", "Mean absolute error: how many points the prediction "
     "missed by, on average."),
    (r"implied totals?", "The score Vegas expects a team to put up, "
     "worked out from the spread and the over/under."),
    (r"ADP", "Average draft position: where real drafters take a "
     "player - the market's opinion of him."),
    (r"OLS", "Ordinary least squares: plain line-fitting - find the "
     "weights that make predictions miss by the least."),
    (r"ridge regression", "Line-fitting with a penalty that keeps any "
     "one stat from being over-trusted."),
    (r"Elo", "A running strength rating: beat good teams and it rises, "
     "lose to bad ones and it falls."),
    (r"quintiles?", "One fifth of the group - the top quintile is the "
     "top 20%."),
    (r"expected points", "The fantasy points a player 'should' have "
     "scored given his usage (targets, carries, red-zone work), before "
     "luck."),
    (r"split-half reliability", "Whether a stat agrees with itself "
     "across two halves of the same data - if it does not, it is noise."),
]
GLOSS_PATTERNS = [(re.compile(rf"\b{p}\b"), d) for p, d in GLOSSARY]

# Don't inject tooltips inside these elements (links, code, headings).
_GLOSS_SKIP = {"a", "code", "pre", "h1", "h2", "h3", "h4"}


def glossarize(html):
    """Wrap the first occurrence of each glossary term in a tooltip span."""
    parts = re.split(r"(<[^>]+>)", html)
    skip = 0
    used = set()
    for i, part in enumerate(parts):
        if part.startswith("<"):
            m = re.match(r"<(/?)([a-zA-Z0-9]+)", part)
            if m and m.group(2).lower() in _GLOSS_SKIP:
                skip += -1 if m.group(1) else 1
            continue
        if skip > 0 or not part.strip():
            continue
        for j, (pat, definition) in enumerate(GLOSS_PATTERNS):
            if j in used:
                continue
            new, n = pat.subn(
                lambda m: f'<span class="gloss" title="{definition}">'
                          f"{m.group(0)}</span>", part, count=1)
            if n:
                part = new
                used.add(j)
        parts[i] = part
    return "".join(parts)


# --------------------------------------------------------------- builders
def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


_SUFFIX = re.compile(r"\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$")


def _norm(name):
    n = name.lower().strip().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", _SUFFIX.sub("", n))


def _market_pos_ranks(fmt):
    """(pos, normalized name) -> market position rank for one scoring
    format, from the ADP snapshot written by update_ranks.py (Sleeper
    ADP for that format, FFC for the same format as fallback)."""
    path = MKT / "adp_2026.csv"
    if not path.exists():
        return {}
    bypos = {}
    for r in read_csv(path):
        val = r.get(f"sleeper_{fmt}") or r.get(f"ffc_{fmt}") or ""
        try:
            v = float(val)
        except ValueError:
            continue
        bypos.setdefault(r["pos"], []).append((v, _norm(r["player"])))
    out = {}
    for pos, pairs in bypos.items():
        pairs.sort()
        for i, (_, n) in enumerate(pairs, 1):
            out[(pos, n)] = i
    return out


# site key -> (model board CSV, ADP column suffix)
FORMATS = {"std": ("model_board_2026.csv", "std"),
           "half": ("model_board_2026_half.csv", "half"),
           "ppr": ("model_board_2026_ppr.csv", "ppr")}


def _player_teams():
    """(pos, normalized name) -> team nickname, for the board's
    per-player offense readout. Roster export first (covers deep-bench
    names; analysis/export_player_teams.py), ADP snapshot on top as the
    fresher word on who moved."""
    out = {}
    ros = MKT / "player_teams_2026.csv"
    if ros.exists():
        for r in read_csv(ros):
            out.setdefault((r["pos"], _norm(r["name"])), r["team"])
    path = MKT / "adp_2026.csv"
    if path.exists():
        for r in read_csv(path):
            if r.get("team"):
                out[(r["pos"], _norm(r["player"]))] = r["team"]
    # feed codes that differ from the TEAMS map (nflverse codes)
    alias = {"LAR": "LA", "JAC": "JAX"}
    return {k: TEAMS.get(alias.get(ab, ab)) for k, ab in out.items()}


def _opportunity():
    """(pos, normalized name) -> 2025 usage row (expected PPG per format,
    centered gap, TD luck, per-game volume). See export_opportunity.py
    for why hot/cold calls must threshold gapc_*, never raw gap."""
    path = MKT / "opportunity_2025.csv"
    if not path.exists():
        print("  (no opportunity_2025.csv — "
              "run analysis/export_opportunity.py)")
        return {}
    return {(r["pos"], _norm(r["name"])): r for r in read_csv(path)}


FM_DIR = {"buy": 0, "fade": 1, "watch": 2}


def _findings_marks():
    """(pos, normalized name) -> [{f, slug, dir, note}], buys first —
    every tested finding that names this player, with his own numbers
    baked into the note (analysis/findings_marks.py). Shown in the
    board's click-note."""
    path = MKT / "findings_marks_2026.csv"
    if not path.exists():
        print("  (no findings_marks_2026.csv — board click-notes get "
              "no findings; run analysis/findings_marks.py)")
        return {}
    out = {}
    for r in read_csv(path):
        out.setdefault((r["pos"], _norm(r["name"])), []).append(
            dict(f=int(r["finding"]), slug=r["slug"], dir=r["dir"],
                 note=r["note"]))
    for v in out.values():
        v.sort(key=lambda m: (FM_DIR.get(m["dir"], 3), m["f"]))
    return out


def _room(r):
    """Where he sits in his own team's position room, off the model
    board (analysis/player_model.py `room_standing`): is he his team's
    WR1, who is next, and did they spend a real pick at his position.

    Context for the click-note only, never a mark on the board. The
    ordering is read off ADP, so it is not a disagreement with the
    market — finding 25 measured it adding nothing on top of ADP."""
    def num(key):
        v = (r.get(key) or "").strip()
        return int(float(v)) if v else None

    rank = num("room_rank")
    if rank is None:
        return None
    pick = num("rook_pick")
    return dict(
        rank=rank,
        ahead=r.get("room_ahead") or None, aheadGap=num("room_ahead_gap"),
        behind=r.get("room_behind") or None, behindGap=num("room_behind_gap"),
        # only a pick worth mentioning: a 7th-rounder is not competition
        rook=(r.get("rook_name") or None) if pick and pick <= 100 else None,
        rookPick=pick if pick and pick <= 100 else None)


def _board_for(csv_name, adp_fmt, opp, teams, fm):
    rows = read_csv(MKT / csv_name)
    mkt = _market_pos_ranks(adp_fmt)
    board = {}
    unmatched = 0
    for r in rows:
        o = opp.get((r["pos"], _norm(r["name"])))
        if opp and o is None:
            unmatched += 1
        board.setdefault(r["pos"], []).append(dict(
            name=r["name"], team=teams.get((r["pos"], _norm(r["name"]))),
            marks=fm.get((r["pos"], _norm(r["name"])), []),
            room=_room(r),
            pred=round(float(r["pred_ppg"]), 1),
            ppg25=round(float(r["ppg"]), 1),
            age=round(float(r["age"]), 1) if r.get("age") else None,
            cap=round(float(r["cap_pct"]), 1) if r.get("cap_pct") else 0,
            mkt=mkt.get((r["pos"], _norm(r["name"]))),
            xfp=round(float(o[f"ep_{adp_fmt}"]), 1) if o else None,
            gapc=round(float(o[f"gapc_{adp_fmt}"]), 1) if o else 0,
            tdl=round(float(o["td_luck_pg"]), 2) if o else 0,
            tpg=round(float(o["tgt_pg"]), 1) if o else 0,
            cpg=round(float(o["carry_pg"]), 1) if o else 0,
            g=int(o["games"]) if o else 0))
    if unmatched:
        print(f"  ({csv_name}: {unmatched} players without 2025 "
              "opportunity data)")
    for pos in board:
        board[pos].sort(key=lambda d: -d["pred"])
        board[pos] = board[pos][:40]
    return board


def build_board():
    """{format: {pos: [rows]}} — one board per scoring format. Each is a
    separate model fit, not the standard board re-sorted."""
    out = {}
    opp = _opportunity()
    teams = _player_teams()
    fm = _findings_marks()
    for key, (csv_name, adp_fmt) in FORMATS.items():
        path = MKT / csv_name
        if not path.exists():
            print(f"  (skipping {key}: {csv_name} missing — "
                  f"run analysis/player_model.py)")
            continue
        out[key] = _board_for(csv_name, adp_fmt, opp, teams, fm)
    return out


def build_rookies():
    """The 2026 rookie board (analysis/rookie_model.py): drafted skill
    rookies ordered by projected rookie-year PPG, all three formats in
    one table."""
    path = MKT / "rookie_board_2026.csv"
    if not path.exists():
        print("  (no rookie_board_2026.csv — run analysis/rookie_model.py)")
        return []
    rows = []
    for r in read_csv(path):
        rows.append(dict(
            name=r["name"], pos=r["pos"],
            team=TEAMS.get(r["team"], r["team"]),
            rnd=int(r["rnd"]), pick=int(r["pick"]),
            std=float(r["pred_std"]), half=float(r["pred_half"]),
            ppr=float(r["pred_ppr"])))
    rows.sort(key=lambda d: -d["std"])
    return rows


def build_market():
    rows = read_csv(MKT / "implied_2026.csv")
    # implied_2026.csv carries full names ("Los Angeles Rams"); every
    # other table shows nicknames, so show the last word here too.
    out = [dict(team=r["team"].split()[-1],
                full=r["team"], ppg=round(float(r["imp_ppg"]), 1),
                wins=round(float(r["imp_wins"]), 1)) for r in rows]
    return sorted(out, key=lambda d: -d["ppg"])


NICK = {nick: ab for ab, nick in TEAMS.items()}   # "Rams" -> "LA"


def build_preseason():
    """Draft-day K and D/ST boards: the weekly models (findings 27, 28)
    aggregated over the whole 2026 schedule instead of one week.

    D/ST ranks on the points its opponents are expected to score all
    season — the season-long form of the one number finding 27 says is
    ~97% of the position. K ranks on its own offense's expected points,
    with dome games shown separately: the model's dome effect is +0.7
    kicker points per indoor game, which is not in the same units as a
    team's implied points, so it stays its own column rather than being
    baked into a composite."""
    domes, games = {}, {}
    for r in read_csv(MKT / "games.csv"):
        if r["season"] != "2026" or r["game_type"] != "REG":
            continue
        for ab in (r["home_team"], r["away_team"]):
            games[ab] = games.get(ab, 0) + 1
            if r["roof"] in ("dome", "closed"):
                domes[ab] = domes.get(ab, 0) + 1

    k, dst = [], []
    for r in read_csv(MKT / "implied_2026.csv"):
        nick = r["team"].split()[-1]
        ab = NICK.get(nick)
        if ab is None:
            continue
        g, d = games.get(ab, 17), domes.get(ab, 0)
        k.append(dict(team=nick, own=round(float(r["imp_ppg"]), 1),
                      dome=d, games=g,
                      # season-average kicker-point edge from the dome
                      # share, in kicker points: 0.7 per indoor game
                      domeEdge=round(0.7 * d / g, 2)))
        dst.append(dict(team=nick, opp=round(float(r["imp_opp_ppg"]), 1)))
    k.sort(key=lambda d: -d["own"])
    dst.sort(key=lambda d: d["opp"])
    return dict(k=k, dst=dst)


def build_weekly():
    rows = [r for r in read_csv(MKT / "games.csv")
            if r["season"] == "2026" and r["week"] == "1"
            and r["total_line"]]
    dst, kick = [], []
    for r in rows:
        tot, sp = float(r["total_line"]), float(r["spread_line"])
        # nflverse spread_line = home margin (positive = home favored)
        imp_h, imp_a = tot / 2 + sp / 2, tot / 2 - sp / 2
        dome = r["roof"] in ("dome", "closed")
        for d, off, imp_opp, imp_own, home in (
                (r["home_team"], r["away_team"], imp_a, imp_h, True),
                (r["away_team"], r["home_team"], imp_h, imp_a, False)):
            dst.append(dict(team=TEAMS[d], opp=TEAMS[off],
                            imp=round(imp_opp, 1), home=home))
            kick.append(dict(team=TEAMS[d], opp=TEAMS[off],
                             imp=round(imp_own, 1), dome=dome, home=home))
    dst.sort(key=lambda d: d["imp"])
    kick.sort(key=lambda d: (-d["imp"] - (0.7 if d["dome"] else 0)))
    return dict(label="2026 Week 1 (preseason lines)", dst=dst, k=kick)


def _full_writeup(stem):
    """The engine write-up (findings/NN-*.md), prepped to sit under the
    reader-facing post: H1 dropped, TL;DR section dropped (the post
    above IS the synopsis), H2s demoted (H2->H3, H3->H4) so the page
    keeps one outline, cross-links pointed at the site's own posts."""
    src = FINDINGS / f"{stem}.md"
    if not src.exists():
        return ""
    out, section = [], None
    for ln in src.read_text().splitlines()[1:]:
        m = re.match(r"^(#{2,3})\s", ln)
        if m:
            if len(m.group(1)) == 2:
                section = ln[3:].strip()
            if section != "TL;DR":
                out.append("#" + ln)
            continue
        if section != "TL;DR":
            out.append(ln)
    md = "\n".join(out).strip()
    return re.sub(r"\]\((\d\d-[a-z0-9-]+)\.md\)", r"](#/blog/\1)", md)


def build_blog():
    published = {p.stem for p in POSTS.glob("[0-9][0-9]-*.md")}
    missing = {p.stem for p in FINDINGS.glob("[0-9][0-9]-*.md")} - published
    for stem in sorted(missing):
        print(f"WARNING: no site/posts/ rewrite for finding {stem} — "
              "it will not appear on the site")
    posts = []
    for p in sorted(POSTS.glob("[0-9][0-9]-*.md")):
        md = p.read_text()
        lines = md.splitlines()
        title = re.sub(r"^#\s*\d+\s*—?\s*", "", lines[0]).strip()
        num = int(p.name[:2])
        conf = next((re.sub(r"\*\*|Confidence:\s*", "", ln).strip()
                     for ln in lines if "Confidence:" in ln), "")
        conf = conf.split("(")[0].strip().rstrip("*").strip()
        body = "\n".join(lines[1:])
        # The posts used to end with a "full write-up on GitHub" pointer;
        # now the full write-up ships on the page itself, synopsis first.
        body = re.sub(r"\n---\s*\n+\*The full write-up.*$", "", body,
                      flags=re.S)
        full = _full_writeup(p.stem)
        if full:
            body += "\n\n---\n\n## The full write-up\n\n" + full
        hook = ""
        tl = re.search(r"## TL;DR\s+(.+?)(\n\n|\n#)", md, re.S)
        if tl:
            hook = re.sub(r"[*`#\[\]]", "", tl.group(1))
            hook = " ".join(hook.split())
            if len(hook) > 220:
                # cut at a sentence boundary when a reasonable one exists
                cut = hook[:220]
                m = re.search(r"^.*[.!?](?=\s|$)", cut, re.S)
                hook = m.group(0) if m and len(m.group(0)) > 80 \
                    else cut + "…"
        posts.append(dict(id=p.stem, num=num, title=title,
                          confidence=conf, hook=hook,
                          html=glossarize(md2html(body))))
    posts.sort(key=lambda d: -d["num"])
    return posts


def build_cheatsheet():
    """site/cheatsheet.md — the findings distilled to one page of
    draft-night rules, every rule linking to its finding."""
    lines = (SITE / "cheatsheet.md").read_text().splitlines()
    return dict(title=re.sub(r"^#\s*", "", lines[0]).strip(),
                html=glossarize(md2html("\n".join(lines[1:]))))


def main():
    out = SITE / "data"
    out.mkdir(exist_ok=True)
    # board/rookies/market dropped 2026-08-05 with the projection models
    # (findings 25, 32 — see archive/season-projection-model/). The
    # builders are kept below so a future model can wire straight back in.
    for name, data in (("preseason", build_preseason()),
                       ("weekly", build_weekly()), ("blog", build_blog()),
                       ("cheatsheet", build_cheatsheet())):
        (out / f"{name}.json").write_text(json.dumps(data))
        print(f"data/{name}.json written")


if __name__ == "__main__":
    main()
