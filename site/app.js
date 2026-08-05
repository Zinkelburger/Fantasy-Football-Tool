/* Static SPA: hash routing over prebuilt JSON (site/build_site.py). */
"use strict";

const VIEWS = ["home", "weekly", "board", "blog", "post", "draft"];
const cache = {};

async function data(name) {
  if (!cache[name]) {
    const r = await fetch(`data/${name}.json`);
    cache[name] = await r.json();
  }
  return cache[name];
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

  if (view === "weekly") renderWeekly();
  if (view === "board") renderBoard();
  if (view === "blog") renderBlogList();
  if (view === "post" && arg) renderPost(arg);
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
  weeklyDone = true;

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
function applyBoardSearch() {
  const q = document.getElementById("board-search").value.trim().toLowerCase();
  document.querySelectorAll("#board-table tbody tr").forEach(row => {
    row.hidden = q && !row.dataset.search.includes(q);
  });
}

/* Scoring formats. The board is a separate model fit per format, and
   the ADP column is that format's ADP — so the two columns compare
   like with like.

   `flag` is the points-per-game gap that earns a bounce-back / come-down
   tag. It rises with the format because PPR inflates every receiver's
   PPG, and a 2-point move should mean the same thing on all three. */
/* `gapFlag` is the hot/cold threshold on the position-centered gap
   between real and expected PPG (¾ of `flag`, same PPR-inflation
   scaling). Centered because actual scoring has floors/fumbles that
   expected points lacks — see analysis/export_opportunity.py. */
const FORMATS = [
  { key: "std", label: "STD", note: "Standard — no points for catches",
    flag: 2.0, gapFlag: 1.5 },
  { key: "half", label: "0.5 PPR", note: "Half PPR — 0.5 points per catch",
    flag: 2.5, gapFlag: 1.9 },
  { key: "ppr", label: "PPR", note: "Full PPR — 1 point per catch",
    flag: 3.0, gapFlag: 2.25 },
];
const FMT_KEY = "ffScoring";

let boardDone = false;
async function renderBoard() {
  if (boardDone) return;
  boardDone = true;
  const board = await data("board");
  const market = await data("market");
  const tabs = document.getElementById("board-tabs");
  const fmtTabs = document.getElementById("board-scoring");
  const order = ["RB", "WR", "QB", "TE"];
  const avail = FORMATS.filter(f => board[f.key]);
  if (!avail.length) return;          // board data not built yet
  let fmt = localStorage.getItem(FMT_KEY);
  if (!avail.some(f => f.key === fmt)) fmt = avail[0].key;
  let pos = "RB";

  fmtTabs.innerHTML = avail.map(f =>
    `<button class="tab fmt${f.key === fmt ? " active" : ""}"
      data-fmt="${f.key}" title="${f.note}">${f.label}</button>`).join("");
  tabs.innerHTML = order.map(p =>
    `<button class="tab pos-${p.toLowerCase()}${p === pos ? " active" : ""}"
      data-pos="${p}">${p}</button>`).join("");

  // Hot/cold chip for the expected-PPG column. `gapc` is how far the
  // player's real-minus-expected scoring sat from the typical player at
  // his position; only flagged with 8+ games so one hot month can't
  // earn a season-long label. Backtested 2017-25 (league-sim
  // analysis/gap_regression_check.py): the gap predicted next-season
  // movement at WR/TE in 8 of 8 year-pairs, but added nothing beyond
  // scoring level at RB/QB — so WR/TE chips are colored verdicts and
  // RB/QB chips render gray, as context only.
  const OPP_SIGNAL_POS = new Set(["WR", "TE"]);
  const oppChip = (r, pos, gapFlag) => {
    if (r.xfp == null || r.g < 8 || Math.abs(r.gapc) < gapFlag) return "";
    const hot = r.gapc > 0;
    const signal = OPP_SIGNAL_POS.has(pos);
    const vol = pos === "QB" ? ""
      : ` His chances: ${r.tpg} targets${r.cpg >= 1
          ? ` and ${r.cpg} carries` : ""} a game.`;
    const why = !signal
      ? `Context, not a verdict: in our 2017-25 backtests a gap like this told us nothing extra about a ${pos}'s next season once you account for how much he scored`
        + (pos === "RB"
          ? " — goal-line roles are sticky, so an RB's extra finishing partly repeats"
          : "")
        + ". The 2026 proj column already weighs this correctly."
      : !hot
        ? "Targets and carries carry over to next season better than "
          + "points do — in our 2017-25 backtests, cold WR/TE seasons "
          + "held their value while the average player slid. The "
          + "strongest buy signal in our research."
        : (r.tdl >= 0.15
            ? `Mostly touchdown luck — ${r.tdl} more TDs a game than his `
              + "chances were worth. "
            : "Efficiency like that rarely repeats. ")
          + "Hot WR/TE seasons gave back about 2 points a game the next "
          + "year in our 2017-25 backtests.";
    return ` <span class="tag ${signal ? (hot ? "down" : "up") : ""}" title="Scored ${
      Math.abs(r.gapc).toFixed(1)} points a game ${hot ? "more" : "less"
      } than a typical ${pos} would have from the same chances. ${why}${vol}">${
      signal ? (hot ? "▼ " : "▲ ") : ""}${hot ? "ran hot" : "ran cold"}</span>`;
  };

  const draw = () => {
    const { note, flag, gapFlag } = avail.find(f => f.key === fmt);
    const t = document.getElementById("board-table");
    t.innerHTML =
      `<thead><tr><th class="rank">#</th><th>Player</th>
       <th class="num" title="What our model expects him to average per game across the 2026 regular season (${note})">2026 proj PPG</th>
       <th class="num" title="What he actually averaged per game in 2025 (${note})">2025 PPG</th>
       <th class="num" title="What a typical player would have averaged from his 2025 chances — targets, carries, and where on the field they came (${note}). When real scoring runs well above or below this, it usually snaps back the next season: the chances repeat, the luck doesn't.">2025 expected</th>
       <th class="num" title="Position rank by current draft market — Sleeper ADP for this same scoring format (${note})">ADP</th>
       <th class="num">Age</th>
       <th class="num" title="Share of the team's salary cap — teams play the players they pay">Cap %</th></tr></thead><tbody>` +
      board[fmt][pos].map((r, i) => {
        const d = r.pred - r.ppg25;
        // Market delta: how many spots later the market drafts this player
        // than we rank him. +n (green) = the market is sleeping on him.
        const md = r.mkt ? r.mkt - (i + 1) : 0;
        const mkt = r.mkt
          ? `${r.mkt}${Math.abs(md) >= 3
              ? ` <span class="${md > 0 ? "up" : "down"}" title="${md > 0
                  ? `market drafts him ${md} spots later than our rank`
                  : `market drafts him ${-md} spots earlier than our rank`}">(${md > 0 ? "+" : ""}${md})</span>`
              : ""}`
          : "—";
        return `<tr data-search="${r.name.toLowerCase()}">
          <td class="rank">${i + 1}</td><td><b>${r.name}</b>
          ${Math.abs(d) > flag ? `<span class="tag ${d > 0 ? "up" : "down"}"
          title="${d > 0
            ? "model projects a jump from last season"
            : "model projects a drop from last season"}">
          ${d > 0 ? "▲ bounce back" : "▼ come down"}</span>` : ""}</td>
          <td class="num"><b>${r.pred.toFixed(1)}</b></td>
          <td class="num">${r.ppg25.toFixed(1)}</td>
          <td class="num">${r.xfp == null ? "—"
            : r.xfp.toFixed(1)}${oppChip(r, pos, gapFlag)}</td>
          <td class="num">${mkt}</td>
          <td class="num">${r.age ?? "—"}</td>
          <td class="num">${r.cap ? r.cap.toFixed(1) : "—"}</td></tr>`;
      }).join("") + "</tbody>";
    applyBoardSearch();
  };
  draw();
  tabs.addEventListener("click", e => {
    const b = e.target.closest("button[data-pos]");
    if (!b) return;
    tabs.querySelectorAll(".tab")
      .forEach(t => t.classList.toggle("active", t === b));
    pos = b.dataset.pos;
    draw();
  });
  fmtTabs.addEventListener("click", e => {
    const b = e.target.closest("button[data-fmt]");
    if (!b) return;
    fmtTabs.querySelectorAll(".tab")
      .forEach(t => t.classList.toggle("active", t === b));
    fmt = b.dataset.fmt;
    localStorage.setItem(FMT_KEY, fmt);
    draw();
  });
  document.getElementById("board-search")
    .addEventListener("input", applyBoardSearch);

  const pre = await data("preseason");
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

  document.getElementById("market-table").innerHTML =
    `<thead><tr><th class="rank">#</th><th>Team</th>
     <th class="num">Implied PPG</th><th class="num">Implied wins</th>
     </tr></thead><tbody>` +
    market.map((r, i) =>
      `<tr><td class="rank">${i + 1}</td><td>${r.team}</td>
       <td class="num">${r.ppg.toFixed(1)}</td>
       <td class="num">${r.wins.toFixed(1)}</td></tr>`).join("") +
    "</tbody>";
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
  blogDone = true;
  const posts = await data("blog");
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

window.addEventListener("hashchange", route);
route();
