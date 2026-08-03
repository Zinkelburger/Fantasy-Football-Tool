// Core functionality shared across all draft sites

// Last payload sent per type, so an unchanged scrape costs nothing. The
// draft rooms mutate on every clock tick, and without this each tick meant a
// storage write plus a POST, which then re-rendered the whole web app board.
//
// Unchanged data is still re-sent every RESEND_MS so that a Go desktop app
// started *after* the draft page can still catch up.
const lastSent = new Map();
const RESEND_MS = 10000;

function sendDataToServer(data) {
  if (!data || !data.type) return;

  const serialized = JSON.stringify(data.players);
  const prev = lastSent.get(data.type);
  if (prev && prev.body === serialized && Date.now() - prev.at < RESEND_MS) return;
  lastSent.set(data.type, { body: serialized, at: Date.now() });

  // Mirror into extension storage so the static web app can read it via
  // bridge.js. Storage persists, so the web app tab does not need to be
  // open while the draft page is scraped.
  try {
    if (chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({
        ['ffda_' + data.type]: {
          site: data.site,
          players: data.players,
          updatedAt: Date.now(),
        },
      });
    }
  } catch (e) {
    // Extension context invalidated (extension reloaded); ignore.
  }

  // Also POST to the Go desktop app if it happens to be running.
  fetch('http://localhost:8000', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  .then(response => response.json())
  .then(serverData => console.log('Server response:', serverData))
  .catch(() => { /* Go desktop app not running; web app gets data via storage */ });
}

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
    // Silently ignore heartbeat errors when Go server isn't running
  });
}

// Handle ESPN authentication requests from Python program  
function handleEspnAuthRequest() {
  // Only allow this on ESPN pages for security
  if (!window.location.hostname.includes('fantasy.espn.com')) {
    return;
  }
  
  // Check if Python program is requesting auth (only from localhost:8001)
  fetch('http://localhost:8001/espn-auth-request', {
    method: 'GET',
  })
  .then(response => {
    if (response.status === 200) {
      return response.json();
    }
    throw new Error('No auth request pending');
  })
  .then(data => {
    if (data.requestAuth) {
      console.log('🔑 Local Python program requesting ESPN authentication...');
      // Python program is requesting ESPN auth cookies + league info
      chrome.runtime.sendMessage({type: "getEspnData"}, function(response) {
        if (chrome.runtime.lastError) {
          console.error('Chrome runtime error:', chrome.runtime.lastError);
          return;
        }
        
        if (response.error) {
          console.error('Auth request denied:', response.error);
          return;
        }
        
        console.log('📤 Received ESPN data from background script:', response);
        
        // Send the cookies and league info back to the Python program
        fetch('http://localhost:8001/espn-auth', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(response),
        })
        .then(() => console.log('✅ ESPN auth data sent to local Python program'))
        .catch((error) => console.error('❌ Error sending ESPN auth:', error));
      });
    }
  })
  .catch((error) => {
    // Silently ignore auth request errors when Python server isn't running
  });
}

// Listen for messages from the background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "getCookieString") {
    console.log("Content Script: Received request, sending cookie string.");
    sendResponse({ cookieString: document.cookie });
  }
  return true;
});

// Extension is now active on all ESPN Fantasy pages
console.log('ESPN Fantasy extension loaded on:', window.location.href);

// NOTE: do not log document.cookie or the ESPN cookie jar here. They contain
// espn_s2 and SWID, which are full session credentials, and the draft-day
// console is often visible on a shared screen.

// Only start heartbeat and auth monitoring when servers are likely running
// (This reduces console spam when extension loads)

// Check for ESPN auth requests every 2 seconds (only on ESPN site)
if (window.location.hostname.includes('fantasy.espn.com')) {
  console.log('ESPN Fantasy page detected - auth monitoring will start when Python program runs');
  setInterval(handleEspnAuthRequest, 2000);
  
  // Start heartbeat for Go server (silently fails if not running)
  setInterval(sendHeartbeat, 2000);
} else {
  console.log('Not on ESPN Fantasy page:', window.location.hostname);
}