// Bridge between the extension and the static web app tab.
//
// Draft pages (ESPN/Sleeper) write scraped player lists into
// chrome.storage.local (see content.js sendDataToServer). This script runs on
// the web app's page and relays that data in via window.postMessage. Because
// the data is persisted in extension storage, the draft tab and the web app
// tab do NOT need to be open at the same time — whenever the app tab opens
// (or regains focus), it receives the latest state.

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

  // Page-initiated requests (handshake retries, reset button).
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
    }
  });

  console.log('FF draft assistant bridge active');
})();
