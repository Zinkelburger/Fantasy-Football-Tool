/* Static SPA: hash routing over prebuilt JSON (site/build_site.py). */
"use strict";

const VIEWS = ["home", "live", "weekly", "board", "blog", "post", "cheat",
  "models", "draft"];
const cache = {};

async function data(name) {
  if (!cache[name]) {
    const r = await fetch(`data/${name}.json`);
    if (!r.ok) throw new Error(`data/${name}.json: HTTP ${r.status}`);
    cache[name] = await r.json();
  }
  return cache[name];
}

/* One banner per view: shown when that view's data fetch fails, cleared
   on the next visit so navigation back retries the load.

   `:scope >` matters. We prepend the banner as a direct child, but views
   own error slots of their own further down — My league has one inside
   its connect form — and an unscoped query found that instead and
   deleted it on the first navigation. Every later attempt to show a
   connect error then threw on a missing element, which is why a wrong
   league id used to fail in silence. */
function loadError(viewId, on) {
  const view = document.getElementById(viewId);
  const old = view.querySelector(":scope > .load-error");
  if (!on) { if (old) old.remove(); return; }
  if (old) return;
  const p = document.createElement("p");
  p.className = "load-error";
  p.textContent = Copy.text("error.load");
  view.prepend(p);
}

/* ------------------------------------------------------------ router */
function route() {
  const hash = location.hash.replace(/^#\/?/, "");
  let [page, arg] = hash.split("/");
  if (page === "blog" && arg) page = "post"; /* #/blog/<slug> deep link */
  const view = VIEWS.includes(page) ? page : "home";

  document.body.classList.toggle("draft-mode", view === "draft");
  for (const v of VIEWS) {
    document.getElementById(`view-${v}`).hidden = v !== view;
  }
  let activeLink = null;
  document.querySelectorAll("#site-nav a").forEach(a => {
    const on = a.dataset.route === view
      || (view === "post" && a.dataset.route === "blog");
    a.classList.toggle("active", on);
    if (on) activeLink = a;
  });
  // On a phone the nav is one swipeable row, so the link for the page you're
  // on is often off the right edge — where a highlight nobody can see is the
  // same as no highlight. Pull it into view.
  if (activeLink && document.getElementById("site-nav").scrollWidth
      > document.getElementById("site-nav").clientWidth) {
    activeLink.scrollIntoView({ block: "nearest", inline: "center" });
  }

  loadError(`view-${view}`, false);
  const guard = p => p.catch(err => {
    console.error(err);
    loadError(`view-${view}`, true);
  });
  if (view === "weekly") guard(renderWeekly());
  if (view === "board") guard(renderBoard());
  if (view === "blog") guard(renderBlogList());
  if (view === "post" && arg) guard(renderPost(arg));
  if (view === "cheat") guard(renderCheat());
  if (view === "live") guard(renderLive(arg)); else Live.stopPolling();
  if (view === "draft") {
    const f = document.getElementById("draft-frame");
    if (!f.src) f.src = "../webapp/index.html";
  }
  if (view !== "post") window.scrollTo(0, 0);
}

/* Hover copy for the weekly and draft tables lives in site/copy.md under
   the tip.* keys, alongside the rest of the site's words. Every number in
   it is a measured effect from the K/DST findings, not a rule of thumb —
   keep them in sync with findings 27 and 28 if either model is refit. */

/* ------------------------------------------------------------ weekly
   Rows can be marked "taken" (rostered in your league) or "mine"
   (on your team) by clicking; marks persist in localStorage. */
const MARKS_KEY = "ffMarks";
let marks = {};
try { marks = JSON.parse(localStorage.getItem(MARKS_KEY)) || {}; } catch { /* fresh */ }

function saveMarks() {
  localStorage.setItem(MARKS_KEY, JSON.stringify(marks));
}

function cycleMark(key) {
  const order = [undefined, "taken", "mine"];
  const next = order[(order.indexOf(marks[key]) + 1) % order.length];
  if (next) marks[key] = next; else delete marks[key];
  saveMarks();
}

function applyWeeklyFilters() {
  const q = document.getElementById("weekly-search").value.trim().toLowerCase();
  const hideTaken = document.getElementById("weekly-hide-taken")
    .getAttribute("aria-pressed") === "true";
  document.querySelectorAll("#view-weekly tbody tr[data-mark-key]")
    .forEach(row => {
      const state = marks[row.dataset.markKey];
      row.classList.toggle("is-taken", state === "taken");
      row.classList.toggle("is-mine", state === "mine");
      row.querySelector(".mark-cell").innerHTML = state
        ? `<span class="mark-chip ${state}">${state}</span>` : "";
      row.hidden = (q && !row.dataset.search.includes(q))
        || (hideTaken && state === "taken");
    });
}

let weeklyDone = false;
async function renderWeekly() {
  const w = await data("weekly");
  document.getElementById("weekly-label").textContent = w.label;
  if (weeklyDone) { applyWeeklyFilters(); return; }
  weeklyDone = true;   /* only after the fetch — a failure must retry */

  const rowAttrs = (tab, r) =>
    `data-mark-key="${tab}:${r.team}"
     data-search="${`${r.team} ${r.opp}`.toLowerCase()}"
     title="${Copy.attr("tip.mark-row")}"`;

  const dst = document.getElementById("dst-table");
  dst.innerHTML =
    `<thead><tr><th class="rank">#</th><th>Defense</th><th>vs</th>
     <th class="num" title="${Copy.attr("tip.opp-implied")}">Opp implied</th>
     <th></th><th class="mark-col"></th></tr></thead><tbody>` +
    w.dst.map((r, i) =>
      `<tr ${rowAttrs("dst", r)}><td class="rank">${i + 1}</td>
       <td><b>${r.team}</b></td>
       <td>${r.home ? "" : "@ "}${r.opp}</td>
       <td class="num ${r.imp <= 18.5 ? "up" : ""}">${r.imp.toFixed(1)}</td>
       <td>${i < 3 ? `<span class="tag up" title="${Copy.attr("tip.stream")}">stream</span>` : ""}</td>
       <td class="mark-cell"></td></tr>`
    ).join("") + "</tbody>";

  const k = document.getElementById("k-table");
  k.innerHTML =
    `<thead><tr><th class="rank">#</th><th>Kicker slot</th><th>vs</th>
     <th class="num" title="${Copy.attr("tip.own-implied")}">Own implied</th>
     <th></th><th class="mark-col"></th></tr></thead><tbody>` +
    w.k.map((r, i) =>
      `<tr ${rowAttrs("k", r)}><td class="rank">${i + 1}</td>
       <td><b>${r.team}</b> K</td>
       <td>${r.home ? "" : "@ "}${r.opp}</td>
       <td class="num">${r.imp.toFixed(1)}</td>
       <td>${r.dome ? `<span class="tag dome" title="${Copy.attr("tip.dome")}">dome</span>` : ""}</td>
       <td class="mark-cell"></td></tr>`
    ).join("") + "</tbody>";

  document.getElementById("weekly-tabs").addEventListener("click", e => {
    const b = e.target.closest("button[data-tab]");
    if (!b) return;
    document.querySelectorAll("#weekly-tabs .tab")
      .forEach(t => t.classList.toggle("active", t === b));
    for (const pane of ["dst", "k", "skill"]) {
      document.getElementById(`weekly-${pane}`).hidden =
        pane !== b.dataset.tab;
    }
    // The shared toolbar only applies to table panes.
    document.getElementById("weekly-tools").hidden = b.dataset.tab === "skill";
  });

  document.getElementById("view-weekly").addEventListener("click", e => {
    const row = e.target.closest("tr[data-mark-key]");
    if (!row) return;
    cycleMark(row.dataset.markKey);
    applyWeeklyFilters();
  });

  document.getElementById("weekly-search")
    .addEventListener("input", applyWeeklyFilters);
  document.getElementById("weekly-hide-taken").addEventListener("click", e => {
    const b = e.currentTarget;
    b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true");
    applyWeeklyFilters();
  });
  document.getElementById("weekly-clear").addEventListener("click", () => {
    marks = {};
    saveMarks();
    applyWeeklyFilters();
  });

  applyWeeklyFilters();
}

/* ------------------------------------------------------------- board */
/* Preseason kicker and defense boards. The season-long skill-position
   projection board used to live here too; it was retired 2026-08-05
   because it ranked worse than ADP and cost title odds in simulation
   (findings 25 and 32). See archive/season-projection-model/. */
let boardDone = false;
async function renderBoard() {
  if (boardDone) return;
  const pre = await data("preseason");
  boardDone = true;   /* only after the fetch — a failure must retry */

  const SECTIONS = ["k", "dst"];
  const sections = document.getElementById("board-sections");
  sections.addEventListener("click", e => {
    const b = e.target.closest("button[data-sec]");
    if (!b) return;
    sections.querySelectorAll(".tab")
      .forEach(t => t.classList.toggle("active", t === b));
    for (const s of SECTIONS) {
      document.getElementById(`board-sec-${s}`).hidden = s !== b.dataset.sec;
    }
  });

  document.getElementById("pre-k-table").innerHTML =
    `<thead><tr><th class="rank">#</th><th>Kicker slot</th>
     <th class="num" title="${Copy.attr("tip.own-season")}">Own PPG</th>
     <th class="num" title="${Copy.attr("tip.dome-schedule")}">Dome games</th>
     </tr></thead><tbody>` +
    pre.k.map((r, i) =>
      `<tr><td class="rank">${i + 1}</td><td><b>${r.team}</b> K</td>
       <td class="num">${r.own.toFixed(1)}</td>
       <td class="num ${r.dome >= 8 ? "up" : ""}"
           title="${Copy.fillAttr("tip.dome-count", {
             dome: r.dome, games: r.games, edge: r.domeEdge.toFixed(2),
           })}">
         ${r.dome}</td></tr>`).join("") + "</tbody>";

  document.getElementById("pre-dst-table").innerHTML =
    `<thead><tr><th class="rank">#</th><th>Defense</th>
     <th class="num" title="${Copy.attr("tip.opp-season")}">Opp PPG faced</th>
     </tr></thead><tbody>` +
    pre.dst.map((r, i) =>
      `<tr><td class="rank">${i + 1}</td><td><b>${r.team}</b></td>
       <td class="num ${r.opp <= 21.5 ? "up" : ""}">${r.opp.toFixed(1)}</td>
       </tr>`).join("") + "</tbody>";
}

/* -------------------------------------------------------------- blog */
function confClass(c) {
  const s = c.toLowerCase();
  if (s.startsWith("high")) return "conf-high";
  if (s.startsWith("low")) return "conf-low";
  return "conf-med";
}

let blogDone = false;
async function renderBlogList() {
  if (blogDone) return;
  const posts = await data("blog");
  blogDone = true;   /* only after the fetch — a failure must retry */
  document.getElementById("blog-list").innerHTML = posts.map(p =>
    `<a class="post-row" href="#/blog/${p.id}">
       <h3><span class="post-num">#${String(p.num).padStart(2, "0")}</span>
       ${p.title}
       ${p.confidence ? `<span class="conf ${confClass(p.confidence)}">
         ${p.confidence}</span>` : ""}</h3>
       <p class="hook">${p.hook}</p></a>`).join("");
}

async function renderPost(id) {
  const posts = await data("blog");
  const p = posts.find(x => x.id === id);
  const el = document.getElementById("post-body");
  if (!p) { el.textContent = Copy.text("blog.notfound"); return; }
  el.innerHTML = `<h1>${p.title}</h1>` + p.html;
  window.scrollTo(0, 0);
}

/* -------------------------------------------------------- cheat sheet */
let cheatDone = false;
async function renderCheat() {
  if (cheatDone) return;
  const c = await data("cheatsheet");
  document.getElementById("cheat-body").innerHTML =
    `<h1>${c.title}</h1>` + c.html;
  cheatDone = true;
}


/* ==================================================================== */
/*  My league                                                           */
/*                                                                      */
/*  One box. Digits (or a URL with leagueId= in it) mean an ESPN        */
/*  league; anything else is a Sleeper username. Sleeper then finds     */
/*  your leagues, ESPN asks which team is yours.                        */
/*                                                                      */
/*  Better than either: if the browser extension is installed it can    */
/*  read the ESPN cookies this page can't, so it just tells us which    */
/*  leagues you're in — private ones included — and the box becomes     */
/*  something you only need for somebody else's league.                 */
/* ==================================================================== */

const LIVE_STORE = "ff_live_v2";
let liveWired = false;
let liveTab = "matchup";
let liveForce = null;      // set when you correct the ESPN/Sleeper guess
let liveFound = null;      // cached answer to "which leagues am I in?"

const liveSaved = () => {
  try { return JSON.parse(localStorage.getItem(LIVE_STORE)) || {}; }
  catch (e) { return {}; }
};
const liveSave = (o) => {
  try { localStorage.setItem(LIVE_STORE, JSON.stringify(o)); }
  catch (e) { /* private mode */ }
};

const liveEl = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

/* --- the extension, holding the same setting -------------------------
   The extension can answer questions this page can't, and the draft
   tool runs inside it, so both ends keep one copy of which league you
   are in and you only pick it once. Writing costs nothing when no
   extension is listening — the message goes nowhere. */
let liveSynced = "";
function liveSyncOut(cfg) {
  const s = JSON.stringify(cfg && cfg.leagueId ? cfg : null);
  if (s === liveSynced) return;
  liveSynced = s;
  try {
    window.postMessage(
      { source: "ffda-page", type: "save-league", cfg: JSON.parse(s) }, "*");
  } catch (e) { /* nothing listening */ }
}

/* The other direction. Adopt the extension's copy only when this
   browser has nothing saved: otherwise a stale copy would yank you out
   of the league you just picked, and our own write above would bounce
   straight back at us through storage.onChanged. */
window.addEventListener("message", (e) => {
  if (e.source !== window) return;
  const m = e.data;
  if (!m || m.source !== "ffda-ext" || m.type !== "state") return;
  const lg = (m.data || {}).league;
  if (!lg || !lg.leagueId || !lg.kind || liveSaved().leagueId) return;
  liveSave(lg);
  liveSynced = JSON.stringify(lg);
  const view = document.getElementById("view-live");
  if (view && !view.hidden) renderLive(liveTab);
});

function liveError(msg) {
  const p = document.getElementById("live-error");
  p.hidden = !msg;
  p.textContent = msg || "";
}

function showLeagueTabs(on) {
  const nav = document.getElementById("league-tabs");
  nav.hidden = !on;
  nav.querySelectorAll("a").forEach(a =>
    a.classList.toggle("active", a.dataset.tab === liveTab));
}

/* Only one of the two bodies is ever populated, so switching tabs can't
   leave a stale matchup sitting under a waiver list. */
function showLeagueTab(cfg) {
  const liveBody = document.getElementById("live-body");
  const lgBody = document.getElementById("league-body");
  showLeagueTabs(true);
  const fail = (box) => (err) => {
    console.error(err);
    box.innerHTML = "";
    const p = document.createElement("p");
    p.className = "load-error";
    p.textContent = Copy.fill("error.generic", { error: err.message });
    box.append(p);
  };
  if (liveTab === "matchup") {
    lgBody.innerHTML = "";
    lgBody.hidden = true;
    liveBody.hidden = false;
    Live.startPolling(liveBody, cfg);
  } else {
    Live.stopPolling();
    liveBody.innerHTML = "";
    liveBody.hidden = true;
    lgBody.hidden = false;
    League.render(liveTab, lgBody, cfg).catch(fail(lgBody));
  }
}

function useLeague(cfg) {
  liveSave(cfg);
  liveSyncOut(cfg);
  Provider.invalidate();
  document.getElementById("live-connect").hidden = true;
  document.getElementById("live-picked").hidden = false;
  document.getElementById("live-picked-name").textContent =
    `${cfg.leagueName} · ${cfg.teamName || "your team"}`;
  document.getElementById("live-source").textContent =
    cfg.kind === "espn" ? "ESPN" : "Sleeper";
  showLeagueTab(cfg);
}

/* A row of buttons; calls back with whichever one is clicked. The
   callback is wired to each button rather than to the container,
   because the container outlives the connection attempt — hanging
   listeners off it meant an abandoned Sleeper search still fired when
   you later picked an ESPN team. */
function chooser(box, heading, items, label, onPick) {
  box.hidden = false;
  box.innerHTML = "";
  box.append(liveEl("p", "dim", heading));
  for (const it of items) {
    const b = liveEl("button", "btn live-league", label(it));
    b.type = "button";
    b.onclick = () => {
      box.querySelectorAll(".live-league").forEach(x =>
        x.classList.toggle("active", x === b));
      onPick(it);
    };
    box.append(b);
  }
  if (items.length === 1) box.querySelector(".live-league").click();
}

/* --- reading the one box --------------------------------------------
   An ESPN league is a run of digits, or a URL with leagueId= in it.
   Anything else is a Sleeper username. That covers everyone without
   making people choose a provider before they've typed anything, and
   the single real ambiguity — a Sleeper username that happens to be
   all digits — gets a one-click correction under the box instead of a
   permanent extra control. */
function liveSniff(raw) {
  const s = (raw || "").trim();
  if (!s) return null;
  const m = s.match(/leagueId[=/](\d+)/i) || s.match(/^(\d+)$/);
  if (m) return { kind: "espn", leagueId: m[1] };
  return { kind: "sleeper", name: s.replace(/^@/, "") };
}

function liveGuess() {
  const raw = document.getElementById("live-id").value.trim();
  const g = liveSniff(raw);
  if (!g || !liveForce || liveForce === g.kind) return g;
  return liveForce === "sleeper"
    ? { kind: "sleeper", name: raw.replace(/^@/, "") }
    : { kind: "espn", leagueId: (raw.match(/\d+/) || [""])[0] };
}

function liveHint() {
  const box = document.getElementById("live-hint");
  box.innerHTML = "";
  const raw = document.getElementById("live-id").value.trim();
  const g = liveGuess();
  if (!g) return;
  box.append(document.createTextNode(g.kind === "espn"
    ? `${Copy.fill("live.hint.espn", { id: g.leagueId })} `
    : `${Copy.fill("live.hint.sleeper", { name: g.name })} `));
  /* Bare digits are the only input that reads two ways. A URL, or a
     name that isn't a number, needs no second opinion. */
  if (/^\d+$/.test(raw)) {
    const other = g.kind === "espn" ? "sleeper" : "espn";
    const b = liveEl("button", "linkish", Copy.text(other === "sleeper"
      ? "live.hint.is-sleeper" : "live.hint.is-espn"));
    b.type = "button";
    b.onclick = () => { liveForce = other; liveHint(); };
    box.append(b);
  }
}

async function runConnect(btn, fn) {
  liveError("");
  /* the found-league cards have their own markup inside, so only
     swap the label on buttons that are just a label */
  const plain = !btn.firstElementChild;
  const was = btn.textContent;
  btn.disabled = true;
  btn.classList.add("is-busy");
  if (plain) btn.textContent = Copy.text("live.connecting");
  try { await fn(); }
  catch (e) { liveError(e.message); }
  finally {
    btn.disabled = false;
    btn.classList.remove("is-busy");
    if (plain) btn.textContent = was;
  }
}

async function liveConnect() {
  const g = liveGuess();
  if (!g) return;
  const season = (await Sleeper.state()).season;
  if (g.kind === "espn") await connectEspn(g.leagueId, season);
  else await connectSleeper(g.name, season);
}

async function connectSleeper(name, season) {
  const user = await Sleeper.user(name);
  const leagues = await Sleeper.leagues(user.user_id, season);
  if (!leagues || !leagues.length) {
    throw new Error(Copy.text("live.err.noleagues"));
  }
  chooser(document.getElementById("live-leagues"),
    leagues.length === 1 ? Copy.text("live.pick.league.one")
      : Copy.fill("live.pick.league.many", { n: leagues.length }),
    leagues, lg => lg.name,
    lg => useLeague({
      kind: "sleeper", leagueId: lg.league_id, leagueName: lg.name,
      teamKey: user.user_id, teamName: user.display_name,
      username: user.username, season,
    }));
}

async function connectEspn(leagueId, season) {
  if (!leagueId) throw new Error(Copy.text("live.err.noid"));
  const pv = await Espn.preview(leagueId, season);
  if (!pv.teams.length) throw new Error(Copy.text("live.err.noteams"));
  chooser(document.getElementById("live-leagues"),
    Copy.fill("live.pick.team", { league: pv.name }), pv.teams, t => t.name,
    t => useLeague({ kind: "espn", leagueId, leagueName: pv.name,
                     teamKey: t.id, teamName: t.name, season }));
}

/* --- the leagues the extension already knows about -------------------
   Silent when there's no extension, or when it can't see an ESPN
   login: the box below is then the only way in, which is where we
   started. When it does answer, your leagues are one click and no
   typing — and this is the only route that reaches a private league
   without you going and finding its id. */
async function liveDetect() {
  const box = document.getElementById("live-found");
  box.hidden = true;
  box.innerHTML = "";

  let season;
  try { season = (await Sleeper.state()).season; } catch (e) { return; }
  if (!liveFound) liveFound = await Espn.myLeagues(season);
  if (!liveFound.leagues.length) return;

  box.hidden = false;
  box.append(liveEl("p", "dim", Copy.text(liveFound.leagues.length === 1
    ? "live.found.one" : "live.found.many")));

  for (const lg of liveFound.leagues) {
    const card = liveEl("button", "live-found-card");
    card.type = "button";
    const nm = liveEl("span", "live-found-name",
      lg.leagueName || `League ${lg.leagueId}`);
    const sub = liveEl("span", "dim", lg.teamName || "…");
    card.append(nm, sub);
    card.onclick = () => runConnect(card, async () => {
      if (!lg.teamId) return connectEspn(lg.leagueId, lg.season || season);
      useLeague({ kind: "espn", leagueId: lg.leagueId,
                  leagueName: lg.leagueName || `League ${lg.leagueId}`,
                  teamKey: lg.teamId, teamName: lg.teamName,
                  season: lg.season || season });
    });
    box.append(card);

    /* The cookie fallback knows the ids but carries no names. One
       preview call fills them in; the card works meanwhile. */
    if (!lg.leagueName || !lg.teamName) {
      Espn.preview(lg.leagueId, lg.season || season).then(pv => {
        const t = pv.teams.find(x => String(x.id) === String(lg.teamId));
        lg.leagueName = lg.leagueName || pv.name;
        lg.teamName = lg.teamName || (t ? t.name : null);
        nm.textContent = lg.leagueName;
        sub.textContent = lg.teamName || Copy.text("live.pick.team.prompt");
      }).catch(() => {
        sub.textContent = Copy.text("live.pick.team.prompt");
      });
    }
  }
}

function wireLive() {
  if (liveWired) return;
  liveWired = true;

  const input = document.getElementById("live-id");
  const btn = document.getElementById("live-go");
  input.oninput = () => { liveForce = null; liveError(""); liveHint(); };
  input.addEventListener("keydown", e => { if (e.key === "Enter") btn.click(); });
  btn.onclick = () => runConnect(btn, liveConnect);

  document.getElementById("live-switch").onclick = () => {
    liveSave({});
    liveSyncOut(null);
    Provider.invalidate();
    Live.stopPolling();
    liveForce = null;
    document.getElementById("live-picked").hidden = true;
    document.getElementById("live-connect").hidden = false;
    document.getElementById("live-leagues").hidden = true;
    document.getElementById("live-body").innerHTML = "";
    document.getElementById("league-body").innerHTML = "";
    showLeagueTabs(false);
    liveDetect();
  };

  const saved = liveSaved();
  if (saved.username) input.value = saved.username;
  liveHint();
}

async function renderLive(tab) {
  liveTab = (tab && (tab === "matchup" || League.TABS[tab])) ? tab : "matchup";
  await Live.init();
  wireLive();

  const cfg = liveSaved();
  if (cfg.leagueId && cfg.kind) {
    document.getElementById("live-connect").hidden = true;
    useLeague(cfg);
  } else {
    document.getElementById("live-connect").hidden = false;
    document.getElementById("live-picked").hidden = true;
    showLeagueTabs(false);
    liveDetect();
  }
}

/* Copy first, then the first route: every view starts hidden, so nothing
   is on screen to flash its empty slots while copy.json is in flight. A
   failed load leaves the words blank and logs — the tables, the draft
   tool and the league pages still work. */
window.addEventListener("hashchange", route);
Copy.load().then(() => {
  Copy.apply(document);
  route();
});
