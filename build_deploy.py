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

# Every file index.html asks for by name. Miss one and the page doesn't
# degrade -- app.js references Live and League at route time, so a single
# missing script takes the whole site down, not just the page that needed
# it. build_deploy checks for that below rather than trusting this list.
SITE_FILES = ["index.html", "app.js", "style.css", "copy.js", "sleeper.js",
              "espn.js", "provider.js", "live.js", "league.js"]
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

/figures/*
  Cache-Control: public, max-age=300

/*.js
  Cache-Control: public, max-age=31536000, immutable

/*.css
  Cache-Control: public, max-age=31536000, immutable
"""
# The .js/.css rules sit last so players-data.js ends up immutable, not
# on the 300s /webapp/data/* rule. Safe because bust() versions every
# .js/.css reference: a deploy changes the ?v= hash, never a cached URL.
#
# That safety depends on NOTFOUND below. Without a 404.html, Pages answers
# a path it doesn't have with index.html and a 200 -- so a request for a
# .js file that isn't there gets HTML, wearing this immutable header, for
# a year. A real 404 can't be mistaken for the asset or cached as one.

REDIRECTS = """\
https://www.foss.football/* https://foss.football/:splat 301
"""

# Cloudflare Pages serves this, with a real 404, for any path it has no
# file for. Deliberately self-contained -- no stylesheet, no script. The
# reason a path is missing is often that a file didn't deploy, and a 404
# page that depends on the files that just failed to deploy shows a blank
# screen at the exact moment somebody needs to read it.
#
# Nothing here needs the SPA: the site routes on the hash (#/blog/...),
# so every real page is / and every deep link still lands on it.
NOTFOUND = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found — FOSS Football</title>
<style>
  html, body { margin: 0; height: 100%; background: #1b1b1f; color: #e6e6ea;
    font-family: "Segoe UI", "Noto Sans", system-ui, sans-serif;
    line-height: 1.55; }
  main { max-width: 34rem; margin: 0 auto; padding: 4rem 1.25rem; }
  h1 { font-size: 1.5rem; margin: 0 0 .75rem; }
  p { color: #9a9aa6; margin: 0 0 1rem; }
  a { color: #4f8ef7; }
  ul { padding-left: 1.1rem; }
  li { margin-bottom: .35rem; }
</style>
</head>
<body>
<main>
  <h1>There's nothing at this address</h1>
  <p>The link was probably mistyped, or pointed at a page we've since
     moved.</p>
  <ul>
    <li><a href="/">Start over from the front page</a></li>
    <li><a href="/#/blog">Research write-ups</a></li>
    <li><a href="/webapp/">Draft tool</a></li>
  </ul>
</main>
</body>
</html>
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


def check_assets(html_path: Path):
    """Every script and stylesheet the page names must actually be here.

    This is a build-breaker on purpose. A missing .js doesn't degrade
    gracefully: app.js touches Live and League on every route, so one
    absent file throws on the first navigation and takes down every
    page, not just the one that needed it. That shipped once already,
    because SITE_FILES was a hand-kept list and the page had grown past
    it. Now the page is the list and this is the check.
    """
    missing = [m.group("ref") for m in ASSET_REF.finditer(html_path.read_text())
               if not (html_path.parent / m.group("ref")).is_file()]
    if missing:
        raise SystemExit(
            f"{html_path.name} asks for files that weren't deployed: "
            f"{', '.join(missing)}\n"
            f"Add them to SITE_FILES (or WEBAPP_FILES) in build_deploy.py.")


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
    if (ROOT / "site" / "figures").exists():
        shutil.copytree(ROOT / "site" / "figures", PUBLIC / "figures")

    webapp_out = PUBLIC / "webapp"
    webapp_out.mkdir()
    for f in WEBAPP_FILES:
        shutil.copy2(ROOT / "webapp" / f, webapp_out / f)
    shutil.copytree(ROOT / "webapp" / "data", webapp_out / "data")

    check_assets(PUBLIC / "index.html")
    check_assets(webapp_out / "index.html")

    bust(PUBLIC / "index.html")
    bust(webapp_out / "index.html")

    (PUBLIC / "_headers").write_text(HEADERS)
    (PUBLIC / "_redirects").write_text(REDIRECTS)
    (PUBLIC / "robots.txt").write_text(ROBOTS)
    (PUBLIC / "404.html").write_text(NOTFOUND)

    n_files = sum(1 for p in PUBLIC.rglob("*") if p.is_file())
    size_mb = sum(p.stat().st_size for p in PUBLIC.rglob("*") if p.is_file()) / 1e6
    print(f"assembled public/ — {n_files} files, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
