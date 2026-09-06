const { test, before, after, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');
const fs = require('node:fs');

let browser, server, context, page, errors;
const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8087';
before(async () => {
  if (!process.env.E2E_BASE_URL) {
    server = spawn('python3', ['-m', 'http.server', '8087', '--bind', '127.0.0.1', '--directory', 'public'], { stdio: 'ignore' });
    for (let i = 0; i < 50; i++) {
      try { if ((await fetch(base)).ok) break; } catch {}
      await new Promise(r => setTimeout(r, 100));
    }
  }
  browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || (!process.env.CI && fs.existsSync('/usr/bin/google-chrome') ? '/usr/bin/google-chrome' : undefined),
  });
});
after(async () => { await browser?.close(); server?.kill(); });
beforeEach(async () => {
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  page.setDefaultTimeout(5000);
  errors = [];
  page.on('pageerror', e => errors.push(e.message));
  // Static hosting deliberately has no Claude bridge. Keep tests deterministic.
  await page.route('**/api/claude/status', r => r.fulfill({ status: 404, body: '{}' }));
});
afterEach(async () => { await context.close(); assert.deepEqual(errors, [], 'Uncaught browser errors'); });

async function draft(settings = {}) {
  await page.addInitScript(s => {
    if (!localStorage.getItem('ffda.settings')) localStorage.setItem('ffda.settings', JSON.stringify({ useClaudeCode: false, ...s }));
  }, settings);
  await page.goto(`${base}/webapp/`);
  await page.locator('#player-tbody tr[data-name]').first().waitFor();
}
async function search(name) { await page.locator('#search-box').fill(name); }
async function settings(tab) {
  await page.locator('#btn-settings').click();
  await page.locator(`#settings-tabs [data-stab="${tab}"]`).click();
}
async function bridge(data) {
  await page.evaluate(data => window.postMessage({ source: 'ffda-ext', type: 'state', data }, '*'), data);
  await page.waitForFunction(() => document.querySelector('#ext-status').textContent.includes('connected'));
}
async function stored(key) { return page.evaluate(k => JSON.parse(localStorage.getItem('ffda.' + k)), key); }
async function pickCount(n) { await page.waitForFunction(n => document.querySelector('#player-count').textContent.includes(`${n} picked`), n); }

test('all public views, research article and embedded draft load', async () => {
  const failures = [];
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('/api/claude/')) failures.push(r.url()); });
  for (const view of ['home', 'plan', 'weekly', 'board', 'blog', 'models', 'live']) {
    await page.goto(`${base}/#/${view}`);
    await page.locator(`#view-${view}`).waitFor();
    await page.waitForFunction(id => document.getElementById(id).innerText.trim().length > 30, `view-${view}`);
    assert.equal(await page.locator(`#view-${view} > .load-error`).count(), 0);
  }
  await page.goto(`${base}/#/blog`);
  await page.locator('#view-blog a[href^="#/blog/"]').first().click();
  await page.locator('#post-body p').first().waitFor();
  await page.goto(`${base}/#/draft`);
  await page.frameLocator('#draft-frame').locator('#player-tbody tr[data-name]').first().waitFor();
  assert.deepEqual(failures, []);
});

test('search, position filters, scoring and notes work', async () => {
  await draft();
  for (const scoring of ['STD', '0.5PPR', 'PPR']) {
    await page.locator('#scoring-format').selectOption(scoring);
    assert.ok(await page.locator('#player-tbody tr[data-name]').count() > 250);
    await search('Josh Allen');
    assert.equal(await page.locator('#player-tbody tr[data-name]').count(), 1);
    await page.locator('#player-tbody tr[data-name]').click();
    assert.match(await page.locator('#note-body').innerText(), /Allen/);
    await search('');
  }
  await page.locator('#pos-filters button', { hasText: /^TE$/ }).click();
  assert.ok(await page.locator('#player-tbody tr[data-name]').count() > 20);
  await search('no-such-player');
  assert.equal(await page.locator('#player-tbody tr[data-name]').count(), 0);
  await page.reload();
  assert.equal(await page.locator('#scoring-format').inputValue(), 'PPR');
});

test('manual picks, roster, ratings and note edits survive reload and reset', async () => {
  await draft({ manualMode: true });
  await search('Josh Allen');
  await page.locator('#player-tbody tr[data-name]').click();
  await page.locator('#btn-edit-note').click();
  await page.locator('#note-textarea').fill('My draft-day note: **target Allen**.');
  await page.locator('#btn-save-note').click();
  await page.locator('.act-mark').click();
  await page.locator('#rating-menu [data-v="love"]').click();
  await page.locator('.act-team').click();
  await pickCount(1);
  assert.match(await page.locator('#team-list').innerText(), /Josh Allen/);
  await page.reload();
  await pickCount(1);
  assert.equal((await stored('toDraft'))['Josh Allen'], 'love');
  page.once('dialog', d => d.accept());
  await page.locator('#btn-reset-top').click();
  await pickCount(0);
  assert.doesNotMatch(await page.locator('#team-list').innerText(), /Josh Allen/);
  await search('Josh Allen');
  await page.locator('#player-tbody tr[data-name]').click();
  assert.match(await page.locator('#note-body').innerText(), /target Allen/);
  assert.deepEqual(await stored('toDraft'), {});
});

test('ESPN ticker accumulates picks, keeps only personal roster, and honors undo', async () => {
  await draft({ manualMode: true, draftSlot: 4 });
  await bridge({ picked_players: { site: 'espn', players: ['Jahmyr Gibbs', 'Bijan Robinson'] }, roster_players: { site: 'espn', players: ['Bijan Robinson'] } });
  await pickCount(2);
  await bridge({ picked_players: { site: 'espn', players: ['Ja\'Marr Chase'] } });
  await pickCount(3);
  assert.match(await page.locator('#team-list').innerText(), /Bijan Robinson/);
  assert.doesNotMatch(await page.locator('#team-list').innerText(), /Gibbs|Chase/);
  await page.locator('#show-picked').check();
  await search('Jahmyr Gibbs');
  await page.locator('.act-pick').click();
  await pickCount(2);
  assert.match(await page.locator('#pick-counter').innerText(), /Pick 3\b/);
  await bridge({ picked_players: { site: 'espn', players: ['Jahmyr Gibbs'] } });
  await pickCount(2);
  await page.reload();
  await pickCount(2);
});

test('draft prediction follows real picks and clears on reset', async () => {
  await draft({ manualMode: true, draftSlot: 4 });
  await page.locator('#tab-strip .tab', { hasText: 'Draft Board' }).click();
  await page.locator('#btn-predict').click();
  assert.match(await page.locator('#board-outlook').innerText(), /At your pick 4/);
  const before = await page.locator('#board-outlook').innerText();
  await bridge({ picked_players: { site: 'espn', players: ['Jahmyr Gibbs', 'Bijan Robinson', 'Jonathan Taylor'] } });
  await pickCount(3);
  assert.notEqual(await page.locator('#board-outlook').innerText(), before);
  const midDraft = await page.evaluate(() => window.FF_DATA.formats.STD.slice(0, 60).map(p => p.name));
  await bridge({ picked_players: { site: 'espn', players: midDraft } });
  await pickCount(60);
  const beforeRoster = await page.locator('#board-outlook').innerText();
  await bridge({ roster_players: { site: 'espn', players: ['Jahmyr Gibbs', 'Bijan Robinson', 'Jonathan Taylor', 'Derrick Henry', 'Saquon Barkley'] } });
  await page.waitForFunction(text => document.querySelector('#board-outlook').innerText !== text, beforeRoster);
  await pickCount(60);
  page.once('dialog', d => d.accept());
  await page.locator('#btn-reset-top').click();
  assert.equal(await page.locator('#btn-clear-predict').isVisible(), false);
});

test('rank import changes only selected scoring format and can revert', async () => {
  await draft();
  await settings('data');
  await page.locator('#file-rankings').setInputFiles({ name: 'ranks.csv', mimeType: 'text/csv', buffer: Buffer.from('Rank,Player\n1,Josh Allen\n2,Bijan Robinson\n') });
  await page.waitForFunction(() => document.querySelector('#status-bar').textContent.includes('Imported'));
  await page.locator('[data-close="settings-dialog"]').click();
  assert.equal(await page.locator('#player-tbody tr[data-name]').first().getAttribute('data-name'), 'Josh Allen');
  await page.locator('#scoring-format').selectOption('PPR');
  assert.notEqual(await page.locator('#player-tbody tr[data-name]').first().getAttribute('data-name'), 'Josh Allen');
  await page.locator('#scoring-format').selectOption('STD');
  await settings('data');
  page.once('dialog', d => d.accept());
  await page.locator('#btn-revert-rankings').click();
  assert.deepEqual(await stored('rankOverrides'), {});
});

test('backup round trip includes extension draft and replaces old cached picks without exporting API key', async () => {
  await draft({ manualMode: true, apiKey: 'test-secret-not-a-real-key' });
  await bridge({ picked_players: { site: 'espn', players: ['Josh Allen', 'Bijan Robinson'] }, roster_players: { site: 'espn', players: ['Josh Allen'] } });
  await pickCount(2);
  await settings('data');
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#btn-export-backup').click();
  const backup = JSON.parse(fs.readFileSync(await (await downloadPromise).path(), 'utf8'));
  assert.equal(backup.settings.apiKey, '');
  await bridge({ picked_players: { site: 'espn', players: ['Jahmyr Gibbs'] } });
  await pickCount(3);
  page.once('dialog', d => d.accept());
  await page.locator('#file-backup').setInputFiles({ name: 'backup.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(backup)) });
  await pickCount(2);
  assert.match(await page.locator('#team-list').innerText(), /Josh Allen/);
  assert.equal((await stored('settings')).apiKey, 'test-secret-not-a-real-key');
  await page.reload();
  await pickCount(2);
});

test('invalid backup is rejected before modifying existing draft', async () => {
  await draft({ manualMode: true });
  await bridge({ picked_players: { site: 'espn', players: ['Josh Allen'] } });
  await pickCount(1);
  await settings('data');
  const dialogs = [];
  page.on('dialog', async d => { dialogs.push(d.type()); await d.accept(); });
  await page.locator('#file-backup').setInputFiles({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({ app: 'ff-draft-tool', manualPicked: 123, noteOverrides: { joshallen: 42 } })) });
  await page.waitForFunction(() => document.querySelector('#status-bar').textContent.includes('backup') || document.querySelector('#settings-dialog').open);
  await page.waitForTimeout(100);
  assert.deepEqual(dialogs, ['alert']);
  await pickCount(1);
});

test('Claude advice renders streamed output and sends current draft context', async () => {
  await page.route('**/api/claude/status', r => r.fulfill({ json: { service: 'ffda-claude', ready: true, token: 'fixture' } }));
  let request;
  await page.route('**/api/claude/chat', r => {
    request = r.request().postDataJSON();
    return r.fulfill({ contentType: 'application/x-ndjson', body: '{"text":"## Recommendation\\n"}\n{"text":"Draft the best available RB."}\n{"done":true}\n' });
  });
  await draft({ useClaudeCode: true, scoringFormat: 'PPR', draftSlot: 4 });
  await bridge({ picked_players: { site: 'espn', players: ['Josh Allen'] }, roster_players: { site: 'espn', players: ['Josh Allen'] } });
  await pickCount(1);
  await page.locator('#btn-ask').click();
  await page.waitForFunction(() => document.querySelector('#ai-status').textContent.startsWith('Done'));
  assert.match(await page.locator('#ai-output').innerText(), /Draft the best available RB/);
  assert.match(request.messages[1].content, /PPR/);
  assert.match(request.messages[1].content, /Josh Allen/);
  assert.equal(await page.locator('#btn-ask').isEnabled(), true);
});

test('Claude failure is visible and leaves board usable', async () => {
  await page.route('**/api/claude/status', r => r.fulfill({ json: { service: 'ffda-claude', ready: true, token: 'fixture' } }));
  await page.route('**/api/claude/chat', r => r.fulfill({ status: 503, json: { error: 'Service unavailable. Try again.' } }));
  await draft({ useClaudeCode: true });
  await page.locator('#btn-ask').click();
  await page.waitForFunction(() => document.querySelector('#ai-status').textContent === 'Error');
  assert.match(await page.locator('#ai-output').innerText(), /Service unavailable/);
  assert.equal(await page.locator('#btn-ask').isEnabled(), true);
  await search('Josh Allen');
  assert.equal(await page.locator('#player-tbody tr[data-name]').count(), 1);
});

test('a partial streamed answer cannot overwrite its subsequent error', async () => {
  await page.route('**/api/claude/status', r => r.fulfill({ json: { service: 'ffda-claude', ready: true, token: 'fixture' } }));
  await page.route('**/api/claude/chat', r => r.fulfill({ contentType: 'application/x-ndjson', body: '{"text":"Incomplete advice"}\n{"error":"Connection lost"}\n' }));
  await draft({ useClaudeCode: true });
  await page.locator('#btn-ask').click();
  await page.waitForFunction(() => document.querySelector('#ai-status').textContent === 'Error');
  // Give the previously queued paint a chance to run.
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert.match(await page.locator('#ai-output').innerText(), /Connection lost/);
  assert.doesNotMatch(await page.locator('#ai-output').innerText(), /Incomplete advice/);
});

test('old backup replaces cached extension state instead of combining drafts', async () => {
  await draft();
  await bridge({ picked_players: { site: 'espn', players: ['Josh Allen'] }, roster_players: { site: 'espn', players: ['Josh Allen'] } });
  await pickCount(1);
  await settings('data');
  page.once('dialog', d => d.accept());
  await page.locator('#file-backup').setInputFiles({ name: 'old.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({ app: 'ff-draft-tool', version: 1, manualPicked: ['Bijan Robinson'], manualTeam: ['Bijan Robinson'] })) });
  await page.waitForFunction(() => document.querySelector('#status-bar').textContent === 'Prep imported from backup');
  await pickCount(1);
  assert.match(await page.locator('#team-list').innerText(), /Bijan Robinson/);
  assert.doesNotMatch(await page.locator('#team-list').innerText(), /Josh Allen/);
  assert.deepEqual(await stored('extPickedRaw'), []);
});

test('ESPN name aliases count once while off-board picks occupy a draft slot', async () => {
  await draft();
  await bridge({ picked_players: { site: 'espn', players: ['Josh Allen', 'Josh Allen ', 'Unlisted Defense'] } });
  await page.waitForFunction(() => document.querySelector('#pick-counter').textContent.startsWith('Pick 3 '));
  await pickCount(1);
  await page.locator('#tab-strip .tab', { hasText: 'Draft Board' }).click();
  assert.match(await page.locator('#board-grid').innerText(), /U\. Defense/);
});

test('Sleeper available snapshots update picks and switch site ranking column', async () => {
  await draft();
  const names = await page.evaluate(() => window.FF_DATA.formats.STD.map(p => p.name));
  await bridge({ available_players: { site: 'sleeper', players: names.filter(n => n !== 'Josh Allen') } });
  await pickCount(1);
  assert.equal(await page.locator('#th-sleeper').isVisible(), true);
  assert.equal(await page.locator('#th-espn').isVisible(), false);
  await bridge({ available_players: { site: 'sleeper', players: names } });
  await pickCount(0);
});

test('failed weekly data load is explained and retries on return', async () => {
  let failing = true;
  await page.route('**/data/weekly.json', r => failing ? r.fulfill({ status: 503, body: '{}' }) : r.continue());
  await page.goto(`${base}/#/weekly`);
  await page.locator('#view-weekly > .load-error').waitFor();
  failing = false;
  await page.goto(`${base}/#/home`);
  await page.goto(`${base}/#/weekly`);
  await page.locator('#dst-table tbody tr').first().waitFor();
  assert.equal(await page.locator('#view-weekly > .load-error').count(), 0);
});

test('phone layout can reach notes, draft board, team and settings without page overflow', async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await draft({ draftSlot: 4 });
  await page.locator('#player-tbody tr[data-name]').first().click();
  await page.locator('#note-body').waitFor();
  for (const view of ['board', 'team', 'players']) {
    await page.locator(`#mobile-nav [data-mview="${view}"]`).click();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  }
  await settings('draft');
  assert.equal(await page.locator('#set-rank-source').isVisible(), true);
  await page.locator('[data-close="settings-dialog"]').click();
});

test('weekly marks persist and hide-taken filters the selected row', async () => {
  await page.goto(`${base}/#/weekly`);
  const first = page.locator('#dst-table tbody tr').first();
  await first.click();
  assert.match(await first.innerText(), /taken/);
  await page.locator('#weekly-hide-taken').click();
  assert.equal(await first.isVisible(), false);
  await page.reload();
  await page.locator('#dst-table tbody tr').first().waitFor();
  assert.match(await page.locator('#dst-table tbody tr').first().innerText(), /taken/);
  await page.locator('#weekly-clear').click();
  assert.doesNotMatch(await page.locator('#dst-table tbody tr').first().innerText(), /taken/);
});
