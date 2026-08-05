/* Static SPA: hash routing over prebuilt JSON (site/build_site.py). */
"use strict";

const VIEWS = ["home", "weekly", "board", "blog", "post", "cheat",
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
   on the next visit so navigation back retries the load. */
function loadError(viewId, on) {
  const view = document.getElementById(viewId);
  const old = view.querySelector(".load-error");
  if (!on) { if (old) old.remove(); return; }
  if (old) return;
  const p = document.createElement("p");
  p.className = "load-error";
  p.textContent = "This page didn't load — check your connection, "
    + "then try again.";
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
  document.querySelectorAll("#site-nav a").forEach(a => {
    a.classList.toggle("active", a.dataset.route === view
      || (view === "post" && a.dataset.route === "blog"));
  });

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
  if (view === "draft") {
    const f = document.getElementById("draft-frame");
    if (!f.src) f.src = "../webapp/index.html";
  }
  if (view !== "post") window.scrollTo(0, 0);
}

/* Hover copy for the weekly tables. Every number here is a measured
   effect from the K/DST findings, not a rule of thumb — keep them in
   sync with findings 27 and 28 if either model is refit. */
const WHY = {
  oppImp: "Points Vegas expects the opponent to score — lower is better. "
    + "This one number does about 97% of the work: each point off the "
    + "opponent's total is worth about +0.38 D/ST points (finding 27).",
  stream:
    "Top-3 matchup this week. Picking defenses by opponent total ranks "
    + "them more than twice as well as going by how good the defense is "
    + "(.30 vs .13) — so stream the matchup, don't hold a name (finding 27).",
  ownImp: "Points Vegas expects this kicker's own offense to score — "
    + "higher is better. Kickers score when their team moves the ball and "
    + "wins; the kicker's own history predicts almost nothing (finding 28).",
  dome: "Indoors: no wind, no weather. Worth about +0.7 points to a kicker "
    + "in our model — small, but it is the second-biggest thing we can see "
    + "after how much the offense is expected to score. Wind costs about "
    + "−0.5 (finding 28).",
  domeSched: "Indoor games on this team's 2026 schedule, home and away. "
    + "Each one is worth about +0.7 kicker points, so a 10-dome schedule "
    + "beats a 0-dome schedule by roughly 0.4 points a game (finding 28). "
    + "A tiebreak, not a reason to reach.",
  oppSeason: "Points this defense's opponents are expected to score, "
    + "averaged over the whole 2026 season. Each point lower is worth about "
    + "+0.38 D/ST points a week (finding 27). Preseason win totals are the "
    + "best season-long signal we have — better than any stat-based one "
    + "(finding 26).",
};

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
     title="Click: taken → mine → clear"`;

  const dst = document.getElementById("dst-table");
  dst.innerHTML =
    `<thead><tr><th class="rank">#</th><th>Defense</th><th>vs</th>
     <th class="num" title="${WHY.oppImp}">Opp implied</th>
     <th></th><th class="mark-col"></th></tr></thead><tbody>` +
    w.dst.map((r, i) =>
      `<tr ${rowAttrs("dst", r)}><td class="rank">${i + 1}</td>
       <td><b>${r.team}</b></td>
       <td>${r.home ? "" : "@ "}${r.opp}</td>
       <td class="num ${r.imp <= 18.5 ? "up" : ""}">${r.imp.toFixed(1)}</td>
       <td>${i < 3 ? `<span class="tag up" title="${WHY.stream}">stream</span>` : ""}</td>
       <td class="mark-cell"></td></tr>`
    ).join("") + "</tbody>";

  const k = document.getElementById("k-table");
  k.innerHTML =
    `<thead><tr><th class="rank">#</th><th>Kicker slot</th><th>vs</th>
     <th class="num" title="${WHY.ownImp}">Own implied</th>
     <th></th><th class="mark-col"></th></tr></thead><tbody>` +
    w.k.map((r, i) =>
      `<tr ${rowAttrs("k", r)}><td class="rank">${i + 1}</td>
       <td><b>${r.team}</b> K</td>
       <td>${r.home ? "" : "@ "}${r.opp}</td>
       <td class="num">${r.imp.toFixed(1)}</td>
       <td>${r.dome ? `<span class="tag dome" title="${WHY.dome}">dome</span>` : ""}</td>
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
     <th class="num" title="Points Vegas expects this offense to score per game across the whole 2026 season. Kicker scoring follows the offense, not the kicker.">Own PPG</th>
     <th class="num" title="${WHY.domeSched}">Dome games</th>
     </tr></thead><tbody>` +
    pre.k.map((r, i) =>
      `<tr><td class="rank">${i + 1}</td><td><b>${r.team}</b> K</td>
       <td class="num">${r.own.toFixed(1)}</td>
       <td class="num ${r.dome >= 8 ? "up" : ""}"
           title="${r.dome} of ${r.games} games indoors — worth about
           ${r.domeEdge.toFixed(2)} kicker points a game over the season">
         ${r.dome}</td></tr>`).join("") + "</tbody>";

  document.getElementById("pre-dst-table").innerHTML =
    `<thead><tr><th class="rank">#</th><th>Defense</th>
     <th class="num" title="${WHY.oppSeason}">Opp PPG faced</th>
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
  if (!p) { el.innerHTML = "<p>Post not found.</p>"; return; }
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

window.addEventListener("hashchange", route);
route();
