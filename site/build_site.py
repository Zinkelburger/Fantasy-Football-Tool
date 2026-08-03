"""Build the static site's data files from repo outputs.

Inputs (all tracked in the repo):
- league-sim/data/market/model_board_2026.csv  -> board.json
- league-sim/data/market/implied_2026.csv      -> market.json
- league-sim/data/market/games.csv (2026 wk1)  -> weekly.json (DST + K)
- league-sim/findings/NN-*.md                  -> blog.json

Run: python3 site/build_site.py   (stdlib only; re-run after any model
refresh or new finding)
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MKT = ROOT / "league-sim" / "data" / "market"
FINDINGS = ROOT / "league-sim" / "findings"

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
        para.append(line.strip())
    flush_para(); flush_table(); close_lists()
    return "\n".join(out)


# --------------------------------------------------------------- builders
def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


_SUFFIX = re.compile(r"\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$")


def _norm(name):
    n = name.lower().strip().replace(".", "").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", _SUFFIX.sub("", n))


def _market_pos_ranks():
    """(pos, normalized name) -> market position rank, from the ADP snapshot
    written by update_ranks.py (Sleeper STD ADP, FFC standard as fallback)."""
    path = MKT / "adp_2026.csv"
    if not path.exists():
        return {}
    bypos = {}
    for r in read_csv(path):
        val = r.get("sleeper_std") or r.get("ffc_std") or ""
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


def build_board():
    rows = read_csv(MKT / "model_board_2026.csv")
    mkt = _market_pos_ranks()
    board = {}
    for r in rows:
        board.setdefault(r["pos"], []).append(dict(
            name=r["name"], pred=round(float(r["pred_ppg"]), 1),
            ppg25=round(float(r["ppg"]), 1),
            age=round(float(r["age"]), 1) if r.get("age") else None,
            cap=round(float(r["cap_pct"]), 1) if r.get("cap_pct") else 0,
            mkt=mkt.get((r["pos"], _norm(r["name"])))))
    for pos in board:
        board[pos].sort(key=lambda d: -d["pred"])
        board[pos] = board[pos][:40]
    return board


def build_market():
    rows = read_csv(MKT / "implied_2026.csv")
    out = [dict(team=TEAMS.get(r["team"].split()[-1], r["team"]),
                full=r["team"], ppg=round(float(r["imp_ppg"]), 1),
                wins=round(float(r["imp_wins"]), 1)) for r in rows]
    return sorted(out, key=lambda d: -d["ppg"])


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
    return dict(label="2026 Week 1 (preseason lines)",
                dst=dst[:16], k=kick[:16])


def build_blog():
    posts = []
    for p in sorted(FINDINGS.glob("[0-9][0-9]-*.md")):
        md = p.read_text()
        lines = md.splitlines()
        title = re.sub(r"^#\s*\d+\s*—?\s*", "", lines[0]).strip()
        num = int(p.name[:2])
        conf = next((re.sub(r"\*\*|Confidence:\s*", "", ln).strip()
                     for ln in lines if "Confidence:" in ln), "")
        conf = conf.split("(")[0].strip().rstrip("*").strip()
        body = "\n".join(lines[1:])
        hook = ""
        tl = re.search(r"## TL;DR\s+(.+?)(\n\n|\n#)", md, re.S)
        if tl:
            hook = re.sub(r"[*`#\[\]]", "", tl.group(1))
            hook = " ".join(hook.split())[:220] + "…"
        posts.append(dict(id=p.stem, num=num, title=title,
                          confidence=conf, hook=hook, html=md2html(body)))
    posts.sort(key=lambda d: -d["num"])
    return posts


def main():
    out = SITE / "data"
    out.mkdir(exist_ok=True)
    for name, data in (("board", build_board()), ("market", build_market()),
                       ("weekly", build_weekly()), ("blog", build_blog())):
        (out / f"{name}.json").write_text(json.dumps(data))
        print(f"data/{name}.json written")


if __name__ == "__main__":
    main()
