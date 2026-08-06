// Background script for handling ESPN authentication cookies.
// Runs as a service worker in Chrome/Edge/Brave and as an event page in
// Firefox (see the manifest's dual background keys).

// Firefox's `browser.*` namespace is the one guaranteed to return promises
// there; Chrome MV3's `chrome.*` does the same. Alias so `await` works in both.
const ext = typeof browser !== 'undefined' ? browser : chrome;

// Listen for messages from content scripts or the extension's popup
ext.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Use a modern async function to handle the request
  const handleRequest = async () => {
    // Security check: Only allow requests from our extension
    // Note: Checking sender.tab.url might fail if the message is from the popup
    if (sender.id !== ext.runtime.id) {
      console.warn("Request denied from unauthorized source:", sender);
      return { error: "Unauthorized request" };
    }

    // Handle different types of requests
    switch (request.type) {
      case "getEspnData":
        console.log("🔍 Background: Forwarding request to content script...");

        // Find the active ESPN fantasy tab
        const [tab] = await ext.tabs.query({
          active: true,
          url: "https://fantasy.espn.com/*",
        });

        if (!tab) {
          console.error("Could not find an active ESPN Fantasy tab.");
          return { error: "No active ESPN Fantasy tab found." };
        }

        // Send a message to the content script in that tab
        const response = await ext.tabs.sendMessage(tab.id, { type: "getCookieString" });

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

      // Read one ESPN fantasy endpoint on the web app's behalf.
      //
      // Why this exists: espn_s2 and SWID are .espn.com cookies, so a
      // request from foss.football is third-party and the browser won't
      // attach them -- which is what makes a private league unreadable
      // from the site itself. (CORS is not the problem; ESPN echoes our
      // origin and allows credentials. The cookies simply never leave.)
      // We hold host permission for espn.com, so the same request made
      // from here does carry them.
      //
      // This is deliberately the narrowest possible door:
      //   - GET only, no body, no way to make a change
      //   - one URL prefix, the read-only league API
      //   - the only header a caller may set is X-Fantasy-Filter, and
      //     it must be JSON
      //   - nothing is stored, and the cookies never reach the page
      // The manifest already limits which origins may ask (bridge.js
      // runs on our own site and localhost only).
      case "espnFetch": {
        const ALLOWED =
          "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/";
        if (typeof request.url !== "string" || !request.url.startsWith(ALLOWED)) {
          return { error: "That URL isn't the ESPN read API." };
        }
        const headers = {};
        if (request.filter) {
          try {
            headers["X-Fantasy-Filter"] = typeof request.filter === "string"
              ? request.filter : JSON.stringify(request.filter);
          } catch (e) {
            return { error: "Bad filter." };
          }
        }
        try {
          const res = await fetch(request.url, {
            method: "GET",
            credentials: "include",
            headers,
          });
          if (!res.ok) {
            return { error: res.status === 401
              ? "ESPN says you're not signed in, or that league isn't yours. "
                + "Open fantasy.espn.com, sign in, then try again."
              : `ESPN returned HTTP ${res.status}.` };
          }
          return { data: await res.json() };
        } catch (e) {
          return { error: `Couldn't reach ESPN: ${e.message}` };
        }
      }

      // NOTE: a "debugCookies" case used to live here and dumped every
      // espn.com cookie (including espn_s2/SWID) to the console. Removed --
      // it was debug-only and leaked session credentials to anyone looking at
      // the screen. Auth for the local Python tool still goes through
      // "getEspnData" above, which only returns what that tool needs.

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