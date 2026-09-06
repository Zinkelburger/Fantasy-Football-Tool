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
  // Every bundled note ends on a "Draft take:" line — the label would eat
  // the whole preview, so show only what the take actually says.
  text = text.replace(/^Draft take:\s*/i, '');
  if (text.length <= 40) return text;

  const words = text.split(/\s+/);
  let truncated = '';
  for (const word of words) {
    if (truncated.length + word.length + 1 > 37) break;
    truncated += (truncated ? ' ' : '') + word;
  }
  return truncated + '...';
}

// Draft advice uses the current league context and labels the limits of the notes.
function buildUserPrompt(currentPick, pickedPlayersStr, currentTeam, userPromptCustom, allNotes, context = {}) {
  const date = context.date || new Date().toLocaleDateString('en-CA');
  const year = context.season || new Date().getFullYear();
  return `It is pick ${currentPick} of a ${year} fantasy football draft. Today is ${date}. ` +
    `Scoring: ${context.scoring || 'not specified'}. League size: ${context.numTeams || 'not specified'}. ` +
    `Draft slot: ${context.slot || 'unknown'}. Your next overall pick: ${context.nextPick || 'unknown'}. ` +
    `Dashboard lineup assumptions: ${context.lineup || 'not specified'}. ` +
    `Use the current candidate rankings below; note headers may contain older ranks. ` +
    `Treat Reddit notes as attributed evidence and opinion, not verified current facts. ` +
    `Do not assume an old injury is ongoing, invent news, or claim to have checked live sources. ` +
    `Explain material uncertainty and use current rankings as the baseline. ` +
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

// Split one CSV line, honoring double-quoted cells ("Smith, John").
function splitCsvLine(line) {
  const cells = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') inQuotes = false;
      else cur += ch;
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      cells.push(cur);
      cur = '';
    } else {
      cur += ch;
    }
  }
  cells.push(cur);
  return cells;
}

function csvCell(v) {
  const s = String(v == null ? '' : v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

// Forgiving rankings parser for user-supplied files. Accepts:
//  - a CSV with a header naming a Player (or Name) column, Rank column optional;
//  - headerless "rank,name" rows;
//  - a plain list of names, optionally numbered like "12. Justin Jefferson"
//    (the number is the rank; otherwise the line's position is).
function parseRankingsText(text) {
  const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const entries = [];
  if (!lines.length) return entries;

  let start = 0;
  const header = splitCsvLine(lines[0]).map(c => c.trim().toLowerCase());
  let nameCol = header.indexOf('player');
  if (nameCol < 0) nameCol = header.indexOf('name');
  const rankCol = nameCol >= 0 ? header.indexOf('rank') : -1;
  if (nameCol >= 0) start = 1;

  for (let i = start; i < lines.length; i++) {
    const cells = splitCsvLine(lines[i]).map(c => c.trim());
    let name = '';
    let rank = NaN;
    if (nameCol >= 0) {
      name = cells[nameCol] || '';
      if (rankCol >= 0) rank = parseFloat(cells[rankCol]);
    } else if (cells.length >= 2 && /^\d+(\.\d+)?$/.test(cells[0])) {
      rank = parseFloat(cells[0]);
      name = cells[1];
    } else {
      const m = /^(\d+)[.)]\s+(.+)$/.exec(lines[i]);
      if (m) { rank = parseFloat(m[1]); name = m[2].trim(); }
      else name = cells[0];
    }
    if (!name) continue;
    entries.push({ rank: isFinite(rank) ? rank : entries.length + 1, name });
  }
  return entries;
}

// The exported sheet re-numbers Rank 1..N in board order, so "reorder the rows
// in Excel and re-import" works without fixing numbers by hand.
function buildRankingsCsv(playersInOrder) {
  const out = ['Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank'];
  playersInOrder.forEach((p, i) => {
    out.push([i + 1, p.name, p.team, p.bye, p.pos, p.espn, p.sleeper].map(csvCell).join(','));
  });
  return out.join('\n') + '\n';
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

function normPos(pos) { return pos === 'DEF' ? 'DST' : pos; }

// Typical single-QB lineup: these are the starting slots a roster must fill
// (FLEX on top of them). Used for the team-panel "still need" line, the draft
// board needs chips, and the pick predictor.
const STARTER_SLOTS = { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, DST: 1 };
// How many of a position a team will draft at most (predictor only).
const ROSTER_CAPS = { QB: 2, RB: 6, WR: 6, TE: 2, K: 1, DST: 1 };
// A team that reaches this round with ZERO players at a position is in real
// trouble — the needs lines flag it in bold ("really needs RB").
const BADLY_NEEDED_BY_ROUND = { QB: 10, RB: 4, WR: 4, TE: 12 };
// Draft-board header order: roughly how much of a draft the position decides,
// so the lines you actually read sit nearest the team name. K/DST aren't on
// the bundled board but can arrive from the extension's pick feed.
const BOARD_POS_ORDER = ['RB', 'WR', 'QB', 'TE', 'DST', 'K'];

/* ---------- pick value: what a draft slot is worth, in points ---------- */
// E[season points] = a + b * ln(draft slot), fit per position on 2020-2025
// ADP vs actual standard-scoring season points. These are the "pooled" rows of
// engine/league-sim/data/pick_value_fits.json (built by
// engine/league-sim/analysis/fit_pick_value.py) — the same curves the
// league-sim's pick_value drafter wins with.
//
// This curve is the whole reason the suggestion can't be made on rank spots:
// spots are not a unit of football. From pick 1, dropping 30 spots at TE costs
// ~29 points; dropping 16 spots at RB costs ~107. Counting spots says take the
// tight end, which is how the old version arrived at Trey McBride at 1.01.
//
// Standard scoring. In a PPR league the WR and TE curves sit higher than this,
// so treat the RB lean as, if anything, slightly overstated there.
const PICK_VALUE_FITS = {
  QB: [539.94, -72.38],
  RB: [250.48, -37.89],
  WR: [230.61, -32.35],
  TE: [214.20, -30.58],
  K: [336.93, -42.55],
};
// Slot at which a position counts as picked clean (nobody left worth having),
// and the floor the curve is evaluated at for unranked players.
const PICK_VALUE_EXHAUSTED = 250;
// A player who doesn't fill a starting slot only scores through the flex or an
// injury, so his wait cost is worth less than the same points at a slot you
// have to fill. Ported from simfl PickValue.BENCH_WEIGHT.
const BENCH_WEIGHT = 0.45;
// One flex on top of the fixed starters, RB/WR in this league (simfl config).
const FLEX_POSITIONS = ['RB', 'WR'];

// What a position is worth to a roster if you take it at board slot `slot`.
function expectedPoints(pos, slot) {
  const fit = PICK_VALUE_FITS[pos];
  if (!fit) return 0;
  const x = Math.min(Math.max(slot || PICK_VALUE_EXHAUSTED, 1), PICK_VALUE_EXHAUSTED);
  return fit[0] + fit[1] * Math.log(x);
}

// The cost of waiting one turn at a position: the best player there now (board
// slot `nowSlot`) minus the best one still there at your following pick
// (`laterSlot`, null when the position empties out). Both run through the same
// curve, so the answer is in projected season points — which is what makes QB,
// RB, WR and TE comparable at all.
function waitCost(pos, nowSlot, laterSlot) {
  return Math.max(0, expectedPoints(pos, nowSlot) - expectedPoints(pos, laterSlot));
}

/* ---------- snake draft math (1-based picks, teams 1..T) ---------- */
function snakeTeamForPick(pick, teams) {
  const round = Math.ceil(pick / teams);
  const idx = (pick - 1) % teams;
  return round % 2 === 1 ? idx + 1 : teams - idx;
}

function nextPickForTeam(team, teams, picksMade) {
  if (!(team >= 1 && team <= teams)) return null;
  for (let n = picksMade + 1; ; n++) {
    if (snakeTeamForPick(n, teams) === team) return n;
  }
}

// The shared draft-sense rule: would a team with `have` players at `pos`
// reasonably draft that position in `round`? No hoarding QBs/TEs early, no
// early K/DST, positional caps, and when a mustFill set is given only those
// positions (missing starters) qualify.
function wouldDraft(pos, have, round, rounds, mustFillSet) {
  if (have >= (ROSTER_CAPS[pos] || 6)) return false;
  const roundsLeft = rounds - round;
  if ((pos === 'K' || pos === 'DST') && roundsLeft > 2) return false;
  if (pos === 'QB' && have >= 1 && round < 10) return false;
  if (pos === 'TE' && have >= 1 && round < 12) return false;
  if (mustFillSet && !mustFillSet.has(pos)) return false;
  return true;
}

// Deterministic autopick — simulates picks with plain rules, no AI: each
// team takes the best available in the order given (the caller decides the
// preference order, e.g. the draft site's own rankings). algo 'need'
// (default) filters through wouldDraft(); 'ba' is pure best available —
// strictly the next name in the order, needs ignored. Positions the pool
// doesn't carry (the bundled board has no K/DST) are simply never required.
//
// available: [{name, pos, team}] in preference order (team = NFL team, kept
// only so the board can label the cell). teamCounts: per-team {POS: n}, index
// team-1. Returns [{pick, round, team, name, pos, nfl}] — here `team` is the
// drafting slot 1..T and `nfl` is the player's NFL team.
function predictDraft(available, teamCounts, startPick, endPick, teams, rounds, algo) {
  const avail = available.map(p => ({ name: p.name, pos: normPos(p.pos), nfl: p.team }));
  const counts = teamCounts.map(c => Object.assign({}, c));
  const poolPos = new Set(avail.map(p => p.pos));
  const out = [];
  for (let n = startPick; n <= endPick && avail.length; n++) {
    const team = snakeTeamForPick(n, teams);
    const c = counts[team - 1] || (counts[team - 1] = {});
    const round = Math.ceil(n / teams);

    let i = 0;
    if (algo !== 'ba') {
      const gaps = new Set();
      let gapCount = 0;
      for (const pos of Object.keys(STARTER_SLOTS)) {
        if (!poolPos.has(pos)) continue;
        const gap = STARTER_SLOTS[pos] - (c[pos] || 0);
        if (gap > 0) { gaps.add(pos); gapCount += gap; }
      }
      const mustFill = gapCount > rounds - round ? gaps : null;

      i = avail.findIndex(p => wouldDraft(p.pos, c[p.pos] || 0, round, rounds, mustFill));
      if (i < 0) i = 0; // every rule blocked -> pure best available
    }
    const p = avail.splice(i, 1)[0];
    c[p.pos] = (c[p.pos] || 0) + 1;
    out.push({ pick: n, round, team, name: p.name, pos: p.pos, nfl: p.nfl });
  }
  return out;
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
  useClaudeCode: null,   // auto-select on our local server until explicitly set
  ollamaEndpoint: 'http://localhost:11434',
  ollamaModel: '',
  scoringFormat: 'STD',
  manualMode: false,      // show Picked/+Team buttons (off = extension drives)
  rankSource: 'auto',     // which site-rank column: auto|espn|sleeper|both
  numTeams: 12,           // draft board: league size
  draftSlot: 0,           // draft board: your position, 0 = auto-detect
  numRounds: 15,          // draft board: rounds
  botRanks: 'auto',       // predictor: ranking the bots draft by (auto|espn|sleeper|mine)
  botAlgo: 'need',        // predictor: need-aware filter or pure best available (need|ba)
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
    splitCsvLine, csvCell, parseRankingsText, buildRankingsCsv,
    normPos, snakeTeamForPick, nextPickForTeam, predictDraft, wouldDraft,
    expectedPoints, waitCost,
    STARTER_SLOTS, ROSTER_CAPS, BADLY_NEEDED_BY_ROUND,
    PICK_VALUE_FITS, PICK_VALUE_EXHAUSTED, BENCH_WEIGHT, FLEX_POSITIONS,
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
  let toDraft = store.load('toDraft', {});                      // name -> MARK_SCALE value
  let extState = store.load('extState', {});                    // raw bridge payloads
  let extPickedRaw = store.load('extPickedRaw', []);            // union of raw scraped picks
  let unpicked = new Set(store.load('unpicked', []));           // canonical names un-picked by hand
  let rankOverrides = store.load('rankOverrides', {});          // format -> { cleanName: rank }
  let noteOverrides = store.load('noteOverrides', {});          // cleanName -> markdown

  /* Your own read on a player, five steps from love him to never. The
     two middle values stay 'yes'/'no', so prep and backup files written
     before the scale existed still load and still mean the same thing.
     In scale order, best first — the order the picker shows and the
     order the number keys follow. Five states is too many to cycle
     through, so nothing cycles: you pick the one you mean. */
  const MARK_SCALE = [
    { v: 'love', key: '1', glyph: '✅', cls: 'mark-love', word: 'really good' },
    { v: 'yes',  key: '2', glyph: '✔', cls: 'mark-yes',  word: 'good' },
    { v: null,   key: '3', glyph: '○', cls: '',          word: 'no opinion' },
    { v: 'no',   key: '4', glyph: '✘', cls: 'mark-no',   word: 'bad' },
    { v: 'hate', key: '5', glyph: '❌', cls: 'mark-hate', word: 'really bad' },
  ];
  const NO_MARK = MARK_SCALE.find(s => s.v === null);
  const markStep = (v) => MARK_SCALE.find(s => s.v === (v || null)) || NO_MARK;
  // The legend, built from the scale so it can never drift from it.
  const MARK_LEGEND = MARK_SCALE.map(s => `${s.glyph} ${s.word}`).join(' · ');

  /* ---------- volatile state ---------- */
  let posFilter = 'All';
  let searchText = '';
  let showPicked = false;
  let showModelMarks = store.load('showModelMarks', true);
  let sortBy = 'board';         // 'board' | 'espn' | 'sleeper' (view only)
  let extDetected = false;
  let querying = false;
  let lastQueryAt = 0;
  let selectedName = null;      // row the keyboard acts on
  let visibleNames = [];        // board order of currently rendered rows
  let openNotes = [];           // note tabs, in tab order (player names)
  let activeTab = 'ai';         // 'ai' or a player name
  let lastNoteTab = null;       // the note tab a plain click replaces (Obsidian-style)
  let tabHistory = ['ai'];      // visit order (MRU last); closing a tab falls back here
  let noteEditingName = null;   // player whose note is being edited, or null
  let teamCollapsed = store.load('teamCollapsed', false);
  let teamGroupsCollapsed = store.load('teamGroupsCollapsed', {}); // pos -> true
  let predictMode = store.load('predictMode', false); // predictions stay on, re-simulated after every live pick
  let tourIndex = -1;           // -1 = tour not running
  let predicted = null;         // [{pick, round, team, name, pos}] from the pick simulation
  let predictedAtCount = -1;    // pick count the prediction was made at (stale otherwise)
  let predictedMeta = null;     // {followNext, byPos, suggestion} — only valid while predicted is

  /* ---------- derived data ---------- */
  function allPlayers() {
    return DATA.formats[settings.scoringFormat] || DATA.formats.STD;
  }

  function bundledNoteFor(player) {
    return DATA.notes[cleanName(player.name)] || '';
  }

  function noteEditedFor(player) {
    return Object.prototype.hasOwnProperty.call(noteOverrides, cleanName(player.name));
  }

  // Edited notes shadow the bundled ones everywhere (table preview, dialog,
  // and the Ask AI prompt) without touching the bundled data.
  function noteFor(player) {
    return noteEditedFor(player) ? noteOverrides[cleanName(player.name)] : bundledNoteFor(player);
  }

  function currentRankOverrides() {
    return rankOverrides[settings.scoringFormat] || {};
  }

  function rankOverrideFor(player) {
    const r = currentRankOverrides()[cleanName(player.name)];
    return typeof r === 'number' && isFinite(r) ? r : null;
  }

  // Board order = your imported ranks where present, bundled rank otherwise;
  // bundled rank breaks ties so a partial import stays stable.
  function boardPlayers() {
    const eff = (p) => {
      const o = rankOverrideFor(p);
      return o === null ? (p.rankNum || 9999) : o;
    };
    return allPlayers().slice().sort((a, b) =>
      eff(a) - eff(b) || (a.rankNum || 9999) - (b.rankNum || 9999));
  }

  // ESPN's pick feed is a ticker: it can show only the recent picks, so any one
  // scrape is a *partial* view. Players never come off a draft board, so we
  // accumulate every name the extension has ever reported rather than trusting
  // the latest scrape — otherwise a short feed silently un-picks the board.
  function mergeExtPicked(names) {
    const seen = new Set(extPickedRaw);
    let added = 0;
    for (const raw of names) {
      const name = (raw || '').trim();
      if (name && !seen.has(name)) { seen.add(name); extPickedRaw.push(name); added++; }
    }
    if (added) store.save('extPickedRaw', extPickedRaw);
    return added;
  }

  // Canonical picks contributed by the extension. Two different shapes:
  //  - ESPN posts picked players, an append-only log -> accumulated above.
  //  - Sleeper posts the full available list; inverting it is a complete
  //    snapshot, so it is recomputed each time instead of accumulated.
  function extPickedCanonical() {
    const players = allPlayers();
    const set = new Set();
    for (const raw of extPickedRaw) {
      const match = fuzzyMatchPlayer(raw, players);
      if (match) set.add(match);
    }
    const available = extState.available_players;
    if (available && Array.isArray(available.players) && available.players.length) {
      for (const name of computePickedFromAvailable(available.players, players)) set.add(name);
    }
    return set;
  }

  // Canonical picked set = extension picks + manual picks, minus anything you
  // un-picked by hand (which is how a bad fuzzy match gets corrected).
  function pickedSet() {
    const set = new Set(manualPicked);
    for (const name of extPickedCanonical()) set.add(name);
    for (const name of unpicked) set.delete(name);
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
    // go/http_server.go: pick number == count of picked players. The raw count
    // is the better number because it also covers picks that aren't on our
    // board at all (K/DST), which fuzzy matching drops.
    return Math.max(extPickedRaw.length, pickedSet().size);
  }

  // Which site the extension is scraping ('espn' | 'sleeper' | null): every
  // payload is tagged with its origin, newest one wins.
  function draftSite() {
    let site = null;
    let at = 0;
    for (const key of ['picked_players', 'available_players', 'roster_players']) {
      const v = extState[key];
      if (v && v.site && (v.updatedAt || 0) >= at) { at = v.updatedAt || 0; site = v.site; }
    }
    return site;
  }

  // Where you actually make the pick. This tool only mirrors the draft — it
  // has no way to draft for you — so anything telling you to act says so by
  // name when the extension knows which room you're in.
  // Returns the whole phrase, not just the name: the unknown-site fallback
  // ("your league site") doesn't take a "tab" suffix the way "your ESPN tab"
  // does, and gluing them at each call site produced "your your league site".
  function siteTab() {
    const s = draftSite();
    return s === 'sleeper' ? 'your Sleeper tab' : s === 'espn' ? 'your ESPN tab' : 'your league site';
  }

  // Which site-rank column(s) to show. Auto = the site the draft is on;
  // ESPN until anything else is detected (the family league is ESPN).
  function siteColumns() {
    const s = settings.rankSource;
    if (s === 'espn' || s === 'sleeper') return [s];
    if (s === 'both') return ['espn', 'sleeper'];
    return draftSite() === 'sleeper' ? ['sleeper'] : ['espn'];
  }

  // Picks in draft order, for the snake board. ESPN's feed arrives in pick
  // order; manual picks in click order; Sleeper picks (derived from the
  // available-list diff) carry no order, so they fall back to board order —
  // approximate, and only for Sleeper.
  function pickLogEntries() {
    const players = allPlayers();
    const seen = new Set();
    const entries = [];
    const push = (name, player) => {
      if (!name || seen.has(name)) return;
      seen.add(name);
      entries.push({ name, player });
    };
    for (const raw of extPickedRaw) {
      const m = fuzzyMatchPlayer(raw, players);
      if (m) { if (!unpicked.has(m)) push(m, playerByName(m)); }
      else push(raw.trim(), null); // off-board pick (K/DST): still occupies a slot
    }
    for (const name of manualPicked) if (!unpicked.has(name)) push(name, playerByName(name));
    const canonical = extPickedCanonical();
    for (const p of boardPlayers()) {
      if (canonical.has(p.name) && !unpicked.has(p.name)) push(p.name, p);
    }
    return entries;
  }

  // Your draft position: the explicit setting wins; otherwise inferred from
  // the first pick in the log that landed on your roster.
  function effectiveSlot(entries) {
    if (settings.draftSlot >= 1) return Math.min(settings.draftSlot, settings.numTeams);
    const list = entries || pickLogEntries();
    const mine = new Set(teamNames());
    for (let i = 0; i < list.length; i++) {
      if (mine.has(list[i].name)) return snakeTeamForPick(i + 1, settings.numTeams);
    }
    return null;
  }

  function rosterCountsByTeam(entries, teams) {
    const counts = Array.from({ length: teams }, () => ({}));
    entries.forEach((en, i) => {
      const t = snakeTeamForPick(i + 1, teams);
      if (t <= teams && en.player) {
        const pos = normPos(en.player.pos);
        counts[t - 1][pos] = (counts[t - 1][pos] || 0) + 1;
      }
    });
    return counts;
  }

  // {slot, next, until} for the pink "your next pick" markers, or null when
  // the slot is unknown or the draft is over.
  function yourNextPick(entries) {
    const list = entries || pickLogEntries();
    const slot = effectiveSlot(list);
    if (!slot) return null;
    const made = Math.max(list.length, pickNumber());
    const next = nextPickForTeam(slot, settings.numTeams, made);
    if (!next || next > settings.numTeams * settings.numRounds) return null;
    return { slot, next, until: next - made - 1 };
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

  /* ---------- 2025 opportunity read ----------
     Bundled by build_data.py from the engine's usage-based expected
     points (analysis/export_opportunity.py). xfp = what a typical player
     would have scored per game from this player's 2025 targets and
     carries; gapc = his actual-minus-expected gap, centered on his
     position (raw gaps are shifted by scoring floors — never threshold
     ppg25 - xfp directly). Hot/cold needs 8+ games and a gap past the
     per-format flag — same constants as the site board.
     Backtested 2017-25 (league-sim analysis/gap_regression_check.py):
     the gap predicts next season at WR/TE only, so those flags render
     red/green while RB/QB get a gray context flag with a tooltip that
     says so. */
  const OPP_GAP_FLAG = { 'STD': 1.5, '0.5PPR': 1.9, 'PPR': 2.25 };
  const OPP_SIGNAL_POS = new Set(['WR', 'TE']);

  function oppRead(p) {
    if (p.xfp === undefined) return null;
    const flagged = p.g25 >= 8 &&
      Math.abs(p.gapc) >= (OPP_GAP_FLAG[settings.scoringFormat] || 1.5);
    const hot = p.gapc > 0;
    const signal = OPP_SIGNAL_POS.has(p.pos);
    const base = `2025: ${p.ppg25.toFixed(1)} PPG on ${p.xfp.toFixed(1)} ` +
      `expected from his chances (${p.g25} games).`;
    const caveat = ` Context, not a verdict: in 2017-25 backtests a gap ` +
      `like this told us nothing extra about a ${p.pos}'s next season ` +
      'once you account for how much he scored' +
      (p.pos === 'RB'
        ? ' — goal-line roles are sticky, so extra finishing partly repeats.'
        : '.');
    const why = !flagged ? ''
      : hot
        ? ` He scored ${p.gapc.toFixed(1)} a game more than a typical ` +
          `${p.pos} does with the same targets and carries.` +
          (!signal ? caveat
            : (p.tdl >= 0.15
                ? ` Most of that is touchdown luck (+${p.tdl.toFixed(1)} TDs ` +
                  'a game over what his chances were worth). '
                : ' ') +
              'Receivers and tight ends who did this gave back about 2 ' +
              'points a game the next year in our 2017-25 backtests.')
        : ` He scored ${(-p.gapc).toFixed(1)} a game less than a ` +
          `typical ${p.pos} does with the same chances.` +
          (!signal ? caveat
            : ' Chances carry over to next season better than points do — ' +
              'receivers and tight ends who did this held their value ' +
              'while the average player slid (2017-25): the strongest ' +
              'buy signal in our research.');
    return { flagged, hot, signal, tip: base + why };
  }

  /* Findings marks (engine/league-sim/analysis/findings_marks.py):
     tested per-player rules from findings 8/9/10/15/16/18 — buy/fade
     with the player's own numbers, watch for context. Bundled per
     clean name, like notes. */
  const FM_LABEL = { buy: 'Buy', fade: 'Fade', watch: 'Context' };
  /* Each rule is named the way you'd say it out loud at a draft table.
     Not "TD regression", not "hot/cold finish" — those are terms you
     have to already know to read, and the whole point of the row is
     that it explains itself. Short, because the chip does not wrap. */
  const FM_TOPIC = {
    10: 'Age',
    13: 'Backup running back',
    14: 'When to take a quarterback',
    16: 'Touchdown luck',
    17: 'How often he got the ball',
    18: 'Games he missed',
    33: 'When to take a tight end',
  };
  // Unmapped finding: fall back to its write-up title ("16-td-luck-
  // regresses" -> "Td luck regresses") rather than a bare number.
  function fmTopic(m) {
    if (FM_TOPIC[m.f]) return FM_TOPIC[m.f];
    const words = String(m.slug || '').replace(/^\d+-/, '').replace(/-/g, ' ');
    return words ? words[0].toUpperCase() + words.slice(1) : `Finding ${m.f}`;
  }
  /* Who else is in his team's position room, on the draft board:
     "31 picks ahead of the next CIN receiver (Tee Higgins)."

     This line used to open with "He's CIN's WR1 on the draft board",
     which the meta line directly above it has already said in fewer
     words ("CIN WR, rank 12"). For a team's clear #1 the two read as
     the same sentence twice. So the standing is only spelled out when
     he is NOT the top of his room — that is the case the meta cannot
     tell you — and the room line otherwise goes straight to the fact
     it alone carries: who is next, and how far back.
     Context for the note page only (build_data.py load_rooms). */
  function roomText(p) {
    const rm = p.room;
    if (!rm) return '';
    // This tool shows team codes, not nicknames — match it: "DET's RB1".
    const poss = p.team ? `${p.team}'s` : 'his team\'s';
    const subj = p.team || 'His team';
    const room = p.team ? `${p.team} ${p.pos}` : p.pos;
    let rookSaid = false;
    const rookTag = (n) => {
      if (!rm.rook || rm.rook !== n) return '';
      rookSaid = true;
      return `, this year's pick ${rm.rookPick}`;
    };
    // Gaps are capped at 200 upstream; 0 means the market prices them level.
    const gap = (n) => (n >= 200 ? '200+ picks' : `${n} picks`);
    const bits = [];
    if (rm.ahead && rm.aheadGap != null)
      bits.push(rm.aheadGap === 0
        ? `Priced level with ${poss} ${p.pos}${rm.rank - 1}, ` +
          `${rm.ahead}${rookTag(rm.ahead)}`
        : `${gap(rm.aheadGap)} behind ${poss} ${p.pos}${rm.rank - 1}, ` +
          `${rm.ahead}${rookTag(rm.ahead)}`);
    if (rm.behind && rm.behindGap != null)
      bits.push((bits.length ? 'and ' : '') +
        (rm.behindGap === 0
          ? `priced level with the next ${room} (${rm.behind}${rookTag(rm.behind)})`
          : `${gap(rm.behindGap)} ahead of the next ${room} ` +
            `(${rm.behind}${rookTag(rm.behind)})`));
    // Nobody else in the room is priced at all — worth saying plainly,
    // it is the strongest version of "the job is his".
    if (!bits.length && !rm.rook)
      return `The only ${room} on the draft board.`;
    const rook = rm.rook && !rookSaid
      ? ` ${subj} spent pick ${rm.rookPick} on a ${p.pos} (${rm.rook}).` : '';
    if (!bits.length) return rook.trim();
    const line = bits.join(' ');
    return `${line[0].toUpperCase()}${line.slice(1)}.${rook}`;
  }

  function fmarksFor(p) {
    return (DATA.fmarks || {})[cleanName(p.name)] || null;
  }
  // The hover carries the marks themselves, in words — no symbol to
  // decode, no write-up to open first.
  function fmTip(fm) {
    return fm.map(m =>
      `${FM_LABEL[m.dir]} — ${fmTopic(m)}: ${m.note}`).join('\n');
  }

  /* Round-by-round guide: the findings condensed to one line per band
     (analysis/round_profile.py numbers; finding 29 checked the whole
     structure holds in 0.5PPR and full PPR). */
  const GUIDE = [
    { lo: 1, hi: 2, text: 'Lean RB early — RB value drains off the ' +
      'board ~45% faster than WR, so the receiver keeps. Skipping RBs ' +
      'on purpose (zero-RB) lost in our sims.',
      links: [['23-early-rb-vs-wr', 'why RB first'],
              ['02-zero-rb-is-a-trap', 'zero-RB']] },
    { lo: 3, hi: 5, text: 'The tested QB sweet spot is rounds 4-6. WR ' +
      'value stays nearly flat for twenty ranks — never reach for one. ' +
      'Round 4 is the last good door on tight end: after it the odds ' +
      'of a top-6 TE fall 53% → 30% → 16%.',
      links: [['14-qb-round-sweep', 'QB timing'],
              ['07-what-a-starter-is-worth', 'value curves'],
              ['33-te-same-pick', 'tight end timing']] },
    { lo: 6, hi: 8, text: 'Have your QB by round 6 — waiting past 10 ' +
      'is what hurts. Don\'t start your tight end here: a rounds 5-9 ' +
      'TE finishes top-6 just 16-30% of the time and misses top-12 ' +
      'over half the time — round-12 odds at a round-6 price. At WR ' +
      'the one rule that held up board-wide is age: 29 and older hit ' +
      'about 8 points less often than others costing the same pick.',
      links: [['06-qb-timing', 'QB'],
              ['33-te-same-pick', 'tight end timing'],
              ['10-wr-age-effects', 'WR age']] },
    { lo: 9, hi: 11, text: 'QB/TE starters are still here (41% and 43% ' +
      'hit) — RB/WR are lotteries now (12% / 17%). Go young at WR/TE. ' +
      'Handcuff your RB1 — it pays ' +
      'exactly when he sits.',
      links: [['29-round-profile', 'the numbers'],
              ['13-handcuffs-are-free-insurance', 'handcuffs']] },
    { lo: 12, hi: 15, text: 'Lottery rounds (5-8% hit): young ' +
      'receivers with a path, your RB\'s handcuff, and K/D-ST dead ' +
      'last — any kicker, the defense facing the lowest opponent total.',
      links: [['29-round-profile', 'the numbers'],
              ['04-kickers-are-noise', 'kickers'],
              ['27-dst-model', 'D/ST']] },
  ];
  const guideLinks = g => g.links.map(([slug, label]) =>
    `<a href="https://foss.football/#/blog/${slug}" target="_blank" ` +
    `rel="noopener">${label} ↗</a>`).join(' · ');

  function renderRoundGuide() {
    const el = $('round-guide');
    if (!showModelMarks) { el.hidden = true; return; }
    const rnd = Math.min(15, Math.floor(
      pickLogEntries().length / settings.numTeams) + 1);
    const g = GUIDE.find(x => rnd >= x.lo && rnd <= x.hi)
      || GUIDE[GUIDE.length - 1];
    el.hidden = false;
    $('round-guide-text').innerHTML =
      `<b>R${rnd}</b> · ${g.text} ${guideLinks(g)}`;
  }

  function renderTable() {
    const picked = pickedSet();
    const extPicked = extPickedCanonical();
    const team = new Set(teamNames());
    const search = searchText.trim().toLowerCase();
    const manual = settings.manualMode;

    const source = DATA.rankSources;
    const sourceFormat = { STD: 'standard', '0.5PPR': 'half-ppr', PPR: 'ppr' }[settings.scoringFormat];
    const sample = source && source.formats && source.formats[sourceFormat];
    const stamp = $('rank-data-stamp');
    if (stamp) {
      const stale = sample && Date.now() - Date.parse(sample.end_date + 'T23:59:59Z') > 7 * 86400000;
      stamp.textContent = sample
        ? `Board: FFC ${sample.teams}-team ${sample.type} mocks · through ${sample.end_date}${stale ? ' · STALE — refresh before drafting' : ''} · — = no current ADP`
        : 'Board source date unavailable — refresh before drafting';
      stamp.title = source ? `Fetched ${source.fetched_at}. ${source.espn}. Blue ranks are your personal overrides.` : '';
    }
    $('th-espn').title = 'ESPN overall ADP order, not standard-only or draft-room order. Click to sort.';
    $('th-rank').title = 'Board order from current FFC mock ADP. Hover a rank for average pick. Blue numbers are your imported ranks.';

    const sites = siteColumns();
    $('th-espn').hidden = !sites.includes('espn');
    $('th-sleeper').hidden = !sites.includes('sleeper');
    const nCols = 6 + sites.length;

    // Sorting is a view of the board, not a reordering of it: the AI top-15,
    // predictions, and the pick marker all still use board (rank) order.
    if (sortBy !== 'board' && !sites.includes(sortBy)) sortBy = 'board';
    $('th-rank').classList.toggle('sorted', sortBy === 'board');
    $('th-espn').classList.toggle('sorted', sortBy === 'espn');
    $('th-sleeper').classList.toggle('sorted', sortBy === 'sleeper');
    let list = boardPlayers();
    if (sortBy !== 'board') {
      const num = (v) => { const n = parseInt(v, 10); return isFinite(n) ? n : Infinity; };
      list = list.slice().sort((a, b) =>
        (sortBy === 'espn' ? num(a.espn) - num(b.espn) : num(a.sleeper) - num(b.sleeper)));
    }

    // NFL-team depth: WR2 = that team's 2nd-ranked WR. Bundled rank, so your
    // imported ranks don't reshuffle other teams' depth charts.
    const depthByName = new Map();
    const depthListByName = new Map();  // name -> the whole team+position chart
    {
      const byTeamPos = new Map();
      for (const q of allPlayers()) {
        const k = q.team + '|' + q.pos;
        if (!byTeamPos.has(k)) byTeamPos.set(k, []);
        byTeamPos.get(k).push(q);
      }
      for (const arr of byTeamPos.values()) {
        arr.sort((a, b) => (a.rankNum || 9999) - (b.rankNum || 9999));
        arr.forEach((q, i) => { depthByName.set(q.name, i + 1); depthListByName.set(q.name, arr); });
      }
    }

    // "Who's behind this guy, and by how much?" — the gap to the next player
    // at the same position on the same NFL team. A small gap means a
    // contested job; a large one means a clean workload whose backup is a
    // cheap handcuff. Also flags the backup directly behind a player you
    // already roster, which is the handcuff you actually want to find.
    function depthInfo(p) {
      const chart = depthListByName.get(p.name) || [p];
      const i = chart.indexOf(p);
      const rank = (q) => (q.rankNum && q.rankNum < 9999) ? q.rankNum : null;
      // Say "behind", never a signed number: a bigger rank is a worse player,
      // so "+112" reads backwards to anyone scanning quickly.
      const top = rank(chart[0]);
      const lines = chart.slice(0, 4).map((q, j) => {
        const r = rank(q);
        const gap = (j > 0 && r !== null && top !== null) ? ` — ${r - top} behind` : '';
        return `${j + 1}. ${q.name} (rank ${r === null ? 'unranked' : r})${gap}` +
          (team.has(q.name) ? ' ← yours' : '');
      });
      const ahead = i > 0 ? chart[i - 1] : null;
      // Running backs only. Handcuffing is an RB idea — finding 13 tested
      // "should you draft your starting RB's backup", and the insurance
      // it prices is the workload transferring whole when the starter
      // sits. Nothing equivalent happens at WR: your WR1 missing time
      // does not hand his targets to one named man. Flagging the WR
      // behind yours was calling a thing a handcuff that never pays like
      // one.
      const handcuffFor =
        (p.pos === 'RB' && ahead && team.has(ahead.name)) ? ahead : null;
      return {
        handcuffFor,
        title: (handcuffFor ? `Handcuff to your ${handcuffFor.name}. ` : '') +
          `${p.team} ${p.pos} depth by rank:\n` + lines.join('\n') +
          (chart.length > 4 ? `\n…${chart.length - 4} more` : ''),
      };
    }

    // Context for the pink "your next pick" marker and the orange
    // predicted-gone rows (both fed by the Draft Board tab).
    const entries = pickLogEntries();
    const nextInfo = yourNextPick(entries);
    const predGone = new Map(); // name -> simulated pick number
    if (predicted && nextInfo) {
      for (const pr of predicted) if (pr.pick < nextInfo.next) predGone.set(pr.name, pr.pick);
    }
    // The marker counts *all* available players above it, so it only makes
    // sense on the unfiltered, rank-ordered board.
    const wantMarker = Boolean(nextInfo) && posFilter === 'All' && !search && sortBy === 'board';

    const tbody = $('player-tbody');
    tbody.innerHTML = '';

    let shown = 0;
    let available = 0;
    let availShown = 0;
    let markerPlaced = false;
    visibleNames = [];
    // Every row advertises its click behavior — Ctrl+click is invisible otherwise.
    const openHint = 'Click / Enter: open the note · Ctrl+click / Ctrl+Enter: open in an extra tab';
    for (const p of list) {
      const isPicked = picked.has(p.name);
      if (!isPicked) available++;
      if (posFilter !== 'All' && p.pos !== posFilter) continue;
      if (isPicked && !showPicked) continue;
      if (search && !(p.name.toLowerCase().includes(search) || p.team.toLowerCase().includes(search))) continue;

      if (wantMarker && !markerPlaced && !isPicked && availShown === nextInfo.until) {
        const mtr = document.createElement('tr');
        mtr.className = 'next-pick-marker' + (nextInfo.until === 0 ? ' on-clock' : '');
        mtr.title = 'Where your next pick lands if players go roughly in board order — ' +
          'set Teams / Your slot on the Draft Board tab';
        mtr.innerHTML = `<td colspan="${nCols}">▼ ` +
          (nextInfo.until === 0
            ? `You're on the clock (pick ${nextInfo.next}) — make it in ${siteTab()}`
            : `Your next pick — pick ${nextInfo.next}, ${nextInfo.until} away`) +
          (predGone.size ? ' · orange rows = predicted gone by then' : '') + `</td>`;
        tbody.appendChild(mtr);
        markerPlaced = true;
      }

      shown++;
      if (!isPicked) availShown++;
      visibleNames.push(p.name);

      const tr = document.createElement('tr');
      tr.dataset.name = p.name;
      tr.title = openHint;
      if (isPicked) tr.classList.add('picked');
      if (team.has(p.name)) tr.classList.add('onteam');
      if (p.name === selectedName) tr.classList.add('selected');

      // Two things can make a row worth looking at twice, and they stack:
      // he backs up a running back you already own, and he may not last
      // until your next pick. That combination is exactly when you act,
      // so both go in the tooltip rather than one overwriting the other.
      const dep = depthInfo(p);
      const isHandcuff = Boolean(dep.handcuffFor) && !isPicked;
      const why = [];
      if (isHandcuff) {
        tr.classList.add('handcuff');
        why.push(`Backs up your ${dep.handcuffFor.name} — this is his ` +
          `handcuff, the back who inherits the work if he misses time`);
      }
      if (!isPicked && predGone.has(p.name)) {
        tr.classList.add('pred-gone');
        why.push('Predicted gone before your next pick — simulation has ' +
          `them taken at #${predGone.get(p.name)}`);
      }
      if (why.length) tr.title = `${why.join('\n')}\n${openHint}`;

      // Empty state is a hollow ring, not a dash: it reads as "slot waiting to
      // be filled" and lines up with the filled states above it.
      const step = markStep(toDraft[p.name]);
      const fromExt = extPicked.has(p.name);
      const ovRank = rankOverrideFor(p);

      // Picked/+Team live behind Manual mode (Settings) — in a live draft the
      // extension does this. Undo stays: it's how a bad fuzzy match gets fixed.
      const pickBtn = (manual || isPicked)
        ? `<button class="act-pick" title="${isPicked
            ? (fromExt ? 'Un-pick — use this if the extension matched the wrong player' : 'Undo pick')
            : (unpicked.has(p.name) ? 'Re-pick (you un-picked this one)' : 'Mark as picked/drafted by someone')} (P)"` +
          `>${isPicked ? 'Undo' : 'Picked'}</button>`
        : '';
      const teamBtn = manual
        ? `<button class="act-team" title="${team.has(p.name) ? 'Remove from your team' : 'Add to your team'} (T)">` +
          `${team.has(p.name) ? '−Team' : '+Team'}</button>`
        : '';

      const opp = showModelMarks ? oppRead(p) : null;
      const fm = showModelMarks ? fmarksFor(p) : null;
      // The model reads live in the name-cell hover and the note pane,
      // written out. No colored glyph on the row: a red/green ◆ is a
      // code you have to learn, and it says less than one sentence does.
      const nameTip = [opp && opp.tip, fm && fmTip(fm)]
        .filter(Boolean).join('\n\n');
      tr.innerHTML =
        (ovRank !== null
          ? `<td class="rank-override" title="Your rank (bundled: ${escapeHtml(p.rank)})">${escapeHtml(String(ovRank))}</td>`
          : `<td title="${p.adp ? `FFC average pick: ${escapeHtml(p.adp)}` : 'No current FFC ADP'}">${escapeHtml(p.rank)}</td>`) +
        `<td class="player-name"${nameTip ? ` title="${escapeHtml(nameTip)}"` : ''}>` +
        `${escapeHtml(p.name)}<span class="name-flags">` +
        `${step.v ? `<span class="${step.cls}" title="You marked him ${step.word}">${step.glyph}</span>` : ''}` +
        `${team.has(p.name) ? '<span class="flag-star">★</span>' : ''}</span></td>` +
        `<td class="team-cell">${escapeHtml(p.team)}</td>` +
        // The ⛓ that used to sit here is gone: the row itself now carries
        // the handcuff, and a symbol you have to learn said less than the
        // highlight does. The depth chart stays on hover.
        `<td class="pos-cell${isHandcuff ? ' is-handcuff' : ''}" ` +
          `title="${escapeHtml(dep.title)}">` +
          `${escapeHtml(p.pos)}${depthByName.get(p.name) || ''}</td>` +
        sites.map(s => {
          const label = s === 'espn' ? 'ESPN' : 'Sleeper';
          const raw = s === 'espn' ? p.espn : p.sleeper;
          const site = parseInt(raw, 10);
          const base = ovRank !== null ? ovRank : p.rankNum;
          if (!isFinite(site) || !isFinite(base) || base >= 9999) return `<td class="site-cell">${escapeHtml(String(raw))}</td>`;
          // Signed like the user thinks about it: how the site feels vs the
          // board. (+n) = the site is n spots HIGHER on them (goes earlier
          // there), (−n) = n spots lower (may fall to you there).
          const d = base - site;
          const diff = d === 0 ? '' :
            ` <span class="rk-diff">(${d > 0 ? '+' : ''}${d})</span>`;
          const tip = d === 0 ? `${label} agrees with the board rank`
            : d > 0 ? `${label} is ${d} spots higher on them than the board — they'll go earlier there`
            : `${label} is ${-d} spots lower on them than the board — they may fall to you there`;
          return `<td class="site-cell" title="${escapeHtml(tip)}">${site}${diff}</td>`;
        }).join('') +
        `<td class="note-cell"${noteEditedFor(p) ? ' title="You edited this note"' : ''}>` +
        `${noteEditedFor(p) ? '✎ ' : ''}${escapeHtml(truncateNote(noteFor(p)))}</td>` +
        `<td class="row-actions">` +
        pickBtn +
        `<button class="act-mark ${step.cls}" aria-haspopup="menu" title="${escapeHtml(
          `${step.v ? `You rate him ${step.word}` : 'Not rated'} — click to change` +
          ` (or press 1-5 with the row selected)\n${MARK_LEGEND}`)}">${step.glyph}</button>` +
        teamBtn +
        `</td>`;

      // One click = select + open the note (Ctrl+click opens an extra tab).
      // Clicks on the row's buttons don't count.
      tr.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        selectedName = p.name;
        updateSelection();
        openNote(p, e.ctrlKey || e.metaKey);
      });
      const pickEl = tr.querySelector('.act-pick');
      if (pickEl) pickEl.addEventListener('click', () => togglePicked(p.name));
      tr.querySelector('.act-mark').addEventListener('click', (e) => {
        const open = ratingMenuFor === p.name;
        closeRatingMenu();
        if (!open) {                      // a second click on it closes it
          selectedName = p.name;
          updateSelection();
          openRatingMenu(p.name, e.currentTarget);
        }
      });
      const teamEl = tr.querySelector('.act-team');
      if (teamEl) teamEl.addEventListener('click', () => toggleTeam(p.name));
      tbody.appendChild(tr);
    }

    $('player-count').textContent =
      `${shown} shown · ${available} available · ${picked.size} picked`;

    // Name the column after what the button in it does. In normal (extension-
    // driven) mode the only control there is your own rating, so the header
    // says Rating; the "we never draft for you" explanation moves into the
    // tooltip, where it answers the question it was really there to answer.
    const thActions = $('th-actions');
    if (thActions) {
      thActions.textContent = manual ? 'Actions' : 'Rating';
      thActions.title = manual
        ? 'Manual mode: mark picks and build your roster by hand with these buttons. ' +
          `Your rating is still here too — ${MARK_LEGEND}.`
        : `What you think of him — ${MARK_LEGEND}. Click the button to pick one ` +
          '(or press 1-5 on the selected row). Drafting itself happens in your ' +
          'ESPN/Sleeper draft room; picks show up here automatically. ' +
          'Settings → Manual mode adds by-hand Picked / +Team buttons.';
    }
    // Whose turn it is, not just how many picks have gone. In a manual
    // (debug) draft you pick for all 12 teams in turn — the snake decides who
    // each click belongs to — so this line is the only thing telling you
    // which team you're currently drafting for.
    const made = pickNumber();
    const totalPicks = settings.numTeams * settings.numRounds;
    const onClock = made + 1;
    const counterEl = $('pick-counter');
    if (onClock > totalPicks) {
      counterEl.textContent = `Draft complete · ${made} picks`;
      counterEl.title = `All ${totalPicks} picks are in`;
      counterEl.classList.remove('your-turn');
    } else {
      const onTeam = snakeTeamForPick(onClock, settings.numTeams);
      const round = Math.ceil(onClock / settings.numTeams);
      const inRound = onClock - (round - 1) * settings.numTeams;
      const mine = effectiveSlot(entries) === onTeam;
      counterEl.textContent = `Pick ${onClock} (${round}.${String(inRound).padStart(2, '0')}) · ` +
        `${mine ? '★ You' : 'Team ' + onTeam} on the clock`;
      counterEl.title = mine
        ? `Your pick — make it in ${siteTab()}; it will appear here automatically`
        : `Team ${onTeam} picks next. In debug mode your next "Picked" click drafts for them.`;
      counterEl.classList.toggle('your-turn', mine);
    }
  }

  function renderTeam() {
    const players = teamPlayers();
    const box = $('team-list');
    $('team-count').textContent = players.length
      ? `${players.length} player${players.length === 1 ? '' : 's'}` : '';

    // "Still need" = unfilled starting slots. K/DST aren't on the board but
    // the league still starts them, so they show up here until draft's end.
    const needsEl = $('team-needs');
    if (players.length) {
      const counts = {};
      for (const p of players) {
        const pos = normPos(p.pos);
        counts[pos] = (counts[pos] || 0) + 1;
      }
      const needs = Object.keys(STARTER_SLOTS).filter(pos => (counts[pos] || 0) < STARTER_SLOTS[pos]);
      // Bold-red when a position is *badly* needed: this deep into the draft
      // with none of them. K/DST are never flagged — they're not on the board,
      // so a drafted one can't be counted (they stay listed until the end).
      const curRound = Math.ceil((pickNumber() + 1) / settings.numTeams);
      needsEl.hidden = false;
      needsEl.innerHTML = needs.length
        ? 'Still need: ' + needs.map(pos =>
            (!counts[pos] && curRound >= (BADLY_NEEDED_BY_ROUND[pos] || 99))
              ? `<b class="need-bad" title="Round ${curRound} with no ${pos} yet — really needs one">${pos}</b>`
              : pos).join(', ')
        : 'All starting spots filled ✓';
    } else {
      needsEl.hidden = true;
    }

    if (!players.length) {
      box.innerHTML = '<p class="muted">No players on your team yet — they appear here ' +
        'automatically once the extension sees your draft room.</p>';
      return;
    }

    box.innerHTML = '';
    for (const group of groupByPosition(players)) {
      const pos = normPos(group.pos);
      const collapsed = Boolean(teamGroupsCollapsed[pos]);

      const head = document.createElement('button');
      head.type = 'button';
      head.className = 'team-group-head';
      head.title = collapsed ? `Show your ${pos}s` : `Hide your ${pos}s`;
      head.innerHTML = `<span class="tg-arrow">${collapsed ? '▸' : '▾'}</span>` +
        `<span>${escapeHtml(pos)}</span><span class="muted">· ${group.players.length}</span>`;
      head.addEventListener('click', () => {
        teamGroupsCollapsed[pos] = !collapsed;
        store.save('teamGroupsCollapsed', teamGroupsCollapsed);
        renderTeam();
      });
      box.appendChild(head);
      if (collapsed) continue;

      // Depth chart within the position: RB1, RB2, ... by rank.
      group.players.forEach((p, i) => {
        const row = document.createElement('div');
        row.className = 'team-row';
        row.innerHTML =
          `<span class="pos-chip pos-${escapeHtml(pos)}" title="Your ${pos}${i + 1}">${escapeHtml(pos)}${i + 1}</span>` +
          `<span class="t-name">${escapeHtml(p.name)}</span>` +
          `<span class="t-team" title="NFL team">${escapeHtml(p.team)}</span>` +
          `<span class="t-bye" title="Bye week — week ${escapeHtml(String(p.bye || '?'))}, they don't play">Bye ${escapeHtml(String(p.bye || '?'))}</span>` +
          `<span class="t-rank" title="Overall rank">#${escapeHtml(String(p.rank))}</span>`;
        const real = playerByName(p.name);
        if (real) {
          row.title = `${p.name} — click: open the note · Ctrl+click: extra tab`;
          row.addEventListener('click', (e) => {
            if (e.target.closest('button')) return;
            openNote(real, e.ctrlKey || e.metaKey);
          });
        }
        if (settings.manualMode && manualTeam.includes(p.name)) {
          const rm = document.createElement('button');
          rm.className = 't-rm';
          rm.textContent = '×';
          rm.title = 'Remove from your team';
          rm.addEventListener('click', () => toggleTeam(p.name));
          row.appendChild(rm);
        }
        box.appendChild(row);
      });
    }
  }

  // This tool never makes a pick for you — you draft on ESPN/Sleeper and the
  // extension mirrors it here. That's easy to misread as a missing feature
  // ("where's the pick button?"), so the badge says which way the data flows,
  // not just whether a connection exists.
  function renderExtStatus() {
    const el = $('ext-status');
    if (!extDetected) {
      el.textContent = 'Extension: not detected';
      el.className = 'ext-off';
      el.title = 'Picks are not syncing. Draft on your league site as usual — ' +
        'to see those picks here, install the extension, or turn on Manual mode ' +
        'in Settings to mark them by hand.';
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
    el.title = 'Picks sync in automatically from your draft site. Make every ' +
      'pick there — this board is a live mirror and never drafts for you.';
  }

  function renderAll() {
    // Predictions follow the live draft: in predict mode every new real pick
    // re-simulates the window instead of leaving a stale snapshot around.
    if (predictMode) {
      if (pickNumber() !== predictedAtCount) computePrediction();
    } else if (predicted) {
      predicted = null;
      predictedMeta = null;
    }
    $('btn-reset-top').hidden = !settings.manualMode;
    // Manual mode puts two more buttons on every row. The phone stylesheet
    // has to trade a column away to fit them, so it needs to know.
    document.body.classList.toggle('manual-mode', settings.manualMode);
    renderPosFilters();
    renderTable();
    renderRoundGuide();
    renderTeam();
    renderExtStatus();
    renderTabs();
  }

  function setStatus(msg) { $('status-bar').textContent = msg; }

  /* ---------- keyboard row selection ---------- */
  function updateSelection() {
    document.querySelectorAll('#player-tbody tr').forEach(tr =>
      tr.classList.toggle('selected', tr.dataset.name === selectedName));
  }

  function moveSelection(delta) {
    if (!visibleNames.length) return;
    const i = visibleNames.indexOf(selectedName);
    const next = i < 0
      ? (delta > 0 ? 0 : visibleNames.length - 1)
      : Math.min(Math.max(i + delta, 0), visibleNames.length - 1);
    selectedName = visibleNames[next];
    updateSelection();
    const tr = document.querySelector('#player-tbody tr.selected');
    if (tr) tr.scrollIntoView({ block: 'nearest' });
  }

  function selectedPlayer() {
    return selectedName ? (allPlayers().find(p => p.name === selectedName) || null) : null;
  }

  // Picking the selected row usually removes it from view; move the selection
  // to the row that takes its place so a rapid keyboard run keeps flowing.
  function keepSelectionNear(action) {
    const i = visibleNames.indexOf(selectedName);
    action();
    if (!visibleNames.includes(selectedName)) {
      selectedName = visibleNames[Math.min(Math.max(i, 0), visibleNames.length - 1)] || null;
      updateSelection();
    }
  }

  /* ---------- actions ---------- */
  // Un-picking an extension-sourced pick records an override instead of trying
  // to edit the scraped data, which the next scrape would just overwrite.
  function togglePicked(name) {
    const fromExt = extPickedCanonical().has(name);
    if (pickedSet().has(name)) {
      manualPicked.delete(name);
      if (fromExt) unpicked.add(name);
    } else {
      unpicked.delete(name);
      if (!fromExt) manualPicked.add(name);
    }
    store.save('manualPicked', [...manualPicked]);
    store.save('unpicked', [...unpicked]);
    renderAll();
  }

  function setMark(name, v) {
    if (v === null) delete toDraft[name];
    else toDraft[name] = v;
    closeRatingMenu();
    savePrep('toDraft', toDraft);
    renderAll();
  }

  /* ---------- rating picker ---------- */
  /* Clicking the rating opens the five steps and you take the one you
     mean. The alternative — click to advance one step — needs four
     clicks to say "really bad" and only tells you the scale exists if
     you keep clicking. A menu shows the whole scale, in words, the
     first time you open it, and teaches its own number keys while it's
     up (1-5 also work straight from the board). */
  let ratingMenuFor = null;      // player the open menu belongs to, or null
  let ratingMenuAnchor = null;   // the rating button it hangs off

  function closeRatingMenu() {
    if (!ratingMenuFor) return;
    ratingMenuFor = null;
    ratingMenuAnchor = null;
    const el = $('rating-menu');
    el.hidden = true;
    el.innerHTML = '';
  }

  function openRatingMenu(name, anchor) {
    const cur = toDraft[name] || null;
    const el = $('rating-menu');
    ratingMenuFor = name;
    ratingMenuAnchor = anchor;
    el.innerHTML =
      `<p class="rating-menu-head">${escapeHtml(name)}</p>` +
      MARK_SCALE.map(s =>
        `<button type="button" class="rating-opt${s.v === cur ? ' is-current' : ''}" ` +
        `data-v="${s.v === null ? '' : s.v}">` +
        `<span class="rating-opt-glyph ${s.cls}">${s.glyph}</span>` +
        `<span class="rating-opt-word">${s.word}</span>` +
        `<kbd>${s.key}</kbd></button>`).join('');
    el.hidden = false;
    positionRatingMenu();

    el.querySelectorAll('.rating-opt').forEach(b => {
      b.addEventListener('click', () => setMark(name, b.dataset.v || null));
    });
    const cursor = el.querySelector('.is-current') || el.querySelector('.rating-opt');
    if (cursor) cursor.focus();
  }

  // Anchored under the button, then pulled back inside the window — rows
  // near the bottom or the right edge must not open off-screen.
  function positionRatingMenu() {
    const el = $('rating-menu');
    if (!ratingMenuAnchor) return;
    const r = ratingMenuAnchor.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    const pad = 6;
    let top = r.bottom + 4;
    if (top + box.height > window.innerHeight - pad)
      top = Math.max(pad, r.top - box.height - 4);
    let left = r.right - box.width;
    left = Math.min(Math.max(pad, left), window.innerWidth - box.width - pad);
    el.style.top = `${top + window.scrollY}px`;
    el.style.left = `${left + window.scrollX}px`;
  }

  /* Scrolling the board moves the row the menu belongs to, so the menu goes
     with it — it does NOT close. Closing on any scroll event looks the same
     in normal use and then quietly eats the menu whenever a re-render
     happens to fire one. It closes only when its row is genuinely gone. */
  document.addEventListener('scroll', () => {
    if (!ratingMenuFor) return;
    const r = ratingMenuAnchor && ratingMenuAnchor.getBoundingClientRect();
    if (!r || !r.height || r.bottom < 0 || r.top > window.innerHeight) closeRatingMenu();
    else positionRatingMenu();
  }, true);
  window.addEventListener('resize', closeRatingMenu);
  document.addEventListener('mousedown', (e) => {
    if (ratingMenuFor && !e.target.closest('#rating-menu, .act-mark')) closeRatingMenu();
  });

  function toggleTeam(name) {
    const i = manualTeam.indexOf(name);
    if (i >= 0) manualTeam.splice(i, 1);
    else manualTeam.push(name);
    store.save('manualTeam', manualTeam);
    renderAll();
  }

  /* ---------- note tabs (Obsidian-style: click replaces, Ctrl+click adds) ---------- */
  function playerByName(name) {
    return allPlayers().find(p => p.name === name) || null;
  }

  function unsavedEditFor(name) {
    if (noteEditingName !== name) return false;
    const p = playerByName(name);
    return p ? $('note-textarea').value !== noteFor(p) : false;
  }

  // True = safe to drop any in-progress edit of `name` (none, unchanged, or
  // the user agreed to discard). Clears the editing state on the way out.
  function confirmDiscardEdit(name) {
    if (noteEditingName !== name) return true;
    if (unsavedEditFor(name) && !confirm(`Discard unsaved edits to ${name}'s note?`)) return false;
    noteEditingName = null;
    return true;
  }

  // 'ai' and 'board' are permanent tabs; everything else is a player note.
  function isNoteTab(tab) { return tab !== 'ai' && tab !== 'board'; }

  function touchTabHistory(tab) {
    dropFromTabHistory(tab);
    tabHistory.push(tab);
  }

  function dropFromTabHistory(tab) {
    const i = tabHistory.indexOf(tab);
    if (i >= 0) tabHistory.splice(i, 1);
  }

  function openNote(player, inNewTab) {
    const name = player.name;
    if (!openNotes.includes(name)) {
      const replaceTarget = inNewTab ? null : (isNoteTab(activeTab) ? activeTab : lastNoteTab);
      const i = replaceTarget ? openNotes.indexOf(replaceTarget) : -1;
      if (i >= 0) {
        if (!confirmDiscardEdit(replaceTarget)) return;
        openNotes[i] = name;
        dropFromTabHistory(replaceTarget);
      } else {
        openNotes.push(name);
      }
    }
    activeTab = name;
    lastNoteTab = name;
    touchTabHistory(name);
    // Tapping a row on a phone is a request to read the note, so go there.
    if (onPhone()) showMobileView('note');
    renderTabs();
  }

  function closeNote(name) {
    if (!confirmDiscardEdit(name)) return;
    const i = openNotes.indexOf(name);
    if (i < 0) return;
    openNotes.splice(i, 1);
    dropFromTabHistory(name);
    // Most recently visited tab that still exists ('ai'/'board' always do).
    const isOpen = (t) => !isNoteTab(t) || openNotes.includes(t);
    const fallback = [...tabHistory].reverse().find(isOpen) || 'ai';
    if (lastNoteTab === name) {
      lastNoteTab = [...tabHistory].reverse().find(t => isNoteTab(t) && openNotes.includes(t)) || null;
    }
    if (activeTab === name) activateTab(fallback);
    else renderTabs();
  }

  function activateTab(tab) {
    activeTab = tab;
    if (isNoteTab(tab)) lastNoteTab = tab;
    touchTabHistory(tab);
    // On a phone the panel is only on screen in two of the four views, so
    // jumping to a tab (B, A, the tab strip) has to bring its view along —
    // otherwise the tab switches behind whatever pane you're looking at.
    if (onPhone()) showMobileView(tab === 'board' ? 'board' : 'note');
    renderTabs();
  }

  function renderTabs() {
    const strip = $('tab-strip');
    strip.innerHTML = '';
    const mkTab = (label, tab, closable, title) => {
      const btn = document.createElement('button');
      btn.className = 'tab' + (activeTab === tab ? ' active' : '');
      btn.title = title || label;
      const lbl = document.createElement('span');
      lbl.className = 'tab-label';
      lbl.textContent = label;
      btn.appendChild(lbl);
      if (closable) {
        const x = document.createElement('span');
        x.className = 'tab-x';
        x.textContent = '×';
        x.title = 'Close (X / Esc)';
        x.addEventListener('click', (e) => { e.stopPropagation(); closeNote(tab); });
        btn.appendChild(x);
      }
      btn.addEventListener('click', () => activateTab(tab));
      strip.appendChild(btn);
    };
    mkTab('AI Output', 'ai', false, 'AI draft advice (A)');
    mkTab('Draft Board', 'board', false, 'Snake draft board with pick prediction (B)');
    for (const name of openNotes) mkTab(name, name, true);

    $('ai-output').hidden = activeTab !== 'ai';
    $('board-view').hidden = activeTab !== 'board';
    $('note-view').hidden = activeTab === 'ai' || activeTab === 'board';
    if (activeTab === 'board') renderBoard();
    else if (activeTab !== 'ai') renderNotePane();
  }

  function renderNotePane() {
    const p = playerByName(activeTab);
    if (!p) return;
    const edited = noteEditedFor(p);
    const editing = noteEditingName === p.name;
    const opp = showModelMarks ? oppRead(p) : null;
    const fm = showModelMarks ? fmarksFor(p) : null;
    /* Two reasons this tag stays quiet, both "we already know it means
       nothing here":
       - Only WR/TE. The 2017-25 backtest behind this number found the
         gap predicts the next season at those two positions only
         (OPP_SIGNAL_POS). Telling a drafter his RB1 "scored above his
         chances" is commentary the engine itself cannot cash — the
         running back's own tooltip goes on to say goal-line work
         repeats. So RB/QB get the plain stat and no verdict.
       - Not alongside the touchdown-luck row, which states the same
         fact in touchdowns that this states in points; for most
         flagged players the whole gap IS the extra scores. The row
         carries the number and the link, so the tag yields. */
    const saidByRow = (fm || []).some(m => m.f === 16);
    const tagWorthIt = opp && opp.flagged && opp.signal && !saidByRow;
    $('note-meta').textContent = `${p.team} ${p.pos}, rank ${p.rank}` +
      (opp ? ` · 2025: ${p.ppg25.toFixed(1)} PPG, ` +
        `${p.xfp.toFixed(1)} from his chances` +
        (tagWorthIt
          ? (opp.hot ? ' — scored above them' : ' — scored below them')
          : '') : '') +
      `${edited ? ' · edited' : ''}`;
    $('note-meta').title = opp ? opp.tip : '';
    // Who else is in his position room. Plain facts off the draft board,
    // so it is shown regardless of the model-marks switch and never gets
    // a row glyph: the room order comes from ADP, so it is not a
    // disagreement with the market (finding 25).
    const roomLine = roomText(p);
    $('note-room').hidden = !roomLine;
    $('note-room').textContent = roomLine || '';
    $('note-findings').hidden = !fm;
    $('note-findings').innerHTML = !fm ? '' : fm.map(m =>
      `<p class="fm-row fm-${m.dir}"><a class="fm-chip" target="_blank" ` +
      `rel="noopener" href="https://foss.football/#/blog/${escapeHtml(m.slug)}" ` +
      `title="Read the research behind this in a new tab">${FM_LABEL[m.dir]}` +
      ` · ${escapeHtml(fmTopic(m))} ↗</a> ${escapeHtml(m.note)}</p>`).join('');
    $('note-editor').hidden = !editing;
    $('note-body').hidden = editing;
    $('btn-edit-note').hidden = editing;
    $('btn-revert-note').disabled = !edited;
    if (!editing) {
      // While editing, never touch the textarea — it holds the user's draft
      // (even across tab switches; the draft survives until Save or Cancel).
      const note = noteFor(p);
      $('note-body').innerHTML = note
        ? renderMarkdown(note)
        : '<p class="muted">No note for this player yet — click Edit to write one.</p>';
    }
  }

  /* ---------- Draft Board tab ---------- */
  function shortPlayerName(name) {
    const parts = name.split(/\s+/);
    return parts.length < 2 ? name : parts[0][0] + '. ' + parts.slice(1).join(' ');
  }

  function syncBoardToolbar(slot) {
    // League shape is auto/default (12 teams, 15 rounds, slot auto-detected);
    // the controls to change it only appear in debug/manual mode.
    const dbg = settings.manualMode;
    $('board-config').hidden = !dbg;
    $('board-config-summary').hidden = dbg;
    if (!dbg) {
      $('board-config-summary').textContent =
        `${settings.numTeams} teams · ${settings.numRounds} rounds · ` +
        (slot ? `your slot: ${slot}` : 'your slot: click your column below');
    }
    const teamsSel = $('board-teams');
    if (!teamsSel.options.length) {
      for (const n of [8, 10, 12, 14, 16]) teamsSel.add(new Option(String(n), String(n)));
    }
    teamsSel.value = String(settings.numTeams);
    const slotSel = $('board-slot');
    slotSel.innerHTML = '';
    slotSel.add(new Option('auto', '0'));
    for (let i = 1; i <= settings.numTeams; i++) slotSel.add(new Option(String(i), String(i)));
    slotSel.value = String(
      settings.draftSlot >= 1 && settings.draftSlot <= settings.numTeams ? settings.draftSlot : 0);
    $('board-rounds').value = settings.numRounds;
    $('board-bot-ranks').value = settings.botRanks || 'auto';
    $('board-bot-algo').value = settings.botAlgo || 'need';
    // The button states the assumption instead of hiding it behind a gear —
    // "which ranking do the bots use" is the question every surprising
    // prediction comes back to, so the answer is always on screen.
    $('bot-config-label').textContent = 'Bots: ' + botRanksLabel();
    // Predict mode is a toggle: while it's on (and auto-updating), the only
    // button that makes sense is the way out.
    $('btn-predict').hidden = predictMode;
    $('btn-clear-predict').hidden = !predictMode;
  }

  // Human name for the ranking the bots sort on. 'auto' resolves the same way
  // computePrediction() does, so the label never claims a source the
  // simulation didn't actually use.
  function botRanksLabel() {
    const src = !settings.botRanks || settings.botRanks === 'auto'
      ? (draftSite() === 'sleeper' ? 'sleeper' : 'espn')
      : settings.botRanks;
    return { espn: 'ESPN ADP', sleeper: 'Sleeper rank', mine: 'my board' }[src] || src;
  }

  // What each position looks like NOW vs at your next pick, per the
  // simulation. This is the "should I take a QB now?" answer: if the drop-off
  // between the two names is steep, the position is about to dry up.
  function renderOutlook(info) {
    const el = $('board-outlook');
    if (!predicted) {
      el.innerHTML = '<span class="muted" title="“Who should I take?” simulates the room between now ' +
        'and your turn, then stays on and re-simulates after every real pick">' + (info
        ? `Next pick <b>${info.next}</b>, ${info.until} away · <b>Who should I take?</b> to see what survives.`
        : 'Click your column header to set your draft slot.') + '</span>';
      return;
    }
    if (!info) {
      el.innerHTML = '<span class="muted">Click your column header to set your draft slot.</span>';
      return;
    }
    const picked = pickedSet();
    const goneByThen = new Set(predicted.filter(pr => pr.pick < info.next).map(pr => pr.name));
    const avail = boardPlayers().filter(p => !picked.has(p.name));
    const meta = predictedMeta;

    // On the clock there is no gap between "now" and "your pick": nothing can
    // go before you, so a "gone before you" column is always 0 and the "now"
    // and "at your pick" columns are the same player. Drop both — what's left
    // is the only live comparison, take it now vs. wait for your next turn.
    const onClock = info.until <= 0;
    const follow = meta ? meta.followNext : null;

    // Two numbers per name, because two different rankings drive this table:
    // your board rank (what the cost is priced off) and the ranking the bots
    // sort on (what decides who's actually gone). Showing only the first is
    // what makes a faller look impossible — "my #18 is still here at pick 28?"
    // reads as a broken sim until you can see ESPN has him 36th.
    const srcLabel = { espn: 'ESPN', sleeper: 'Sleeper' }[meta && meta.botSrc] || '';
    const myRank = (p) => {
      const o = meta && meta.effRank ? meta.effRank(p) : null;
      return o === null || o === undefined ? p.rank : String(o).replace(/\.0$/, '');
    };
    const cell = (p) => {
      if (!p) return '—';
      const bot = srcLabel && p[meta.botSrc] ? p[meta.botSrc] : '';
      return `${escapeHtml(p.name)} <span class="ol-rank">${escapeHtml(myRank(p))}</span>` +
        (bot ? ` <span class="ol-adp">${srcLabel}&nbsp;${escapeHtml(bot)}</span>` : '');
    };

    let suggest = '';
    if (meta && meta.suggestion) {
      const s = meta.suggestion;
      // Answer first, reasoning second. This panel is read while a clock runs,
      // so the name leads and the arithmetic justifies it underneath — the
      // question is "who do I take", not "what does the simulation forecast".
      // Cost ~0 means nothing drops off before your following turn — usually
      // back-to-back at the snake turn. A bare "0" invites the obvious "then
      // why this player?"; the honest answer is that no position is scarce.
      const pts = Math.round(s.cost);
      const spots = s.spots
        ? ` — ${s.spots} spot${s.spots === 1 ? '' : 's'} further down your board`
        : '';
      const why = !s.B
        ? `${s.pos} runs out entirely before pick ${meta.followNext} — last chance at the position`
        : pts >= 1
          ? `Waiting until pick ${meta.followNext} costs about <b>${pts} points</b> at ${s.pos}: ` +
            `pass and the best one left is <b>${escapeHtml(s.B.name)}</b> ` +
            `${escapeHtml(myRank(s.B))}${spots}`
          : `nothing worth having goes before pick ${meta.followNext} — no position is scarce, ` +
            'so this is simply best available';
      suggest = '<div class="ol-suggest" title="Among the positions you\'d draft now, the one ' +
        'where waiting until your following turn costs the most projected points.">' +
        `<div class="ol-suggest-head">${onClock ? 'Your pick now' : `At your pick ${info.next}`} — ` +
        `<b>${escapeHtml(s.A.name)}</b> <span class="ol-suggest-meta">${s.pos} · your #${escapeHtml(myRank(s.A))}</span></div>` +
        `<div class="ol-suggest-why">${why}</div></div>`;
    }

    const head = '<tr><th></th>' +
      (onClock ? '' : '<th>Best now</th>' +
        '<th title="How many at this position the simulation expects to come off the board before your turn">Taken before you</th>') +
      `<th>${onClock ? 'Best available' : `Yours at ${info.next}`}</th>` +
      `<th title="The best one at this position the simulation still leaves you at your following turn">If you pass${follow ? ` — pick ${follow}` : ''}</th>` +
      '<th title="What passing here costs, in projected season points: the two names on this row ' +
      'priced off this position\'s points-per-draft-slot curve. Points rather than rank spots, ' +
      'because 30 spots of TE and 16 spots of RB are nothing like the same amount of football.">' +
      'Cost of waiting</th></tr>';

    const rows = [];
    for (const pos of ['QB', 'RB', 'WR', 'TE']) {
      const now = avail.find(p => p.pos === pos);
      if (!now) continue;
      const atPick = avail.find(p => p.pos === pos && !goneByThen.has(p.name));
      const gone = avail.filter(p => p.pos === pos && goneByThen.has(p.name)).length;
      const pv = meta && meta.byPos[pos];
      // Points decide; the spot count rides along because "16 spots" is how
      // the drop actually looks when you scroll the board next to this panel.
      // A "bench" tag explains the one thing that otherwise looks broken here:
      // why a row with a bigger number than the suggested pick didn't win.
      const under = pv && pv.bench
        ? `${pv.spots} spot${pv.spots === 1 ? '' : 's'} · <span class="ol-bench">bench</span>`
        : pv ? `${pv.spots} spot${pv.spots === 1 ? '' : 's'}` : '';
      const waitCells = !pv
        ? '<td>—</td><td>—</td>'
        : !pv.B
          ? '<td class="ol-gone">none left</td><td class="ol-gone">runs out</td>'
          : `<td>${cell(pv.B)}</td>` +
            `<td class="ol-cost">${Math.round(pv.cost) < 1 ? '<span class="ol-free">nothing</span>'
              : `${Math.round(pv.cost)} pts<span class="ol-spots">${under}</span>`}</td>`;
      rows.push('<tr>' +
        `<td><span class="pos-chip pos-${pos}">${pos}</span></td>` +
        (onClock ? '' : `<td>${cell(now)}</td><td class="ol-gone">${gone}</td>`) +
        `<td>${cell(atPick)}</td>` + waitCells + '</tr>');
    }

    // Spell out whose ranking is whose under the table, and what the points
    // are. The two rank numbers are only interpretable as a pair, and the
    // bots' source is the assumption most worth doubting — so it's named here,
    // next to the button that changes it.
    const legend = '<div class="ol-legend muted">' +
      '<span class="ol-rank">18</span> your board rank' +
      (srcLabel ? ` · <span class="ol-adp">${srcLabel}&nbsp;36</span> what the bots draft from — ` +
        `who disappears is decided by ${srcLabel}, not by your board.` : '') +
      '<br><b>Cost of waiting</b> is projected season points (standard scoring), from the ' +
      'points-per-draft-slot curve each position was fitted to over the 2020–2025 drafts. ' +
      'That conversion is the point: rank spots are not comparable across positions, points are.' +
      (Object.values(meta ? meta.byPos : {}).some(v => v.bench)
        ? ' A row marked <span class="ol-bench">bench</span> has its starting spots filled ' +
          'already, so its cost counts for less toward the suggested pick — points on your ' +
          'bench are not points in your lineup.'
        : '') +
      '</div>';

    el.innerHTML = suggest +
      `<div class="ol-status muted">${onClock
        ? `<b>You're on the clock — make the pick in ${siteTab()}.</b>`
        : `Simulated through pick ${info.next}`} ` +
      '<span title="Predict mode is live: the window re-simulates automatically after every ' +
      'real pick">· live</span></div>' +
      `<table><thead>${head}</thead><tbody>${rows.join('')}</tbody></table>` + legend;
  }

  // Below this a cell can't hold even a shortened name, so the board stops
  // shrinking columns and starts scrolling sideways instead. That is the
  // whole phone story for this grid: 12 columns will never fit 375px.
  const BD_MIN_COL = 64;

  // Width one team column gets at a given wrapper width, before the floor.
  // Mirrors the grid template: round gutter + padding + inter-column gaps.
  function boardColWidth(wrapW, teams) {
    return (wrapW - 21 - 0.8 * 15 - 2 * teams) / teams;
  }

  // Cell text scales to the column width: as large as fits where there's
  // room, smaller (never unreadable) when 12+ columns share a narrow panel.
  // Everything else in a cell is sized in em off this, so one number drives
  // the whole grid. Re-run on resize, not just on render — the panel divider
  // changes the width without changing the board's contents.
  function sizeBoardFont() {
    const wrap = $('board-grid-wrap');
    const grid = $('board-grid');
    if (!wrap || !grid || !wrap.clientWidth) return;
    const teams = settings.numTeams;
    // Once the floor kicks in the columns are BD_MIN_COL wide regardless of
    // the wrapper, so size the text off that and not off the squeezed share.
    const colW = Math.max(BD_MIN_COL, boardColWidth(wrap.clientWidth, teams));
    // Sized to fit ~10 bold characters, which covers the median shortened
    // name ("J. Chase", 9 chars). Longer ones wrap to a second line rather
    // than holding the whole grid down to their width.
    // Rounded, and only written when it actually changes: resizing the text
    // resizes the grid, which can add or remove the scrollbar this
    // measurement depends on. Quantising keeps that from oscillating.
    const px = Math.round(Math.max(12, Math.min(16, (colW - 10) / 5.6)) * 2) / 2;
    const next = px + 'px';
    if (grid.style.getPropertyValue('--bd-font') !== next) {
      grid.style.setProperty('--bd-font', next);
    }
  }

  function renderBoard() {
    const teams = settings.numTeams;
    const rounds = settings.numRounds;
    const entries = pickLogEntries();
    const made = entries.length;
    const info = yourNextPick(entries);
    const slot = info ? info.slot : effectiveSlot(entries);
    syncBoardToolbar(slot);
    const counts = rosterCountsByTeam(entries, teams);
    const predByPick = new Map();
    if (predicted) for (const pr of predicted) predByPick.set(pr.pick, pr);

    renderOutlook(info);

    const grid = $('board-grid');
    // Equal columns that grow with the panel: on a normal window the board
    // fills the width and never scrolls sideways. On a phone the columns hit
    // their floor and the board pans instead — a 12-wide grid squeezed into
    // 375px would be twelve columns of ellipsis.
    const wrapW = $('board-grid-wrap').clientWidth;
    const min = wrapW && boardColWidth(wrapW, teams) < BD_MIN_COL ? `${BD_MIN_COL}px` : '0';
    grid.style.gridTemplateColumns = `1.4em repeat(${teams}, minmax(${min}, 1fr))`;
    sizeBoardFont();
    grid.innerHTML = '';

    // The round the draft is in right now — the "badly needs" threshold.
    const curRound = Math.min(Math.ceil((made + 1) / teams), rounds);

    // Corner above the round numbers. Classed so it can stay pinned with them
    // when the board is being panned sideways on a narrow screen.
    const corner = document.createElement('div');
    corner.className = 'bd-corner';
    grid.appendChild(corner);
    for (let t = 1; t <= teams; t++) {
      const h = document.createElement('button');
      h.type = 'button';
      h.className = 'bd-head' + (slot === t ? ' your-col' : '');
      const c = counts[t - 1];
      const needs = Object.keys(STARTER_SLOTS)
        .filter(pos => pos !== 'K' && pos !== 'DST' && (c[pos] || 0) < STARTER_SLOTS[pos]);
      const badly = new Set(needs.filter(pos => !c[pos] && curRound >= BADLY_NEEDED_BY_ROUND[pos]));
      const roster = BOARD_POS_ORDER
        .filter(pos => c[pos]).map(pos => `${pos} ${c[pos]}`).join(', ');
      h.title = (slot === t ? 'Your team' : `Team ${t} — click if this is your draft slot`) +
        (roster ? ` · has ${roster}` : ' · empty roster') +
        (needs.length
          ? ' · ' + needs.map(pos => badly.has(pos)
              ? `REALLY needs ${pos} (round ${curRound}, none yet)` : `needs ${pos}`).join(' · ')
          : ' · starters filled');
      // What they've actually drafted, one line per position they own —
      // positions at zero are simply absent. Draft-priority order, so the
      // lines that matter most sit closest to the team name. The headers all
      // share a row of the grid, so they already size to the busiest team;
      // a team with 3 RBs stays one line, and everyone grows only when
      // someone spreads across more positions.
      const hasLine = '<div class="bd-has">' + BOARD_POS_ORDER
        .filter(pos => c[pos])
        .map(pos => `<span>${pos} ${c[pos]}</span>`).join('') + '</div>';
      h.innerHTML = `<div class="bd-team-name">${slot === t ? '★ You' : 'Team ' + t}</div>` +
        hasLine;
      h.addEventListener('click', () => {
        settings.draftSlot = settings.draftSlot === t ? 0 : t; // click again = back to auto
        store.save('settings', settings);
        if (predictMode) computePrediction(); // the window is defined by your slot
        renderBoard();
        renderTable(); // the pink marker on the main board moves too
      });
      grid.appendChild(h);
    }

    for (let round = 1; round <= rounds; round++) {
      const rl = document.createElement('div');
      rl.className = 'bd-round';
      rl.textContent = String(round);
      rl.title = `Round ${round}`;
      grid.appendChild(rl);
      for (let col = 1; col <= teams; col++) {
        // Snake: odd rounds run 1..T, even rounds T..1.
        const n = round % 2 === 1 ? (round - 1) * teams + col : round * teams - col + 1;
        const pickLabel = `${round}.${String(n - (round - 1) * teams).padStart(2, '0')}`;
        const cell = document.createElement('div');
        let cls = 'bd-cell';
        if (col === slot) cls += ' your-col';
        // A filled cell reads top-to-bottom like any draft board: pick
        // number, name, then position and NFL team. The full name is in the
        // tooltip for the few that don't fit on one line.
        const fill = (name, pos, nfl) =>
          `<div class="bd-pick">${pickLabel}</div>` +
          `<div class="bd-name">${escapeHtml(shortPlayerName(name))}</div>` +
          `<div class="bd-meta">${escapeHtml(pos === 'UNK' ? (nfl || '') : pos + (nfl ? ' · ' + nfl : ''))}</div>`;
        if (n <= made) {
          const en = entries[n - 1];
          const pos = en.player ? normPos(en.player.pos) : 'UNK';
          cls += ` done pos-${pos}`;
          cell.title = `#${n} (${pickLabel}) — ${en.name}` +
            (en.player ? ` (${en.player.team} ${en.player.pos})` : '');
          cell.innerHTML = fill(en.name, pos, en.player ? en.player.team : '');
        } else if (predByPick.has(n)) {
          const pr = predByPick.get(n);
          cls += ` pred pos-${pr.pos}`;
          cell.title = `#${n} (${pickLabel}) — predicted: ${pr.name} (${pr.pos})`;
          cell.innerHTML = fill(pr.name, pr.pos, pr.nfl);
        } else {
          cls += ' empty';
          cell.title = `Pick #${n}` + (col === slot ? ' — yours' : '');
          cell.innerHTML = `<div class="bd-pick">${pickLabel}</div>`;
        }
        if (info && n === info.next) {
          cls += ' next-your';
          if (info.until <= 0) {
            // Your turn, right now. This cell goes solid pink and says so —
            // it's the one thing on the board you must not scroll past.
            // (info.next is always an unmade, unpredicted pick, so there's no
            // player content here to overwrite.)
            cls += ' on-clock';
            cell.innerHTML = `<div class="bd-pick">${pickLabel}</div>` +
              '<div class="bd-clock">YOUR PICK</div>';
            cell.title = `Pick ${n} — you're on the clock. Make it in ${siteTab()}.`;
          } else {
            cell.title += ' — your next pick';
          }
        }
        cell.className = cls;
        grid.appendChild(cell);
      }
    }
  }

  // Simulate only the picks between now and YOUR next turn — that's the
  // decision-relevant window ("who makes it back to me?"), not the whole
  // draft. By default opponents don't share your board: they draft by their
  // own site's rankings (ESPN or Sleeper, whichever the draft is on),
  // need-adjusted — but the toolbar's "Bots follow" / "Bot style" selects
  // can pin the ranking source or drop the need filter.
  //
  // Recomputes from the current live state and returns the pick info (or
  // null when your slot is unknown). In predict mode renderAll() calls this
  // again after every real pick, so the simulation tracks the live draft.
  // On the clock (until 0) there is nothing to simulate before your pick,
  // but the outlook/suggestion is exactly what you want right then.
  function computePrediction() {
    predicted = null;
    predictedMeta = null;
    predictedAtCount = pickNumber();
    const teams = settings.numTeams;
    const rounds = settings.numRounds;
    const entries = pickLogEntries();
    const info = yourNextPick(entries);
    if (!info) return null;
    const picked = pickedSet();
    const num = (v) => { const n = parseInt(v, 10); return isFinite(n) ? n : Infinity; };
    const effRank = (p) => {
      const o = rankOverrideFor(p);
      return o === null ? (p.rankNum || 9999) : o;
    };
    const src = !settings.botRanks || settings.botRanks === 'auto'
      ? (draftSite() === 'sleeper' ? 'sleeper' : 'espn')
      : settings.botRanks;
    // 'mine' = your board order, edits included; a site column falls back to
    // board rank for players the site didn't rank (num() -> Infinity).
    const botRank = src === 'mine' ? effRank : (p) => num(p[src]);
    const algo = settings.botAlgo;
    const avail = boardPlayers()
      .filter(p => !picked.has(p.name))
      .sort((a, b) => (botRank(a) - botRank(b)) || ((a.rankNum || 9999) - (b.rankNum || 9999)));
    const made = Math.max(entries.length, pickNumber());
    predicted = predictDraft(avail, rosterCountsByTeam(entries, teams),
      made + 1, info.next - 1, teams, rounds, algo);

    // Pick value for YOUR turn: for each position, compare the best player
    // there at your pick (A) vs the best left at your FOLLOWING pick (B), with
    // opponents simulated in between, and price both off that position's
    // points-per-slot curve. E(pos, rank A) − E(pos, rank B) is the cost of
    // waiting one turn in projected season points; among positions you'd
    // reasonably draft, the most expensive wait is the pick. The extended
    // simulation is internal — the grid still only shows up to your pick.
    const goneNames = new Set(predicted.map(pr => pr.name));
    const followNext = nextPickForTeam(info.slot, teams, info.next);
    const countsAfter = rosterCountsByTeam(entries, teams);
    for (const pr of predicted) {
      countsAfter[pr.team - 1][pr.pos] = (countsAfter[pr.team - 1][pr.pos] || 0) + 1;
    }
    const ext = predictDraft(avail.filter(p => !goneNames.has(p.name)), countsAfter,
      info.next + 1, Math.min(followNext - 1, teams * rounds), teams, rounds, algo);
    const goneByFollowing = new Set([...goneNames, ...ext.map(pr => pr.name)]);

    const myCounts = {};
    for (const p of teamPlayers()) {
      const pos = normPos(p.pos);
      myCounts[pos] = (myCounts[pos] || 0) + 1;
    }
    const round = Math.ceil(info.next / teams);
    const boardAvail = boardPlayers().filter(p => !picked.has(p.name));
    const myGaps = new Set();
    let myGapCount = 0;
    const poolPos = new Set(boardAvail.map(p => normPos(p.pos)));
    for (const pos of Object.keys(STARTER_SLOTS)) {
      if (!poolPos.has(pos)) continue;
      const gap = STARTER_SLOTS[pos] - (myCounts[pos] || 0);
      if (gap > 0) { myGaps.add(pos); myGapCount += gap; }
    }
    const myMustFill = myGapCount > rounds - round ? myGaps : null;
    // One flex on top of the fixed starters, so a third RB/WR is still lineup
    // value rather than bench depth.
    const flexBodies = FLEX_POSITIONS.reduce((n, pos) => n + (myCounts[pos] || 0), 0);
    const flexSlots = FLEX_POSITIONS.reduce((n, pos) => n + STARTER_SLOTS[pos], 0) + 1;
    const flexOpen = flexBodies < flexSlots;

    const byPos = {};
    let suggestion = null;
    for (const pos of ['QB', 'RB', 'WR', 'TE']) {
      const A = boardAvail.find(p => p.pos === pos && !goneNames.has(p.name));
      if (!A) continue;
      const B = boardAvail.find(p => p.pos === pos && !goneByFollowing.has(p.name));
      const spots = B ? effRank(B) - effRank(A) : null;
      const cost = waitCost(pos, effRank(A), B ? effRank(B) : null);
      // Points on the bench aren't points in the lineup: a position whose
      // starting slots you've already filled is worth a fraction of the same
      // wait cost. Without this the math cheerfully drafts a fifth running
      // back because the RB curve is the steepest one on the board.
      const bench = !(myGaps.has(pos) || (flexOpen && FLEX_POSITIONS.includes(pos)));
      const weighted = bench ? cost * BENCH_WEIGHT : cost;
      byPos[pos] = { A, B, cost, spots, bench };
      if (!wouldDraft(pos, myCounts[pos] || 0, round, rounds, myMustFill)) continue;
      if (!suggestion || weighted > suggestion.weighted ||
          (weighted === suggestion.weighted && effRank(A) < effRank(suggestion.A))) {
        suggestion = { pos, A, B, cost, spots, weighted, bench };
      }
    }
    // botSrc rides along so the outlook can show the number the bots actually
    // sorted on next to your own rank. Without it the table mixes two rank
    // systems silently, and any player your board likes more than the site
    // does reads as an inexplicable faller.
    predictedMeta = { followNext, byPos, suggestion, botSrc: src, effRank };
    return info;
  }

  // The "Who should I take?" button: turn predict mode on. From here on the
  // simulation refreshes itself after every real pick, until Return to live.
  function runPrediction() {
    const info = computePrediction();
    if (!info) {
      setStatus('Set your draft slot first — click your column header on the grid below');
      return;
    }
    predictMode = true;
    store.save('predictMode', true);
    setStatus(info.until <= 0
      ? `You're on the clock — take the suggested pick in ${siteTab()}; predictions continue after you pick`
      : `Simulated the ${info.until} picks before your turn (#${info.next}) — ` +
        'stays on and re-simulates as real picks come in');
    renderTable();
    renderBoard();
  }

  /* ---------- extension bridge (see chrome-extension/bridge.js) ---------- */

  /* Your prep — the marks you set, the notes you rewrote, the ranks you
     imported — is work you can't get back, and localStorage is the wrong
     place to keep the only copy of it: "clear browsing data" wipes it, and
     it doesn't follow you from one origin to another (a local copy of the
     tool and foss.football are separate stores). So when the extension is
     installed we mirror prep into chrome.storage.local, which survives both.
     localStorage stays the working copy — synchronous, always there,
     unchanged when there's no extension — and the mirror is a backup that
     wins only when it is newer than what this browser has. */
  const PREP_FIELDS = ['toDraft', 'noteOverrides', 'rankOverrides'];

  function savePrep(key, value) {
    store.save(key, value);
    mirrorPrep();
  }

  function mirrorPrep() {
    const at = Date.now();
    store.save('prepSavedAt', at);
    // Harmless when no extension is listening — nobody answers.
    window.postMessage({ source: 'ffda-page', type: 'save-prep',
      prep: { savedAt: at, toDraft, noteOverrides, rankOverrides } }, '*');
  }

  // The extension's copy is newer than this browser's: adopt it wholesale.
  // Whole-blob, not per-player: merging two edit histories without a real
  // sync protocol invents a third state that neither browser ever had.
  function adoptPrep(prep) {
    if (!prep || typeof prep !== 'object') return false;
    const mine = store.load('prepSavedAt', 0);
    if (!(prep.savedAt > mine)) return false;
    if (noteEditingName) return false;   // never yank a note out from under an edit
    toDraft = prep.toDraft || {};
    noteOverrides = prep.noteOverrides || {};
    rankOverrides = prep.rankOverrides || {};
    for (const f of PREP_FIELDS) store.save(f, { toDraft, noteOverrides, rankOverrides }[f]);
    store.save('prepSavedAt', prep.savedAt);
    return true;
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const msg = event.data;
    if (!msg || msg.source !== 'ffda-ext') return;

    extDetected = true;
    // The bridge says hello with an empty payload before any draft page has
    // been scraped; that is not "data received", it is just a handshake.
    let gotData = false;
    let gotPrep = false;
    if (msg.type === 'state' && msg.data) {
      for (const key of ['picked_players', 'roster_players', 'available_players']) {
        if (msg.data[key]) { extState[key] = msg.data[key]; gotData = true; }
      }
      // Prep rides along with every state push. Either the extension has a
      // newer copy and we take it, or ours is newer and it should have it.
      if (adoptPrep(msg.data.prep)) gotPrep = true;
      else if (!msg.data.prep || msg.data.prep.savedAt < store.load('prepSavedAt', 0)) mirrorPrep();
    }
    if (!gotData && !gotPrep) { renderExtStatus(); return; }

    if (gotData) store.save('extState', extState);
    const picked = extState.picked_players;
    if (gotData && picked && Array.isArray(picked.players)) mergeExtPicked(picked.players);
    setStatus(gotPrep && !gotData
      ? 'Your marks and note edits came back from the extension'
      : gotPrep ? 'Draft data and your saved prep received from the extension'
      : 'Draft data received from extension');
    renderAll();
  });

  function requestExtState() {
    window.postMessage({ source: 'ffda-page', type: 'request-state' }, '*');
  }
  // The bridge may inject after us; retry the handshake for a while.
  [0, 500, 1500, 3500, 8000].forEach(ms => setTimeout(() => { if (!extDetected) requestExtState(); }, ms));
  setInterval(() => { if (!extDetected) requestExtState(); }, 30000);

  /* ---------- LLM ---------- */
  async function localClaudeStatus() {
    if (!['localhost', '127.0.0.1'].includes(location.hostname)) {
      throw new Error('Claude Code needs the local dashboard. Run python3 webapp/local_server.py and open http://localhost:8765.');
    }
    let info;
    try {
      const response = await fetch('/api/claude/status', { signal: AbortSignal.timeout(12000) });
      if (!response.ok) throw new Error('Server not ready');
      info = await response.json();
    } catch (e) {
      throw new Error('Start the Claude bridge with python3 webapp/local_server.py, then open http://localhost:8765. A plain file or static server cannot launch Claude Code.');
    }
    if (info.service !== 'ffda-claude') throw new Error('This server does not provide Claude Code. Run python3 webapp/local_server.py.');
    return info;
  }

  async function detectLocalClaude() {
    if (!['localhost', '127.0.0.1'].includes(location.hostname)) return;
    try {
      const info = await localClaudeStatus();
      $('claude-status').textContent = info.ready
        ? 'Sonnet is ready through your Claude Code login. Uses your Claude plan limits.'
        : info.error;
      if (settings.useClaudeCode == null && !settings.apiKey && !settings.useOllama) {
        settings.useClaudeCode = true;
        store.save('settings', settings);
      }
      if (settings.useClaudeCode) {
        $('ai-status').textContent = info.ready ? 'Claude Sonnet ready' : 'Claude Code needs login';
      }
    } catch (e) { $('claude-status').textContent = e.message; }
  }
  // Run after the synchronous UI initialization has completed.
  setTimeout(detectLocalClaude, 0);

  function llmConfigured() {
    if (settings.useClaudeCode) return true;
    return settings.useOllama
      ? Boolean(settings.ollamaEndpoint && settings.ollamaModel)
      : Boolean(settings.apiKey);
  }

  async function streamClaudeCode(messages, onChunk) {
    const info = await localClaudeStatus();
    if (!info.ready) throw new Error(info.error);
    const response = await fetch('/api/claude/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-FFDA-Token': info.token },
      body: JSON.stringify({ messages }),
      signal: AbortSignal.timeout(165000),
    });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({}));
      throw new Error(problem.error || `Claude bridge HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) throw new Error('Claude connection ended before the answer completed. Try again.');
        buffer += decoder.decode(value, { stream: true });
        let newline;
        while ((newline = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, newline).trim();
          buffer = buffer.slice(newline + 1);
          if (!line) continue;
          const event = JSON.parse(line);
          if (event.error) throw new Error(event.error);
          if (event.model) $('ai-status').textContent = `Asking ${event.model}…`;
          if (event.text) onChunk(event.text);
          if (event.done) return;
        }
      }
    } finally { await reader.cancel().catch(() => {}); }
  }

  async function streamOpenAI(messages, onChunk) {
    const models = [];
    if (settings.model.trim()) models.push(settings.model.trim());
    for (const m of OPENAI_FALLBACK_MODELS) if (!models.includes(m)) models.push(m);

    let lastErr = null;
    let gotResponse = false;
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
        gotResponse = true;
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
    // An invalid API key is rejected at OpenAI's edge with a response that
    // carries no CORS headers, so the browser surfaces it as a generic
    // "Failed to fetch" rather than a 401. Never reaching *any* response while
    // a key is set almost always means the key is wrong.
    if (!gotResponse && settings.apiKey) {
      throw new Error(
        'Could not reach the OpenAI API. This is usually a bad API key — an ' +
        'invalid key fails as a network error in the browser, not a 401. ' +
        'Check the key in Settings (⚙). Original error: ' +
        String(lastErr && lastErr.message || lastErr));
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
    activateTab('ai'); // the answer (or the how-to-configure card) lands here
    if (!llmConfigured()) {
      $('ai-output').innerHTML = renderMarkdown(
        '## LLM not configured\n\n' +
        'Open Settings (⚙) and either:\n\n' +
        '- paste an **OpenAI API key**, or\n' +
        '- enable **Claude Code (Sonnet)** on the local dashboard, or\n' +
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
    $('ai-status').textContent = settings.useClaudeCode ? 'Asking Claude Sonnet…'
      : settings.useOllama ? 'Asking Ollama…' : 'Asking OpenAI…';
    $('ai-output').innerHTML = '';

    try {
      const picked = pickedSet();
      const available = boardPlayers().filter(p => !picked.has(p.name));
      const top = available.slice(0, 15);

      let allNotes = '';
      for (const p of top) {
        const note = noteFor(p);
        allNotes += `---start ${p.name}---\nCurrent board rank: ${p.rank}; position: ${p.pos}; ` +
          `ESPN rank: ${p.espn || 'unknown'}; Sleeper rank: ${p.sleeper || 'unknown'}.\n` +
          `${note || 'No research note available.'}\n---end ${p.name}---\n\n`;
      }

      const pickedNames = [...picked];
      const pickedStr = pickedNames.length ? `[${pickedNames.join(', ')}]` : '[No players picked yet]';

      const groups = groupByPosition(teamPlayers());
      const teamStr = groups.length
        ? groups.map(g => `=== ${g.pos} ===\n` + g.players.map(p => p.name).join('\n')).join('\n')
        : '[No players on your team yet]';

      const prompt = buildUserPrompt(pickNumber() + 1, pickedStr, teamStr, settings.userPrompt, allNotes, {
        scoring: settings.scoringFormat, numTeams: settings.numTeams,
        slot: effectiveSlot(), nextPick: yourNextPick()?.next,
        lineup: '1 QB, 2 RB, 2 WR, 1 TE, 1 RB/WR FLEX, 1 K, 1 DST. Override with explicit custom league instructions.',
      });
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

      if (settings.useClaudeCode) await streamClaudeCode(messages, onChunk);
      else if (settings.useOllama) await streamOllama(messages, onChunk);
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

  /* ---------- file import / export ---------- */
  function download(filename, text, mime) {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function importRankingsFile(file) {
    file.text().then((text) => {
      const entries = parseRankingsText(text);
      if (!entries.length) { alert('No player rows found in that file.'); return; }
      const players = allPlayers();
      const overrides = {};
      const unmatched = [];
      for (const e of entries) {
        const match = fuzzyMatchPlayer(e.name, players);
        if (match) overrides[cleanName(match)] = e.rank;
        else unmatched.push(e.name);
      }
      if (!Object.keys(overrides).length) {
        alert('None of those names matched players on the board — nothing was imported.');
        return;
      }
      const fmt = settings.scoringFormat;
      rankOverrides[fmt] = overrides;
      savePrep('rankOverrides', rankOverrides);
      renderAll();
      setStatus(`Imported ${Object.keys(overrides).length} custom ranks for the ${fmt} board`);
      if (unmatched.length) {
        alert(`Applied ${Object.keys(overrides).length} ranks to the ${fmt} board.\n\n` +
          `${unmatched.length} name(s) didn't match anyone on the board and were skipped:\n- ` +
          unmatched.join('\n- '));
      }
    });
  }

  function importBackupFile(file) {
    file.text().then((text) => {
      let b;
      try { b = JSON.parse(text); } catch (e) { alert('Not a valid backup file (bad JSON).'); return; }
      if (!b || b.app !== 'ff-draft-tool') { alert('Not a draft-prep backup file.'); return; }
      if (!confirm('Replace your prep (markers, picks, team, rank overrides, note edits, prompts) ' +
        "with this file's data? Your API key is kept as-is.")) return;
      settings = Object.assign({}, DEFAULT_SETTINGS, b.settings || {}, { apiKey: settings.apiKey });
      manualPicked = new Set(b.manualPicked || []);
      manualTeam = Array.isArray(b.manualTeam) ? b.manualTeam : [];
      toDraft = b.toDraft || {};
      unpicked = new Set(b.unpicked || []);
      rankOverrides = b.rankOverrides || {};
      noteOverrides = b.noteOverrides || {};
      store.save('settings', settings);
      store.save('manualPicked', [...manualPicked]);
      store.save('manualTeam', manualTeam);
      store.save('toDraft', toDraft);
      store.save('unpicked', [...unpicked]);
      store.save('rankOverrides', rankOverrides);
      store.save('noteOverrides', noteOverrides);
      mirrorPrep();
      $('scoring-format').value = settings.scoringFormat;
      $('settings-dialog').close();
      renderAll();
      setStatus('Prep imported from backup');
    });
  }

  function exportBackup() {
    const backup = {
      app: 'ff-draft-tool',
      version: 1,
      exportedAt: new Date().toISOString(),
      settings: Object.assign({}, settings, { apiKey: '' }), // never export the secret
      manualPicked: [...manualPicked],
      manualTeam,
      toDraft,
      unpicked: [...unpicked],
      rankOverrides,
      noteOverrides,
    };
    download('draft-prep-backup.json', JSON.stringify(backup, null, 2), 'application/json');
    setStatus('Prep exported (API key not included)');
  }

  /* ---------- settings dialog ---------- */
  let settingsTab = 'ai';
  function applySettingsTab() {
    document.querySelectorAll('#settings-tabs .stab').forEach(b =>
      b.classList.toggle('active', b.dataset.stab === settingsTab));
    document.querySelectorAll('#settings-form fieldset').forEach(fs =>
      fs.hidden = settingsTab !== 'all' && fs.dataset.stab !== settingsTab);
  }
  document.querySelectorAll('#settings-tabs .stab').forEach(b =>
    b.addEventListener('click', () => { settingsTab = b.dataset.stab; applySettingsTab(); }));

  // Save is greyed out until a field actually differs from what's stored —
  // compared against a snapshot taken when the dialog opens, so changing a
  // value and changing it back re-disables it.
  function settingsFormValues() {
    return JSON.stringify({
      apiKey: $('set-apikey').value,
      model: $('set-model').value,
      useOllama: $('set-use-ollama').checked,
      useClaudeCode: $('set-use-claude').checked,
      ollamaEndpoint: $('set-ollama-endpoint').value,
      ollamaModel: $('set-ollama-model').value,
      systemPrompt: $('set-system-prompt').value,
      userPrompt: $('set-user-prompt').value,
      manualMode: $('set-manual-mode').checked,
      rankSource: $('set-rank-source').value,
    });
  }
  let settingsSnapshot = '';
  function updateSaveEnabled() {
    const dirty = settingsFormValues() !== settingsSnapshot;
    const btn = $('btn-save-settings');
    btn.disabled = !dirty;
    btn.title = dirty ? 'Save your changes' : 'Nothing changed yet';
  }
  $('settings-form').addEventListener('input', updateSaveEnabled);
  $('settings-form').addEventListener('change', updateSaveEnabled);

  function openSettings() {
    $('set-apikey').value = settings.apiKey;
    $('set-model').value = settings.model;
    $('set-use-ollama').checked = settings.useOllama;
    $('set-use-claude').checked = Boolean(settings.useClaudeCode);
    $('set-ollama-endpoint').value = settings.ollamaEndpoint;
    $('set-ollama-model').value = settings.ollamaModel;
    $('set-system-prompt').value = settings.systemPrompt;
    $('set-user-prompt').value = settings.userPrompt;
    $('set-manual-mode').checked = settings.manualMode;
    $('set-rank-source').value = settings.rankSource;
    applySettingsTab();
    settingsSnapshot = settingsFormValues();
    updateSaveEnabled();
    $('settings-dialog').showModal();
  }

  function saveSettings() {
    settings.apiKey = $('set-apikey').value.trim();
    settings.model = $('set-model').value.trim();
    settings.useOllama = $('set-use-ollama').checked;
    settings.useClaudeCode = $('set-use-claude').checked;
    settings.ollamaEndpoint = $('set-ollama-endpoint').value.trim() || DEFAULT_SETTINGS.ollamaEndpoint;
    settings.ollamaModel = $('set-ollama-model').value.trim();
    settings.systemPrompt = $('set-system-prompt').value;
    settings.userPrompt = $('set-user-prompt').value;
    settings.manualMode = $('set-manual-mode').checked;
    settings.rankSource = $('set-rank-source').value;
    store.save('settings', settings);
    setStatus('Settings saved (this browser only)');
    renderAll();
  }

  function resetDraftState() {
    if (!confirm('Clear all draft state (picked players, your team, your ratings, extension data)?')) return;
    manualPicked = new Set();
    manualTeam = [];
    toDraft = {};
    extState = {};
    extPickedRaw = [];
    unpicked = new Set();
    predicted = null;
    predictedMeta = null;
    predictMode = false;
    store.save('predictMode', false);
    store.save('manualPicked', []);
    store.save('manualTeam', []);
    store.save('toDraft', {});
    mirrorPrep();
    store.save('extState', {});
    store.save('extPickedRaw', []);
    store.save('unpicked', []);
    window.postMessage({ source: 'ffda-page', type: 'clear-state' }, '*');
    setStatus('Draft state cleared');
    renderAll();
  }

  /* ---------- guided tour ---------- */
  const TOUR_STEPS = [
    { target: '#player-table', title: 'The board',
      text: 'Every draftable player, best available on top. As the draft goes on, picked players drop off so this is always "who can I still get". A pink line shows where your next pick lands.' },
    { target: '#pos-filters', title: 'Position filters',
      text: 'Show only one position — handy when you know you need an RB and want to compare who\'s left.' },
    { target: '#search-box', title: 'Search',
      text: 'Type a few letters of a name or team. The board narrows as you type — fastest way to find someone mid-draft. Press / to jump here.' },
    { target: '#player-tbody tr', title: 'Player notes',
      text: 'Click any row to open that player\'s full analysis note in a tab on the right — Ctrl+click opens it in an extra tab (like Obsidian). Press E to edit the note and make it yours.' },
    { target: '#player-tbody tr .row-actions', title: 'Rate the players',
      text: 'Click the Rating button and pick what you think of him — ✅ really good, ✔ good, ○ no opinion, ✘ bad, ❌ really bad. The picker shows the number key for each one, so once you know them you can just press 1 to 5 on the selected row and fly down the list. Your rating shows next to the player\'s name, so on draft day you can scan the board instead of reading it. It is a note to yourself, nothing more. Manual Picked/+Team buttons are hidden by default — the extension tracks the draft for you. Turn on Manual mode in Settings to run a draft by hand.' },
    { target: '#tab-bar', title: 'Tabs',
      text: 'AI Output and Draft Board live here permanently; player notes open as tabs next to them. A normal click on a player replaces the current note tab, Ctrl+click adds another, × (or the X key) closes one.' },
    { target: '#tab-strip .tab:nth-child(2)', title: 'The draft board',
      text: 'A snake-draft grid: every pick colored by position, your next pick pink. Team headers count what each team has drafted by position — read across a row to spot a run forming; a red 0 means they are badly short there. Hover a header for what they still need. "Who should I take?" simulates every pick between now and your turn (no AI), then names the position where waiting costs the most projected points; it keeps re-simulating as real picks land, and "Return to live" clears it.' },
    { target: '#btn-ask', title: 'Ask AI',
      text: 'Sends the draft state — pick number, who\'s gone, your roster, and the notes of the top 15 available — to the AI and streams back advice. Press Q anytime.' },
    { target: '#team-panel .panel-head', title: 'Your team',
      text: 'Your roster as a depth chart — QB1, RB1, RB2 … — with a "still need" line for unfilled starting spots. Click a player to open their note; the » button collapses the panel.' },
    { target: '#ext-status', title: 'Live draft sync',
      text: 'With the Chrome extension installed, picks flow in automatically from the ESPN or Sleeper draft room — this badge turns green when connected. The board even shows the rank column for whichever site you\'re drafting on.' },
    { target: '#btn-help', title: 'Help',
      text: 'Press ? anytime for the keyboard shortcuts, what every column means, and this tour again.' },
    { target: '#btn-settings', title: 'Settings',
      text: 'API key for the AI, Manual mode, the site-rank column, import/export your own rankings as a spreadsheet (CSV), and backing up all your prep to a file.' },
  ];

  function tourActive() { return tourIndex >= 0; }

  function startTour() {
    tourIndex = 0;
    $('tour-overlay').hidden = false;
    showTourStep();
  }

  function endTour() {
    tourIndex = -1;
    $('tour-overlay').hidden = true;
  }

  function showTourStep() {
    // Skip steps whose target isn't on the page right now.
    while (tourIndex < TOUR_STEPS.length && !document.querySelector(TOUR_STEPS[tourIndex].target)) {
      tourIndex++;
    }
    if (tourIndex >= TOUR_STEPS.length) { endTour(); return; }
    const step = TOUR_STEPS[tourIndex];
    const el = document.querySelector(step.target);
    el.scrollIntoView({ block: 'nearest' });

    const r = el.getBoundingClientRect();
    const pad = 5;
    const hl = $('tour-highlight');
    hl.style.top = (r.top - pad) + 'px';
    hl.style.left = (r.left - pad) + 'px';
    hl.style.width = (r.width + pad * 2) + 'px';
    hl.style.height = (r.height + pad * 2) + 'px';

    $('tour-title').textContent = step.title;
    $('tour-text').textContent = step.text;
    $('tour-step-count').textContent = `${tourIndex + 1} / ${TOUR_STEPS.length}`;
    $('tour-next').textContent = tourIndex === TOUR_STEPS.length - 1 ? 'Done' : 'Next';

    // Position the tip after its content has resized it: below the target if
    // there's room, above otherwise, clamped to the viewport.
    const tip = $('tour-tip');
    tip.style.visibility = 'hidden';
    requestAnimationFrame(() => {
      const th = tip.offsetHeight;
      const tw = tip.offsetWidth;
      let top = r.bottom + pad + 8;
      if (top + th > window.innerHeight - 8) top = r.top - th - pad - 8;
      if (top < 8) top = 8;
      const left = Math.min(Math.max(r.left, 8), Math.max(window.innerWidth - tw - 8, 8));
      tip.style.top = top + 'px';
      tip.style.left = left + 'px';
      tip.style.visibility = 'visible';
    });
  }

  $('tour-next').addEventListener('click', () => { tourIndex++; showTourStep(); });
  $('tour-skip').addEventListener('click', endTour);
  $('tour-close').addEventListener('click', endTour);
  window.addEventListener('resize', () => { if (tourActive()) showTourStep(); });

  // Board text tracks the panel width — window resize and divider drags both
  // land here, so no re-render is needed to keep the cells legible.
  if (window.ResizeObserver) new ResizeObserver(sizeBoardFont).observe($('board-grid-wrap'));

  /* ---------- help dialog (? opens it; the tour starts from inside) ---------- */
  function openHelp() { $('help-dialog').showModal(); }
  $('btn-help').addEventListener('click', openHelp);
  $('btn-start-tour').addEventListener('click', () => {
    $('help-dialog').close();
    startTour();
  });

  /* ---------- wire up ---------- */
  $('scoring-format').value = settings.scoringFormat;
  $('scoring-format').addEventListener('change', (e) => {
    settings.scoringFormat = e.target.value;
    store.save('settings', settings);
    renderAll();
  });
  $('search-box').addEventListener('input', (e) => { searchText = e.target.value; renderTable(); });
  $('show-picked').addEventListener('change', (e) => { showPicked = e.target.checked; renderTable(); });
  $('show-model-marks').checked = showModelMarks;
  $('show-model-marks').addEventListener('change', (e) => {
    showModelMarks = e.target.checked;
    store.save('showModelMarks', showModelMarks);
    renderTable();
    renderRoundGuide();
    renderTabs();
  });
  $('guide-body').innerHTML = GUIDE.map(g =>
    `<h3>Rounds ${g.lo}–${g.hi}</h3><p>${g.text} ${guideLinks(g)}</p>`
  ).join('') +
    '<h3>Bench, all rounds</h3><p>Don\'t tilt the bench toward RBs on ' +
    'purpose — it bought ~1% of championships. A backup QB or TE is ' +
    'optional; the waiver wire patches QB and K in-season. ' +
    guideLinks({ links: [['19-bench-composition', 'bench'],
      ['20-second-qb-te', 'backups'],
      ['22-waiver-wire-reality', 'the wire']] }) + '</p>';
  $('btn-round-guide').addEventListener('click',
    () => $('guide-dialog').showModal());
  const setSort = (s) => { sortBy = s; renderTable(); };
  $('th-rank').addEventListener('click', () => setSort('board'));
  $('th-espn').addEventListener('click', () => setSort('espn'));
  $('th-sleeper').addEventListener('click', () => setSort('sleeper'));
  $('btn-ask').addEventListener('click', askLLM);
  $('btn-settings').addEventListener('click', openSettings);
  $('settings-form').addEventListener('submit', saveSettings);
  $('btn-reset-prompts').addEventListener('click', () => {
    $('set-system-prompt').value = DEFAULT_SETTINGS.systemPrompt;
    $('set-user-prompt').value = DEFAULT_SETTINGS.userPrompt;
    updateSaveEnabled(); // programmatic .value changes fire no input event
  });
  $('btn-reset-draft').addEventListener('click', resetDraftState);
  $('btn-reset-top').addEventListener('click', resetDraftState);
  document.querySelectorAll('.dialog-close').forEach(btn => {
    btn.addEventListener('click', () => $(btn.dataset.close).close());
  });

  /* ---------- note editing ---------- */
  function startNoteEdit() {
    // Editing a different note than the one mid-edit? Settle that draft first.
    if (noteEditingName && noteEditingName !== activeTab && !confirmDiscardEdit(noteEditingName)) return;
    const p = playerByName(activeTab);
    if (!p) return;
    noteEditingName = p.name;
    $('note-textarea').value = noteFor(p);
    renderNotePane();
    $('note-textarea').focus();
  }
  $('btn-edit-note').addEventListener('click', startNoteEdit);
  function cancelNoteEdit() {
    // Asks before discarding a changed draft; no-op prompt when unchanged.
    if (!confirmDiscardEdit(noteEditingName)) return;
    renderNotePane();
  }
  $('btn-cancel-note').addEventListener('click', cancelNoteEdit);
  $('btn-save-note').addEventListener('click', () => {
    const p = playerByName(noteEditingName);
    if (!p) return;
    const key = cleanName(p.name);
    const text = $('note-textarea').value;
    // Saving the bundled text unchanged just clears the override.
    if (text === bundledNoteFor(p)) delete noteOverrides[key];
    else noteOverrides[key] = text;
    savePrep('noteOverrides', noteOverrides);
    noteEditingName = null;
    renderAll();
    setStatus(`Note for ${p.name} saved (this browser only)`);
  });
  $('btn-revert-note').addEventListener('click', () => {
    const p = playerByName(activeTab);
    if (!p) return;
    if (!confirm(`Discard your edits to ${p.name}'s note and restore the bundled one?`)) return;
    delete noteOverrides[cleanName(p.name)];
    savePrep('noteOverrides', noteOverrides);
    noteEditingName = null;
    renderAll();
  });

  /* ---------- resizable panel split ---------- */
  let leftPct = store.load('leftPct', null); // null = default flex ratio

  function applySplit() {
    $('left-panel').style.flex = leftPct === null ? '' : `0 0 ${leftPct}%`;
  }
  $('panel-divider').addEventListener('mousedown', (e) => {
    e.preventDefault();
    document.body.classList.add('dragging');
    const main = document.querySelector('main');
    const onMove = (ev) => {
      const r = main.getBoundingClientRect();
      leftPct = Math.min(80, Math.max(25, ((ev.clientX - r.left) / r.width) * 100));
      applySplit();
    };
    const onUp = () => {
      document.body.classList.remove('dragging');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      store.save('leftPct', leftPct);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
  $('panel-divider').addEventListener('dblclick', () => {
    leftPct = null;
    store.remove('leftPct');
    applySplit();
  });

  /* ---------- phone layout: one pane at a time ---------- */
  // The divider above is a mouse affordance for a two-pane screen. A phone
  // has neither, so below the breakpoint the panes become four views and the
  // bar at the bottom switches between them. The breakpoint here must match
  // the one in style.css — the CSS hides the panes, this only picks which.
  const phoneQuery = window.matchMedia('(max-width: 620px)');
  function onPhone() { return phoneQuery.matches; }

  // Purely presentational: the CSS keys off the body attribute. It never
  // calls activateTab, so activateTab can call it without looping.
  function showMobileView(v) {
    document.body.dataset.mview = v;
    for (const b of document.querySelectorAll('#mobile-nav button')) {
      b.classList.toggle('active', b.dataset.mview === v);
    }
    // The board sizes its text off a width it can only measure once its pane
    // is actually on screen, so re-measure after the layout settles.
    if (v === 'board') requestAnimationFrame(sizeBoardFont);
  }

  for (const btn of document.querySelectorAll('#mobile-nav button')) {
    btn.addEventListener('click', () => {
      const v = btn.dataset.mview;
      // Board and Note are the same pane showing different tabs, so those two
      // go through activateTab (which calls showMobileView back).
      if (v === 'board' && activeTab !== 'board') activateTab('board');
      else if (v === 'note' && activeTab === 'board') activateTab(lastNoteTab || 'ai');
      else showMobileView(v);
    });
  }
  showMobileView('players');
  // Rotating a phone into landscape crosses the breakpoint: the two-pane CSS
  // takes over and the stale attribute stops mattering, but coming back has
  // to land on a view whose pane matches the tab that's actually active.
  phoneQuery.addEventListener('change', (e) => {
    if (e.matches && document.body.dataset.mview !== 'players') {
      showMobileView(activeTab === 'board' ? 'board' : 'note');
    }
  });

  /* ---------- Your Team collapse ---------- */
  function applyTeamCollapsed() {
    $('team-panel').classList.toggle('collapsed', teamCollapsed);
    $('btn-team-collapse').title = teamCollapsed ? 'Expand Your Team' : 'Collapse Your Team';
  }
  $('btn-team-collapse').addEventListener('click', () => {
    teamCollapsed = !teamCollapsed;
    store.save('teamCollapsed', teamCollapsed);
    applyTeamCollapsed();
  });

  /* ---------- draft board toolbar ---------- */
  // League-shape or slot changes redefine the simulated window — in predict
  // mode, re-simulate under the new shape instead of going stale.
  $('board-teams').addEventListener('change', (e) => {
    settings.numTeams = parseInt(e.target.value, 10) || 12;
    if (settings.draftSlot > settings.numTeams) settings.draftSlot = 0;
    store.save('settings', settings);
    if (predictMode) computePrediction();
    renderBoard();
    renderTable();
  });
  $('board-slot').addEventListener('change', (e) => {
    settings.draftSlot = parseInt(e.target.value, 10) || 0;
    store.save('settings', settings);
    if (predictMode) computePrediction();
    renderBoard();
    renderTable();
  });
  $('board-rounds').addEventListener('change', (e) => {
    const v = parseInt(e.target.value, 10);
    settings.numRounds = v >= 8 && v <= 30 ? v : DEFAULT_SETTINGS.numRounds;
    store.save('settings', settings);
    if (predictMode) computePrediction();
    renderBoard();
    renderTable();
  });
  $('board-bot-ranks').addEventListener('change', (e) => {
    settings.botRanks = e.target.value;
    store.save('settings', settings);
    if (predictMode) computePrediction();
    renderBoard();
    renderTable();
  });
  $('board-bot-algo').addEventListener('change', (e) => {
    settings.botAlgo = e.target.value;
    store.save('settings', settings);
    if (predictMode) computePrediction();
    renderBoard();
    renderTable();
  });
  // Gear popover: click to open, click anywhere else (or Escape) to dismiss.
  // Kept out of the Debug tab because it explains the predictions, not the
  // internals — you reach for it the moment a prediction looks wrong.
  $('btn-bot-config').addEventListener('click', (e) => {
    e.stopPropagation();
    const box = $('bot-config');
    box.hidden = !box.hidden;
    $('btn-bot-config').setAttribute('aria-expanded', String(!box.hidden));
  });
  $('bot-config').addEventListener('click', (e) => e.stopPropagation());
  document.addEventListener('click', () => {
    if ($('bot-config') && !$('bot-config').hidden) {
      $('bot-config').hidden = true;
      $('btn-bot-config').setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && $('bot-config') && !$('bot-config').hidden) {
      $('bot-config').hidden = true;
      $('btn-bot-config').setAttribute('aria-expanded', 'false');
    }
  });
  $('btn-predict').addEventListener('click', runPrediction);
  $('btn-clear-predict').addEventListener('click', () => {
    predictMode = false;
    store.save('predictMode', false);
    predicted = null;
    predictedMeta = null;
    setStatus('Back to live only — simulated picks removed (real picks always show as they happen)');
    renderTable();
    renderBoard();
  });

  /* ---------- rankings & data import/export ---------- */
  $('btn-import-rankings').addEventListener('click', () => $('file-rankings').click());
  $('file-rankings').addEventListener('change', (e) => {
    const f = e.target.files[0];
    e.target.value = '';
    if (f) importRankingsFile(f);
  });
  $('btn-export-rankings').addEventListener('click', () => {
    download(`rankings-${settings.scoringFormat.replace('.', '_')}.csv`,
      buildRankingsCsv(boardPlayers()), 'text/csv');
    setStatus('Rankings downloaded — reorder in a spreadsheet, then Import to apply');
  });
  $('btn-revert-rankings').addEventListener('click', () => {
    const fmt = settings.scoringFormat;
    if (!Object.keys(currentRankOverrides()).length) {
      setStatus(`No custom ranks on the ${fmt} board`);
      return;
    }
    if (!confirm(`Remove your custom ranks from the ${fmt} board and restore the bundled order?`)) return;
    delete rankOverrides[fmt];
    savePrep('rankOverrides', rankOverrides);
    renderAll();
    setStatus(`${fmt} board restored to bundled rankings`);
  });
  $('btn-export-backup').addEventListener('click', exportBackup);
  $('btn-import-backup').addEventListener('click', () => $('file-backup').click());
  $('file-backup').addEventListener('change', (e) => {
    const f = e.target.files[0];
    e.target.value = '';
    if (f) importBackupFile(f);
  });
  $('btn-export-notes').addEventListener('click', () => {
    const names = Object.keys(noteOverrides).sort();
    if (!names.length) { setStatus('No edited notes to download'); return; }
    const parts = names.map(n => `----- ${n}.md -----\n\n${noteOverrides[n]}\n`);
    download('edited-notes.md', parts.join('\n'), 'text/markdown');
    setStatus(`${names.length} edited note(s) downloaded`);
  });

  document.addEventListener('keydown', (e) => {
    if (tourActive()) {
      if (e.key === 'Escape') endTour();
      return;
    }
    const tag = (e.target.tagName || '').toLowerCase();
    // Esc inside the note editor cancels the edit (E started it).
    if (e.key === 'Escape' && noteEditingName && e.target.id === 'note-textarea') {
      e.preventDefault();
      cancelNoteEdit();
      return;
    }
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    // A just-clicked button keeps focus; Space/Enter must activate IT (the
    // browser default), not also fire a shortcut on the selected row.
    if (tag === 'button' && (e.key === ' ' || e.key === 'Enter')) return;
    if (document.querySelector('dialog[open]')) return;
    // An open rating picker owns the arrows and Esc — otherwise ↑/↓ would
    // move the board selection out from under the menu. Enter/Space fall
    // through to the focused option, and 1-5 to the switch below.
    if (ratingMenuFor && (e.key === 'Escape' || e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault();
      if (e.key === 'Escape') { closeRatingMenu(); return; }
      const opts = [...$('rating-menu').querySelectorAll('.rating-opt')];
      const i = opts.indexOf(document.activeElement);
      opts[((i < 0 ? 0 : i) + (e.key === 'ArrowDown' ? 1 : -1) + opts.length)
        % opts.length].focus();
      return;
    }
    const sel = selectedPlayer();
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      if (sel) { e.preventDefault(); openNote(sel, true); }
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    switch (e.key) {
      case 'q': case 'Q':
        e.preventDefault(); askLLM(); break;
      case 'r': case 'R':
        e.preventDefault(); renderAll(); setStatus('Refreshed ' + new Date().toLocaleTimeString()); break;
      case 'ArrowDown':
        e.preventDefault(); moveSelection(1); break;
      case 'ArrowUp':
        e.preventDefault(); moveSelection(-1); break;
      case '1': case '2': case '3': case '4': case '5': {
        // Straight to the step you mean — the fast path once you know the
        // numbers, which is what the picker spends its right-hand column
        // teaching. Works whether or not the picker is open.
        const step = MARK_SCALE.find(s => s.key === e.key);
        const on = ratingMenuFor || (sel && sel.name);
        if (step && on) { e.preventDefault(); setMark(on, step.v); }
        break;
      }
      case 'd': case 'D': case ' ':
        // Same key as before, now opening the picker instead of nudging
        // the rating one step — the scale is too long to walk.
        if (sel) {
          e.preventDefault();
          // Selected row, found by data — player names carry apostrophes,
          // which an attribute selector would need escaping for.
          const row = document.querySelector('#player-tbody tr.selected');
          const btn = row && row.querySelector('.act-mark');
          if (ratingMenuFor === sel.name) closeRatingMenu();
          else if (btn) openRatingMenu(sel.name, btn);
        }
        break;
      case 'p': case 'P':
        if (sel) { e.preventDefault(); keepSelectionNear(() => togglePicked(sel.name)); }
        break;
      case 't': case 'T':
        if (sel) { e.preventDefault(); toggleTeam(sel.name); }
        break;
      case 'Enter':
        if (sel) { e.preventDefault(); openNote(sel, false); }
        break;
      case 'e': case 'E':
        // Open the selected player's note and jump straight into editing.
        if (sel) {
          e.preventDefault();
          openNote(sel, false);
          if (activeTab === sel.name) startNoteEdit();
        }
        break;
      case 'a': case 'A':
        e.preventDefault(); activateTab('ai'); break;
      case 'b': case 'B':
        e.preventDefault(); activateTab('board'); break;
      case 'x': case 'X':
        // Same as clicking the tab's × — Esc still works too.
        if (isNoteTab(activeTab)) { e.preventDefault(); closeNote(activeTab); }
        break;
      case '/':
        e.preventDefault(); $('search-box').focus(); break;
      case '?':
        e.preventDefault(); openHelp(); break;
      case 'Escape':
        if (isNoteTab(activeTab)) { e.preventDefault(); closeNote(activeTab); }
        break;
    }
  });

  $('help-data-stamp').textContent =
    `Bundle built ${DATA.generatedAt}. Rankings fetched ${DATA.rankSources?.fetched_at || 'at an unknown date'}. Refresh rankings with engine/update_ranks.py, then rebuild with webapp/build_data.py.`;
  applySplit();
  applyTeamCollapsed();
  renderAll();
  setStatus('Ready — listening for draft updates');
}
