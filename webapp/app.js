/* Fantasy Football Draft Tool — static web app.
 * Port of the Go/Fyne desktop app. All state lives in this browser's
 * localStorage; draft picks arrive from the chrome extension via
 * window.postMessage (see chrome-extension/bridge.js).
 */
'use strict';

/* ========================= pure helpers ========================= */

// Mirrors go/loader.go nameCleaner: strip Jr./Sr./II/III/IV/V suffixes.
const SUFFIX_RE = /\s+(?:Jr\.|Sr\.|II|III|IV|V)$/;

function cleanName(name) {
  return name.trim().replace(SUFFIX_RE, '').trim();
}

// Port of ui.go fuzzyMatchPlayer: exact -> substring -> word overlap.
function fuzzyMatchPlayer(inputName, allPlayers) {
  const inputLower = inputName.trim().toLowerCase();
  if (!inputLower) return null;

  for (const p of allPlayers) {
    if (p.name.toLowerCase() === inputLower) return p.name;
  }

  for (const p of allPlayers) {
    const playerLower = p.name.toLowerCase();
    if (inputLower.includes(playerLower) || playerLower.includes(inputLower)) {
      return p.name;
    }
  }

  const inputWords = inputLower.split(/\s+/).filter(Boolean);
  for (const p of allPlayers) {
    const playerWords = p.name.toLowerCase().split(/\s+/).filter(Boolean);
    let matchCount = 0;
    for (const iw of inputWords) {
      if (playerWords.includes(iw)) matchCount++;
    }
    if (matchCount >= 2 && matchCount >= Math.floor(inputWords.length / 2)) {
      return p.name;
    }
  }
  return null;
}

// Port of players.go loadTruncatedNote: short summary for the table row.
function truncateNote(content) {
  if (!content) return 'No note';
  const lines = content.split('\n');

  let analysisStarted = false;
  const analysisLines = [];
  for (const line of lines) {
    if (line.trim().startsWith('# Analysis')) { analysisStarted = true; continue; }
    if (analysisStarted && line.trim() !== '') analysisLines.push(line);
  }

  let text = '';
  if (analysisLines.length > 0) {
    text = analysisLines.join(' ');
  } else {
    for (let i = lines.length - 1; i >= 0; i--) {
      const line = lines[i].trim();
      if (line !== '' && !line.startsWith('#')) { text = line; break; }
    }
  }
  if (!text) return 'No content';

  text = text.replace(/\*\*/g, '').replace(/\*/g, '').replace(/- /g, '').trim();
  if (text.length <= 40) return text;

  const words = text.split(/\s+/);
  let truncated = '';
  for (const word of words) {
    if (truncated.length + word.length + 1 > 37) break;
    truncated += (truncated ? ' ' : '') + word;
  }
  return truncated + '...';
}

// Port of prompt_manager.go BuildFullUserPrompt — same template, verbatim.
function buildUserPrompt(currentPick, pickedPlayersStr, currentTeam, userPromptCustom, allNotes) {
  return `It is pick ${currentPick} of a 2025 fantasy football draft. ` +
    `These players have been picked so far: ${pickedPlayersStr}. ` +
    `Current team info: ${currentTeam}. ${userPromptCustom} ` +
    `The notes for each player are separated by '---start playername---' and '---end playername---'.` +
    `\n\nPlayer Notes:\n${allNotes}`;
}

// Sleeper sends AVAILABLE players; picked = all - available (go/http_server.go
// handleAvailablePlayers), but match scraped names fuzzily instead of exactly.
function computePickedFromAvailable(availableNames, allPlayers) {
  const availableSet = new Set();
  for (const raw of availableNames) {
    const match = fuzzyMatchPlayer(raw, allPlayers);
    if (match) availableSet.add(match);
  }
  return allPlayers.filter(p => !availableSet.has(p.name)).map(p => p.name);
}

const POSITION_ORDER = { QB: 1, RB: 2, WR: 3, TE: 4, K: 5, DST: 6, DEF: 6 };

function groupByPosition(players) {
  const sorted = players.slice().sort((a, b) => {
    const pa = POSITION_ORDER[a.pos] || 9;
    const pb = POSITION_ORDER[b.pos] || 9;
    if (pa !== pb) return pa - pb;
    return (a.rankNum || 9999) - (b.rankNum || 9999);
  });
  const groups = [];
  let current = null;
  for (const p of sorted) {
    if (!current || current.pos !== p.pos) {
      current = { pos: p.pos, players: [] };
      groups.push(current);
    }
    current.players.push(p);
  }
  return groups;
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Minimal markdown renderer for notes and LLM output (headings, lists,
// bold/italic/code/links). Input is escaped first, so output is safe HTML.
function renderMarkdown(md) {
  const inline = (s) => s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');

  const lines = escapeHtml(md).split('\n');
  const out = [];
  let list = null; // 'ul' | 'ol' | null
  let para = [];

  const flushPara = () => {
    if (para.length) { out.push('<p>' + inline(para.join(' ')) + '</p>'); para = []; }
  };
  const flushList = () => {
    if (list) { out.push(`</${list}>`); list = null; }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const trimmed = line.trim();
    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    const bullet = /^[-*•]\s+(.*)$/.exec(trimmed);
    const numbered = /^\d+[.)]\s+(.*)$/.exec(trimmed);

    if (trimmed === '') {
      flushPara(); flushList();
    } else if (heading) {
      flushPara(); flushList();
      const level = Math.min(heading[1].length, 3);
      out.push(`<h${level}>` + inline(heading[2]) + `</h${level}>`);
    } else if (bullet) {
      flushPara();
      if (list !== 'ul') { flushList(); out.push('<ul>'); list = 'ul'; }
      out.push('<li>' + inline(bullet[1]) + '</li>');
    } else if (numbered) {
      flushPara();
      if (list !== 'ol') { flushList(); out.push('<ol>'); list = 'ol'; }
      out.push('<li>' + inline(numbered[1]) + '</li>');
    } else if (list && /^\s{2,}/.test(raw)) {
      // continuation of a list item
      out[out.length - 1] = out[out.length - 1].replace(/<\/li>$/, ' ' + inline(trimmed) + '</li>');
    } else {
      flushList();
      para.push(trimmed);
    }
  }
  flushPara(); flushList();
  return out.join('\n');
}

const DEFAULT_SETTINGS = {
  apiKey: '',
  model: '',
  useOllama: false,
  ollamaEndpoint: 'http://localhost:11434',
  ollamaModel: '',
  scoringFormat: 'STD',
  // Same defaults as go/prompts/*.md
  systemPrompt: 'You are a fantasy football expert. Give a summary of who to draft and why.',
  userPrompt: 'Output the top several players you think could help me the most along with an ' +
    'explanation, considering their value, upside, and drawbacks. Look for high upside players ' +
    'with good matchups. Give me a short list at the end like 1. 2. 3. 4. I NEED THE LIST AT THE END!!!!',
};

// Same fallback chain as go/chatgpt.go AskStream.
const OPENAI_FALLBACK_MODELS = ['gpt-5-nano-2025-08-07', 'gpt-5-mini-2025-08-07', 'gpt-4o-mini'];

/* Node test hook: `require('./app.js')` gets the pure helpers and skips the DOM app. */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    cleanName, fuzzyMatchPlayer, truncateNote, buildUserPrompt,
    computePickedFromAvailable, groupByPosition, renderMarkdown, escapeHtml,
    DEFAULT_SETTINGS, OPENAI_FALLBACK_MODELS,
  };
} else {
  initApp();
}

/* ========================= browser app ========================= */

function initApp() {
  const $ = (id) => document.getElementById(id);

  if (!window.FF_DATA) {
    document.body.innerHTML = '<p style="padding:2rem">players-data.js is missing. ' +
      'Run <code>python3 build_data.py</code> in the webapp directory.</p>';
    return;
  }
  const DATA = window.FF_DATA;

  /* ---------- persistent state ---------- */
  const store = {
    load(key, fallback) {
      try {
        const raw = localStorage.getItem('ffda.' + key);
        return raw === null ? fallback : JSON.parse(raw);
      } catch (e) { return fallback; }
    },
    save(key, value) { localStorage.setItem('ffda.' + key, JSON.stringify(value)); },
    remove(key) { localStorage.removeItem('ffda.' + key); },
  };

  let settings = Object.assign({}, DEFAULT_SETTINGS, store.load('settings', {}));
  let manualPicked = new Set(store.load('manualPicked', []));   // canonical names
  let manualTeam = store.load('manualTeam', []);                // canonical names
  let toDraft = store.load('toDraft', {});                      // name -> 'yes' | 'no'
  let extState = store.load('extState', {});                    // raw bridge payloads

  /* ---------- volatile state ---------- */
  let posFilter = 'All';
  let searchText = '';
  let showPicked = false;
  let extDetected = false;
  let querying = false;
  let lastQueryAt = 0;

  /* ---------- derived data ---------- */
  function allPlayers() {
    return DATA.formats[settings.scoringFormat] || DATA.formats.STD;
  }

  function noteFor(player) {
    return DATA.notes[cleanName(player.name)] || '';
  }

  // Raw picked names from the extension (ESPN sends picked directly;
  // Sleeper sends available, which we invert).
  function extPickedRawNames() {
    const players = allPlayers();
    const picked = extState.picked_players;
    const available = extState.available_players;
    let names = [];
    if (picked && Array.isArray(picked.players)) names = picked.players.slice();
    if ((!names.length) && available && Array.isArray(available.players) && available.players.length) {
      names = computePickedFromAvailable(available.players, players);
    }
    return names;
  }

  // Canonical picked set = extension picks (fuzzy-matched) + manual picks.
  function pickedSet() {
    const players = allPlayers();
    const set = new Set(manualPicked);
    for (const raw of extPickedRawNames()) {
      const match = fuzzyMatchPlayer(raw, players);
      if (match) set.add(match);
    }
    return set;
  }

  function extPickedCanonical() {
    const players = allPlayers();
    const set = new Set();
    for (const raw of extPickedRawNames()) {
      const match = fuzzyMatchPlayer(raw, players);
      if (match) set.add(match);
    }
    return set;
  }

  function teamNames() {
    const players = allPlayers();
    const names = [];
    const seen = new Set();
    const add = (name) => { if (name && !seen.has(name)) { seen.add(name); names.push(name); } };
    for (const n of manualTeam) add(n);
    const roster = extState.roster_players;
    if (roster && Array.isArray(roster.players)) {
      for (const raw of roster.players) add(fuzzyMatchPlayer(raw, players));
    }
    return names;
  }

  function teamPlayers() {
    const byName = new Map(allPlayers().map(p => [p.name, p]));
    return teamNames().map(n => byName.get(n) || { name: n, team: '?', pos: '?', rank: '?', rankNum: 9999 });
  }

  function pickNumber() {
    // go/http_server.go: pick number == count of picked players
    const ext = extPickedRawNames().length;
    return Math.max(ext, pickedSet().size);
  }

  /* ---------- rendering ---------- */
  function renderPosFilters() {
    const positions = ['All', ...new Set(allPlayers().map(p => p.pos)
      .sort((a, b) => (POSITION_ORDER[a] || 9) - (POSITION_ORDER[b] || 9)))];
    const box = $('pos-filters');
    box.innerHTML = '';
    for (const pos of positions) {
      const btn = document.createElement('button');
      btn.textContent = pos;
      if (pos === posFilter) btn.classList.add('active');
      btn.addEventListener('click', () => { posFilter = pos; renderAll(); });
      box.appendChild(btn);
    }
  }

  function renderTable() {
    const picked = pickedSet();
    const extPicked = extPickedCanonical();
    const team = new Set(teamNames());
    const search = searchText.trim().toLowerCase();
    const tbody = $('player-tbody');
    tbody.innerHTML = '';

    let shown = 0;
    let available = 0;
    for (const p of allPlayers()) {
      const isPicked = picked.has(p.name);
      if (!isPicked) available++;
      if (posFilter !== 'All' && p.pos !== posFilter) continue;
      if (isPicked && !showPicked) continue;
      if (search && !(p.name.toLowerCase().includes(search) || p.team.toLowerCase().includes(search))) continue;
      shown++;

      const tr = document.createElement('tr');
      if (isPicked) tr.classList.add('picked');
      if (team.has(p.name)) tr.classList.add('onteam');

      const mark = toDraft[p.name];
      const markLabel = mark === 'yes' ? '✅' : mark === 'no' ? '❌' : '–';
      const markClass = mark === 'yes' ? 'todraft-yes' : mark === 'no' ? 'todraft-no' : '';
      const fromExt = extPicked.has(p.name);

      tr.innerHTML =
        `<td>${escapeHtml(p.rank)}</td>` +
        `<td class="player-name">${escapeHtml(p.name)}${mark === 'yes' ? ' ✅' : mark === 'no' ? ' ❌' : ''}</td>` +
        `<td>${escapeHtml(p.team)}</td>` +
        `<td>${escapeHtml(p.bye)}</td>` +
        `<td>${escapeHtml(p.pos)}</td>` +
        `<td>${escapeHtml(p.espn)}</td>` +
        `<td>${escapeHtml(p.sleeper)}</td>` +
        `<td class="note-cell">${escapeHtml(truncateNote(noteFor(p)))}</td>` +
        `<td class="row-actions">` +
        `<button class="act-pick" title="${isPicked ? (fromExt ? 'Synced from extension' : 'Undo pick') : 'Mark as picked/drafted by someone'}"` +
        `${fromExt ? ' disabled' : ''}>${isPicked ? 'Undo' : 'Picked'}</button>` +
        `<button class="act-mark ${markClass}" title="Cycle target/avoid marker">${markLabel}</button>` +
        `<button class="act-team" title="${team.has(p.name) ? 'Remove from your team' : 'Add to your team'}">` +
        `${team.has(p.name) ? '−Team' : '+Team'}</button>` +
        `</td>`;

      tr.querySelector('.player-name').addEventListener('click', () => showNote(p));
      tr.querySelector('.act-pick').addEventListener('click', () => togglePicked(p.name));
      tr.querySelector('.act-mark').addEventListener('click', () => cycleToDraft(p.name));
      tr.querySelector('.act-team').addEventListener('click', () => toggleTeam(p.name));
      tbody.appendChild(tr);
    }

    $('player-count').textContent =
      `${shown} shown · ${available} available · ${picked.size} picked`;
    $('pick-counter').textContent = `Pick: ${pickNumber()}`;
  }

  function renderTeam() {
    const players = teamPlayers();
    const box = $('team-list');
    $('team-count').textContent = players.length ? `${players.length} players` : '';
    if (!players.length) {
      box.innerHTML = '<p class="muted">No players on your team yet</p>';
      return;
    }
    box.innerHTML = '';
    for (const group of groupByPosition(players)) {
      const h = document.createElement('h4');
      h.textContent = `=== ${group.pos} ===`;
      box.appendChild(h);
      const ul = document.createElement('ul');
      for (const p of group.players) {
        const li = document.createElement('li');
        li.textContent = `${p.name} (${p.team}, rank ${p.rank})`;
        if (manualTeam.includes(p.name)) {
          const rm = document.createElement('button');
          rm.textContent = '×';
          rm.title = 'Remove from your team';
          rm.addEventListener('click', () => toggleTeam(p.name));
          li.appendChild(rm);
        }
        ul.appendChild(li);
      }
      box.appendChild(ul);
    }
  }

  function renderExtStatus() {
    const el = $('ext-status');
    if (!extDetected) {
      el.textContent = 'Extension: not detected';
      el.className = 'ext-off';
      return;
    }
    const stamps = ['picked_players', 'available_players', 'roster_players']
      .map(k => extState[k] && extState[k].updatedAt).filter(Boolean);
    if (stamps.length) {
      const t = new Date(Math.max(...stamps));
      el.textContent = `Extension: connected · draft data ${t.toLocaleTimeString()}`;
    } else {
      el.textContent = 'Extension: connected · no draft data yet';
    }
    el.className = 'ext-on';
  }

  function renderAll() {
    renderPosFilters();
    renderTable();
    renderTeam();
    renderExtStatus();
  }

  function setStatus(msg) { $('status-bar').textContent = msg; }

  /* ---------- actions ---------- */
  function togglePicked(name) {
    if (manualPicked.has(name)) manualPicked.delete(name);
    else manualPicked.add(name);
    store.save('manualPicked', [...manualPicked]);
    renderAll();
  }

  function cycleToDraft(name) {
    const next = { undefined: 'yes', yes: 'no', no: undefined }[toDraft[name]];
    if (next === undefined) delete toDraft[name];
    else toDraft[name] = next;
    store.save('toDraft', toDraft);
    renderAll();
  }

  function toggleTeam(name) {
    const i = manualTeam.indexOf(name);
    if (i >= 0) manualTeam.splice(i, 1);
    else manualTeam.push(name);
    store.save('manualTeam', manualTeam);
    renderAll();
  }

  function showNote(player) {
    $('note-title').textContent = `${player.name} — ${player.team} ${player.pos}, rank ${player.rank}`;
    const note = noteFor(player);
    $('note-body').innerHTML = note ? renderMarkdown(note) : '<p class="muted">No note file for this player.</p>';
    $('note-dialog').showModal();
  }

  /* ---------- extension bridge (see chrome-extension/bridge.js) ---------- */
  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const msg = event.data;
    if (!msg || msg.source !== 'ffda-ext') return;

    extDetected = true;
    if (msg.type === 'state' && msg.data) {
      for (const key of ['picked_players', 'roster_players', 'available_players']) {
        if (msg.data[key]) extState[key] = msg.data[key];
      }
      store.save('extState', extState);
      setStatus('Draft data received from extension');
      renderAll();
    } else {
      renderExtStatus();
    }
  });

  function requestExtState() {
    window.postMessage({ source: 'ffda-page', type: 'request-state' }, '*');
  }
  // The bridge may inject after us; retry the handshake for a while.
  [0, 500, 1500, 3500, 8000].forEach(ms => setTimeout(() => { if (!extDetected) requestExtState(); }, ms));
  setInterval(() => { if (!extDetected) requestExtState(); }, 30000);

  /* ---------- LLM ---------- */
  function llmConfigured() {
    return settings.useOllama
      ? Boolean(settings.ollamaEndpoint && settings.ollamaModel)
      : Boolean(settings.apiKey);
  }

  async function streamOpenAI(messages, onChunk) {
    const models = [];
    if (settings.model.trim()) models.push(settings.model.trim());
    for (const m of OPENAI_FALLBACK_MODELS) if (!models.includes(m)) models.push(m);

    let lastErr = null;
    for (const model of models) {
      try {
        const resp = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + settings.apiKey,
          },
          body: JSON.stringify({ model, messages, stream: true }),
        });
        if (!resp.ok) {
          const text = await resp.text().catch(() => '');
          lastErr = new Error(`${model}: HTTP ${resp.status} ${text.slice(0, 300)}`);
          continue;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) return;
          buf += decoder.decode(value, { stream: true });
          let nl;
          while ((nl = buf.indexOf('\n')) >= 0) {
            const line = buf.slice(0, nl).trim();
            buf = buf.slice(nl + 1);
            if (!line.startsWith('data:')) continue;
            const payload = line.slice(5).trim();
            if (payload === '[DONE]') return;
            try {
              const delta = JSON.parse(payload).choices?.[0]?.delta?.content;
              if (delta) onChunk(delta);
            } catch (e) { /* partial line; ignore */ }
          }
        }
      } catch (e) {
        lastErr = e;
      }
    }
    throw lastErr || new Error('all models failed');
  }

  async function streamOllama(messages, onChunk) {
    const endpoint = settings.ollamaEndpoint.replace(/\/+$/, '');
    const resp = await fetch(endpoint + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: settings.ollamaModel, messages, stream: true }),
    });
    if (!resp.ok) throw new Error(`Ollama HTTP ${resp.status}: ${await resp.text().catch(() => '')}`);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) return;
      buf += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        try {
          const j = JSON.parse(line);
          if (j.message && j.message.content) onChunk(j.message.content);
          if (j.done) return;
        } catch (e) { /* ignore partial */ }
      }
    }
  }

  // Mirrors ui.go performLLMQuery: top-15 available players' full notes,
  // picked list, grouped roster, pick number -> one prompt.
  async function askLLM() {
    if (!llmConfigured()) {
      $('ai-output').innerHTML = renderMarkdown(
        '## LLM not configured\n\n' +
        'Open Settings (⚙) and either:\n\n' +
        '- paste an **OpenAI API key**, or\n' +
        '- enable **Ollama** with a local model.\n\n' +
        'Everything else (draft tracking, filters, notes) works without it.');
      return;
    }
    if (querying) return;
    if (Date.now() - lastQueryAt < 5000) {
      setStatus('Wait 5 seconds between queries');
      return;
    }
    querying = true;
    lastQueryAt = Date.now();
    $('btn-ask').disabled = true;
    $('ai-status').textContent = settings.useOllama ? 'Asking Ollama…' : 'Asking OpenAI…';
    $('ai-output').innerHTML = '';

    try {
      const picked = pickedSet();
      const available = allPlayers().filter(p => !picked.has(p.name));
      const top = available.slice(0, 15);

      let allNotes = '';
      for (const p of top) {
        const note = noteFor(p);
        if (note) allNotes += `---start ${p.name}---\n${note}\n---end ${p.name}---\n\n`;
      }

      const pickedNames = [...picked];
      const pickedStr = pickedNames.length ? `[${pickedNames.join(', ')}]` : '[No players picked yet]';

      const groups = groupByPosition(teamPlayers());
      const teamStr = groups.length
        ? groups.map(g => `=== ${g.pos} ===\n` + g.players.map(p => p.name).join('\n')).join('\n')
        : '[No players on your team yet]';

      const prompt = buildUserPrompt(pickNumber(), pickedStr, teamStr, settings.userPrompt, allNotes);
      const messages = [
        { role: 'system', content: settings.systemPrompt },
        { role: 'user', content: prompt },
      ];

      let answer = '';
      let renderQueued = false;
      const onChunk = (chunk) => {
        answer += chunk;
        if (!renderQueued) {
          renderQueued = true;
          requestAnimationFrame(() => {
            renderQueued = false;
            const out = $('ai-output');
            out.innerHTML = renderMarkdown(answer);
            out.scrollTop = out.scrollHeight;
          });
        }
      };

      if (settings.useOllama) await streamOllama(messages, onChunk);
      else await streamOpenAI(messages, onChunk);

      $('ai-status').textContent = 'Done ' + new Date().toLocaleTimeString();
      setStatus('AI query complete');
    } catch (e) {
      $('ai-output').innerHTML = renderMarkdown('## Error\n\n' + String(e && e.message || e));
      $('ai-status').textContent = 'Error';
    } finally {
      querying = false;
      $('btn-ask').disabled = false;
    }
  }

  /* ---------- settings dialog ---------- */
  function openSettings() {
    $('set-apikey').value = settings.apiKey;
    $('set-model').value = settings.model;
    $('set-use-ollama').checked = settings.useOllama;
    $('set-ollama-endpoint').value = settings.ollamaEndpoint;
    $('set-ollama-model').value = settings.ollamaModel;
    $('set-system-prompt').value = settings.systemPrompt;
    $('set-user-prompt').value = settings.userPrompt;
    $('settings-dialog').showModal();
  }

  function saveSettings() {
    settings.apiKey = $('set-apikey').value.trim();
    settings.model = $('set-model').value.trim();
    settings.useOllama = $('set-use-ollama').checked;
    settings.ollamaEndpoint = $('set-ollama-endpoint').value.trim() || DEFAULT_SETTINGS.ollamaEndpoint;
    settings.ollamaModel = $('set-ollama-model').value.trim();
    settings.systemPrompt = $('set-system-prompt').value;
    settings.userPrompt = $('set-user-prompt').value;
    store.save('settings', settings);
    setStatus('Settings saved (this browser only)');
    renderAll();
  }

  function resetDraftState() {
    if (!confirm('Clear all draft state (picked players, your team, target markers, extension data)?')) return;
    manualPicked = new Set();
    manualTeam = [];
    toDraft = {};
    extState = {};
    store.save('manualPicked', []);
    store.save('manualTeam', []);
    store.save('toDraft', {});
    store.save('extState', {});
    window.postMessage({ source: 'ffda-page', type: 'clear-state' }, '*');
    setStatus('Draft state cleared');
    renderAll();
  }

  /* ---------- wire up ---------- */
  $('scoring-format').value = settings.scoringFormat;
  $('scoring-format').addEventListener('change', (e) => {
    settings.scoringFormat = e.target.value;
    store.save('settings', settings);
    renderAll();
  });
  $('search-box').addEventListener('input', (e) => { searchText = e.target.value; renderTable(); });
  $('show-picked').addEventListener('change', (e) => { showPicked = e.target.checked; renderTable(); });
  $('btn-ask').addEventListener('click', askLLM);
  $('btn-settings').addEventListener('click', openSettings);
  $('settings-form').addEventListener('submit', saveSettings);
  $('btn-reset-prompts').addEventListener('click', () => {
    $('set-system-prompt').value = DEFAULT_SETTINGS.systemPrompt;
    $('set-user-prompt').value = DEFAULT_SETTINGS.userPrompt;
  });
  $('btn-reset-draft').addEventListener('click', resetDraftState);
  document.querySelectorAll('.dialog-close').forEach(btn => {
    btn.addEventListener('click', () => $(btn.dataset.close).close());
  });

  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (document.querySelector('dialog[open]')) return;
    if (e.key === 'q' || e.key === 'Q') { e.preventDefault(); askLLM(); }
    if (e.key === 'r' || e.key === 'R') { e.preventDefault(); renderAll(); setStatus('Refreshed ' + new Date().toLocaleTimeString()); }
  });

  $('data-stamp').textContent = `Data generated ${DATA.generatedAt}`;
  renderAll();
  setStatus('Ready — listening for draft updates');
}
