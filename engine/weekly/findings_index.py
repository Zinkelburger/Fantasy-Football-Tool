"""Search the repository's own research: numbered league-sim findings and
the research/ studies. Returns the index lines and paths that match, so
"have we studied X?" is one call instead of a grep session.

The index row is the claim as last corrected; read the file itself
before quoting a number (its latest correction or audit section wins).
"""
from __future__ import annotations

import re

from common import ROOT

FINDINGS = ROOT / "engine" / "league-sim" / "findings"
RESEARCH = ROOT / "research"


def _terms(topic: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9/+-]+", topic.lower()) if len(t) > 2]


def _index() -> list[dict]:
    rows = []
    readme = FINDINGS / "README.md"
    if readme.exists():
        for line in readme.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*\[(\d+)\]\(([^)]+)\)\s*\|(.*)\|(.*)\|(.*)\|\s*$", line)
            if m:
                rows.append({"id": m.group(1), "path": FINDINGS / m.group(2),
                             "claim": m.group(3).strip(), "evidence": m.group(4).strip(),
                             "confidence": m.group(5).strip()})
    listed = {r["path"].name for r in rows}
    for p in sorted(FINDINGS.glob("[0-9]*.md")):
        if p.name not in listed:     # a finding the index table has not caught up with
            title = next((ln.lstrip("# ").strip() for ln in p.read_text(encoding="utf-8").splitlines()
                          if ln.startswith("#")), p.stem)
            rows.append({"id": p.name.split("-")[0], "path": p, "claim": title,
                         "evidence": "", "confidence": "see file"})
    return rows


def _studies() -> list[dict]:
    out = []
    if not RESEARCH.exists():
        return out
    for d in sorted(RESEARCH.iterdir()):
        docs = ([d / "README.md"] if (d / "README.md").exists() else sorted(d.glob("*.md"))[:3]) \
            if d.is_dir() else ([d] if d.suffix == ".md" else [])
        text = " ".join(p.read_text(encoding="utf-8", errors="ignore") for p in docs)
        title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), d.name)
        out.append({"path": d, "docs": docs, "title": title, "text": text.lower()})
    return out


def search(topic: str, limit: int = 8) -> str:
    terms = _terms(topic)
    if not terms:
        return "give a topic, e.g. findings(topic='opportunity regression') or 'kicker'"
    hits = []
    for r in _index():
        body = r["path"].read_text(encoding="utf-8", errors="ignore").lower() if r["path"].exists() else ""
        head = f"{r['path'].name} {r['claim']}".lower()
        score = sum(3 * head.count(t) + min(body.count(t), 5) for t in terms)
        if score and all(t in head or t in body for t in terms):
            hits.append((score, "finding", r))
    for s in _studies():
        score = sum(3 * f"{s['path'].name} {s['title']}".lower().count(t) + min(s["text"].count(t), 5)
                    for t in terms)
        if score and all(t in s["text"] or t in s["path"].name.lower() for t in terms):
            hits.append((score, "study", s))
    hits.sort(key=lambda h: -h[0])
    if not hits:
        return (f"no finding or research study mentions all of {terms}; try fewer words. "
                f"Index: {FINDINGS.relative_to(ROOT)}/README.md")
    out = [f"Research matching {topic!r} (best first). Read the file before quoting: its latest "
           "correction/audit section overrides the index line."]
    for _, kind, r in hits[:limit]:
        if kind == "finding":
            claim = re.sub(r"\*\*|\[|\]\([^)]*\)", "", r["claim"])
            out.append(f"  finding {r['id']} [{r['confidence']}] {claim[:320]}"
                       f"\n    {r['path'].relative_to(ROOT)}")
        else:
            docs = ", ".join(str(p.relative_to(ROOT)) for p in r["docs"]) or str(r["path"].relative_to(ROOT))
            out.append(f"  study {r['path'].name}: {r['title'][:200]}\n    {docs}")
    if len(hits) > limit:
        out.append(f"  ... {len(hits) - limit} more; narrow the topic")
    return "\n".join(out)
