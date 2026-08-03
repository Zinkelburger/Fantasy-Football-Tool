// NFL.com Fantasy draft room scraper.
//
// UNVERIFIED SELECTORS: written without access to a live NFL.com draft room.
// NFL.com's fantasy pages have long used `.playerName` / `.playerNameFull`
// classes, so those lead the candidate lists, backed by the generic fallback
// in draft-common.js. Before draft day, run an NFL.com mock draft and check
// the console for "[ffda:nfl]" lines; if nothing matches, run
// window.ffdaDiag() and use its output to extend the lists.

(function () {
  'use strict';

  // The draft client lives at fantasy.nfl.com/draftclient; league pages get
  // content.js but no scraper.
  if (!/draft/i.test(location.pathname + location.search)) {
    console.log('[ffda:nfl] not a draft page, scraper idle:', location.pathname);
    return;
  }

  const NAME_SELECTORS = [
    '.playerNameFull',
    '.playerName',
    '[class*="playerName"]',
    '[class*="player-name" i]',
    'a[href*="playerId"]',
  ];

  ffdaWatch({
    site: 'nfl',
    type: 'picked_players',
    containers: [
      '#draftResults',
      '[class*="draftResults"]',
      '[class*="draft-results" i]',
      '[class*="pickHistory" i]',
      '[class*="results" i]',
    ],
    nameSelectors: NAME_SELECTORS,
  });

  ffdaWatch({
    site: 'nfl',
    type: 'roster_players',
    containers: [
      '#myTeam',
      '[class*="myTeam"]',
      '[class*="my-team" i]',
      '[id*="myteam" i]',
      '[class*="roster" i]',
    ],
    nameSelectors: NAME_SELECTORS,
  });

  console.log('NFL.com draft assistant initialized (selectors unverified — run a mock!)');
})();
