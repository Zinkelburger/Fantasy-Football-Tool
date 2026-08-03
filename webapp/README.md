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

**Option B — foss.football (production).** `python3 ../build_deploy.py`
assembles this app under `/webapp/` of the Cloudflare Pages deploy (see
`../site/README.md`). The extension manifest already lists the origin.

**Option C — GitHub Pages.** The site is pure
static files, but Pages only serves from the repo root or `/docs` — there is no
"deploy from `/webapp`" option. Pick one:

- push `webapp/`'s contents to the root of a `gh-pages` branch, or
- rename this directory to `docs/` and set Pages → branch `main`, folder
  `/docs`, or
- add an Actions workflow that uploads `webapp/` as the Pages artifact.

Whichever you choose, the resulting origin must be listed in the extension's
`manifest.json` bridge entry or live sync will not work there (see below).

**Option D — any local server.** `python3 -m http.server` in this directory.

## Features (parity with the desktop app, plus some)

- Ranked player board for STD / 0.5 PPR / PPR (switcher in the header), with
  tooltips on every column and **one** site-rank column that auto-matches
  where your draft is (ESPN by default, Sleeper when detected — Settings can
  pin it). Pos shows NFL-team depth (WR2 = that team's 2nd WR), site ranks
  show a quiet delta vs board rank (**11 (−4)** = that site is 4 spots lower
  on him, may fall to you), and clicking Rank/ESPN/Sleeper sorts the view
- Position filters, search, per-player analysis notes — **one click on a row
  opens the note** as a tab next to AI Output (Ctrl+click for an extra tab,
  × to close, Obsidian-style)
- **Draft Board tab** (B): Sleeper-style snake grid, picks colored by
  position, past picks greyed, your next pick pink — on the main board too, a
  pink "Your next pick — #N" line shows how far away you are. Team headers
  show each team's roster chips plus a needs line ("needs QB, TE"), bold red
  when a team is deep in the draft with none of a position. **Who should I
  take?** deterministically simulates just the picks between now and your
  turn — opponents draft by their own site's rankings, adjusted for team
  needs (no AI) — tints predicted-gone players orange on the board, shows
  best available now vs at your pick per position with a "falls" figure
  (board spots lost by waiting), and headlines a **Suggested pick** (the
  position that drops off hardest before your following pick, among ones
  your roster needs) — naming who you'd fall back to if you passed. Every
  name shows both your board rank and the ranking the bots draft from, and
  a toolbar button states which ranking that is ("Bots: ESPN ADP") and
  opens the controls to change it. It
  stays on, re-simulating after every real pick, until **Return to live**.
  League shape defaults to 12 teams / 15 rounds with the slot auto-detected;
  the controls appear in Debug mode
- **Resizable split**: drag the divider between the board and the right
  panel (double-click resets); **tabbed Settings** (AI | Prompts | Draft |
  My data | Debug, plus View all) with a Debug tab holding Manual mode and
  Reset draft state — Manual mode also adds a header Reset button
- **Your Team as a depth chart**: QB1/RB1/RB2… chips, team/bye/rank columns,
  a "Still need" line for unfilled starters (bold red when it's getting
  urgent), collapsible position groups,
  click a player for their note, » collapses the whole panel
- Cycle ✅/❌ target markers anywhere; **Manual mode** (Settings) reveals
  Picked/+Team buttons for extension-less drafting — in a live draft the
  extension does all of that automatically
- **? help**: keyboard reference, column glossary, data stamp, and a guided
  spotlight tour — the footer stays clean
- **Keyboard-first**: ↑/↓ select, **D**/Space marks ✅/❌, **P** picks,
  **T** team, **Enter**/**E** open/edit the note, **Q** asks the AI,
  **A**/**B** switch tabs, **/** searches, **X**/**Esc** close a tab —
  buttons show their shortcut in the hover tooltip
- **Your own rankings**: Settings → Download rankings (CSV), reorder in
  Excel/Sheets, Import — the board re-sorts instantly. Also accepts a plain
  (optionally numbered) list of names. Stored as a localStorage overlay per
  scoring format; revert anytime.
- **Editable notes**: Edit button in the note tab (or press E); edits overlay the
  bundled notes (✎ in the table), feed the AI prompt, and can be downloaded
  as markdown to merge back into `go/analysis/`
- **Export/Import my data**: one JSON file with markers, picks, team, rank
  overrides, note edits, and prompts — move your prep between browsers
  (API key never included)
- **Ask AI** (Q): sends pick number, picked players, your roster, and the full
  notes of the top-15 available players to the LLM — same prompt template as
  the Go app — and streams the answer with a model fallback chain
  (`gpt-5-nano → gpt-5-mini → gpt-4o-mini`, or your own model from Settings)
- Live draft sync from the Chrome extension — ESPN and Sleeper (verified),
  plus Yahoo, NFL.com and CBS (scrapers shipped but **selectors unverified**;
  run a mock draft there first, see below)

Every user-facing action is written down as a checkable spec in `specs/` —
one file per action, including planned ones marked `status: missing`. Run
`/verify-specs` in Claude Code to have AI verify the app and the specs still
agree.

## Chrome extension sync

1. The extension's content scripts on the ESPN/Sleeper/Yahoo/NFL.com/CBS draft page scrape
   picked/roster players and write them to `chrome.storage.local`
   (`chrome-extension/content.js`). Scrapes are debounced and identical
   payloads are skipped, so a ticking draft clock doesn't cause a write storm.
2. `chrome-extension/bridge.js` runs on this web app's page, reads that
   storage, and relays it in via `window.postMessage`, pushing live updates
   whenever the draft page writes new data.
3. **You do not have to switch tabs.** `chrome.storage.onChanged` fires in
   background tabs, so this page updates while you're looking at the draft
   room — put the two windows side by side. And because the data is persisted
   in extension storage, the two tabs don't need to be open simultaneously
   either; open this one whenever and it picks up the latest state.

Setup: `chrome://extensions` → Developer mode → Load unpacked →
`chrome-extension/` (or press **Reload** if already installed, since the
manifest changed). To use the app from `file://`, also enable "Allow access to
file URLs" on the extension. **Firefox** works too: see
`chrome-extension/README.md` for the temporary-install and AMO-signing
paths, plus the host-permission caveat.

**Hosting elsewhere:** add your exact origin to the bridge entry's `matches` in
`manifest.json`. Keep it exact — a wildcard like `https://*.github.io/*` would
inject the bridge into every GitHub Pages site on the internet.
`https://foss.football` (the production site, deployed via `../build_deploy.py`
to Cloudflare Pages) is already listed, and the bridge runs with
`all_frames: true` so it also works when the site iframes this app in its
Draft Tool view.

The header shows `Extension: connected` once the bridge is present. The old
localhost POST to the Go desktop app still happens too, so the desktop app
keeps working unchanged.

No extension? Everything still works — click **Picked** on players as they go.

### Picks accumulate, and you can override them

ESPN's pick feed is a ticker, so any single scrape may only show recent picks.
The app therefore treats extension picks as **append-only**: a scrape that comes
back short can never un-pick your board. If the fuzzy name matcher ever picks
the wrong player, click **Undo** on that row — the override is remembered and
survives later scrapes. Sleeper is different (it reports the full *available*
list, which is a complete snapshot), so its picks are recomputed rather than
accumulated. **Reset draft state** clears all of it between drafts.

### Before draft day: run a mock

The scrapers depend on each site's CSS class names, which are the most likely
thing to break. Run a mock draft on your league's site first and check the
page console:

- **ESPN**: picks should appear in the app as they happen; `espn-draft.js`
  logs which container it scoped **Your Team** to. If it warns that no "my
  team" container matched and the roster fills with other people's players,
  find the real container in DevTools and add its selector to
  `MY_ROSTER_CONTAINERS` in `chrome-extension/espn-draft.js`.
- **Yahoo / NFL.com / CBS**: these scrapers were written *without* access to
  a live draft room, so their selectors are educated guesses over a generic
  fallback — a mock draft is **required**, not just recommended. Watch the
  console for `[ffda:yahoo]` / `[ffda:nfl]` / `[ffda:cbs]` lines saying which
  selector matched. If nothing matches (or wrong names come through), run
  `window.ffdaDiag()` in the draft-room console and paste its output into a
  Claude session (or a GitHub issue) — it dumps every panel that smells like
  a pick list so the candidate selectors in `chrome-extension/<site>-draft.js`
  can be fixed in minutes.

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
