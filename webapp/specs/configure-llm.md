---
id: configure-llm
title: Configure the AI (key, model, prompts)
status: implemented
---

**As a user, I want to** choose OpenAI, local Ollama or my Claude Code subscription,
and tune the prompts. Only the chosen provider receives the draft question.

## Steps
1. Open Settings (⚙) — it opens on the **AI** tab.
2. Paste an OpenAI key and optionally a model name — or tick "Use Ollama"
   with an endpoint and model — or select "Use Claude Code" on the local dashboard.
3. On the **Prompts** tab, optionally edit the system/user prompts; "Reset
   prompts to defaults" restores them.
4. Save.

## Expected
- Settings are organized in tabs (AI | Prompts | Draft | My data | Debug)
  with a **View all** button that shows every setting on one page.
- **Save is greyed out until something actually changes** — compared against
  the values at dialog-open, so editing a field back to its original value
  re-disables it. Its tooltip says "Nothing changed yet" while disabled.
- Settings persist in this browser's localStorage. OpenAI/Ollama requests go
  directly to their endpoint; Claude Code requests go through the loopback server
  to the installed CLI. No Claude credential is stored in the browser.
- The Claude section shows login readiness. A fresh local setup selects it
  automatically if neither OpenAI nor Ollama is configured. An explicit saved
  opt-out is preserved. Claude Code takes precedence when checked.
- The custom model is tried first, then the fallback chain.
- Custom prompts are actually used in the next Ask AI query.

## Verify against
- `webapp/app.js` — `openSettings()`, `saveSettings()`, `DEFAULT_SETTINGS`
- `webapp/index.html` — `#settings-dialog`
