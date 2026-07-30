"""Command-line interface.

  python -m simfl fetch                         # warm data caches
  python -m simfl draft   --year 2023 --hero zero_rb --seat 5
  python -m simfl season  --year 2023 --hero zero_rb --seat 5
  python -m simfl mc      --year 2023 --hero zero_rb -n 200
  python -m simfl compare --years 2020-2025 --heroes all -n 100
"""

import argparse
import random

from .config import DEFAULT_LEAGUE, DEFAULT_SCORING, SEASONS
from .montecarlo import compare, get_pool, hero_experiment, pooled
from .season import run_season
from .strategies import STRATEGIES, make

BOLD, DIM, GREEN, YELLOW, END = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[0m"


def table(headers: list[str], rows: list[list[str]], highlight_col: int | None = None):
    widths = [max(len(str(headers[c])), *(len(str(r[c])) for r in rows))
              for c in range(len(headers))]
    line = "  ".join(f"{BOLD}{h:<{w}}{END}" for h, w in zip(headers, widths))
    print(line)
    print(DIM + "  ".join("-" * w for w in widths) + END)
    best = None
    if highlight_col is not None and rows:
        best = max(range(len(rows)), key=lambda r: float(rows[r][highlight_col]))
    for i, r in enumerate(rows):
        cells = "  ".join(f"{str(c):<{w}}" for c, w in zip(r, widths))
        print(f"{GREEN}{cells}{END}" if i == best else cells)


def parse_years(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(y) for y in spec.split(",")]


def cmd_fetch(args):
    from .data import fetch_all
    fetch_all(SEASONS, DEFAULT_SCORING)
    print("caches warm for", SEASONS)


def _one_season(args):
    pool, tab = get_pool(args.year)
    rng = random.Random(args.seed)
    strategies = [make("family") for _ in range(DEFAULT_LEAGUE.n_teams)]
    strategies[args.seat - 1] = make(args.hero)
    for s in strategies:
        s.bind_year(args.year)
    return run_season(pool, strategies, DEFAULT_LEAGUE, tab, rng), args.seat - 1, pool


def cmd_draft(args):
    result, seat, pool = _one_season(args)
    hero = result.teams[seat]
    by_pid = {p.pid: p for p in pool}
    print(f"\n{BOLD}{hero.name} — {args.year} draft (seed {args.seed}){END}\n")
    rows = []
    for pid, rnd in sorted(hero.drafted_round.items(), key=lambda kv: kv[1]):
        p = by_pid[pid]
        tot = sum(p.week_pts.values())
        rows.append([rnd, p.name, p.pos, f"{p.adp:.0f}" if p.adp else "--",
                     f"{tot:.0f}", "R" if p.rookie else ""])
    table(["Rd", "Player", "Pos", "ADP", "Season pts", ""], rows)


def cmd_season(args):
    result, seat, pool = _one_season(args)
    hero = result.teams[seat]
    print(f"\n{BOLD}{args.year} season — {hero.name} (seed {args.seed}){END}\n")
    rows = []
    for t in result.standings:
        tag = " 🏆" if t is result.champion else (" *" if t in result.playoff_seeds else "")
        star = ">" if t is hero else " "
        rows.append([star, t.name.replace(" baseline", ""), t.record,
                     f"{t.points_for:.0f}", f"{t.all_play_pct:.3f}", t.moves, tag])
    table(["", "Team", "W-L", "PF", "All-play", "Moves", ""], rows)
    tx = [t for t in result.transactions if t[1] is hero]
    if tx:
        print(f"\n{BOLD}Hero waiver moves:{END}")
        for w, _, a, d in tx:
            print(f"  wk{w:>2}  + {a.name} ({a.pos})  — dropped {d.name}")


def cmd_mc(args):
    stats = hero_experiment(args.year, args.hero, args.n, args.seed)
    s = stats.summary
    print(f"\n{BOLD}{args.year}: {STRATEGIES[args.hero].label} vs 11 family bots "
          f"({s['n']} sims, all seats){END}\n")
    for k, label, fmt in [("avg_wins", "Avg record", None), ("avg_pf", "Avg points for", ".0f"),
                          ("all_play", "All-play win %", ".1%"),
                          ("playoff_pct", "Playoff rate", ".1%"),
                          ("title_pct", "Championship rate", ".1%"),
                          ("avg_finish", "Avg reg-season finish", ".2f"),
                          ("avg_moves", "Waiver adds/season", ".1f")]:
        v = s[k]
        if k == "avg_wins":
            print(f"  {label:<22} {v:.1f}-{14 - v:.1f}")
        else:
            print(f"  {label:<22} {v:{fmt}}")
    print(f"\n  {DIM}A no-edge strategy expects all-play 50.0%, playoffs 50.0%, "
          f"title 8.3%.{END}")


def cmd_compare(args):
    years = parse_years(args.years)
    heroes = list(STRATEGIES) if args.heroes == "all" else args.heroes.split(",")
    results = compare(years, heroes, args.n, args.seed)
    print(f"\n{BOLD}Strategy comparison — seasons {years[0]}–{years[-1]}, "
          f"{args.n} sims/season each vs family field{END}\n")
    rows = []
    for h in heroes:
        s = pooled(results[h])
        rows.append([STRATEGIES[h].label, f"{s['all_play']:.3f}",
                     f"{s['avg_pf']:.0f}", f"{s['playoff_pct']:.1%}",
                     f"{s['title_pct']:.1%}", f"{s['avg_finish']:.2f}"])
    rows.sort(key=lambda r: -float(r[1]))
    table(["Strategy", "All-play", "PF", "Playoffs", "Title", "Avg finish"],
          rows, highlight_col=1)
    print(f"\n{DIM}Baselines: all-play 0.500, playoffs 50.0%, title 8.3%.{END}")
    if args.by_year:
        for h in heroes:
            print(f"\n{BOLD}{STRATEGIES[h].label}{END}")
            yrows = []
            for y in years:
                s = results[h][y].summary
                yrows.append([y, f"{s['all_play']:.3f}", f"{s['avg_pf']:.0f}",
                              f"{s['playoff_pct']:.1%}", f"{s['title_pct']:.1%}"])
            table(["Year", "All-play", "PF", "Playoffs", "Title"], yrows)


def cmd_analyze(args):
    from . import analysis
    if args.what == "kickers":
        rows = [[r["year"], r["wk1_top"], r["wk1_pts"],
                 f"#{r['wk1_top_ros_rank']}" if r["wk1_top_ros_rank"] else "n/a",
                 r["wk1_4_top"],
                 f"#{r['wk1_4_top_ros_rank']}" if r["wk1_4_top_ros_rank"] else "n/a",
                 r["n_kickers"]]
                for r in analysis.kicker_persistence()]
        print(f"\n{BOLD}Hot kicker persistence: does early season K scoring hold up?{END}\n")
        table(["Year", "Wk1 top K", "Pts", "ROS rank", "Wk1-4 top K",
               "ROS rank", "#K"], rows)
    elif args.what == "streaming":
        rows = []
        for r in analysis.streaming_supply(args.pos, after=args.after):
            rows.append([r["year"], r["n_undrafted_in_top"],
                         f"{r['best_undrafted']} ({r['best_undrafted_ros']})",
                         f"#{r['best_undrafted_rank_by_wk']}" if r["best_undrafted_rank_by_wk"] else "n/a",
                         f"{r['early_pick']} ({r['early_pick_ros']})"])
        print(f"\n{BOLD}Punting {args.pos}: rest-of-season top-8 after week "
              f"{args.after} — how many were free agents?{END}\n")
        table(["Year", f"FAs in top8 {args.pos}", "Best FA (ROS ppg)",
               f"its wk1-{args.after} rank", "6th-ADP pick (ROS ppg)"], rows)
        print(f"\n{DIM}Details, e.g. {args.pos} ROS top-8 per year:{END}")
        for r in analysis.streaming_supply(args.pos, after=args.after):
            names = ", ".join(f"{n}[{tag}]{p}" for n, p, tag in r["ros_top_names"])
            print(f"  {r['year']}: {names}")
    elif args.what == "scarcity":
        curves = analysis.scarcity()
        print(f"\n{BOLD}Avg PPG by positional rank, 2020-2025 (standard){END}\n")
        rows = []
        for rank in range(0, 30, 3):
            row = [f"#{rank+1}"]
            for pos in ("QB", "RB", "WR", "TE", "K"):
                c = curves[pos]
                row.append(f"{c[rank]:.1f}" if rank < len(c) else "-")
            rows.append(row)
        table(["Rank", "QB", "RB", "WR", "TE", "K"], rows)


def main():
    ap = argparse.ArgumentParser(prog="simfl", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=cmd_fetch)

    for name, fn in [("draft", cmd_draft), ("season", cmd_season)]:
        p = sub.add_parser(name)
        p.add_argument("--year", type=int, default=2024)
        p.add_argument("--hero", choices=STRATEGIES, default="bpa")
        p.add_argument("--seat", type=int, default=6)
        p.add_argument("--seed", type=int, default=1)
        p.set_defaults(fn=fn)

    p = sub.add_parser("mc")
    p.add_argument("--year", type=int, default=2024)
    p.add_argument("--hero", choices=STRATEGIES, default="bpa")
    p.add_argument("-n", type=int, default=100)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(fn=cmd_mc)

    p = sub.add_parser("analyze")
    p.add_argument("what", choices=["kickers", "streaming", "scarcity"])
    p.add_argument("--pos", default="TE", choices=["TE", "QB", "RB", "WR", "K"])
    p.add_argument("--after", type=int, default=3)
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("compare")
    p.add_argument("--years", default="2020-2025")
    p.add_argument("--heroes", default="all")
    p.add_argument("-n", type=int, default=100)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--by-year", action="store_true")
    p.set_defaults(fn=cmd_compare)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
