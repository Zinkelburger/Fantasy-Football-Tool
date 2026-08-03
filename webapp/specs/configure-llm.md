---
id: configure-llm
title: Configure the AI (key, model, prompts)
status: implemented
---

**As a user, I want to** bring my own OpenAI key or local Ollama, and tune the
prompts, without any of it leaving my browser.

## Steps
1. Open Settings (⚙) — it opens on the **AI** tab.
2. Paste an OpenAI key and optionally a model name — or tick "Use Ollama"
   with an endpoint and model.
3. On the **Prompts** tab, optionally edit the system/user prompts; "Reset
   prompts to defaults" restores them.
4. Save.

## Expected
- Settings are organized in tabs (AI | Prompts | Draft | My data | Debug)
  with a **View all** button that shows every setting on one page.
- **Save is greyed out until something actually changes** — compared against
  the values at dialog-open, so editing a field back to its original value
  re-disables it. Its tooltip says "Nothing changed yet" while disabled.
- Everything persists in this browser's localStorage only; requests go
  browser → API directly with no middle server.
- The custom model is tried first, then the fallback chain.
- Custom prompts are actually used in the next Ask AI query.

## Verify against
- `webapp/app.js` — `openSettings()`, `saveSettings()`, `DEFAULT_SETTINGS`
- `webapp/index.html` — `#settings-dialog`
