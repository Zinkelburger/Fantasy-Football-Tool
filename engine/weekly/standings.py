"""League standings, playoff line and remaining schedule from ESPN.

Facts only: records, points for/against, where the last playoff seed
sits, how many games are left and who they are against. It does not
turn any of that into a chance of making the playoffs; there is no
calibrated model for that here, and a simulated percentage would read
as more certain than it is.
"""
from __future__ import annotations


def table(settings: dict, schedule: list[dict]) -> dict:
    names = {t["id"]: t["name"] for t in settings["teams"]}
    reg_weeks = settings.get("regular_season_weeks") or 14
    rec = {tid: {"id": tid, "name": n, "w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0, "games": 0}
           for tid, n in names.items()}
    remaining: dict[int, list[tuple[int, int]]] = {tid: [] for tid in names}
    live: dict[int, tuple[int, int, float, float]] = {}
    current = settings.get("matchup_period") or 0
    decided = set()
    for m in schedule:
        if not m["period"] or m["period"] > reg_weeks or m["away_id"] is None:
            continue
        h, a = m["home_id"], m["away_id"]
        if m["winner"] in ("HOME", "AWAY", "TIE"):
            decided.add(m["period"])
            for me, opp, mine, theirs in ((h, a, m["home_pts"], m["away_pts"]),
                                          (a, h, m["away_pts"], m["home_pts"])):
                r = rec[me]
                r["games"] += 1
                r["pf"] += mine or 0
                r["pa"] += theirs or 0
                if m["winner"] == "TIE":
                    r["t"] += 1
                elif (m["winner"] == "HOME") == (me == h):
                    r["w"] += 1
                else:
                    r["l"] += 1
        else:
            remaining[h].append((m["period"], a))
            remaining[a].append((m["period"], h))
            if m["period"] <= current:
                live[h] = (m["period"], a, m["home_pts"] or 0, m["away_pts"] or 0)
                live[a] = (m["period"], h, m["away_pts"] or 0, m["home_pts"] or 0)
    order = sorted(rec.values(), key=lambda r: (-(r["w"] + 0.5 * r["t"]), -r["pf"]))
    return {"order": order, "remaining": remaining, "names": names, "live": live,
            "decided_weeks": sorted(decided), "reg_weeks": reg_weeks}


def report(settings: dict, schedule: list[dict], my_id: int | None) -> str:
    t = table(settings, schedule)
    seeds = settings.get("playoff_teams") or 6
    rule = settings.get("playoff_seeding") or "?"
    order = t["order"]
    line = order[seeds - 1] if len(order) >= seeds else None
    line_wins = (line["w"] + 0.5 * line["t"]) if line else None
    done = t["decided_weeks"]
    out = [f"{settings['league']} standings after final week {done[-1] if done else 0} of "
           f"{t['reg_weeks']} regular-season weeks; top {seeds} make the playoffs; "
           f"tiebreak/seeding rule {rule} (points for).",
           f"  {'#':>2} {'team':28} {'W-L-T':7} {'PF':>7} {'PA':>7} {'PF/g':>6} {'left':>4} {'GB':>4}"]
    for i, r in enumerate(order, 1):
        wins = r["w"] + 0.5 * r["t"]
        gb = (line_wins - wins) if line_wins is not None else 0
        left = len(t["remaining"][r["id"]])
        pg = r["pf"] / r["games"] if r["games"] else 0
        mark = "  <- you" if r["id"] == my_id else ""
        cut = "  -- playoff line --" if i == seeds else ""
        out.append(f"  {i:>2} {r['name'][:28]:28} {r['w']}-{r['l']}-{r['t']:<3} {r['pf']:7.1f} {r['pa']:7.1f} "
                   f"{pg:6.1f} {left:>4} {gb:>+4.1f}{mark}{cut}")
    if my_id in t["names"]:
        me = next(r for r in order if r["id"] == my_id)
        left = sorted(t["remaining"][my_id])
        best = me["w"] + 0.5 * me["t"] + len(left)
        out.append(f"You: {me['w']}-{me['l']}-{me['t']}, {len(left)} regular-season games left, "
                   f"so at most {best:g} wins. The current #{seeds} seed has {line_wins:g}"
                   + (f" with {len(left)} games left too." if line else "."))
        out.append(f"Tiebreaks go to points for: you have {me['pf']:.1f}; "
                   f"#{seeds} has {line['pf']:.1f}." if line else "")
        recs = {r["id"]: r for r in order}
        out.append("Remaining schedule (opponent record, points for per game):")
        for week, opp in left:
            o = recs[opp]
            pg = o["pf"] / o["games"] if o["games"] else 0
            now = t["live"].get(my_id)
            score = (f"  IN PROGRESS {now[2]:.0f}-{now[3]:.0f} (live, not final)"
                     if now and now[0] == week else "")
            out.append(f"  wk{week:>2} vs {o['name'][:28]:28} {o['w']}-{o['l']}-{o['t']}  {pg:.1f} PF/g{score}")
    out.append("Records and schedule only: no playoff probability is computed. Use "
               "power_rankings for roster strength; a point lead is not a win chance.")
    return "\n".join(x for x in out if x)
