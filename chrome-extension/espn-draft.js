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

// ESPN renders every team's roster with the same `.player-column[title]`
// markup, so an unscoped query can sweep all 12 rosters into "Your Team".
// Prefer a container that is clearly *your* roster; fall back to the whole
// document, but say so loudly in the console.
const MY_ROSTER_CONTAINERS = [
  '.draft-columns__col--myteam',
  '[class*="myTeamRoster"]',
  '[class*="my-team-roster"]',
  '[class*="myTeam"]',
  '[class*="my-team"]',
];

let rosterScopeLogged = false;

function findRosterRoot() {
  for (const sel of MY_ROSTER_CONTAINERS) {
    const el = document.querySelector(sel);
    if (el) return { root: el, sel: sel };
  }
  return { root: null, sel: null };
}

// Only ever reports a roster it could scope to *your* team. The old fallback
// read the whole document, which swept all 12 rosters in as yours — and the
// app infers your draft slot from the first pick it sees on your team, so
// that fallback silently assigned you to whoever made pick 1. Reporting
// nothing is strictly better: the slot stays unknown, and you can click your
// column header to set it.
function extractEspnRosterPlayers() {
    const scope = findRosterRoot();

    if (!scope.root) {
      if (!rosterScopeLogged) {
        rosterScopeLogged = true;
        console.warn(
          `ESPN roster: no "my team" container matched, so no roster is being ` +
          `reported (your draft slot won't auto-detect — click your column ` +
          `header on the Draft Board to set it). To fix detection, find your ` +
          `roster's container in DevTools and add its selector to ` +
          `MY_ROSTER_CONTAINERS in espn-draft.js.`);
      }
      return;
    }

    const playerElements = scope.root.querySelectorAll('div.player-column[title]');
    const playerNames = Array.from(playerElements).map(el => el.title);

    if (!rosterScopeLogged) {
      rosterScopeLogged = true;
      console.log(`ESPN roster scoped to "${scope.sel}" (${playerNames.length} players)`);
    }

    if (playerNames.length > 0) {
        sendDataToServer({ site: 'espn', type: 'roster_players', players: playerNames });
    }
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
    observer.observe(document.body, { childList: true, subtree: true });
    console.log('ESPN draft assistant initialized');
}

// Auto-initialize when script loads
initializeEspnDraft();
