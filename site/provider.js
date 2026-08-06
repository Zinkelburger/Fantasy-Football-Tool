/* One league, one shape, whatever site it came from.
 *
 * Sleeper and ESPN model a fantasy league differently enough that
 * letting either one leak into the page code means writing every
 * feature twice. So each service gets an adapter (sleeper.js, espn.js)
 * whose only job is to return the context below, and live.js /
 * league.js are written against that and never see a raw API again.
 *
 * ---------------------------------------------------------------- ctx
 *   kind        "sleeper" | "espn"
 *   leagueId    string        leagueName  string
 *   season      string        week        number (the scoring week)
 *   scoring     "std" | "half" | "ppr"
 *   slots       ["QB","RB","RB","WR","WR","TE","FLEX","DST","K"]
 *                             starting slots only, normalised names
 *   players     {id: {name, pos, team, inj}}
 *   teams       [{id, name, mine, players[], starters[], w,l,t, pf,pa}]
 *   proj        {id: points}  this week, in the league's own scoring
 *   live        {id: points}  this week so far
 *   pool        [{id,...,proj, ownerTeamId|null, pctOwned|null}]
 *                             the waiver universe: rostered + available
 *   myTeam, opponent          this week's matchup, either may be null
 *   completedWeeks            weeks that are actually finished
 *   scores(week)  -> [{teamId, matchupId, points}]
 *   moves(a, b)   -> [{week, type, teamIds[], adds[], drops[], when}]
 *
 * Positions are normalised to QB/RB/WR/TE/K/DST everywhere. Flex slots
 * are FLEX (RB/WR/TE), WRRB_FLEX, REC_FLEX, SUPERFLEX.
 */
"use strict";

const Provider = (() => {
  const FLEX = {
    FLEX: ["RB", "WR", "TE"],
    WRRB_FLEX: ["RB", "WR"],
    REC_FLEX: ["WR", "TE"],
    SUPERFLEX: ["QB", "RB", "WR", "TE"],
  };

  let ctx = null;
  let ctxKey = null;

  const keyOf = (cfg) => `${cfg.kind}:${cfg.leagueId}:${cfg.teamKey}`;

  async function load(cfg, force) {
    const k = keyOf(cfg);
    if (ctx && ctxKey === k && !force) return ctx;
    const adapter = cfg.kind === "espn" ? Espn : Sleeper;
    const c = await adapter.context(cfg);
    ctx = c;
    ctxKey = k;
    return c;
  }

  function invalidate() { ctx = null; ctxKey = null; }

  /* ------------------------------------------------------- lineups */

  /* The best legal starting lineup out of a set of players, and what it
     projects. Strict slots are filled first out of a globally sorted
     pool, then the flexes take what's left — which is optimal here
     because the strict slots don't compete with each other and the
     flexes only ever see leftovers.

     `extra` lets a caller ask "what if I also had this guy", which is
     how the waiver page prices a pickup. */
  function bestLineup(playerIds, ctx, extra) {
    const ids = extra ? playerIds.concat([extra]) : playerIds;
    const pool = ids
      .map(id => ({ id, pos: (ctx.players[id] || {}).pos,
                    pr: ctx.proj[id] || 0 }))
      .filter(p => p.pos)
      .sort((a, b) => b.pr - a.pr);

    const used = new Set();
    const picked = [];
    let total = 0;
    /* strict slots before flexes; stable sort keeps the league's own
       slot order within each group */
    const order = ctx.slots
      .map((s, i) => ({ s, i }))
      .sort((a, b) => (FLEX[a.s] ? 1 : 0) - (FLEX[b.s] ? 1 : 0) || a.i - b.i);

    for (const { s } of order) {
      const ok = FLEX[s] || [s];
      const pick = pool.find(p => !used.has(p.id) && ok.includes(p.pos));
      if (pick) {
        used.add(pick.id);
        total += pick.pr;
        picked.push({ slot: s, id: pick.id, pr: pick.pr });
      } else {
        picked.push({ slot: s, id: null, pr: 0 });
      }
    }
    return { total, picked, used };
  }

  /* What adding this player would do to your best lineup this week.
     Zero means he doesn't crack it — which is the honest answer to
     "should I pick him up", and a number anyone can read. */
  function lineupUpgrade(playerId, ctx) {
    if (!ctx.myTeam) return 0;
    const base = bestLineup(ctx.myTeam.players, ctx).total;
    const with_ = bestLineup(ctx.myTeam.players, ctx, playerId).total;
    return Math.max(0, with_ - base);
  }

  /* Slots this league actually starts, per position — used to explain
     roster shape and to size the "who's startable" question. */
  function slotCounts(ctx) {
    const out = {};
    for (const s of ctx.slots) out[s] = (out[s] || 0) + 1;
    return out;
  }

  return { load, invalidate, bestLineup, lineupUpgrade, slotCounts, FLEX };
})();
