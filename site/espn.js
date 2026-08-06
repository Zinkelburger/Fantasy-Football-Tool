/* ESPN: raw API client, and the adapter that normalises it.
 *
 * Two routes in, because ESPN has two kinds of league:
 *
 * 1. **Public leagues go straight from the browser.** The read API
 *    answers cross-origin requests properly — it echoes our Origin,
 *    allows credentials, and even allows the `X-Fantasy-Filter` header
 *    on preflight, which is what makes the free-agent list reachable.
 *    No key, no login, nothing stored. Give it a league id and it
 *    works.
 *
 * 2. **Private leagues go through the browser extension.** Not because
 *    of CORS — CORS is fine — but because the `espn_s2` and `SWID`
 *    cookies live on .espn.com and a request from our origin is a
 *    third-party one, so the browser won't attach them. The extension
 *    holds host permission for espn.com, so it *can* make that request
 *    with cookies, and it relays the answer back to this page. If the
 *    extension isn't installed we say so plainly instead of failing
 *    with a raw 401.
 *
 * ESPN's own weekly projections ride along in the same payload as the
 * rosters (statSourceId 1), so an ESPN league needs no second source
 * for the projection the live model runs on.
 */
"use strict";

const Espn = (() => {
  const READ = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl";
  const mem = {};

  /* proTeamId -> abbreviation, matching the scoreboard's abbreviations
     so live.js can line a player up with his game. Checked against
     site.api.espn.com/.../teams on 2026-08-05. */
  const PRO_TEAM = {
    0: null, 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL",
    7: "DEN", 8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV",
    14: "LAR", 15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG",
    20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF",
    26: "SEA", 27: "TB", 28: "WSH", 29: "CAR", 30: "JAX", 33: "BAL",
    34: "HOU",
  };

  const POSITION = { 1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST" };

  /* lineupSlotId -> our slot names. Anything not here (IDP, punter,
     head coach) is a slot we don't model and is dropped. */
  const SLOT = {
    0: "QB", 1: "QB", 2: "RB", 3: "WRRB_FLEX", 4: "WR", 5: "REC_FLEX",
    6: "TE", 7: "SUPERFLEX", 16: "DST", 17: "K", 23: "FLEX",
  };
  const BENCH = new Set([20, 21, 24]);   // bench, IR, "extra"

  const INJURY = {
    ACTIVE: null, QUESTIONABLE: "Q", DOUBTFUL: "D", OUT: "O",
    INJURY_RESERVE: "IR", SUSPENSION: "SUSP", DAY_TO_DAY: "DTD",
  };

  /* ------------------------------------------------- extension bridge */

  /* The extension announces itself with a postMessage on page load and
     answers requests the same way. This resolves to false quickly when
     no extension is there, so the public path never waits on it. */
  let extReady = null;
  function extension() {
    if (extReady) return extReady;
    extReady = new Promise(resolve => {
      let done = false;
      const onMsg = (e) => {
        if (e.source !== window) return;
        const m = e.data;
        if (m && m.source === "ffda-ext" && m.type === "hello") {
          done = true;
          window.removeEventListener("message", onMsg);
          resolve(true);
        }
      };
      window.addEventListener("message", onMsg);
      window.postMessage({ source: "ffda-page", type: "request-state" }, "*");
      setTimeout(() => {
        if (!done) { window.removeEventListener("message", onMsg); resolve(false); }
      }, 700);
    });
    return extReady;
  }

  let reqId = 0;
  function viaExtension(url, filter) {
    return new Promise((resolve, reject) => {
      const id = `espn-${++reqId}`;
      const onMsg = (e) => {
        if (e.source !== window) return;
        const m = e.data;
        if (!m || m.source !== "ffda-ext" || m.type !== "espn-result"
            || m.id !== id) return;
        window.removeEventListener("message", onMsg);
        clearTimeout(timer);
        if (m.error) reject(new Error(m.error));
        else resolve(m.data);
      };
      const timer = setTimeout(() => {
        window.removeEventListener("message", onMsg);
        reject(new Error("the extension didn't answer"));
      }, 20000);
      window.addEventListener("message", onMsg);
      window.postMessage(
        { source: "ffda-page", type: "espn-fetch", id, url, filter }, "*");
    });
  }

  /* Which ESPN leagues is this browser signed in to?
     Only the extension can answer: the question is keyed on the SWID
     cookie, which lives on .espn.com and is invisible from here.

     Never rejects. "No extension", "not signed in" and "you're in no
     leagues" all leave the caller doing the same thing — showing the
     box where you type a league id — so they all resolve to an empty
     list rather than an error somebody has to catch. */
  async function myLeagues(season) {
    const none = { leagues: [], from: null };
    if (!(await extension())) return none;
    return new Promise((resolve) => {
      const id = `espn-me-${++reqId}`;
      const done = (v) => {
        window.removeEventListener("message", onMsg);
        clearTimeout(timer);
        resolve(v);
      };
      const onMsg = (e) => {
        if (e.source !== window) return;
        const m = e.data;
        if (!m || m.source !== "ffda-ext" || m.type !== "espn-leagues-result"
            || m.id !== id) return;
        done(m.error ? none : { leagues: m.leagues || [], from: m.from || null });
      };
      const timer = setTimeout(() => done(none), 8000);
      window.addEventListener("message", onMsg);
      window.postMessage(
        { source: "ffda-page", type: "espn-leagues", id, season }, "*");
    });
  }

  /* ---------------------------------------------------------- fetching */

  async function get(url, filter) {
    const headers = filter ? { "X-Fantasy-Filter": JSON.stringify(filter) } : {};
    let r;
    try {
      r = await fetch(url, { headers });
    } catch (e) {
      /* a network-level failure, not an auth one */
      throw new Error("couldn't reach ESPN — check your connection");
    }
    if (r.ok) return r.json();
    if (r.status === 401 || r.status === 403) {
      /* private league: only the extension can sign this request */
      if (await extension()) return viaExtension(url, filter);
      throw new Error(
        "That's a private ESPN league, so it needs the browser extension "
        + "to read it — a page on this site can't send your ESPN login. "
        + "Public leagues work without it.");
    }
    if (r.status === 404) throw new Error("No ESPN league with that id.");
    throw new Error(`ESPN returned HTTP ${r.status}`);
  }

  function url(leagueId, season, views, params) {
    const q = new URLSearchParams(params || {});
    for (const v of views) q.append("view", v);
    return `${READ}/seasons/${season}/segments/0/leagues/${leagueId}?${q}`;
  }

  const league = (leagueId, season, views, params, filter) =>
    get(url(leagueId, season, views, params), filter);

  /* --------------------------------------------------------- reading */

  /* ESPN hangs every kind of number off one `stats` array. The two we
     want are both "this scoring period, split by week": source 0 is
     what he actually did, source 1 is what ESPN projects. */
  function statFor(player, week, source) {
    for (const s of player.stats || []) {
      if (s.scoringPeriodId === week && s.statSourceId === source
          && s.statSplitTypeId === 1) {
        return typeof s.appliedTotal === "number" ? s.appliedTotal : null;
      }
    }
    return null;
  }

  function playerOf(p) {
    return {
      name: p.fullName || `${p.firstName || ""} ${p.lastName || ""}`.trim(),
      pos: POSITION[p.defaultPositionId] || null,
      team: PRO_TEAM[p.proTeamId] || null,
      inj: p.injuryStatus ? (INJURY[p.injuryStatus] !== undefined
        ? INJURY[p.injuryStatus] : p.injuryStatus) : null,
    };
  }

  function scoringOf(settings) {
    const items = ((settings || {}).scoringSettings || {}).scoringItems || [];
    const rec = items.find(i => i.statId === 53);
    const pts = rec ? (rec.points || 0) : 0;
    if (pts >= 1) return "ppr";
    if (pts > 0) return "half";
    return "std";
  }

  function slotsOf(settings) {
    const counts = ((settings || {}).rosterSettings || {}).lineupSlotCounts || {};
    const out = [];
    for (const id in counts) {
      const n = counts[id];
      if (!n || BENCH.has(Number(id))) continue;
      const name = SLOT[Number(id)];
      if (!name) continue;
      for (let i = 0; i < n; i++) out.push(name);
    }
    return out;
  }

  /* Teams: ESPN moved the display name around over the years, so try
     the modern field first and fall back to the old two-part one. */
  const teamName = (t) =>
    (t.name || `${t.location || ""} ${t.nickname || ""}`.trim()
      || t.abbrev || `Team ${t.id}`).trim();

  /* -------------------------------------------------- league listing */

  /* Enough of a league to show "is this the right one, and which team
     is yours" before committing to the full pull. */
  async function preview(leagueId, season) {
    const d = await league(leagueId, season, ["mTeam", "mSettings"]);
    return {
      leagueId: String(leagueId),
      name: (d.settings || {}).name || `League ${leagueId}`,
      season: String(season),
      teams: (d.teams || []).map(t => ({ id: t.id, name: teamName(t) })),
    };
  }

  /* --------------------------------------------------------- context */

  async function context(cfg) {
    const season = cfg.season;
    const base = await league(cfg.leagueId, season,
      ["mTeam", "mSettings", "mRoster", "mMatchupScore"],
      cfg.week ? { scoringPeriodId: cfg.week } : {});

    const settings = base.settings || {};
    const status = base.status || {};
    /* scoringPeriodId is the NFL week; currentMatchupPeriod is the
       fantasy week. They differ only in leagues with multi-week
       matchups, which we don't model — take the scoring period. */
    const week = cfg.week || base.scoringPeriodId || status.latestScoringPeriod || 1;
    const scoring = scoringOf(settings);

    const players = {};
    const proj = {};
    const live = {};
    const owner = {};

    const teams = (base.teams || []).map(t => {
      const entries = ((t.roster || {}).entries) || [];
      const ids = [];
      const starters = [];
      for (const e of entries) {
        const p = (e.playerPoolEntry || {}).player;
        if (!p) continue;
        const id = String(p.id);
        const info = playerOf(p);
        if (!info.pos) continue;
        players[id] = info;
        owner[id] = t.id;
        ids.push(id);
        if (!BENCH.has(e.lineupSlotId)) starters.push(id);
        const pr = statFor(p, week, 1);
        if (pr !== null && pr > 0) proj[id] = pr;
        const ac = statFor(p, week, 0);
        if (ac !== null) live[id] = ac;
      }
      const rec = t.record ? (t.record.overall || {}) : {};
      return {
        id: t.id,
        name: teamName(t),
        mine: String(t.id) === String(cfg.teamKey),
        players: ids,
        starters,
        w: rec.wins || 0, l: rec.losses || 0, t: rec.ties || 0,
        pf: rec.pointsFor || t.points || 0,
        pa: rec.pointsAgainst || 0,
      };
    });

    /* this week's pairings, out of the season schedule */
    const pairing = {};
    for (const m of base.schedule || []) {
      if (m.matchupPeriodId !== week) continue;
      const h = (m.home || {}).teamId, a = (m.away || {}).teamId;
      if (h != null) pairing[h] = m.id;
      if (a != null) pairing[a] = m.id;
    }
    for (const t of teams) t.matchupId = pairing[t.id];

    const myTeam = teams.find(t => t.mine) || null;
    const opponent = myTeam && myTeam.matchupId != null
      ? teams.find(t => t.id !== myTeam.id && t.matchupId === myTeam.matchupId) || null
      : null;

    /* Free agents come from a separate call with a filter header. It's
       the one thing ESPN does better than Sleeper here: we get real
       ownership percentages and only players who are genuinely
       available, rather than everyone minus everyone's roster. */
    const pool = [];
    for (const id in players) {
      pool.push({ id, ...players[id], proj: proj[id] !== undefined ? proj[id] : null,
                  ownerTeamId: owner[id], pctOwned: null });
    }
    try {
      const fa = await league(cfg.leagueId, season, ["kona_player_info"],
        { scoringPeriodId: week },
        { players: {
            filterStatus: { value: ["FREEAGENT", "WAIVERS"] },
            limit: 400,
            sortPercOwned: { sortAsc: false, sortPriority: 1 },
          } });
      for (const e of fa.players || []) {
        const p = e.player;
        if (!p) continue;
        const id = String(p.id);
        const info = playerOf(p);
        if (!info.pos || owner[id] !== undefined) continue;
        players[id] = info;
        const pr = statFor(p, week, 1);
        if (pr !== null && pr > 0) proj[id] = pr;
        const ac = statFor(p, week, 0);
        if (ac !== null) live[id] = ac;
        pool.push({ id, ...info, proj: proj[id] !== undefined ? proj[id] : null,
                    ownerTeamId: null,
                    pctOwned: ((p.ownership || {}).percentOwned) ?? null });
      }
    } catch (e) {
      console.warn("ESPN free agents unavailable:", e.message);
    }

    /* A week counts as done only once it's behind both the league's
       matchup pointer and the week we're showing. */
    const completed = Math.max(0,
      Math.min((status.currentMatchupPeriod || week) - 1, week - 1));

    return {
      kind: "espn",
      leagueId: String(cfg.leagueId),
      leagueName: settings.name || `League ${cfg.leagueId}`,
      season: String(season), week, scoring, slots: slotsOf(settings),
      players, teams, proj, live, pool, myTeam, opponent,
      completedWeeks: completed,
      scores: async (w) => {
        const out = [];
        for (const m of base.schedule || []) {
          if (m.matchupPeriodId !== w) continue;
          for (const side of ["home", "away"]) {
            const s = m[side];
            if (!s || s.teamId == null) continue;
            const byWeek = s.pointsByScoringPeriod || {};
            const pts = byWeek[w] !== undefined ? byWeek[w] : s.totalPoints;
            if (typeof pts === "number") {
              out.push({ teamId: s.teamId, matchupId: m.id, points: pts });
            }
          }
        }
        return out;
      },
      /* Transactions are the one thing ESPN doesn't hand over cleanly.
         `mTransactions2` accepts the request and answers 200 with no
         `transactions` key at all on the leagues we could test against,
         so we can't tell "this league had no moves" apart from "ESPN
         didn't answer the question". Rather than render an empty list
         that reads like the former, say which one it is.
         (Valid filterType values are WAIVER / FREEAGENT / ROSTER /
         TRADE_ACCEPT / DRAFT — TRADE and LINEUP are rejected with a
         400, which is worth writing down since it isn't documented.) */
      moves: async (from, to) => {
        try {
          const d = await league(cfg.leagueId, season, ["mTransactions2"], {},
            { transactions: {
                filterType: { value: ["WAIVER", "FREEAGENT", "TRADE_ACCEPT"] },
                limit: 200,
              } });
          if (!Array.isArray(d.transactions)) {
            return { ok: false, why: "ESPN didn't return a transaction log "
              + "for this league. Sleeper leagues show one here." };
          }
          const items = d.transactions
            .filter(t => (t.scoringPeriodId || 0) >= from
              && (t.scoringPeriodId || 0) <= to)
            .map(t => ({
              week: t.scoringPeriodId,
              type: t.type === "FREEAGENT" ? "add"
                : t.type === "WAIVER" ? "waiver" : "trade",
              teamIds: [...new Set((t.items || []).map(i => i.toTeamId)
                .filter(x => x != null && x !== 0))],
              adds: (t.items || []).filter(i => i.type === "ADD")
                .map(i => ({ id: String(i.playerId), teamId: i.toTeamId })),
              drops: (t.items || []).filter(i => i.type === "DROP")
                .map(i => ({ id: String(i.playerId), teamId: i.fromTeamId })),
              when: t.proposedDate || 0,
            }))
            .sort((a, b) => b.when - a.when);
          return { ok: true, items };
        } catch (e) {
          return { ok: false,
                   why: Copy.fill("league.moves.error", { error: e.message }) };
        }
      },
    };
  }

  return { preview, context, league, extension, myLeagues,
           PRO_TEAM, POSITION, SLOT };
})();
