// CBS Sports Fantasy draft room scraper.
//
// UNVERIFIED SELECTORS — and the most speculative of the three new sites:
// CBS league sites live on per-league subdomains and the draft room markup
// has not been inspected. Candidates below lean on CBS's historical
// `.playerLink` / player-name classes plus the generic fallback in
// draft-common.js. Before draft day, run a CBS mock draft and check the
// console for "[ffda:cbs]" lines; if nothing matches, run window.ffdaDiag()
// and use its output to extend the lists.

(function () {
  'use strict';

  if (!/draft/i.test(location.pathname + location.search)) {
    console.log('[ffda:cbs] not a draft page, scraper idle:', location.pathname);
    return;
  }

  const NAME_SELECTORS = [
    '[class*="player-name" i]',
    '[class*="playerName"]',
    '.playerLink',
    'a[href*="/players/"]',
  ];

  ffdaWatch({
    site: 'cbs',
    type: 'picked_players',
    containers: [
      '[class*="draft-results" i]',
      '[class*="draftResults"]',
      '[class*="pick-history" i]',
      '[class*="picks" i]',
      '[class*="results" i]',
    ],
    nameSelectors: NAME_SELECTORS,
  });

  ffdaWatch({
    site: 'cbs',
    type: 'roster_players',
    containers: [
      '[class*="my-team" i]',
      '[class*="myTeam"]',
      '[id*="myteam" i]',
      '[class*="roster" i]',
    ],
    nameSelectors: NAME_SELECTORS,
  });

  console.log('CBS draft assistant initialized (selectors unverified — run a mock!)');
})();
