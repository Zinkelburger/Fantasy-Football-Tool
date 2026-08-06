/* Every user-facing sentence on the site comes from site/copy.md, built
 * into data/copy.json by build_site.py. Edit the markdown, re-run the
 * build; neither index.html nor any of these scripts needs touching.
 *
 * Two ways to use a block:
 *
 *   markup   <div data-copy="board.blurb"></div>        rendered markdown
 *            <p data-copy-text="home.tagline"></p>      the words only
 *            <th data-copy-title="tip.dome"></th>       hover text
 *            <input data-copy-placeholder="live.field.placeholder">
 *            <a data-copy-aria="link.github">                 aria-label
 *
 *   script   Copy.text("league.loading")                for textContent
 *            Copy.attr("tip.dome")                      inside title="…"
 *            Copy.fill("live.hint.espn", {id: 42})      {placeholders}
 *
 * A missing key returns an empty string rather than throwing: a typo in
 * the markdown should cost one sentence, not the page.
 */
"use strict";

const Copy = (() => {
  let blocks = {};

  async function load() {
    try {
      const r = await fetch("data/copy.json");
      if (!r.ok) throw new Error(`data/copy.json: HTTP ${r.status}`);
      blocks = await r.json();
    } catch (e) {
      console.error("copy failed to load — the site will render bare", e);
    }
  }

  const get = (key) => blocks[key] || null;
  const html = (key) => (get(key) || {}).html || "";
  const text = (key) => (get(key) || {}).text || "";

  const quote = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;");

  /* For a value going into title="…" in a template string. */
  const attr = (key) => quote(text(key));

  /* {name} placeholders, filled from an object. An unknown name is left
     as written, so a mistyped placeholder is visible instead of blank. */
  const fill = (key, vars) => text(key).replace(
    /\{(\w+)\}/g, (m, k) => (vars && k in vars ? String(vars[k]) : m));

  const fillAttr = (key, vars) => quote(fill(key, vars));

  function apply(root) {
    const r = root || document;
    r.querySelectorAll("[data-copy]").forEach(n => {
      const v = html(n.dataset.copy);
      if (v) n.innerHTML = v;
    });
    r.querySelectorAll("[data-copy-text]").forEach(n => {
      const v = text(n.dataset.copyText);
      if (v) n.textContent = v;
    });
    r.querySelectorAll("[data-copy-title]").forEach(n => {
      const v = text(n.dataset.copyTitle);
      if (v) n.title = v;
    });
    r.querySelectorAll("[data-copy-placeholder]").forEach(n => {
      const v = text(n.dataset.copyPlaceholder);
      if (v) n.placeholder = v;
    });
    r.querySelectorAll("[data-copy-aria]").forEach(n => {
      const v = text(n.dataset.copyAria);
      if (v) n.setAttribute("aria-label", v);
    });
  }

  return { load, apply, html, text, attr, fill, fillAttr };
})();
