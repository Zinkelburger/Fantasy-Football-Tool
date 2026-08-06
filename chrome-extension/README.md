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
  (`all_frames: true` so it works inside foss.football's Draft Tool iframe),
  stores the user's prep (`ffda_prep`, below), and relays the site's ESPN
  league reads (below)
- `background.js` — ESPN cookie handoff and the ESPN read proxy
  (service worker in Chrome, event page in Firefox)
- `package.py` — emits `dist/` per-browser builds


## Reading a private ESPN league for the web app (v1.4.0)

The site's **My league** page can read an ESPN league directly when
that league is public — ESPN's read API answers cross-origin requests
properly, so no extension is needed for those.

Private leagues are different, and the reason is worth stating
precisely because it is easy to get wrong: **it is not a CORS
problem.** ESPN echoes the requesting origin and sets
`access-control-allow-credentials: true`. The blocker is that
`espn_s2` and `SWID` are cookies on `.espn.com`, so a request from
`foss.football` is a third-party one and the browser never attaches
them. The request is allowed; it just arrives signed out.

This extension already holds host permission for `espn.com`, so the
same request made from its background script does carry the cookies.
That's the whole feature:

```
site/espn.js  --401-->  bridge.js  -->  background.js  -->  ESPN
                                   <--   JSON only    <--
```

The door is deliberately narrow:

- **GET only.** No body, no method choice, so nothing can be changed —
  no lineup set, no player dropped, no trade accepted.
- **One URL prefix**, `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/`,
  checked in the background script rather than trusted from the page.
- **One allowed header**, `X-Fantasy-Filter`, and it must be JSON.
- **Nothing is stored**, and the cookies never reach the page — only
  the JSON answer does.
- Only pages listed in the manifest's `bridge.js` matches can ask at
  all (our own site, localhost, and local files).

If you'd rather not grant this, don't install the extension: public
leagues and every Sleeper league work without it.


## Finding your leagues for you (v1.5.0)

Same cookie asymmetry, put to better use. The site cannot ask "which
leagues am I in" — the question is keyed on your `SWID`, which it
can't see. We can, so it doesn't have to ask you for a league id at
all: install the extension, open **My league**, and your ESPN
leagues are already on screen as buttons. Private ones included,
since this is the same signed-in path as above.

Two readers, because the good one is undocumented:

1. `fan.api.espn.com/apis/v2/fans/{SWID}` lists every league a SWID
   belongs to. Nothing obliges its shape to hold still, so
   `fanLeagues()` reads it loosely and returns an empty list rather
   than a wrong one.
2. When that comes back empty, the `kona_v3_environment_season_ffl`
   cookie. It only remembers the last league you looked at and
   carries no names, but it has been stable for years, and the site
   fills the names in with one public preview call.

Only league ids and names cross back to the page; the cookies stay
here. `fan.api.espn.com` is already inside the `https://*.espn.com/*`
host permission, so this asked for nothing new.

The league you pick is also kept here, under `ffda_league`, so the
site and the draft tool agree on which league you're in without you
setting it twice. The page writes it and reads it back; it is a
setting, not a credential, and "reset the board" no longer clears it.

## Keeping your prep when the browser forgets (v1.5.0)

The draft tool's own state — your player ratings, your note edits, the
ranks you imported — lived only in the page's `localStorage`. That is
the wrong place for the only copy of work you can't get back: "clear
browsing data" wipes it, and it doesn't cross origins, so a local copy
of the tool and foss.football each keep their own and neither can see
the other's.

So the page mirrors that prep here, under `ffda_prep`, on every change
(`save-prep`), and gets it back with every state push. Extension storage
survives clearing site data and is one store for every origin this
bridge runs on.

`localStorage` is still the working copy — synchronous, always there,
and untouched when the extension isn't installed. This is a backup that
wins only when it is newer. Conflicts are settled by the page, by
timestamp, on the whole blob: it adopts what we hand back only if
`savedAt` beats its own, and pushes its own up when ours is older or
missing. Merging two edit histories player-by-player would invent a
third state that neither browser ever had.

One wrinkle worth knowing about: a write here fires
`chrome.storage.onChanged` on the page that made it, and relaying that
echo would re-render the board on every click. `bridge.js` remembers the
last blob the page pushed and drops its own echo — but still relays prep
changes from *other* tabs, which is what keeps two open copies level.

