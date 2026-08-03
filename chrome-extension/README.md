# Draft Assistant extension

Scrapes live draft picks from fantasy sites and relays them to the
[foss.football](https://foss.football) draft tool (and the local Go app
if running). Works on Chrome, Edge, Brave, Opera, and Firefox.

| Site | Status |
|---|---|
| ESPN | verified in live drafts |
| Sleeper | verified in live drafts |
| Yahoo | selectors unverified — run a mock first |
| NFL.com | selectors unverified — run a mock first |
| CBS | selectors unverified — run a mock first |

If a scraper finds nothing during a mock, run `window.ffdaDiag()` in the
draft-room console and use its output to fix the candidate selectors in
`<site>-draft.js` (see `draft-common.js`).

## One source, two builds

This directory is the **single source of truth**. `manifest.json` carries
the union of what Chrome and Firefox need — each browser ignores the
other's keys (Chrome runs `background.service_worker` and ignores
`scripts`/`browser_specific_settings`; Firefox 121+ runs `background.scripts`
as an event page and ignores `service_worker`). Two hand-maintained
folders would drift on every scraper fix; generated variants can't.

For clean, store-ready per-browser packages:

```bash
python3 package.py
# dist/chrome/  + draft-assistant-chrome-<v>.zip    (Chrome Web Store / Edge / Brave)
# dist/firefox/ + draft-assistant-firefox-<v>.zip   (addons.mozilla.org)
```

## Installing for development

- **Chrome / Edge / Brave**: `chrome://extensions` → Developer mode →
  Load unpacked → this directory (loading the source dir directly is fine;
  Chrome may show cosmetic warnings about the Firefox-only keys, or load
  `dist/chrome/` for zero warnings). To use the draft tool from `file://`,
  also enable "Allow access to file URLs".
- **Firefox**: `about:debugging#/runtime/this-firefox` → Load Temporary
  Add-on → this directory's `manifest.json`. Temporary add-ons vanish on
  restart — for a permanent install the zip must be signed by AMO (below).
  Dev loop: `npx web-ext run --source-dir chrome-extension`.

### Firefox caveat: host permissions are opt-in

Firefox MV3 treats host permissions as optional. If picks don't flow or
the ESPN cookie handoff to the local Python tool fails, open the puzzle
icon → Draft Assistant → gear → and grant access to the fantasy sites
(or "Always allow" from the address-bar extension button while on the
draft page).

## Publishing to the stores

- **Chrome Web Store**: one-time $5 developer fee →
  https://chrome.google.com/webstore/devconsole → upload
  `draft-assistant-chrome-<v>.zip`. Review usually takes a few days.
- **Firefox (AMO)**: free account at https://addons.mozilla.org/developers/
  → submit `draft-assistant-firefox-<v>.zip`. Choose listed (public on
  AMO) or self-hosted (AMO signs it, you serve the .xpi from
  foss.football). The manifest already declares the required add-on id
  and data-collection disclosure (`none` — everything stays in the
  user's browser).
- **Edge**: Chrome zip works at
  https://partner.microsoft.com/dashboard/microsoftedge (free), though
  Edge users can also install straight from the Chrome Web Store.

## Files

- `manifest.json` — cross-browser master manifest (MV3)
- `content.js` — storage relay + localhost POST + ESPN auth plumbing
- `espn-draft.js`, `sleeper-draft.js` — verified scrapers (self-contained)
- `draft-common.js` — candidate-selector engine + `ffdaDiag()` for the new sites
- `yahoo-draft.js`, `nfl-draft.js`, `cbs-draft.js` — unverified scrapers
- `bridge.js` — relays extension storage into the web app page
  (`all_frames: true` so it works inside foss.football's Draft Tool iframe)
- `background.js` — ESPN cookie handoff (service worker in Chrome,
  event page in Firefox)
- `package.py` — emits `dist/` per-browser builds
