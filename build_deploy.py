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
"""

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

    (PUBLIC / "_headers").write_text(HEADERS)
    (PUBLIC / "_redirects").write_text(REDIRECTS)
    (PUBLIC / "robots.txt").write_text(ROBOTS)

    n_files = sum(1 for p in PUBLIC.rglob("*") if p.is_file())
    size_mb = sum(p.stat().st_size for p in PUBLIC.rglob("*") if p.is_file()) / 1e6
    print(f"assembled public/ — {n_files} files, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
