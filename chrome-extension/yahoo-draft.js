// Yahoo Fantasy Football draft room scraper.
//
// UNVERIFIED SELECTORS: written without access to a live Yahoo draft room.
// The candidate lists below are best guesses layered over the generic
// fallback in draft-common.js. Before draft day, run a Yahoo mock draft,
// open the console, and check for "[ffda:yahoo]" lines. If nothing matches,
// run window.ffdaDiag() and use its output to extend the candidate lists.

(function () {
  'use strict';

  // Only spin up on pages that could be a draft room. Yahoo's draft client
  // lives under football.fantasysports.yahoo.com (path contains "draft");
  // regular league pages get content.js but no scraper.
  if (!/draft/i.test(location.pathname + location.search)) {
    console.log('[ffda:yahoo] not a draft page, scraper idle:', location.pathname);
    return;
  }

  const NAME_SELECTORS = [
    '[class*="player-name" i]',
    '[class*="playerName"]',
    'a[href*="/players/"]',
    '[class*="name" i]',
  ];

  // Draft results / pick history panel.
  ffdaWatch({
    site: 'yahoo',
    type: 'picked_players',
    containers: [
      '[class*="draft-results" i]',
      '[id*="draftresults" i]',
      '[class*="pick-history" i]',
      '[class*="results" i]',
      '[aria-label*="result" i]',
      '[aria-label*="pick" i]',
    ],
    nameSelectors: NAME_SELECTORS,
  });

  // Your roster panel.
  ffdaWatch({
    site: 'yahoo',
    type: 'roster_players',
    containers: [
      '[class*="my-team" i]',
      '[class*="myteam" i]',
      '[id*="myteam" i]',
      '[aria-label*="my team" i]',
      '[class*="roster" i]',
    ],
    nameSelectors: NAME_SELECTORS,
  });

  console.log('Yahoo draft assistant initialized (selectors unverified — run a mock!)');
})();
