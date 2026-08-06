// Background script for handling ESPN authentication cookies.
// Runs as a service worker in Chrome/Edge/Brave and as an event page in
// Firefox (see the manifest's dual background keys).

// Firefox's `browser.*` namespace is the one guaranteed to return promises
// there; Chrome MV3's `chrome.*` does the same. Alias so `await` works in both.
const ext = typeof browser !== 'undefined' ? browser : chrome;

// Pull the football leagues out of a fan-API payload.
//
// The shape is undocumented and has moved before, so this reads loosely:
// walk the preferences, take anything carrying an `entry` with `groups`,
// and keep the ones that look like football. Anything unreadable is
// skipped rather than guessed at — the caller has a fallback.
function fanLeagues(json, season) {
  const out = [];
  const seen = new Set();
  for (const p of (json && json.preferences) || []) {
    const e = (p && p.metaData && p.metaData.entry) || null;
    if (!e || !Array.isArray(e.groups)) continue;
    // gameId 1 is football. Older payloads leave it off and put the sport
    // in the entry's URL instead.
    const url = String(e.entryURL || e.entryLocation || '');
    const football =
      e.gameId === 1 || (e.gameId === undefined && /football|\bffl\b/i.test(url));
    if (!football) continue;
    if (e.seasonId && season && Number(e.seasonId) !== Number(season)) continue;
    for (const g of e.groups || []) {
      const id = g && g.groupId;
      if (id == null || seen.has(String(id))) continue;
      seen.add(String(id));
      const teamId = e.entryId != null ? e.entryId : g.groupManagerTeamId;
      out.push({
        leagueId: String(id),
        leagueName: g.groupName || null,
        teamId: teamId != null ? String(teamId) : null,
        teamName: e.name || e.abbrev || null,
        season: String(e.seasonId || season),
      });
    }
  }
  return out;
}

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

      // Which ESPN football leagues is this browser signed in to?
      //
      // Same root cause as espnFetch above: the SWID that identifies you
      // to ESPN is a .espn.com cookie, so the site can't read it and
      // can't ask this question. We can. The answer turns the site's
      // "paste your league id" box into a list of your leagues, private
      // ones included.
      //
      // Two readers, because the good one is undocumented:
      //   1. ESPN's fan API returns every league a SWID belongs to.
      //      Nothing obliges its shape to hold still, so fanLeagues()
      //      above is deliberately loose and comes back empty rather
      //      than wrong.
      //   2. When that comes back empty, the kona_v3_environment_season_ffl
      //      cookie. It only remembers the last league you looked at and
      //      carries no names, but it has been stable for years. One
      //      league you can click beats a text box.
      //
      // Read-only. Nothing is stored, and no cookie reaches the page --
      // only the league ids and names come back.
      case "espnMe": {
        const season = Number(request.season) || new Date().getFullYear();
        const cookie = async (name) => {
          try {
            const c = await ext.cookies.get({
              url: "https://fantasy.espn.com", name });
            return c && c.value ? c.value : null;
          } catch (e) { return null; }
        };

        const swid = await cookie("SWID");
        if (swid) {
          try {
            const res = await fetch(
              "https://fan.api.espn.com/apis/v2/fans/"
                + encodeURIComponent(swid)
                + "?useCookieAuth=true&featureFlags=expandAthlete"
                + "&content=placeholder&showAirings=false"
                + "&displayEvents=false&displayNow=false&displayRecs=false",
              { method: "GET", credentials: "include",
                headers: { accept: "application/json" } });
            if (res.ok) {
              const leagues = fanLeagues(await res.json(), season);
              if (leagues.length) return { leagues, from: "fan" };
            }
          } catch (e) { /* fall through to the cookie */ }
        }

        const raw = await cookie("kona_v3_environment_season_ffl");
        if (raw) {
          try {
            const d = JSON.parse(decodeURIComponent(raw));
            if (d && d.leagueId) {
              return { from: "cookie", leagues: [{
                leagueId: String(d.leagueId),
                leagueName: null,
                teamId: d.teamId != null ? String(d.teamId) : null,
                teamName: null,
                season: String(d.seasonId || season),
              }] };
            }
          } catch (e) { /* not JSON any more */ }
        }

        return { from: null, leagues: [], error: swid ? null
          : "You're not signed in to ESPN in this browser." };
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