// ESPN Draft Assistant functionality

function extractEspnPickedPlayers() {
  const playerElements = document.querySelectorAll('.pick__message-information .playerinfo__playername');
  const playerNames = Array.from(playerElements).map(el => el.textContent.trim());
  if (playerNames.length > 0) {
    sendDataToServer({ site: 'espn', type: 'picked_players', players: playerNames });
  }
}

function extractEspnRosterPlayers() {
    const playerElements = document.querySelectorAll('div.player-column[title]');
    const playerNames = Array.from(playerElements).map(el => el.title);
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
    const observer = new MutationObserver(runEspnExtractions);
    observer.observe(document.body, { childList: true, subtree: true });
    console.log('ESPN draft assistant initialized');
}

// Auto-initialize when script loads
initializeEspnDraft();