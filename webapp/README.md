# Fantasy Football Draft Tool — Web Version

A fully static, browser-based port of the Go/Fyne desktop app (`../go`). No
server, no accounts, no state stored anywhere except your own browser's
localStorage. Draft picks flow in live from the Chrome extension; AI
recommendations call the OpenAI API (or a local Ollama) directly from your
browser.

## Running it

**Option A — just open it.** Double-click `index.html` (or `File → Open` in
Chrome). Everything works from disk because the player data is bundled into
`data/players-data.js`.

**Option B — GitHub Pages (recommended for draft day).**
Settings → Pages → deploy from branch, folder `/webapp` (or copy `webapp/` to
a `gh-pages` branch). The site is pure static files.

**Option C — any local server.** `python3 -m http.server` in this directory.

## Features (parity with the desktop app)

- Ranked player board for STD / 0.5 PPR / PPR (switcher in the header)
- Position filters, search, per-player analysis notes (click a player's name)
- Mark players **Picked** (removed from the board), cycle ✅/❌ target markers,
  build **Your Team** (grouped by position)
- **Ask AI (Q)**: sends pick number, picked players, your roster, and the full
  notes of the top-15 available players to the LLM — same prompt template as
  the Go app — and streams the answer with a model fallback chain
  (`gpt-5-nano → gpt-5-mini → gpt-4o-mini`, or your own model from Settings)
- Live draft sync from the Chrome extension (ESPN and Sleeper)

## Chrome extension sync (how it works, and why tabs don't need to be open together)

1. The extension's content scripts on the ESPN/Sleeper draft page scrape
   picked/roster players (unchanged from before) and now **also write them to
   `chrome.storage.local`** (`chrome-extension/content.js`).
2. `chrome-extension/bridge.js` runs on this web app's page (it matches
   `*.github.io`, `localhost`, `127.0.0.1`, and `file://`), reads that storage,
   and relays it into the page via `window.postMessage`. It also pushes live
   updates whenever the draft page writes new data.
3. Because the data is *persisted in extension storage*, the draft tab and this
   tab do **not** need to be open at the same time — open this tab whenever you
   want and it receives the latest state.

Setup: `chrome://extensions` → Developer mode → Load unpacked →
`chrome-extension/` (or press **Reload** if already installed, since the
manifest changed). If you host the app somewhere other than `*.github.io`,
add that origin to the bridge entry in `manifest.json`. To use the app from
`file://`, also enable "Allow access to file URLs" on the extension.

The header shows `Extension: connected` once the bridge is present. The old
localhost POST to the Go desktop app still happens too, so the desktop app
keeps working unchanged.

No extension? Everything still works — click **Picked** on players as they go.

## API key & privacy

- Your OpenAI key is entered in Settings (⚙) and saved **only in this
  browser's localStorage**. Requests go browser → api.openai.com directly.
- Never commit a key into this directory or bake it into the page — anyone who
  can view the site source could read it.
- For Ollama on a *hosted* page: start Ollama with your site allowed, e.g.
  `OLLAMA_ORIGINS=https://<you>.github.io ollama serve`. (From `file://` or
  localhost it generally works without this.)

## Updating player data

Rankings and notes are bundled at build time from `../go/*.csv` and
`../go/analysis/*.md`:

```bash
python3 build_data.py   # regenerates data/players-data.js
```

Re-run it (and redeploy) whenever the CSVs or notes change.

## Resetting between drafts

Settings (⚙) → **Reset draft state** clears picked players, your team, target
markers, and the extension's stored draft data.
