// This function sends data with a 'site' field. (No changes here)
function sendDataToServer(data) {
  fetch('http://localhost:8000', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  .then(response => response.json())
  .then(serverData => console.log('Server response:', serverData))
  .catch((error) => console.error('Error sending data:', error));
}

// Send heartbeat to server every 2 seconds
function sendHeartbeat() {
  fetch('http://localhost:8000/heartbeat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  })
  .then(response => response.json())
  .then(() => {
    // Heartbeat successful - no need to log every time
  })
  .catch((error) => {
    console.error('Error sending heartbeat:', error);
  });
}

// ========== ESPN EXTRACTION LOGIC (No changes here) ==========
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

// ========== SLEEPER EXTRACTION LOGIC (No changes here) ==========
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

// ========== ** NEW AND IMPROVED OBSERVER LOGIC ** ==========

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

// This is the main function that runs. It checks the site and calls the correct functions/observers.
function initializeExtension() {
  const hostname = window.location.hostname;

  if (hostname.includes('fantasy.espn.com')) {
    // For ESPN, the old method is fine since the page structure is simpler.
    runEspnExtractions(); // Run once on load
    const observer = new MutationObserver(runEspnExtractions);
    observer.observe(document.body, { childList: true, subtree: true });

  } else if (hostname.includes('sleeper.com')) {
    // For Sleeper, we use the new, targeted observers.
    startObserverFor('.player-rank-list', extractSleeperAvailablePlayers);
    startObserverFor('.draft-roster2-teams', extractSleeperRosterPlayers);
  }
}

// Start the whole process.
initializeExtension();

// Start sending heartbeat every 2 seconds
setInterval(sendHeartbeat, 2000);
sendHeartbeat(); // Send initial heartbeat