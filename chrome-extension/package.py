#!/usr/bin/env python3
"""Package the extension for each browser from the single source manifest.

This directory is the only source of truth — manifest.json carries the union
of what Chrome and Firefox need (each ignores the other's keys, so loading
the source dir unpacked works in both browsers for development). For store
submission this script emits per-browser variants with clean manifests:

    dist/chrome/    + dist/draft-assistant-chrome-<v>.zip    (Chrome Web Store;
                      also Edge/Brave/Opera)
    dist/firefox/   + dist/draft-assistant-firefox-<v>.zip   (addons.mozilla.org)

Chrome variant drops: background.scripts, browser_specific_settings.
Firefox variant drops: background.service_worker (Firefox runs event pages).
"""
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"

EXCLUDE = {"dist", "package.py", "__pycache__", ".DS_Store"}


def variant_manifest(manifest: dict, browser: str) -> dict:
    m = json.loads(json.dumps(manifest))  # deep copy
    if browser == "chrome":
        m["background"].pop("scripts", None)
        m.pop("browser_specific_settings", None)
    elif browser == "firefox":
        m["background"].pop("service_worker", None)
    return m


def build(browser: str, manifest: dict) -> Path:
    out = DIST / browser
    out.mkdir(parents=True)
    for item in HERE.iterdir():
        if item.name in EXCLUDE or item.name == "manifest.json":
            continue
        if item.is_dir():
            shutil.copytree(item, out / item.name)
        else:
            shutil.copy2(item, out / item.name)
    (out / "manifest.json").write_text(
        json.dumps(variant_manifest(manifest, browser), indent=2) + "\n")

    zip_path = DIST / f"draft-assistant-{browser}-{manifest['version']}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out))
    return zip_path


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    if DIST.exists():
        shutil.rmtree(DIST)
    for browser in ("chrome", "firefox"):
        zip_path = build(browser, manifest)
        print(f"{browser}: dist/{browser}/ + {zip_path.name}")


if __name__ == "__main__":
    main()
