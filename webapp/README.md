# Fantasy Football Draft Tool — Web Version

A browser-based port of the Go/Fyne desktop app (`../go`). The draft board can
run as a static page, with draft state stored in your browser's localStorage.
Claude Code integration requires the optional local server and a CLI login.
Draft picks flow in live from the Chrome extension; AI
recommendations use OpenAI, Ollama, or the optional local Claude Code bridge.

## Local ESPN draft with Claude Sonnet (no API key)

From the repository root:

```bash
python3 webapp/local_server.py
```

Open **http://localhost:8765** in Chrome and leave the terminal running. This
serves the bundled dashboard locally; foss.football does not need to be online.
Python's standard library is sufficient. Claude Code must be installed and signed
in with your subscription (`claude auth login`). The server prints login readiness.
On a fresh local dashboard, Claude Code is selected automatically; otherwise choose
**Settings → AI → Use Claude Code**. **Ask AI** (Q) starts Sonnet and streams its
answer into the dashboard using the current draft state and candidate notes.

Install the Chrome extension in the **same Chrome profile** as the ESPN and local
dashboard tabs:

1. Run `python3 chrome-extension/package.py` from the repository root.
2. Open `chrome://extensions`, enable Developer mode, click **Load unpacked**, and
   select `chrome-extension/dist/chrome`.
3. Open your ESPN draft room and the local dashboard. Refresh both tabs if they
   were already open when you installed/reloaded the extension.
4. Confirm **Extension: connected** and that actual ESPN picks and your roster
   appear correctly. The connected badge alone confirms the bridge, not the ESPN
   selectors. Try an ESPN mock before relying on it for a live draft.
5. Select scoring and check league size/draft slot in Settings → Draft. Put any
   custom lineup rules in Settings → Prompts; the dashboard otherwise assumes its
   standard 1-QB, RB/WR-flex lineup. Ask AI gives advice; make the actual pick on ESPN.

The localhost server binds only to this computer, serves dashboard assets, and
allows one Claude answer at a time. It launches the official `claude -p --model
sonnet` command with tools/customizations disabled and a temporary working directory.
It uses the CLI subscription login, strips API-key/provider overrides from the child
environment, and never sends credentials to the page. Each question is independent;
draft context is supplied again so previous picks do not linger as available.

Claude still needs internet access and available subscription usage. Anthropic's
[current notice](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)
says `claude -p` draws from subscription limits (the announced separate credit
change was paused). This is not unlimited or offline inference. The bridge does
not browse for new injury news; it reasons from the provided notes and draft state.
Errors and a 150-second timeout are surfaced in the AI panel without stopping the
board. A plain `python -m http.server` or `file://` page still supports draft tracking,
but cannot launch Claude Code.

Verification: `python3 -m unittest discover -s webapp -p 'test_*.py'` exercises the
bridge's request checks, static-file boundary, streaming and error handling without
using Claude credits. `node --test webapp/test_draft_connection.cjs` checks draft
prompt context, synthetic ESPN markup, and extension URL coverage. A real Sonnet
connection and the Ask AI browser flow were also
tested on September 5, 2026. Extension 1.5.1 was also tested in a browser against
user-supplied ESPN room HTML: 58 picks and the correct four-player personal roster.
It reads draft-board pick cells explicitly marked `myTeam`, so the selectable
roster panel cannot substitute another team. Reload the extension in
`chrome://extensions`, then refresh ESPN and the dashboard to activate updates.
Live mutation timing and your installed Chrome bridge still warrant a mock check.

## Browser regression tests

From the repository root, run `npm ci`, `npx playwright install chromium`,
then `npm test`. This builds the actual `public/` deployment and runs the
Python/Node tests plus Chrome browser scenarios covering navigation, scoring,
notes, manual drafting, ESPN/Sleeper messages, predictions, backup restore,
AI streaming/errors, and phone layouts. Installed Google Chrome is used when
available; set `CHROME_PATH` to choose another Chromium executable.
GitHub Actions runs the same suite on pushes to main and pull requests.

The hosted fallback is [the Cloudflare draft tool](https://fantasy-football-tool.pages.dev/webapp/).
Extension 1.5.2 adds this exact origin to the bridge. Run
`python3 chrome-extension/package.py`, reload the unpacked extension, and
refresh the dashboard to activate it.

External draft messages and AI responses use fixtures, so these tests do not
make real draft picks or consume AI credits. They cannot verify selectors in
your live ESPN room or your installed extension; use a mock draft for that.

## Refreshing the draft board

Run `python3 engine/update_ranks.py` then `python3 webapp/build_data.py` from
this repository's root, and reload the dashboard. Rank follows current FFC
12-team mock ADP for the selected scoring format; hover it for the average
pick. The sample date is displayed above the board. A dash means that player
is outside the fresh sample. ESPN is overall ADP order, not standard-only or
the draft room's default order. Imported ranks still take precedence; use
Settings → Revert to bundled if you want to remove your personal overrides.

For a new draft, close the old ESPN draft tab, use Settings → Reset draft state,
then open the new draft. There is no draft-ID isolation yet: old tabs can write
old picks back. Reset clears picks, roster, ratings and cached extension state;
it preserves edited notes, imported ranks and settings. Recheck draft slot and
team count. Merely opening a new draft does not reliably clear accumulated picks.

## Running it

**Option A — just open it.** Double-click `index.html` (or `File → Open` in
Chrome). The board works from disk because the player data is bundled into
`data/players-data.js`. Use the local server above for Claude Code integration.

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
