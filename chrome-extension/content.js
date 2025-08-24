// --- Unified Data Sending Function ---
// Sends an object to your server, like: { type: '...', players: [...] }
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


// --- Extraction Functions ---

// 1. Extracts the "Picked Players"
function extractPickedPlayers() {
  const playerElements = document.querySelectorAll('.pick__message-information .playerinfo__playername');
  const playerNames = Array.from(playerElements).map(el => el.textContent.trim());

  // If any names are found, send them
  if (playerNames.length > 0) {
    sendDataToServer({ type: 'picked_players', players: playerNames });
  }
}

// 2. Extracts the "Roster Players"
function extractRosterPlayers() {
    const playerElements = document.querySelectorAll('div.player-column[title]');
    const playerNames = Array.from(playerElements).map(el => el.title);

    // If any names are found, send them
    if (playerNames.length > 0) {
        sendDataToServer({ type: 'roster_players', players: playerNames });
    }
}


// --- Main Execution Logic ---

// This function runs both extraction routines.
function runAllExtractions() {
    extractPickedPlayers();
    extractRosterPlayers();
}

// Set up the observer to run our main function whenever the page content changes.
const observer = new MutationObserver(runAllExtractions);
observer.observe(document.body, { childList: true, subtree: true });

// Also run it once right away when the extension loads.
runAllExtractions();
