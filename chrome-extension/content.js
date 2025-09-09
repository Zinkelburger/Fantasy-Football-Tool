// Core functionality shared across all draft sites

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

// Debug: Log all ESPN cookies immediately  
console.log('🔍 Requesting cookies from background script...');
chrome.runtime.sendMessage({type: "debugCookies"}, function(response) {
  if (chrome.runtime.lastError) {
    console.error('❌ Background script error:', chrome.runtime.lastError);
  } else {
    console.log('🍪 Debug: All ESPN cookies:', response);
  }
});

console.log('🍪 Document cookies:', document.cookie);

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