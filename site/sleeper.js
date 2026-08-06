/* Sleeper: raw API client, and the adapter that normalises it.
 *
 * Sleeper is CORS-open and needs no key or login of any kind, which is
 * why a static site can do a whole in-season product against it (see
 * docs/DATA-SOURCES.md §6). Everything here is a plain GET.
 *
 * Caching, because one payload is enormous:
 *   players      14.6MB raw / 2.5MB gzipped — localStorage for a day,
 *                filtered down to ~0.4MB before it's stored (Sleeper
 *                asks for at most one fetch a day)
 *   projections  ~0.5MB per week — memory, per session
 *   everything else is small and refetched, since it moves during games
 *
 * A note on projection coverage, because it matters upstream: the
 * projections endpoint answers with ~9,400 player ids, but only about
 * 810 of them carry a points field. The rest are deep-roster bodies
 * with nothing but an ADP stub. Anyone without a number gets no number
 * — see live.js on why inventing one is worse than admitting it.
 */
"use strict";

const Sleeper = (() => {
  const BASE = "https://api.sleeper.app/v1";
  const STORE = "ff_sleeper_v1";
  const DAY = 86400000;
  const mem = {};

  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    return r.json();
  }

  const store = () => {
    try { return JSON.parse(localStorage.getItem(STORE)) || {}; }
    catch (e) { return {}; }
  };
  const put = (o) => {
    try { localStorage.setItem(STORE, JSON.stringify(o)); }
    catch (e) { /* private mode, or the quota is full */ }
  };

  const cached = (key, fn) => {
    if (!mem[key]) mem[key] = fn().catch(e => { delete mem[key]; throw e; });
    return mem[key];
  };

  /* ------------------------------------------------------------ raw */
  const state = () => cached("state", () => getJSON(`${BASE}/state/nfl`));

  async function user(username) {
    const u = await getJSON(`${BASE}/user/${encodeURIComponent(username)}`);
    /* Sleeper answers an unknown username with null and HTTP 200. */
    if (!u || !u.user_id) throw new Error("No Sleeper account with that username.");
    return u;
  }

  const leagues = (userId, season) =>
    getJSON(`${BASE}/user/${userId}/leagues/nfl/${season}`);
  const league = (id) => cached(`lg:${id}`, () => getJSON(`${BASE}/league/${id}`));
  const rosters = (id) => getJSON(`${BASE}/league/${id}/rosters`);
  const users = (id) => cached(`us:${id}`, () => getJSON(`${BASE}/league/${id}/users`));
  const matchups = (id, week) => getJSON(`${BASE}/league/${id}/matchups/${week}`);
  const transactions = (id, week) =>
    getJSON(`${BASE}/league/${id}/transactions/${week}`);

  async function players() {
    const s = store();
    if (s.players && Date.now() - (s.playersAt || 0) < DAY) return s.players;
    const raw = await getJSON(`${BASE}/players/nfl`);
    const out = {};
    for (const id in raw) {
      const p = raw[id];
      if (!["QB", "RB", "WR", "TE", "K", "DEF"].includes(p.position)) continue;
      out[id] = {
        name: p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim() || id,
        pos: p.position === "DEF" ? "DST" : p.position,
        team: p.team || null,
        inj: p.injury_status || null,
      };
    }
    const next = store();
    next.players = out;
    next.playersAt = Date.now();
    put(next);
    return out;
  }

  const projections = (season, week) =>
    cached(`pr:${season}:${week}`, () =>
      getJSON(`${BASE}/projections/nfl/regular/${season}/${week}`).catch(() => ({})));

  /* ----------------------------------------------------- normalising */

  /* Which points field to read, from the league's own scoring rules. */
  function scoringOf(lg) {
    const rec = ((lg || {}).scoring_settings || {}).rec;
    if (rec >= 1) return "ppr";
    if (rec > 0) return "half";
    return "std";
  }
  const PTS = { std: "pts_std", half: "pts_half_ppr", ppr: "pts_ppr" };

  const SLOT = { QB: "QB", RB: "RB", WR: "WR", TE: "TE", K: "K", DEF: "DST",
                 FLEX: "FLEX", WRRB_FLEX: "WRRB_FLEX", REC_FLEX: "REC_FLEX",
                 SUPER_FLEX: "SUPERFLEX", IDP_FLEX: null };

  function slotsOf(lg) {
    return ((lg || {}).roster_positions || [])
      .map(s => SLOT[s] === undefined ? null : SLOT[s])
      .filter(Boolean);
  }

  async function context(cfg) {
    const st = await state();
    /* Sleeper rolls `week` forward the moment a week's games are done,
       so it is the week you are about to play, which is the one to
       show. In the preseason it is 0. */
    const week = Math.max(1, st.week || 1);
    const [lg, rst, usr, plyrs, pr] = await Promise.all([
      league(cfg.leagueId), rosters(cfg.leagueId), users(cfg.leagueId),
      players(), projections(st.season, week),
    ]);
    const mus = await matchups(cfg.leagueId, week).catch(() => []);

    const scoring = scoringOf(lg);
    const field = PTS[scoring];
    const proj = {};
    for (const id in pr) {
      const v = pr[id][field];
      if (typeof v === "number" && v > 0) proj[id] = v;
    }

    const muOf = (rosterId) => mus.find(m => m.roster_id === rosterId) || {};
    const live = {};
    for (const m of mus) {
      for (const id in m.players_points || {}) live[id] = m.players_points[id];
    }

    const teams = rst.map(r => {
      const u = usr.find(x => x.user_id === r.owner_id);
      const s = r.settings || {};
      const m = muOf(r.roster_id);
      return {
        id: r.roster_id,
        name: (u && (u.metadata || {}).team_name) || (u && u.display_name)
          || `Team ${r.roster_id}`,
        mine: r.owner_id === cfg.teamKey,
        players: (r.players || []).filter(id => id && id !== "0"),
        starters: (m.starters || []).filter(id => id && id !== "0"),
        matchupId: m.matchup_id,
        w: s.wins || 0, l: s.losses || 0, t: s.ties || 0,
        pf: (s.fpts || 0) + (s.fpts_decimal || 0) / 100,
        pa: (s.fpts_against || 0) + (s.fpts_against_decimal || 0) / 100,
      };
    });

    const myTeam = teams.find(t => t.mine) || null;
    const opponent = myTeam && myTeam.matchupId != null
      ? teams.find(t => t.id !== myTeam.id && t.matchupId === myTeam.matchupId) || null
      : null;

    const owner = {};
    for (const t of teams) for (const id of t.players) owner[id] = t.id;

    /* The waiver universe. Sleeper has no free-agent endpoint — anyone
       not on a roster is free — so this is every player with an NFL
       team, which is about 1,050 of the 4,260 we keep. */
    const pool = [];
    for (const id in plyrs) {
      const p = plyrs[id];
      if (!p.team && owner[id] === undefined) continue;
      pool.push({ id, name: p.name, pos: p.pos, team: p.team, inj: p.inj,
                  proj: proj[id] !== undefined ? proj[id] : null,
                  ownerTeamId: owner[id] !== undefined ? owner[id] : null,
                  pctOwned: null });
    }

    return {
      kind: "sleeper",
      leagueId: cfg.leagueId, leagueName: lg.name,
      season: st.season, week, scoring, slots: slotsOf(lg),
      players: plyrs, teams, proj, live, pool, myTeam, opponent,
      /* a week only counts once it is behind us */
      completedWeeks: Math.max(0, week - 1),
      scores: async (w) => {
        const ms = await matchups(cfg.leagueId, w).catch(() => []);
        return (ms || [])
          .filter(m => typeof m.points === "number")
          .map(m => ({ teamId: m.roster_id, matchupId: m.matchup_id,
                       points: m.points }));
      },
      moves: async (from, to) => {
        const weeks = [];
        for (let w = from; w <= to; w++) weeks.push(w);
        const all = await Promise.all(weeks.map(w =>
          transactions(cfg.leagueId, w)
            .then(x => (x || []).map(t => ({ ...t, week: w })))
            .catch(() => [])));
        const items = all.flat()
          .filter(t => t.status === "complete")
          .sort((a, b) => (b.status_updated || 0) - (a.status_updated || 0))
          .map(t => ({
            week: t.week,
            type: t.type === "free_agent" ? "add" : t.type,
            teamIds: t.roster_ids || [],
            adds: Object.keys(t.adds || {}).map(id => ({ id, teamId: t.adds[id] })),
            drops: Object.keys(t.drops || {}).map(id => ({ id, teamId: t.drops[id] })),
            when: t.status_updated || 0,
          }));
        return { ok: true, items };
      },
    };
  }

  return { state, user, leagues, league, rosters, users, matchups,
           transactions, players, projections, context, scoringOf, slotsOf };
})();
