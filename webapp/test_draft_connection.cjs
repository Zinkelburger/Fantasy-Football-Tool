// Synthetic ESPN/extension fixtures; these cannot verify ESPN's current live DOM.
// Run: node --test webapp/test_draft_connection.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { buildUserPrompt } = require('./app.js');
const extension = path.join(__dirname, '../chrome-extension');

test('draft request carries season, league and evidence limitations', () => {
  const prompt = buildUserPrompt(1, 'none', 'none', 'Be brief', 'notes', {
    date: '2026-09-06', season: 2026, scoring: 'PPR', numTeams: 12,
    slot: 4, nextPick: 4, lineup: '1 QB',
  });
  for (const text of ['pick 1', '2026 fantasy', 'PPR', 'League size: 12',
    'next overall pick: 4', 'notes', 'not verified current facts']) {
    assert.ok(prompt.includes(text), text);
  }
  assert.ok(!prompt.includes('2025 fantasy'));
});

test('ESPN scraper sends picks and only the scoped personal roster', () => {
  const sent = [];
  let personalPanelPresent = true;
  const context = vm.createContext({
    document: {
      body: {},
      querySelectorAll: selector => {
        if (selector === '.draft-board-grid-pick-cell.myTeam') return [];
        assert.equal(selector, '.pick__message-information .playerinfo__playername');
        return [{ textContent: ' Jahmyr Gibbs ' }, { textContent: 'Bijan Robinson'}];
      },
      querySelector: selector => personalPanelPresent && selector === '.draft-columns__col--myteam'
        ? { querySelectorAll: () => [{ title: 'Bijan Robinson' }] } : null,
    },
    console: { log() {}, warn() {} }, setTimeout, clearTimeout,
    MutationObserver: class { observe() {} },
    sendDataToServer: data => sent.push(JSON.parse(JSON.stringify(data))),
  });
  vm.runInContext(fs.readFileSync(path.join(extension, 'espn-draft.js'), 'utf8'), context);
  assert.deepEqual(sent, [
    { site: 'espn', type: 'picked_players', players: ['Jahmyr Gibbs', 'Bijan Robinson'] },
    { site: 'espn', type: 'roster_players', players: ['Bijan Robinson'] },
  ]);
  personalPanelPresent = false;
  sent.length = 0;
  vm.runInContext('extractEspnRosterPlayers()', context);
  assert.equal(sent.length, 0, 'Do not mistake other teams for the personal roster');
});

function runEspnBoard({ cells = [], legacyNames = null } = {}) {
  const sent = [];
  const context = vm.createContext({
    document: {
      body: {},
      querySelectorAll: selector => {
        if (selector === '.draft-board-grid-pick-cell.myTeam') return cells;
        if (selector === '.pick__message-information .playerinfo__playername') return [];
        throw new Error(`Unexpected selector ${selector}`);
      },
      querySelector: selector => {
        // Reproduce the old bug: the broad selector hits a team header first.
        if (selector === '[class*="myTeam"]') return { querySelectorAll: () => [] };
        if (selector === '.draft-columns__col--myteam' && legacyNames) {
          return { querySelectorAll: () => legacyNames.map(title => ({ title })) };
        }
        return null;
      },
    },
    console: { log() {}, warn() {} }, setTimeout, clearTimeout,
    MutationObserver: class { observe() {} },
    sendDataToServer: data => sent.push(JSON.parse(JSON.stringify(data))),
  });
  vm.runInContext(fs.readFileSync(path.join(extension, 'espn-draft.js'), 'utf8'), context);
  return sent;
}

function pickCell(first, last, completed = true) {
  return {
    classList: { contains: cls => completed && cls === 'completedPick' },
    querySelector: selector => {
      const value = selector === '.playerFirstName' ? first : last;
      return value ? { textContent: value } : null;
    },
  };
}

test('current ESPN myTeam pick cells yield the four picks from the reported room', () => {
  const sent = runEspnBoard({ cells: [
    pickCell('Derrick', 'Henry'), pickCell('Saquon', 'Barkley'),
    pickCell('Kyren', 'Williams'), pickCell('Josh', 'Allen'),
    pickCell('', '', false),
  ], legacyNames: ['Some Other Player'] });
  assert.deepEqual(sent, [{ site: 'espn', type: 'roster_players',
    players: ['Derrick Henry', 'Saquon Barkley', 'Kyren Williams', 'Josh Allen'] }]);
});

test('confirmed empty draft board clears the previous roster', () => {
  assert.deepEqual(runEspnBoard({ cells: [pickCell('', '', false)] }),
    [{ site: 'espn', type: 'roster_players', players: [] }]);
});

test('a completed pick still rendering cannot publish a partial roster', () => {
  assert.deepEqual(runEspnBoard({ cells: [pickCell('Josh', 'Allen'), pickCell('', '')] }), []);
});

test('an unscoped team header or selectable roster is not treated as the personal roster', () => {
  assert.deepEqual(runEspnBoard(), []);
});

test('extension manifest connects ESPN and localhost without public hosting', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(extension, 'manifest.json')));
  const bridge = manifest.content_scripts.find(s => s.js.includes('bridge.js'));
  assert.ok(bridge.matches.includes('http://localhost/*'));
  assert.ok(bridge.matches.includes('http://127.0.0.1/*'));
  assert.ok(bridge.matches.includes('https://fantasy-football-tool.pages.dev/*'));
  assert.ok(manifest.content_scripts.some(s => s.js.includes('espn-draft.js')
    && s.matches.includes('https://fantasy.espn.com/football/draft*')));
});

const app = require('./app.js');

test('draft request fixes the answer shape: own ranking, upside labels, several positions', () => {
  const prompt = buildUserPrompt(30, '[a]', 'RB: RB1 X', 'Go young', 'notes', {
    nextPick: 31, followingPick: 42, waitCosts: 'RB: about 100 points',
    previous: '1. A (RB) 2. B (WR)', previousPick: 19, boardTail: '#40 C (WR1, DAL)',
  });
  for (const text of ['Upside play', 'Stable play', 'heading "Ranking"', 'at least three positions',
    'never list four of one position in a row', 'context, not a filter',
    'following pick after that: 42', '10 other teams pick in between',
    'previous answer, at pick 19', '1. A (RB) 2. B (WR)', 'RB: about 100 points',
    'Further down the board', '#40 C (WR1, DAL)', 'The user adds: Go young']) {
    assert.ok(prompt.includes(text), text);
  }
  assert.ok(prompt.indexOf('How to answer') < prompt.indexOf('Player Notes'));
});

test('the Ask AI slate spreads across positions instead of running down the board', () => {
  const mk = (pos, n) => Array.from({ length: n }, (_, i) => ({ name: `${pos}${i + 1}`, pos }));
  // A board where the next fifteen names are all quarterbacks and tight ends.
  const board = [...mk('QB', 8), ...mk('TE', 7), ...mk('RB', 10), ...mk('WR', 10), ...mk('K', 3)];
  const slate = app.pickCandidates(board, {});
  const count = pos => slate.filter(p => p.pos === pos).length;
  assert.equal(slate.length, app.AI_SLATE_SIZE);
  assert.deepEqual([count('QB'), count('TE'), count('RB'), count('WR'), count('K')], [3, 3, 6, 6, 0]);
  assert.deepEqual(slate.map(p => p.name).slice(0, 4), ['QB1', 'QB2', 'QB3', 'TE1'], 'board order kept');
  // Already starting a QB and a TE: one of each stays as a word of context,
  // the room goes to the positions the user can still start.
  const later = app.pickCandidates(board, { QB: 1, TE: 1 });
  const c2 = pos => later.filter(p => p.pos === pos).length;
  assert.deepEqual([c2('QB'), c2('TE'), c2('RB'), c2('WR')], [1, 1, 8, 8]);
  // A thin late board simply returns what is there, kickers excluded.
  assert.deepEqual(app.pickCandidates([...mk('RB', 2), ...mk('K', 2)], {}).map(p => p.name), ['RB1', 'RB2']);
});

test('the final Ranking list is carried from one answer to the next', () => {
  const answer = '## Walkthrough\n1. **A** (RB) — Upside play\n2. **B** (WR)\n\n' +
    'Some prose.\n\n## Ranking\n1. **Bijan Robinson** (RB) — Stable, clean workload\n' +
    '2. Puka Nacua (WR) — Balanced\n\n3) `Josh Allen` (QB) — Stable\n';
  assert.deepEqual(app.parseRanking(answer), [
    'Bijan Robinson (RB) — Stable, clean workload', 'Puka Nacua (WR) — Balanced', 'Josh Allen (QB) — Stable']);
  assert.deepEqual(app.parseRanking('no list here'), []);
  assert.deepEqual(app.parseRanking(''), []);
});

test('prompts saved by the old page upgrade to the new defaults; edited ones stay', () => {
  const d = app.DEFAULT_SETTINGS;
  const stale = app.upgradeLegacyPrompts({
    systemPrompt: 'You are a fantasy football expert. Give a summary of who to draft and why.',
    userPrompt: 'my own words',
  }, d);
  assert.equal(stale.systemPrompt, d.systemPrompt);
  assert.equal(stale.userPrompt, 'my own words');
  assert.ok(!d.userPrompt.includes('I NEED THE LIST'), 'the list demand now lives in the fixed contract');
});
