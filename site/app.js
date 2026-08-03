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
  const [page, arg] = hash.split("/");
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

/* ------------------------------------------------------------ weekly */
let weeklyDone = false;
async function renderWeekly() {
  const w = await data("weekly");
  document.getElementById("weekly-label").textContent = w.label;
  if (weeklyDone) return;
  weeklyDone = true;

  const dst = document.getElementById("dst-table");
  dst.innerHTML =
    `<thead><tr><th class="rank">#</th><th>Defense</th><th>vs</th>
     <th class="num">Opp implied</th><th></th></tr></thead><tbody>` +
    w.dst.map((r, i) =>
      `<tr><td class="rank">${i + 1}</td><td><b>${r.team}</b></td>
       <td>${r.home ? "" : "@ "}${r.opp}</td>
       <td class="num ${r.imp <= 18.5 ? "up" : ""}">${r.imp.toFixed(1)}</td>
       <td>${i < 3 ? '<span class="tag up">stream</span>' : ""}</td></tr>`
    ).join("") + "</tbody>";

  const k = document.getElementById("k-table");
  k.innerHTML =
    `<thead><tr><th class="rank">#</th><th>Kicker slot</th><th>vs</th>
     <th class="num">Own implied</th><th></th></tr></thead><tbody>` +
    w.k.map((r, i) =>
      `<tr><td class="rank">${i + 1}</td><td><b>${r.team}</b> K</td>
       <td>${r.home ? "" : "@ "}${r.opp}</td>
       <td class="num">${r.imp.toFixed(1)}</td>
       <td>${r.dome ? '<span class="tag dome">dome</span>' : ""}</td></tr>`
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
  });
}

/* ------------------------------------------------------------- board */
let boardDone = false;
async function renderBoard() {
  if (boardDone) return;
  boardDone = true;
  const board = await data("board");
  const market = await data("market");
  const tabs = document.getElementById("board-tabs");
  const order = ["RB", "WR", "QB", "TE"];
  tabs.innerHTML = order.map((p, i) =>
    `<button class="tab pos-${p.toLowerCase()}${i === 0 ? " active" : ""}"
      data-pos="${p}">${p}</button>`).join("");

  const draw = pos => {
    const t = document.getElementById("board-table");
    t.innerHTML =
      `<thead><tr><th class="rank">#</th><th>Player</th>
       <th class="num">Proj PPG</th><th class="num">2025 PPG</th>
       <th class="num" title="Position rank by current draft market (Sleeper standard ADP)">ADP</th>
       <th class="num">Age</th><th class="num">Cap %</th></tr></thead><tbody>` +
      board[pos].map((r, i) => {
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
        return `<tr><td class="rank">${i + 1}</td><td><b>${r.name}</b>
          ${Math.abs(d) > 2 ? `<span class="tag ${d > 0 ? "up" : "down"}">
          ${d > 0 ? "▲ buys the bounce" : "▼ fades the spike"}</span>` : ""}</td>
          <td class="num"><b>${r.pred.toFixed(1)}</b></td>
          <td class="num">${r.ppg25.toFixed(1)}</td>
          <td class="num">${mkt}</td>
          <td class="num">${r.age ?? "—"}</td>
          <td class="num">${r.cap ? r.cap.toFixed(1) : "—"}</td></tr>`;
      }).join("") + "</tbody>";
  };
  draw("RB");
  tabs.addEventListener("click", e => {
    const b = e.target.closest("button[data-pos]");
    if (!b) return;
    tabs.querySelectorAll(".tab")
      .forEach(t => t.classList.toggle("active", t === b));
    draw(b.dataset.pos);
  });

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
    `<a class="post-row" href="#/post/${p.id}">
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

/* internal links like #/blog/27-dst-model → #/post/... */
document.addEventListener("click", e => {
  const a = e.target.closest('a[href^="#/blog/"]');
  if (a) {
    e.preventDefault();
    location.hash = a.getAttribute("href").replace("#/blog/", "#/post/");
  }
});

window.addEventListener("hashchange", route);
route();
