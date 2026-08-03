// Shared helpers for the per-site draft scrapers (Yahoo, NFL.com, CBS).
// ESPN (espn-draft.js) and Sleeper (sleeper-draft.js) predate this file and
// keep their own local copies of debounce/observer logic.
//
// These sites' draft rooms cannot be inspected without a live mock draft, so
// every scraper works off *candidate* selector lists plus a generic
// rows-that-look-like-players fallback, and logs loudly which one matched.
// Run window.ffdaDiag() in the draft-room console to dump what the scraper
// sees — paste that output into an issue/Claude session to fix selectors.

function ffdaDebounce(fn, wait) {
  let timer = null;
  return function () {
    clearTimeout(timer);
    timer = setTimeout(fn, wait);
  };
}

// UI strings that show up inside player-list containers but are not players.
const FFDA_UI_WORDS = new RegExp(
  '^(round|pick|picks|player|players|team|teams|queue|queued|results?|draft|' +
  'drafted|available|position|positions|watchlist|my team|autopick|autodraft|' +
  'auto|timer|history|board|roster|bench|starters?|settings?|filters?|all|' +
  'none|search|rank|adp|proj|projected|points|bye|status|news|notes?|stats?|' +
  'add|drop|trade|owner|manager|time left|on the clock)$', 'i');

// Does a scraped string plausibly name an NFL player (or a D/ST unit)?
// Permissive on purpose: the web app's fuzzy matcher drops anything that
// doesn't correspond to a board player, so false positives are cheap and
// false negatives lose picks.
function ffdaLooksLikeName(s) {
  s = (s || '').replace(/\s+/g, ' ').trim();
  if (!s || s.length < 4 || s.length > 40) return false;
  if (FFDA_UI_WORDS.test(s)) return false;
  if (/D\/?ST|Defense/i.test(s)) return true;
  if (/\d/.test(s)) return false;
  const words = s.split(' ');
  if (words.length < 2 || words.length > 4) return false;
  return words.every(w =>
    /^[A-Z][A-Za-z.'’-]*\.?$/.test(w) || /^(Jr\.?|Sr\.?|II|III|IV|V)$/.test(w));
}

// First element matching any candidate selector, or null.
function ffdaFindContainer(candidates) {
  for (const sel of candidates) {
    let el = null;
    try { el = document.querySelector(sel); } catch (e) { /* bad selector */ }
    if (el) return { el: el, sel: sel };
  }
  return null;
}

// Extract player names inside root: try each name selector in order and keep
// the first that yields valid names; otherwise fall back to scanning the
// container's own rows (li/tr) for text that looks like a player.
function ffdaCollectNames(root, nameSelectors) {
  for (const sel of nameSelectors) {
    let els = [];
    try { els = Array.from(root.querySelectorAll(sel)); } catch (e) { continue; }
    const names = [];
    for (const el of els) {
      // First text node only, so "Bijan Robinson RB - ATL" nested spans don't
      // glue together; fall back to full text.
      const first = el.childNodes.length ? el.childNodes[0].textContent : el.textContent;
      const cand = [first, el.textContent].map(t => (t || '').replace(/\s+/g, ' ').trim());
      const good = cand.find(ffdaLooksLikeName);
      if (good && !names.includes(good)) names.push(good);
    }
    if (names.length) return { names: names, via: sel };
  }
  // Generic fallback: any row-ish element whose leading text looks like a name.
  const rows = root.querySelectorAll('li, tr, [class*="row" i]');
  const names = [];
  for (const row of rows) {
    const text = (row.textContent || '').replace(/\s+/g, ' ').trim();
    // Try the first 2–4 words of the row.
    const words = text.split(' ');
    for (let n = 4; n >= 2; n--) {
      const head = words.slice(0, n).join(' ');
      if (ffdaLooksLikeName(head)) {
        if (!names.includes(head)) names.push(head);
        break;
      }
    }
  }
  return { names: names, via: 'row-fallback' };
}

// Watch one feed (picked players, roster, …): wait for a container, then
// re-extract on every (debounced) mutation. Logs which selector matched once,
// and complains once if nothing ever matches.
function ffdaWatch(cfg) {
  // cfg: { site, type, containers, nameSelectors, retryMs=1000, maxRetries=60 }
  let tries = 0;
  let logged = false;

  function extract(containerEl, containerSel) {
    const got = ffdaCollectNames(containerEl, cfg.nameSelectors);
    if (!logged && got.names.length) {
      logged = true;
      console.log(`[ffda:${cfg.site}] ${cfg.type}: container "${containerSel}", ` +
                  `names via "${got.via}" (${got.names.length} found)`);
    }
    if (got.names.length) {
      sendDataToServer({ site: cfg.site, type: cfg.type, players: got.names });
    }
  }

  function attach() {
    const found = ffdaFindContainer(cfg.containers);
    if (!found) {
      tries++;
      if (tries === (cfg.maxRetries || 60)) {
        console.warn(`[ffda:${cfg.site}] ${cfg.type}: no container matched after ` +
          `${tries} tries. Candidates: ${cfg.containers.join(', ')} — run ` +
          `window.ffdaDiag() and report the output so the selectors can be fixed.`);
      }
      setTimeout(attach, cfg.retryMs || 1000);
      return;
    }
    extract(found.el, found.sel);
    const observer = new MutationObserver(
      ffdaDebounce(() => extract(found.el, found.sel), 250));
    observer.observe(found.el, { childList: true, subtree: true, characterData: true });
    console.log(`[ffda:${cfg.site}] observer attached: ${cfg.type} @ "${found.sel}"`);
  }

  attach();
}

// Console helper for mock-draft debugging: dumps every element whose class or
// id smells like a draft-room panel, with a text preview, so the right
// selectors can be identified without digging through DevTools.
window.ffdaDiag = function () {
  const smells = ['pick', 'draft', 'result', 'roster', 'team', 'player', 'queue', 'history'];
  const seen = new Set();
  const out = [];
  for (const el of document.querySelectorAll('[class], [id]')) {
    const cls = typeof el.className === 'string'
      ? el.className : (el.className && el.className.baseVal) || '';
    const key = `${el.tagName}.${cls}#${el.id}`;
    if (seen.has(key)) continue;
    const idc = (cls + ' ' + el.id).toLowerCase();
    if (!smells.some(s => idc.includes(s))) continue;
    seen.add(key);
    const text = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120);
    if (text) out.push(`${key} :: ${text}`);
    if (out.length >= 80) break;
  }
  console.log('=== ffda diagnostic (paste this back to fix selectors) ===\n' + out.join('\n'));
  return `${out.length} candidate containers logged`;
};
