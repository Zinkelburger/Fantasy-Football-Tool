#!/usr/bin/env python3
"""Assemble the deployable foss.football site into public/.

Layout of the output:
    public/            <- site/ (landing, weekly boards, 2026 board, research)
    public/webapp/     <- webapp/ (the draft tool; the site iframes it at
                          ../webapp/index.html, which resolves to /webapp/
                          when the site sits at the domain root)

Regenerates both data bundles first (webapp/build_data.py, site/build_site.py)
from tracked repo files — no network access, so builds are deterministic and
this can run as the Cloudflare Pages build command:

    build command:    python3 build_deploy.py
    output directory: public

Local preview:  cd public && python3 -m http.server 8080
Direct upload:  npx wrangler pages deploy public --project-name foss-football
"""
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"

SITE_FILES = ["index.html", "app.js", "style.css"]
WEBAPP_FILES = ["index.html", "app.js", "style.css"]

HEADERS = """\
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN

/data/*
  Cache-Control: public, max-age=300

/webapp/data/*
  Cache-Control: public, max-age=300

/*.js
  Cache-Control: public, max-age=31536000, immutable

/*.css
  Cache-Control: public, max-age=31536000, immutable
"""
# The .js/.css rules sit last so players-data.js ends up immutable, not
# on the 300s /webapp/data/* rule. Safe because bust() versions every
# .js/.css reference: a deploy changes the ?v= hash, never a cached URL.

REDIRECTS = """\
https://www.foss.football/* https://foss.football/:splat 301
"""

ROBOTS = """\
User-agent: *
Allow: /
"""


def run(script: Path):
    print(f"» python3 {script.relative_to(ROOT)}")
    subprocess.run([sys.executable, str(script)], check=True, cwd=ROOT)


ASSET_REF = re.compile(r'(?:src|href)="(?P<ref>[^":]+\.(?:js|css))"')


def bust(html_path: Path):
    """Rewrite local .js/.css references to <ref>?v=<content hash>.

    HTML is served with max-age=0 while assets get a long cache (see
    HEADERS), so without this a deploy takes up to the old asset
    max-age to reach returning browsers. Content hashes keep the
    build deterministic. The [^":] in ASSET_REF skips data:/https:
    URLs; refs already carrying ?v= can't occur since this runs once
    on freshly copied files.
    """
    html = html_path.read_text()

    def stamp(m):
        asset = html_path.parent / m.group("ref")
        if not asset.is_file():
            return m.group(0)
        digest = hashlib.md5(asset.read_bytes()).hexdigest()[:8]
        return m.group(0)[:-1] + f'?v={digest}"'

    html_path.write_text(ASSET_REF.sub(stamp, html))


def main():
    if "--no-rebuild" not in sys.argv:
        run(ROOT / "webapp" / "build_data.py")
        run(ROOT / "site" / "build_site.py")

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir()

    for f in SITE_FILES:
        shutil.copy2(ROOT / "site" / f, PUBLIC / f)
    shutil.copytree(ROOT / "site" / "data", PUBLIC / "data")

    webapp_out = PUBLIC / "webapp"
    webapp_out.mkdir()
    for f in WEBAPP_FILES:
        shutil.copy2(ROOT / "webapp" / f, webapp_out / f)
    shutil.copytree(ROOT / "webapp" / "data", webapp_out / "data")

    bust(PUBLIC / "index.html")
    bust(webapp_out / "index.html")

    (PUBLIC / "_headers").write_text(HEADERS)
    (PUBLIC / "_redirects").write_text(REDIRECTS)
    (PUBLIC / "robots.txt").write_text(ROBOTS)

    n_files = sum(1 for p in PUBLIC.rglob("*") if p.is_file())
    size_mb = sum(p.stat().st_size for p in PUBLIC.rglob("*") if p.is_file()) / 1e6
    print(f"assembled public/ — {n_files} files, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
