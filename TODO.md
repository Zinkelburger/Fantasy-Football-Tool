# TODO — mock-draft verification (do this BEFORE draft week)

The extension's draft-room sync depends on each site's CSS class names —
the single most likely thing to be broken on draft day. **ESPN and
Sleeper were verified in mock drafts; Yahoo, NFL.com and CBS have NEVER
been tested against a live draft room.** Their scrapers are educated
guesses and should be assumed broken until a mock draft proves
otherwise.

Deadline: family league drafts around Labor Day (2026-09-07). Run these
by **late August** so there's time to fix selectors.

## The checklist

- [ ] **Sleeper mock draft** — re-verify (was working; selectors rot).
  Picks should appear in the app as they happen. Sleeper reports the
  *available* list, so the board should stay a complete snapshot.
- [ ] **ESPN mock draft** — re-verify (was working). Watch the console:
  `espn-draft.js` logs which container it scoped "Your Team" to. If it
  warns that no my-team container matched, your draft slot won't
  auto-detect — find the real container in DevTools and add it to
  `MY_ROSTER_CONTAINERS` in `chrome-extension/espn-draft.js`.
- [ ] **Yahoo mock draft** — NEVER TESTED. Watch for `[ffda:yahoo]`
  console lines saying which selector matched.
- [ ] **NFL.com mock draft** — NEVER TESTED. Watch for `[ffda:nfl]`.
- [ ] **CBS mock draft** — NEVER TESTED. Watch for `[ffda:cbs]`.

## How to run one

1. `chrome://extensions` → verify the extension is loaded (Reload it if
   the manifest changed).
2. Join a mock draft lobby on the site.
3. Open the draft tool (foss.football → Draft Tool, or `webapp/index.html`)
   side-by-side. Header should say **Extension: connected**.
4. Confirm: picks stream in, your roster fills only with YOUR players,
   and names match the right people (fuzzy matcher can miss — click
   Undo on a wrong row to override).

## If nothing comes through (Yahoo / NFL / CBS especially)

Run `window.ffdaDiag()` in the draft-room page console and paste its
output into a Claude session (or a GitHub issue). It dumps every panel
that looks like a pick list, so the candidate selectors in
`chrome-extension/<site>-draft.js` can be fixed in minutes.

## Also before draft day (smaller)

- [ ] Re-fetch data feeds if stale (see `docs/DATA-SOURCES.md` —
  JuiceBox sheets + FantasyPros CSV go suspect after ~1 week in August;
  re-fetch the morning of the draft, then `python3 build_deploy.py`).
- [ ] `python3 engine/update_ranks.py` daily during draft week.
