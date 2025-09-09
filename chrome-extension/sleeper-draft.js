// Sleeper Draft Assistant functionality

function extractSleeperAvailablePlayers() {
  const playerElements = document.querySelectorAll('.player-rank-item2 .name-wrapper');
  const playerNames = Array.from(playerElements).map(el => {
    return el.childNodes[0].textContent.trim();
  });
  if (playerNames.length > 0) {
    sendDataToServer({ site: 'sleeper', type: 'available_players', players: playerNames });
  }
}

function extractSleeperRosterPlayers() {
    const playerElements = document.querySelectorAll('.player-data .name');
    const playerNames = Array.from(playerElements).map(el => el.textContent.trim());
    if (playerNames.length > 0) {
        sendDataToServer({ site: 'sleeper', type: 'roster_players', players: playerNames });
    }
}

function startObserverFor(selector, callback) {
  const targetNode = document.querySelector(selector);

  // Only start the observer if the target element actually exists on the page.
  if (targetNode) {
    // Run the callback once immediately to get the initial data.
    callback();

    // Create an observer that will run the callback whenever the target's children change.
    const observer = new MutationObserver(callback);
    observer.observe(targetNode, { childList: true, subtree: true });
    console.log(`Observer started for: ${selector}`);
  } else {
    // If the element isn't found, wait a bit and try again. Modern apps need time to load.
    setTimeout(() => startObserverFor(selector, callback), 1000);
  }
}

function initializeSleeperDraft() {
    // For Sleeper, we use the targeted observers.
    startObserverFor('.player-rank-list', extractSleeperAvailablePlayers);
    startObserverFor('.draft-roster2-teams', extractSleeperRosterPlayers);
    console.log('Sleeper draft assistant initialized');
}

// Auto-initialize when script loads
initializeSleeperDraft();