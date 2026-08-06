/* The league hub: start/sit, waivers, team strength, week in review,
 * transactions.
 *
 * Every tab runs off the one normalised context in provider.js, so
 * none of this knows or cares whether the league lives on Sleeper or
 * ESPN.
 *
 * The tone rule from the rest of the site applies: say what a number
 * means in plain words, and don't imply more precision than we
 * measured.
 */
"use strict";

const League = (() => {
  const POS = ["QB", "RB", "WR", "TE", "K", "DST"];

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const fmt = (v, d = 1) => (v === null || v === undefined || isNaN(v))
    ? "—" : v.toFixed(d);
  const nameOf = (id, c) => (c.players[id] || {}).name || `#${id}`;

  /* ---------------------------------------------------------- start/sit */

  /* The one screen that changes an outcome. Everything else on this
     page is information; this is a decision, and it's the decision the
     projection is actually good enough to help with (finding 35: all
     the value is before kickoff). */
  function renderStartSit(root, c) {
    root.innerHTML = "";
    if (!c.myTeam) {
      root.append(el("p", "dim", "We couldn't work out which team is yours."));
      return;
    }
    /* Out of season, and for a week the provider hasn't projected yet,
       every number here is zero — which would otherwise render as the
       cheerful and completely wrong "your lineup is already the best
       one available". */
    if (!c.myTeam.players.some(id => c.proj[id] > 0)) {
      root.append(el("p", "dim",
        `Nobody on your roster has a projection for week ${c.week} yet, so `
        + "there's nothing to compare. Weekly projections usually appear a "
        + "few days before the games."));
      return;
    }

    const best = Provider.bestLineup(c.myTeam.players, c);
    const started = new Set(c.myTeam.starters);
    const bestIds = new Set(best.picked.map(p => p.id).filter(Boolean));

    const actual = c.myTeam.starters.reduce((s, id) => s + (c.proj[id] || 0), 0);
    const gain = best.total - actual;

    root.append(el("p", "blurb",
      "Your best legal lineup this week against the one you've actually "
      + "set, using this week's projections. A projection is not a "
      + "promise — but over a season, starting the higher number wins "
      + "more weeks than not."));

    const head = el("div", "ss-head");
    const big = el("div", "ss-gain", gain > 0.05 ? `+${gain.toFixed(1)}` : "0.0");
    big.style.color = gain > 2 ? "var(--yellow)" : "var(--green)";
    head.append(big);
    const lab = el("div", "ss-gain-label");
    lab.append(el("div", "", gain > 0.05
      ? "projected points you're leaving on your bench"
      : "your lineup is already the best one available"));
    lab.append(el("div", "dim",
      `${actual.toFixed(1)} started · ${best.total.toFixed(1)} available`));
    head.append(lab);
    root.append(head);

    /* The swaps are a set difference, not a slot-by-slot comparison.
       Which slot the optimiser happened to drop a player into is an
       artifact — swap two interchangeable running backs between RB2 and
       the flex and nothing about your team changed. So: who's in the
       best lineup but on your bench, against who you started but
       shouldn't have. Pair them best-with-worst, which is the order the
       gains actually come in. */
    const toStart = best.picked
      .filter(p => p.id && !started.has(p.id))
      .sort((a, b) => b.pr - a.pr);
    const toSit = c.myTeam.starters
      .filter(id => !bestIds.has(id))
      .sort((a, b) => (c.proj[a] || 0) - (c.proj[b] || 0));

    const swaps = toStart.map((p, i) => {
      const out = i < toSit.length ? toSit[i] : null;
      return { in: p.id, out,
               delta: p.pr - (out ? (c.proj[out] || 0) : 0) };
    });

    if (!swaps.length) {
      root.append(el("p", "dim", "Nothing to change. Go and enjoy your Sunday."));
    } else {
      const list = el("div", "lg-table");
      for (const s of swaps.sort((a, b) => b.delta - a.delta)) {
        const row = el("div", "ss-swap");
        row.append(el("span", "lg-kind lg-kind-add",
          (c.players[s.in] || {}).pos || "?"));
        const body = el("div", "lg-move-body");
        const inRow = el("div", "ss-line");
        inRow.append(el("span", "lg-add", `start ${nameOf(s.in, c)}`));
        inRow.append(el("span", "dim", `${fmt(c.proj[s.in] || 0)} proj`));
        body.append(inRow);
        if (s.out) {
          const outRow = el("div", "ss-line");
          outRow.append(el("span", "lg-drop", `sit ${nameOf(s.out, c)}`));
          outRow.append(el("span", "dim", `${fmt(c.proj[s.out] || 0)} proj`));
          body.append(outRow);
        } else {
          body.append(el("div", "dim", "an empty slot in your lineup"));
        }
        row.append(body);
        row.append(el("span", "ss-delta", `+${s.delta.toFixed(1)}`));
        list.append(row);
      }
      root.append(list);
    }

    /* the lineup itself, so the advice is checkable */
    const t = el("div", "lg-table ss-lineup");
    const lhead = el("div", "lg-row lg-row-head ss-row");
    lhead.append(el("span", "", "slot"), el("span", "", "best available"),
                 el("span", "lg-num", "proj"), el("span", "", "you started"));
    t.append(lhead);
    for (const slot of best.picked) {
      const row = el("div", "lg-row ss-row");
      row.append(el("span", "dim", slot.slot));
      row.append(el("span", "lg-player-name",
        slot.id ? nameOf(slot.id, c) : "— nobody eligible —"));
      row.append(el("span", "lg-num", fmt(slot.pr)));
      const same = slot.id && started.has(slot.id);
      row.append(el("span", same ? "dim" : "ss-diff", same ? "✓ started" : "on your bench"));
      t.append(row);
    }
    root.append(el("h3", "", "The lineup"));
    root.append(t);

    const missing = c.myTeam.starters.filter(id => c.proj[id] === undefined);
    if (missing.length) {
      root.append(el("p", "dim lg-note",
        `No projection for ${missing.map(id => nameOf(id, c)).join(", ")} — `
        + "they're counted as zero here, which is usually right (a bye or "
        + "an inactive) and occasionally just a gap in the feed."));
    }
  }

  /* ------------------------------------------------------------ waivers */

  /* "Who should I pick up" has a better answer than "who has the
     biggest projection". The number that decides it is what the player
     would add to *your* starting lineup this week — a 20-point
     quarterback is worth nothing to a team that already starts a
     better one, and the raw projection can't see that. */
  const waiverState = { pos: "RB", hideRostered: true, q: "" };

  function renderWaivers(root, c) {
    root.innerHTML = "";

    const bar = el("div", "lg-toolbar");
    const tabs = el("div", "lg-postabs");
    for (const p of POS) {
      const b = el("button", "lg-pos-btn" + (p === waiverState.pos ? " active" : ""), p);
      b.type = "button";
      b.onclick = () => { waiverState.pos = p; renderWaivers(root, c); };
      tabs.append(b);
    }
    bar.append(tabs);

    const right = el("div", "lg-toolbar-right");
    const search = el("input", "lg-search");
    search.type = "search";
    search.placeholder = "search players";
    search.value = waiverState.q;
    search.oninput = () => { waiverState.q = search.value; drawList(); };
    const lbl = el("label", "lg-check");
    const cb = el("input");
    cb.type = "checkbox";
    cb.checked = waiverState.hideRostered;
    cb.onchange = () => { waiverState.hideRostered = cb.checked; drawList(); };
    lbl.append(cb, el("span", "", "only show available"));
    right.append(search, lbl);
    bar.append(right);
    root.append(bar);

    const listBox = el("div", "lg-list");
    root.append(listBox);

    const myIds = c.myTeam ? c.myTeam.players : [];
    const baseline = c.myTeam ? Provider.bestLineup(myIds, c).total : 0;
    const mySet = new Set(myIds);

    function drawList() {
      const q = waiverState.q.trim().toLowerCase();
      const rows = [];
      for (const p of c.pool) {
        if (p.pos !== waiverState.pos) continue;
        const isMine = mySet.has(p.id);
        const owned = p.ownerTeamId !== null && p.ownerTeamId !== undefined;
        if (waiverState.hideRostered && owned && !isMine) continue;
        if (q && !p.name.toLowerCase().includes(q)) continue;
        /* Somebody with no projection is usually on a bye or inactive.
           Keep him if he's rostered somewhere or you searched for him —
           a bye-week stash is a real waiver move and the old code hid
           those players completely. */
        if (p.proj === null && !owned && !q) continue;
        const upgrade = (c.myTeam && !isMine && p.proj)
          ? Math.max(0, Provider.bestLineup(myIds, c, p.id).total - baseline)
          : 0;
        rows.push({ ...p, owned, isMine, upgrade });
      }
      rows.sort((a, b) => (b.upgrade - a.upgrade) || ((b.proj || 0) - (a.proj || 0)));

      listBox.innerHTML = "";
      const head = el("div", "lg-row lg-row-head lg-waiver-row");
      head.append(el("span", "", "player"), el("span", "", "status"),
                  el("span", "lg-num", "proj"), el("span", "lg-num", "adds"));
      listBox.append(head);

      if (!rows.length) {
        listBox.append(el("p", "dim", "Nobody matches that."));
        return;
      }
      for (const r of rows.slice(0, 120)) {
        const row = el("div", "lg-row lg-waiver-row"
          + (r.isMine ? " is-mine" : r.owned ? " is-owned" : " is-free"));
        const nm = el("div", "lg-player");
        nm.append(el("span", `lg-pos pos-${r.pos.toLowerCase()}`, r.pos));
        nm.append(el("span", "lg-player-name", r.name));
        nm.append(el("span", "dim lg-team", r.team || "FA"));
        if (r.inj) nm.append(el("span", "lg-inj", r.inj));
        row.append(nm);
        const st = el("span", "lg-status",
          r.isMine ? "yours" : r.owned ? "rostered" : "available");
        if (r.pctOwned !== null && r.pctOwned !== undefined && !r.owned) {
          st.title = `rostered in ${r.pctOwned.toFixed(0)}% of ESPN leagues`;
        }
        row.append(st);
        row.append(el("span", "lg-num" + (r.proj === null ? " dim" : ""),
          r.proj === null ? "—" : fmt(r.proj)));
        const up = el("span", "lg-num lg-upgrade",
          r.upgrade > 0.05 ? `+${r.upgrade.toFixed(1)}` : "—");
        up.title = r.upgrade > 0.05
          ? "what he'd add to your best lineup this week"
          : "he wouldn't crack your lineup this week";
        if (r.upgrade > 0.05) up.classList.add("is-up");
        row.append(up);
        listBox.append(row);
      }
      if (rows.length > 120) {
        listBox.append(el("p", "dim", `Showing the top 120 of ${rows.length}.`));
      }
    }
    drawList();

    root.append(el("p", "dim lg-note",
      "“Proj” is this week's projected points in your league's scoring. "
      + "“Adds” is what he would add to your best legal lineup if you "
      + "picked him up — a dash means he wouldn't crack it this week, "
      + "which is the real answer to whether he's worth a waiver claim. "
      + "It's a one-week number, so a player on a bye reads as a dash "
      + "even when he's worth stashing."));
  }

  /* -------------------------------------------------------------- teams */

  function renderTeams(root, c) {
    root.innerHTML = "";
    const rows = c.teams.map(t => ({
      name: t.name, mine: t.mine, w: t.w, l: t.l, t: t.t, pf: t.pf, pa: t.pa,
      strength: Provider.bestLineup(t.players, c).total,
    })).sort((a, b) => b.strength - a.strength);

    root.append(el("p", "blurb",
      "Teams ranked by how many points their best legal lineup projects "
      + "for this week — not by record. A good team in a bad bye week "
      + "will sit lower than its record suggests, and that's the point: "
      + "this is who is dangerous on Sunday, not who has been lucky."));

    const t = el("div", "lg-table");
    const head = el("div", "lg-row lg-row-head lg-team-row");
    head.append(el("span", "", "#"), el("span", "", "team"),
      el("span", "lg-num", "record"), el("span", "lg-num", "points for"),
      el("span", "lg-num", "against"), el("span", "lg-num", "lineup"));
    t.append(head);
    rows.forEach((r, i) => {
      const row = el("div", "lg-row lg-team-row" + (r.mine ? " is-mine" : ""));
      row.append(el("span", "dim", String(i + 1)));
      row.append(el("span", "lg-player-name", r.name));
      row.append(el("span", "lg-num", `${r.w}-${r.l}${r.t ? "-" + r.t : ""}`));
      row.append(el("span", "lg-num", fmt(r.pf, 0)));
      row.append(el("span", "lg-num", fmt(r.pa, 0)));
      row.append(el("span", "lg-num lg-strong", fmt(r.strength)));
      t.append(row);
    });
    root.append(t);
  }

  /* ------------------------------------------------------------- review */

  /* All-play: what your record would be if you played every team every
     week. It strips out schedule luck, which is most of what separates
     a 7-4 team from a 4-7 one in a 12-team league.

     Only finished weeks count. Reading the week in progress used to
     drag every team's record around on a Sunday afternoon, when half
     the league had played a Thursday game and the rest hadn't started. */
  async function renderReview(root, c) {
    root.innerHTML = "";
    root.append(el("p", "dim", "Loading every week…"));

    const done = c.completedWeeks;
    if (done < 1) {
      root.innerHTML = "";
      root.append(el("p", "dim",
        "No week has finished yet this season — there's nothing to "
        + "compare until one has."));
      return;
    }

    const weeks = [];
    for (let w = 1; w <= done; w++) weeks.push(w);
    const all = await Promise.all(weeks.map(w => c.scores(w).catch(() => [])));

    const tally = {};
    const get = (id) => (tally[id] = tally[id]
      || { aw: 0, al: 0, w: 0, l: 0, pf: 0, weeks: 0 });

    for (const wk of all) {
      const sides = (wk || []).filter(s => typeof s.points === "number");
      /* a week where nobody scored never happened */
      if (sides.length < 2 || !sides.some(s => s.points > 0)) continue;
      for (const s of sides) {
        const t = get(s.teamId);
        t.pf += s.points;
        t.weeks++;
        for (const o of sides) {
          if (o.teamId === s.teamId) continue;
          if (s.points > o.points) t.aw++;
          else if (s.points < o.points) t.al++;
        }
        const opp = sides.find(o => o.matchupId === s.matchupId
          && o.teamId !== s.teamId);
        if (opp) {
          if (s.points > opp.points) t.w++;
          else if (s.points < opp.points) t.l++;
        }
      }
    }

    const rows = c.teams.map(t => {
      const x = get(t.id);
      const allPct = (x.aw + x.al) ? x.aw / (x.aw + x.al) : 0;
      const realPct = (x.w + x.l) ? x.w / (x.w + x.l) : 0;
      return { name: t.name, mine: t.mine, w: x.w, l: x.l, allPct, realPct,
               luck: realPct - allPct, ppg: x.weeks ? x.pf / x.weeks : 0 };
    }).sort((a, b) => b.allPct - a.allPct);

    root.innerHTML = "";
    if (!rows.some(r => r.w + r.l > 0)) {
      root.append(el("p", "dim", "No finished games to read yet."));
      return;
    }

    root.append(el("p", "blurb",
      "All-play is the record you'd have if you played every team every "
      + "week. It ignores who you happened to be scheduled against, so "
      + "it's the fairer measure of how you're actually doing. "
      + "“Luck” is your real win rate minus your all-play win rate — "
      + "positive means the schedule has been kind."));
    root.append(el("p", "dim",
      `Through ${done} finished ${done === 1 ? "week" : "weeks"}. `
      + "The week in progress isn't counted."));

    const t = el("div", "lg-table");
    const head = el("div", "lg-row lg-row-head lg-review-row");
    head.append(el("span", "", "team"), el("span", "lg-num", "record"),
      el("span", "lg-num", "pts/wk"), el("span", "lg-num", "all-play"),
      el("span", "lg-num", "luck"));
    t.append(head);
    for (const r of rows) {
      const row = el("div", "lg-row lg-review-row" + (r.mine ? " is-mine" : ""));
      row.append(el("span", "lg-player-name", r.name));
      row.append(el("span", "lg-num", `${r.w}-${r.l}`));
      row.append(el("span", "lg-num", fmt(r.ppg, 1)));
      row.append(el("span", "lg-num", `${(r.allPct * 100).toFixed(0)}%`));
      const lk = el("span", "lg-num",
        `${r.luck > 0 ? "+" : ""}${(r.luck * 100).toFixed(0)}`);
      lk.style.color = r.luck > 0.08 ? "var(--green)"
        : r.luck < -0.08 ? "var(--red)" : "var(--fg-dim)";
      lk.title = r.luck > 0 ? "winning more than the scores deserve"
        : "losing more than the scores deserve";
      row.append(lk);
      t.append(row);
    }
    root.append(t);
  }

  /* -------------------------------------------------------- transactions */

  async function renderMoves(root, c) {
    root.innerHTML = "";
    root.append(el("p", "dim", "Loading recent moves…"));

    const from = Math.max(1, c.week - 3);
    const res = await c.moves(from, c.week);
    root.innerHTML = "";

    if (!res.ok) {
      root.append(el("p", "dim", res.why));
      return;
    }
    if (!res.items.length) {
      root.append(el("p", "dim", "No completed moves in the last four weeks."));
      return;
    }

    const teamOf = (id) => {
      const t = c.teams.find(x => String(x.id) === String(id));
      return t ? t.name : `Team ${id}`;
    };

    root.append(el("p", "blurb",
      "Every completed add, drop and trade from the last four weeks, "
      + "newest first."));

    const list = el("div", "lg-table");
    for (const t of res.items.slice(0, 80)) {
      const row = el("div", "lg-move");
      row.append(el("span", `lg-kind lg-kind-${t.type}`, t.type));
      const body = el("div", "lg-move-body");
      body.append(el("div", "lg-move-team", t.teamIds.map(teamOf).join(" ↔ ")));
      const detail = el("div", "lg-move-players");
      for (const a of t.adds) detail.append(el("span", "lg-add", `+ ${nameOf(a.id, c)}`));
      for (const d of t.drops) detail.append(el("span", "lg-drop", `− ${nameOf(d.id, c)}`));
      body.append(detail);
      row.append(body);
      row.append(el("span", "dim lg-move-week", `wk ${t.week}`));
      list.append(row);
    }
    root.append(list);
  }

  /* ---------------------------------------------------------------- api */

  const TABS = {
    startsit: { label: "Start/sit", fn: renderStartSit },
    waivers: { label: "Waivers", fn: renderWaivers },
    teams: { label: "Teams", fn: renderTeams },
    review: { label: "Week in review", fn: renderReview },
    moves: { label: "Moves", fn: renderMoves },
  };

  async function render(tab, root, cfg) {
    const t = TABS[tab];
    if (!t) return;
    root.innerHTML = "";
    root.append(el("p", "dim", "Loading your league…"));
    const c = await Provider.load(cfg);
    await t.fn(root, c);
  }

  return { render, TABS,
           __test: { renderStartSit, renderWaivers, renderTeams, renderReview,
                     renderMoves } };
})();
