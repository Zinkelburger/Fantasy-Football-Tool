function extractPlayerNames() {
    const playerElements = document.querySelectorAll('.jsx-2093861861.pick__message-information .playerinfo__playername');
    const playerNames = Array.from(playerElements).map(el => el.textContent.trim());
  
    // Send the player names to the Python server
    if (playerNames.length > 0) {
      sendPlayerNamesToServer(playerNames);
    }
  }
  
  function sendPlayerNamesToServer(playerNames) {
    fetch('http://localhost:8000', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ playerNames }),
    })
    .then(response => response.json())
    .then(data => console.log('Success:', data))
    .catch((error) => console.error('Error:', error));
  }
  
  // Monitor the page for updates to the player names
  const observer = new MutationObserver(extractPlayerNames);
  observer.observe(document.body, { childList: true, subtree: true });
  
  // Initial extraction
  extractPlayerNames();
  