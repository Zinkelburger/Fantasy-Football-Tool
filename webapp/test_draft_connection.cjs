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
  assert.ok(manifest.content_scripts.some(s => s.js.includes('espn-draft.js')
    && s.matches.includes('https://fantasy.espn.com/football/draft*')));
});
