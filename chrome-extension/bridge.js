// Bridge between the extension and the static web app tab.
//
// Draft pages (ESPN/Sleeper) write scraped player lists into
// chrome.storage.local (see content.js sendDataToServer). This script runs on
// the web app's page and relays that data in via window.postMessage. Because
// the data is persisted in extension storage, the draft tab and the web app
// tab do NOT need to be open at the same time — whenever the app tab opens
// (or regains focus), it receives the latest state. Nor do they need to be
// *focused*: chrome.storage.onChanged fires in background tabs, so the app tab
// updates live while you sit on the draft page.
//
// The manifest lists the exact origins this runs on. If you host the app
// somewhere new, add that origin there — but keep it exact. A wildcard like
// https://*.github.io/* would inject this into every GitHub Pages site on the
// internet.

(function () {
  'use strict';

  // Only act on pages that identify themselves as the draft tool.
  if (!document.querySelector('meta[name="ff-draft-assistant"]')) return;

  const STORAGE_KEYS = ['ffda_picked_players', 'ffda_roster_players', 'ffda_available_players'];

  function postToPage(type, data) {
    window.postMessage({ source: 'ffda-ext', type: type, data: data }, '*');
  }

  function readAndPostState() {
    try {
      chrome.storage.local.get(STORAGE_KEYS, (items) => {
        if (chrome.runtime.lastError) return;
        postToPage('state', {
          picked_players: items.ffda_picked_players || null,
          roster_players: items.ffda_roster_players || null,
          available_players: items.ffda_available_players || null,
        });
      });
    } catch (e) {
      // Extension context invalidated (e.g. extension was reloaded); page
      // will keep working off its last-known state.
    }
  }

  // Announce ourselves, then push whatever state we already have.
  postToPage('hello', { version: chrome.runtime.getManifest().version });
  readAndPostState();

  // Live updates: draft tab writes to storage -> we push to the page.
  try {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== 'local') return;
      if (STORAGE_KEYS.some((k) => k in changes)) readAndPostState();
    });
  } catch (e) { /* context invalidated */ }

  // Page-initiated requests (handshake retries, reset button, and the
  // ESPN read relay below).
  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const msg = event.data;
    if (!msg || msg.source !== 'ffda-page') return;

    if (msg.type === 'request-state') {
      postToPage('hello', {});
      readAndPostState();
    } else if (msg.type === 'clear-state') {
      try {
        chrome.storage.local.remove(STORAGE_KEYS);
      } catch (e) { /* context invalidated */ }
    } else if (msg.type === 'espn-fetch') {
      // The site is asking us to read one ESPN league endpoint for it.
      // We can do this and the page can't, because the espn_s2/SWID
      // cookies are .espn.com cookies and won't ride along on a
      // third-party request from our origin -- see background.js.
      //
      // Everything about the request is re-checked in the background
      // script (GET only, one URL prefix, one allowed header). Nothing
      // here needs the cookie itself, and the cookie never reaches the
      // page: only the JSON answer does.
      const reply = (payload) =>
        window.postMessage(
          Object.assign({ source: 'ffda-ext', type: 'espn-result', id: msg.id },
                        payload), '*');
      try {
        chrome.runtime.sendMessage(
          { type: 'espnFetch', url: msg.url, filter: msg.filter },
          (response) => {
            if (chrome.runtime.lastError) {
              reply({ error: chrome.runtime.lastError.message });
            } else if (!response) {
              reply({ error: 'the extension gave no answer' });
            } else {
              reply(response.error ? { error: response.error }
                                   : { data: response.data });
            }
          });
      } catch (e) {
        reply({ error: 'the extension needs reloading' });
      }
    }
  });

  console.log('FF draft assistant bridge active');
})();
