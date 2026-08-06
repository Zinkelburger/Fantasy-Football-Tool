/* Live matchup tracking: finding 35's model, running in your browser.
 *
 * Three feeds, none of which needs a key or a backend:
 *   - your league        (provider.js: Sleeper or ESPN)
 *   - ESPN scoreboard    (site.api.espn.com, CORS *)  the game clock
 *   - us                 (data/ingame.json)            the model
 *
 * The model, from findings/35-in-game-model.md:
 *   remaining = decay[pos] x projection x (seconds left / 3600)
 *   sigma     = the fitted full-game spread for that projection, scaled
 *               down the measured clock curve
 *   draw      = pass-catchers independent of each other, the QB built
 *               out of his own pass-catchers, opposing QBs sharing a
 *               game factor
 *   win prob  = P(mine > theirs) over 10k draws, shrunk 0.87 to 50%
 *
 * Three things this file used to get wrong, all fixed here and all
 * worth naming because each one moved the printed number:
 *
 * 1. **Sigma was scaled by the clock twice.** `sigma_var_fn` is fit at
 *    kickoff — it maps a *full game's* projection to a *full game's*
 *    spread. The old code fed it the already-clock-scaled mean and then
 *    multiplied by sqrt(fraction left) on top, which made a halftime
 *    matchup roughly 17% narrower than the data says. Now the variance
 *    function is evaluated where it was fit, and the clock scaling
 *    comes from the measured sigma-by-clock table.
 *
 * 2. **Two receivers on one team were correlated 0.28.** The old draw
 *    put WR/TE on a shared team shock, which forces WR-to-WR to equal
 *    QB-to-WR. Finding 35 measured WR-to-WR at 0.00 and said so
 *    explicitly. Now pass-catchers are drawn independently and the QB
 *    is built out of them, which reproduces every measured pair.
 *
 * 3. **Players who cannot score were given points.** A starter on a bye
 *    got a positional average and a full 3,600 seconds, inventing about
 *    nine points that could never arrive. Nobody without a projection
 *    gets one now, and the page says which players it can't see.
 */
"use strict";

const Live = (() => {
  const SCOREBOARD =
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard";
  const SIMS = 10000;

  let params = null;    // data/ingame.json
  let timer = null;

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    return r.json();
  }

  /* --------------------------------------------------------- the model */

  /* Seconds left in a player's game. No game at all means a bye, which
     is zero — not a full game, which is what the old code assumed and
     is how bye-week starters used to earn imaginary points. */
  function secondsLeft(game) {
    if (!game) return 0;
    if (game.state === "pre") return 3600;
    if (game.state === "post") return 0;
    const [m, s] = (game.clock || "0:00").split(":").map(Number);
    const inQuarter = (m || 0) * 60 + (s || 0);
    const quartersLeft = Math.max(0, 4 - (game.period || 1));
    return Math.min(3600, quartersLeft * 900 + inQuarter);
  }

  /* How much of a full game's uncertainty is still ahead at this clock
     reading, straight off the fitted table (interpolated between its
     300-second checkpoints). This replaces the sqrt(fraction) guess:
     for a running back at halftime the table says 0.665 where the
     square root says 0.707. */
  function clockScale(pos, secLeft) {
    const table = (params.sigma || {})[pos];
    if (!table) return Math.sqrt(secLeft / 3600);
    const full = table["3600"];
    if (!full) return Math.sqrt(secLeft / 3600);
    const keys = Object.keys(table).map(Number).sort((a, b) => a - b);
    if (secLeft <= keys[0]) return (table[keys[0]] / full) * (secLeft / keys[0]);
    for (let i = 1; i < keys.length; i++) {
      if (secLeft <= keys[i]) {
        const a = keys[i - 1], b = keys[i];
        const w = (secLeft - a) / (b - a);
        return ((1 - w) * table[a] + w * table[b]) / full;
      }
    }
    return 1;
  }

  /* Full-game spread for a full-game projection, where the variance
     function was actually fit. */
  function sigmaAtKickoff(pos, kickoffPred) {
    const c = (params.sigma_var_fn || {})[pos];
    const flat = ((params.sigma || {})[pos] || {})["3600"];
    if (!c) return flat || 6;
    const v = c[0] + c[1] * kickoffPred + c[2] * kickoffPred * kickoffPred;
    const floor = Math.pow(0.25 * (flat || 6), 2);
    return Math.sqrt(Math.max(v, floor));
  }

  /* One player's expected rest-of-game points. */
  function remaining(p) {
    if (!p.playable) return 0;
    const decay = (params.decay || {})[p.pos];
    if (decay === undefined) return 0;
    return decay * p.proj * (p.secLeft / 3600);
  }

  function sdOf(p) {
    if (!p.playable || p.secLeft <= 0) return 0;
    const decay = (params.decay || {})[p.pos] || 0.92;
    return sigmaAtKickoff(p.pos, decay * p.proj) * clockScale(p.pos, p.secLeft);
  }

  function gauss(rng) {
    let u = 0, v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /* mulberry32 — seeded, so the number doesn't jitter between refreshes
     when nothing about the games has actually changed. */
  function seeded(seed) {
    let a = seed >>> 0;
    return () => {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* The correlation structure, built the way finding 35 says the data
     implies rather than the way that's convenient.

     Every skill player draws his own independent shock. A quarterback
     is then assembled out of the pass-catchers of his that are in the
     same lineup, plus a game factor he shares with the opposing
     quarterback, plus whatever is left over as his own. Loading his own
     receivers with weight r reproduces corr(QB, that receiver) = r
     exactly, and leaves receiver-to-receiver at zero, which is what was
     measured. If none of his receivers are in the lineup there's
     nothing to load onto and he's simply independent — also correct. */
  function lineupPlan(lineup) {
    const C = params.correlation || {};
    const W = { WR: C.qb_wr_same_team ?? 0.277, TE: C.qb_te_same_team ?? 0.219,
                RB: C.qb_rb_same_team ?? 0.054 };
    const rhoGame = C.qb_qb_opposing ?? 0.123;

    const games = [...new Set(lineup.map(p => p.gameId))];
    return lineup.map((p, i) => {
      if (p.pos !== "QB") return { i, kind: "plain" };
      /* his own pass-catchers, in this lineup */
      const mates = [];
      let sumSq = 0;
      lineup.forEach((q, j) => {
        if (j === i || q.team !== p.team || !W[q.pos]) return;
        const w = W[q.pos];
        if (sumSq + w * w + rhoGame > 0.98) return;   // keep the QB's own share real
        mates.push({ j, w });
        sumSq += w * w;
      });
      const own = Math.sqrt(Math.max(0, 1 - sumSq - rhoGame));
      return { i, kind: "qb", mates, own, rhoGame,
               game: games.indexOf(p.gameId) };
    });
  }

  /* Simulate one lineup's remaining points SIMS times. */
  function simulate(lineup, rng, gameShocks) {
    const plan = lineupPlan(lineup);
    const mu = lineup.map(remaining);
    const sd = lineup.map(sdOf);
    const out = new Float64Array(SIMS);
    const z = new Float64Array(lineup.length);

    for (let s = 0; s < SIMS; s++) {
      for (let i = 0; i < lineup.length; i++) z[i] = gauss(rng);
      let total = 0;
      for (const step of plan) {
        const i = step.i;
        if (mu[i] <= 0 && sd[i] <= 0) continue;
        let e;
        if (step.kind === "qb") {
          e = step.own * z[i]
            + Math.sqrt(step.rhoGame) * gameShocks[step.game][s];
          for (const m of step.mates) e += m.w * z[m.j];
        } else {
          e = z[i];
        }
        total += Math.max(0, mu[i] + e * sd[i]);
      }
      out[s] = total;
    }
    return out;
  }

  function winProbability(mine, theirs) {
    const rng = seeded(1234567);
    /* opposing quarterbacks share their game's factor, so it has to be
       drawn once and handed to both lineups */
    const games = [...new Set(mine.concat(theirs).map(p => p.gameId))];
    const gameShocks = games.map(() => {
      const a = new Float64Array(SIMS);
      for (let s = 0; s < SIMS; s++) a[s] = gauss(rng);
      return a;
    });
    /* lineupPlan indexes games within its own lineup, so hand each side
       its shocks in that same order */
    const shockFor = (l) =>
      [...new Set(l.map(p => p.gameId))].map(g => gameShocks[games.indexOf(g)]);

    const a = simulate(mine, rng, shockFor(mine));
    const b = simulate(theirs, rng, shockFor(theirs));

    const nowMine = mine.reduce((s, p) => s + p.scored, 0);
    const nowTheirs = theirs.reduce((s, p) => s + p.scored, 0);

    let wins = 0;
    const margins = new Float64Array(SIMS);
    for (let s = 0; s < SIMS; s++) {
      const diff = (nowMine + a[s]) - (nowTheirs + b[s]);
      margins[s] = diff;
      if (diff > 0) wins++;
    }
    const raw = wins / SIMS;
    const shrink = params.shrink || 0.87;
    margins.sort();
    return {
      raw,
      /* finding 35: the raw simulation is overconfident at the tails,
         and one shrink constant beats every structural fix tried. */
      p: 0.5 + shrink * (raw - 0.5),
      nowMine, nowTheirs,
      projMine: nowMine + a.reduce((s, v) => s + v, 0) / SIMS,
      projTheirs: nowTheirs + b.reduce((s, v) => s + v, 0) / SIMS,
      lo: margins[Math.floor(SIMS * 0.1)],
      hi: margins[Math.floor(SIMS * 0.9)],
    };
  }

  /* ------------------------------------------------------------- feeds */

  async function loadParams() {
    if (!params) params = await getJSON("data/ingame.json");
    if (!params.decay) throw new Error("ingame.json has no model in it");
  }

  /* The scoreboard for a specific week, so that looking at Sunday's
     matchup on a Tuesday doesn't read last week's clock. It also hands
     us the bye teams outright, which beats inferring them from who's
     missing. */
  async function loadGames(season, week) {
    const d = await getJSON(
      `${SCOREBOARD}?week=${week}&seasontype=2&dates=${season}`);
    const byTeam = {};
    for (const e of d.events || []) {
      const c = (e.competitions || [])[0];
      if (!c) continue;
      const st = c.status || {};
      const g = {
        id: e.id,
        state: (st.type || {}).state || "pre",
        clock: st.displayClock,
        period: st.period,
      };
      for (const t of c.competitors || []) byTeam[t.team.abbreviation] = g;
    }
    const bye = new Set(((d.week || {}).teamsOnBye || []).map(t => t.abbreviation));
    /* If the scoreboard came back thin, we can't tell a bye from a
       missing game, so don't let it zero anyone out. */
    const trustworthy = Object.keys(byTeam).length >= 20;
    return { byTeam, bye, trustworthy };
  }

  /* The two outside feeds, behind one seam. live-demo.html swaps them
     for a fixture so these pages can be worked on in August instead of
     only on a Sunday afternoon in November. */
  const feeds = { games: loadGames, league: (cfg) => Provider.load(cfg, true) };

  /* ---------------------------------------------------------- assembly */

  /* A starting lineup, in the shape the model wants. Anyone who cannot
     score — on a bye, ruled out, or with no projection anywhere — is
     marked unplayable rather than handed a stand-in number. */
  function lineupOf(team, ctx, games) {
    return (team.starters || []).map(id => {
      const info = ctx.players[id] || { name: `#${id}`, pos: "WR", team: null };
      const game = info.team ? games.byTeam[info.team] : null;
      const onBye = info.team ? games.bye.has(info.team) : false;
      const proj = ctx.proj[id];
      const ruledOut = info.inj === "O" || info.inj === "IR"
        || info.inj === "SUSP" || info.inj === "Out";
      const secLeft = game ? secondsLeft(game)
        : (games.trustworthy ? 0 : 3600);

      let why = null;
      if (onBye) why = "on bye";
      else if (!info.team) why = "no NFL team";
      else if (ruledOut) why = "ruled out";
      else if (proj === undefined) why = "no projection";

      return {
        id, name: info.name, pos: info.pos, team: info.team, inj: info.inj,
        game, gameId: game ? game.id : `none-${info.team || id}`,
        secLeft: (onBye || ruledOut) ? 0 : secLeft,
        scored: ctx.live[id] || 0,
        proj: proj === undefined ? 0 : proj,
        playable: !onBye && !ruledOut && proj !== undefined,
        why,
      };
    });
  }

  /* ------------------------------------------------------------ render */

  function probColor(p) {
    if (p >= 0.65) return "var(--green)";
    if (p <= 0.35) return "var(--red)";
    return "var(--yellow)";
  }

  function playerRow(p) {
    const row = el("div", "live-player" + (p.playable ? "" : " is-dark"));
    row.append(el("span", `live-pos pos-${(p.pos || "wr").toLowerCase()}`, p.pos));
    const name = el("div", "live-name");
    name.append(el("span", "", p.name));
    const st = el("span", "live-gamestate");
    if (p.why) st.textContent = p.why;
    else if (!p.game) st.textContent = "no game";
    else if (p.game.state === "pre") st.textContent = "yet to play";
    else if (p.game.state === "post") st.textContent = "final";
    else st.textContent = `Q${p.game.period} ${p.game.clock}`;
    if (p.game && p.game.state === "in" && !p.why) st.classList.add("is-live");
    name.append(st);
    row.append(name);
    row.append(el("div", "live-score", p.scored.toFixed(1)));
    const rest = remaining(p);
    const rem = el("div", "live-rem", rest > 0.05 ? `+${rest.toFixed(1)}` : "—");
    rem.title = p.why
      ? Copy.fill("matchup.tip.no-remaining", { why: p.why })
      : Copy.text("matchup.tip.remaining");
    row.append(rem);
    return row;
  }

  function renderMatchup(root, d) {
    root.innerHTML = "";
    const { week, mine, opp, mineName, oppName, wp } = d;

    const head = el("div", "live-head");
    const pct = el("div", "live-prob");
    pct.style.color = probColor(wp.p);
    pct.textContent = `${Math.round(wp.p * 100)}%`;
    const lab = el("div", "live-prob-label");
    lab.append(el("div", "", Copy.text("matchup.prob.label")));
    lab.append(el("div", "dim", Copy.text("matchup.prob.caveat")));
    head.append(pct, lab);
    root.append(head);

    const bar = el("div", "live-bar");
    const fill = el("div", "live-bar-fill");
    fill.style.width = `${Math.round(wp.p * 100)}%`;
    fill.style.background = probColor(wp.p);
    bar.append(fill);
    root.append(bar);

    const score = el("div", "live-scoreline");
    for (const [name, now, proj] of [[mineName, wp.nowMine, wp.projMine],
                                     [oppName, wp.nowTheirs, wp.projTheirs]]) {
      const box = el("div", "live-team");
      box.append(el("div", "live-team-name", name));
      box.append(el("div", "live-team-now", now.toFixed(1)));
      box.append(el("div", "dim", `projected final ${proj.toFixed(1)}`));
      score.append(box);
    }
    root.append(score);

    const yetToPlay = mine.filter(p => p.playable && p.secLeft >= 3600).length;
    const signed = (v) => `${v > 0 ? "+" : ""}${v.toFixed(0)}`;
    root.append(el("p", "dim live-note", Copy.fill("matchup.note", {
      week, n: yetToPlay, have: yetToPlay === 1 ? "has" : "have",
      sims: SIMS.toLocaleString(), lo: signed(wp.lo), hi: signed(wp.hi),
    })));

    /* Say out loud who the model is writing off, rather than letting a
       bye-week starter quietly count for nothing. */
    const dead = mine.concat(opp).filter(p => p.why);
    if (dead.length) {
      root.append(el("p", "dim live-note", Copy.fill("matchup.dead", {
        names: dead.map(p => `${p.name} (${p.why})`).join(", "),
      })));
    }

    const cols = el("div", "live-cols");
    for (const [name, side] of [[mineName, mine], [oppName, opp]]) {
      const col = el("div", "live-col");
      const h = el("div", "live-col-head");
      h.append(el("span", "", name), el("span", "dim", "now / left"));
      col.append(h);
      for (const p of side) col.append(playerRow(p));
      cols.append(col);
    }
    root.append(cols);
  }

  /* ------------------------------------------------------------- flow */

  async function refresh(root, cfg) {
    const ctx = await feeds.league(cfg);
    if (!ctx.myTeam) {
      root.innerHTML = "";
      root.append(el("p", "dim", Copy.text("matchup.no-team")));
      return;
    }
    if (!ctx.opponent) {
      root.innerHTML = "";
      root.append(el("p", "dim",
        Copy.fill("matchup.no-opponent", { week: ctx.week })));
      return;
    }
    const games = await feeds.games(ctx.season, ctx.week);
    const mine = lineupOf(ctx.myTeam, ctx, games);
    const opp = lineupOf(ctx.opponent, ctx, games);
    const wp = winProbability(mine, opp);
    renderMatchup(root, {
      week: ctx.week, mine, opp,
      mineName: ctx.myTeam.name, oppName: ctx.opponent.name, wp,
    });
  }

  function startPolling(root, cfg) {
    if (timer) clearInterval(timer);
    const tick = () => refresh(root, cfg).catch(e => {
      console.error(e);
      root.innerHTML = "";
      root.append(el("p", "load-error",
        Copy.fill("matchup.error", { error: e.message })));
    });
    tick();
    timer = setInterval(tick, 60000);   // a minute is plenty; the clock is the model
  }

  function stopPolling() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  const init = () => loadParams();

  return { init, startPolling, stopPolling, feeds, lineupOf,
           /* exported for the node tests and the console */
           _model: { remaining, sdOf, secondsLeft, clockScale, sigmaAtKickoff,
                     winProbability, lineupPlan, setParams: (p) => { params = p; } } };
})();
