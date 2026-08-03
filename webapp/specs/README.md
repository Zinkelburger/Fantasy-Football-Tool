# User-action specs

One file per thing a user can do (or should be able to do) in the web app.
This is the source of truth for what the app promises: if a spec says
`status: implemented`, the behavior must actually exist in the app; if the app
grows a user-facing control with no spec here, that's a gap too.

## File format

```markdown
---
id: read-player-note          # kebab-case, matches the filename
title: One-line user goal
status: implemented           # implemented | missing
---

**As a user, I want to** <goal>.

## Steps            <- exactly what the user does (clicks, keys)
## Expected         <- observable results, each one checkable
## Verify against   <- hints: files/functions where this lives (not proof)
```

`status: missing` marks an action we want but haven't built — the backlog
lives here in the same format, so building a feature is just flipping its
spec to `implemented` and making verification pass.

## Verifying

Run `/verify-specs` in Claude Code. It checks, for every spec file:

1. Do the Steps/Expected match what the code actually does (with
   file:line evidence)?
2. Is the `status:` field honest?
3. Reverse check: does every user-facing control in `index.html`/`app.js`
   map to some spec?

It reports a pass/fail table and lists any drift it found.
