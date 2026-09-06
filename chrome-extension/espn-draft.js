// ESPN Draft Assistant functionality
//
// Defined locally rather than shared from content.js: on ESPN the two files are
// separate manifest entries, so injection order is not guaranteed.
function debounce(fn, wait) {
  let timer = null;
  return function () {
    clearTimeout(timer);
    timer = setTimeout(fn, wait);
  };
}

function extractEspnPickedPlayers() {
  const playerElements = document.querySelectorAll('.pick__message-information .playerinfo__playername');
  const playerNames = Array.from(playerElements).map(el => el.textContent.trim());
  if (playerNames.length > 0) {
    sendDataToServer({ site: 'espn', type: 'picked_players', players: playerNames });
  }
}

// Current ESPN rooms mark each of your draft-board cells with `.myTeam`.
// The roster dropdown can display another team, and the board HEADER also has
// `.myTeam`, so neither a generic roster panel nor a substring match is safe.
const MY_ROSTER_CONTAINERS = [
  '.draft-columns__col--myteam',
  '.myTeamRoster',
  '.my-team-roster',
];

let rosterScopeLogged = false;

function findRosterRoot() {
  for (const sel of MY_ROSTER_CONTAINERS) {
    const el = document.querySelector(sel);
    if (el) return { root: el, sel: sel };
  }
  return { root: null, sel: null };
}

function extractEspnRosterPlayers() {
  let names;
  let source;
  const ownCells = document.querySelectorAll('.draft-board-grid-pick-cell.myTeam');
  if (ownCells.length > 0) {
    names = [];
    source = 'draft-board cells marked myTeam';
    for (const cell of ownCells) {
      if (!cell.classList.contains('completedPick')) continue;
      const first = cell.querySelector('.playerFirstName')?.textContent.trim() || '';
      const last = cell.querySelector('.playerLastName')?.textContent.trim() || '';
      const name = [first, last].filter(Boolean).join(' ');
      // A completed cell may be mid-render. Keep the last complete snapshot
      // until the next mutation rather than replacing it with a partial team.
      if (!name) return;
      names.push(name);
    }
  } else {
    const scope = findRosterRoot();
    if (!scope.root) {
      if (!rosterScopeLogged) {
        rosterScopeLogged = true;
        console.warn('ESPN roster: no personal draft cells or explicit personal roster found; ' +
          'not reporting an unverified team. Try opening ESPN’s Draft Board tab.');
      }
      return;
    }
    source = scope.sel;
    names = Array.from(scope.root.querySelectorAll('div.player-column[title]'))
      .map(el => el.title.trim()).filter(Boolean);
    // An empty legacy container may not yet have rendered its roster table.
    if (!names.length && !scope.root.querySelector('.roster-module')) return;
  }

  if (!rosterScopeLogged) {
    rosterScopeLogged = true;
    console.log(`ESPN roster scoped to ${source} (${names.length} players)`);
  }
  // Include confirmed empty rosters, so a new draft or undo clears old picks.
  sendDataToServer({ site: 'espn', type: 'roster_players', players: [...new Set(names)] });
}

function runEspnExtractions() {
    extractEspnPickedPlayers();
    extractEspnRosterPlayers();
}

function initializeEspnDraft() {
    runEspnExtractions(); // Run once on load
    // The draft room mutates on every clock tick; without a debounce this
    // re-scrapes (and re-renders the web app) dozens of times a second.
    const observer = new MutationObserver(debounce(runEspnExtractions, 250));
    observer.observe(document.body, { childList: true, subtree: true,
      characterData: true, attributes: true, attributeFilter: ['class', 'title'] });
    console.log('ESPN draft assistant initialized');
}

// Auto-initialize when script loads
initializeEspnDraft();
