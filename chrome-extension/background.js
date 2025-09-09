// Background service worker for handling ESPN authentication cookies

// Listen for messages from content scripts or the extension's popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Use a modern async function to handle the request
  const handleRequest = async () => {
    // Security check: Only allow requests from our extension
    // Note: Checking sender.tab.url might fail if the message is from the popup
    if (sender.id !== chrome.runtime.id) {
      console.warn("Request denied from unauthorized source:", sender);
      return { error: "Unauthorized request" };
    }

    // Handle different types of requests
    switch (request.type) {
      case "getEspnData":
        console.log("🔍 Background: Forwarding request to content script...");

        // Find the active ESPN fantasy tab
        const [tab] = await chrome.tabs.query({
          active: true,
          url: "https://fantasy.espn.com/*",
        });

        if (!tab) {
          console.error("Could not find an active ESPN Fantasy tab.");
          return { error: "No active ESPN Fantasy tab found." };
        }

        // Send a message to the content script in that tab
        const response = await chrome.tabs.sendMessage(tab.id, { type: "getCookieString" });

        if (!response || !response.cookieString) {
          console.error("Did not receive a cookie string from the content script.");
          return { error: "Failed to get cookies from content script." };
        }

        // --- NEW: Parse the raw cookie string ---
        const cookies = response.cookieString.split(';').map(c => c.trim());
        const cookieMap = new Map(cookies.map(c => c.split('=')));

        const espnAuthValue = cookieMap.get("espnAuth");
        const s2Value = cookieMap.get("espn_s2");
        const leagueValue = cookieMap.get("kona_v3_environment_season_ffl");
        
        let swid = null;
        if (espnAuthValue) {
            try {
                swid = JSON.parse(decodeURIComponent(espnAuthValue)).swid;
            } catch (e) { console.error("Could not parse espnAuth", e); }
        }

        let leagueData = {};
        if (leagueValue) {
            try {
                leagueData = JSON.parse(decodeURIComponent(leagueValue));
            } catch (e) { console.error("Could not parse league cookie", e); }
        }

        const finalResponse = {
          swid: swid || "Could not load SWID",
          espn_s2: s2Value || "Could not load S2",
          league_id: leagueData.leagueId || "Could not load League ID",
          season_id: leagueData.seasonId || new Date().getFullYear(),
          team_id: leagueData.teamId || "Could not load Team ID",
        };

        console.log("📤 Background: Sending final parsed response:", finalResponse);
        return finalResponse;

      case "debugCookies":
        console.log("🔍 Background: Received debugCookies request.");

        // Get all cookies from the parent domain to ensure we find them all
        const debugCookies = await chrome.cookies.getAll({ domain: "espn.com" });
        
        console.log(`Found ${debugCookies.length} cookies for domain 'espn.com'.`);
        
        if (debugCookies.length === 0) {
            console.warn("No cookies found. Ensure you are logged into ESPN and have the correct permissions in manifest.json.");
        } else {
            // Log all found cookie names for debugging
            debugCookies.forEach(cookie => {
                console.log(`- ${cookie.name}: ${cookie.value.substring(0, 30)}${cookie.value.length > 30 ? '...' : ''}`);
            });
        }
        
        return { cookies: debugCookies };

      default:
        console.warn("Unknown request type received:", request.type);
        return { error: `Unknown request type: ${request.type}` };
    }
  };

  // Execute the async function and send the response
  handleRequest().then(sendResponse);

  // Return true to indicate that sendResponse will be called asynchronously
  return true;
});