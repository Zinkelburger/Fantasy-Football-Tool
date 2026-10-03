"""Query layer, schedule, history, standings, league points, findings and the
compact text views agents read. Offline: every test builds its own files."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import polars as pl

import datastore
import findings_index
import league_points
import mcp_server as S
import player_history as ph
import schedule_view as sv
import standings
import target_share as ts


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def game(week, away, home, a=None, h=None, spread=None, total=None, day="2026-09-13"):
    return {"game_id": f"2026_{week:02d}_{away}_{home}", "season": 2026, "game_type": "REG",
            "week": week, "gameday": day, "weekday": "Sunday", "gametime": "13:00",
            "away_team": away, "home_team": home, "away_score": a, "home_score": h,
            "spread_line": spread, "total_line": total, "roof": "outdoors", "stadium": "X",
            "away_qb_name": "", "home_qb_name": "", "div_game": 0}


class Files(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.data, self.cache, self.market = root / "data", root / "cache", root / "market"
        for d in (self.data, self.cache, self.market):
            d.mkdir()
        for mod in (datastore, sv, ph):
            for name, value in (("DATA", self.data), ("CACHE", self.cache)):
                if hasattr(mod, name):
                    p = patch.object(mod, name, value)
                    p.start()
                    self.addCleanup(p.stop)
        p = patch.object(sv, "PRESEASON", self.market)
        p.start()
        self.addCleanup(p.stop)
        pl.DataFrame([
            game(1, "LA", "DET", 20, 27, 3.0, 50.0),
            game(1, "BUF", "MIA", 30, 10, -6.0, 48.0),
            game(2, "DET", "BUF", 24, None, 1.0, 51.0, "2026-09-21"),  # not final yet
            game(3, "MIA", "LA", day="2026-09-27"),
        ]).write_parquet(self.cache / "schedules_2026.parquet")
        write_csv(self.data / "advanced_usage_2026_weekly.csv", [
            {"season": 2026, "week": 1, "game_id": "g", "player_id": "p1", "team": "DET",
             "name": "Amon Ra", "position": "WR", "tgt": 10, "team_targets": 40,
             "target_share": 0.25, "snap_share": 0.9},
            {"season": 2026, "week": 1, "game_id": "g", "player_id": "p2", "team": "DET",
             "name": "Sam Tight", "position": "TE", "tgt": 4, "team_targets": 40,
             "target_share": 0.1, "snap_share": 0.7},
        ])
        write_csv(self.data / "injuries_2026.csv", [
            {"week": 1, "team": "DET", "gsis_id": "p2", "full_name": "Sam Tight",
             "position": "TE", "report_status": "Questionable",
             "report_primary_injury": "Knee", "practice_status": "Limited"}])
        write_csv(self.data / "lines_2026.csv", [
            {"week": 1, "team": "DET", "opp": "LA", "home": "true", "imp_own": 26.5,
             "imp_opp": 23.5, "spread": -3, "total": 50, "dome": "true",
             "kickoff": "2026-09-13T17:00", "provider": "x", "played": "true"}])
        write_csv(self.market / "implied_2026.csv", [
            {"team": "Los Angeles Rams", "games": 17, "imp_ppg": 26.0, "imp_opp_ppg": 20.0, "imp_wins": 11},
            {"team": "Miami Dolphins", "games": 17, "imp_ppg": 18.0, "imp_opp_ppg": 25.0, "imp_wins": 5}])


class DataQuery(Files):
    def test_only_single_selects_run(self):
        self.assertIn("only SELECT", datastore.query(2026, "DROP TABLE usage"))
        self.assertIn("one statement", datastore.query(2026, "SELECT 1 FROM usage; SELECT 2 FROM usage"))
        self.assertIn("names no known table", datastore.query(2026, "SELECT 1"))
        self.assertIn("query failed", datastore.query(2026, "SELECT nope FROM usage"))

    def test_rows_are_capped_and_the_cap_is_stated(self):
        out = datastore.query(2026, "SELECT name, tgt FROM usage ORDER BY tgt DESC", limit=1)
        self.assertEqual(out.splitlines()[:2], ["name,tgt", "Amon Ra,10"])
        self.assertIn("more exist", out)
        out = datastore.query(2026, "SELECT name FROM usage", limit=10_000)
        self.assertIn("(2 rows)", out)

    def test_output_is_cut_by_characters(self):
        with patch.object(datastore, "MAX_CHARS", 20):
            out = datastore.query(2026, "SELECT name, team, position FROM usage")
        self.assertIn("output cut at 20 characters", out)

    def test_targets_table_carries_that_weeks_report(self):
        out = datastore.query(2026, "SELECT name, share, report_status FROM targets WHERE pos = 'TE'")
        self.assertIn("Sam Tight,0.1,Questionable", out)

    def test_describe_lists_tables_and_filters_columns(self):
        self.assertIn("targets", datastore.describe(2026))
        cols = datastore.describe(2026, "usage", match="tgt")
        self.assertIn("tgt", cols)
        self.assertNotIn("snap_share", cols.split("columns")[1].split("example")[0])
        self.assertIn("unknown table", datastore.describe(2026, "nope"))


class Schedule(Files):
    def test_implied_sources_are_line_then_nflverse_then_prior(self):
        self.assertEqual(sv.team_weeks(2026, "DET", 1, 1)[0]["imp_own"], 26.5)
        self.assertEqual(sv.team_weeks(2026, "DET", 1, 1)[0]["imp_source"], "line")
        rows = {r["week"]: r for r in sv.team_weeks(2026, "LA", 1, 3)}
        # no posted line for LA: the nflverse spread (home DET -3, total 50)
        self.assertEqual((rows[1]["imp_own"], rows[1]["imp_source"]), (23.5, "nflverse line"))
        self.assertEqual(rows[2]["bye"], True)
        # week 3 has no line and no nflverse spread: preseason prior, averaged.
        self.assertEqual(rows[3]["imp_source"], "preseason prior")
        self.assertEqual(rows[3]["imp_own"], (26.0 + 25.0) / 2)
        det = sv.team_weeks(2026, "DET", 2, 2)[0]
        self.assertEqual((det["imp_own"], det["imp_source"]), (25.0, "nflverse line"))

    def test_team_text_labels_prior_and_results(self):
        text = sv.team_text(2026, "LA", 1, 3)
        self.assertIn("L 20-27", text)
        self.assertIn("BYE", text)
        self.assertIn("not a game line", text)

    def test_completed_weeks_and_missing_usage(self):
        self.assertEqual(sv.completed_weeks(2026), [1])
        gap = sv.usage_gap(2026)          # BUF@MIA finished but has no usage rows
        self.assertIn("BUF@MIA", gap)
        self.assertIn("refresh_week", gap)

    def test_monday_hint_names_both_weeks(self):
        hint = sv.decision_week_hint(2026, 2)
        self.assertIn("0/1 games final", hint)
        self.assertIn("target week 3", hint)
        self.assertIn("pass week=2", sv.decision_week_hint(2026, 1))


class History(Files):
    def setUp(self):
        super().setUp()
        base = {"player_display_name": "Kick Er", "position": "K", "season_type": "REG",
                "team": "GB", "opponent_team": "MIN", "fantasy_points": 0.0,
                "fantasy_points_ppr": 0.0}
        cols = ["fg_made", "fg_att", "fg_missed", "fg_made_0_19", "fg_made_20_29",
                "fg_made_30_39", "fg_made_40_49", "fg_made_50_59", "fg_made_60_",
                "pat_made", "pat_att", "pat_missed"]
        zero = {c: 0 for c in cols}
        pl.DataFrame([{**base, **zero, "player_id": "k1", "season": 2026, "week": 1,
                       "fg_made": 3, "fg_att": 4, "fg_missed": 1, "fg_made_30_39": 1,
                       "fg_made_40_49": 1, "fg_made_50_59": 1, "pat_made": 2, "pat_att": 2}]
                     ).write_parquet(self.cache / "player_stats_2026.parquet")

    def test_kicker_points_follow_standard_rules(self):
        self.assertEqual(ph.kicker_points({"fg_made_30_39": 1, "fg_made_40_49": 1, "fg_made_50_59": 1,
                                           "pat_made": 2, "fg_missed": 1}), 3 + 4 + 5 + 2 - 1)

    def test_kicker_log_and_season(self):
        hit = ph.find("kick er", 2026)[0]
        self.assertEqual(hit["pos"], "K")
        log = "\n".join(ph.weekly(2026, hit["player_id"]))
        self.assertIn("3/4 (1 1 1)", log)
        self.assertIn(" 13", log)
        season = "\n".join(ph.seasons(hit["player_id"], [2026]))
        self.assertIn("approx std 13.0/g, K1", season)

    def test_parse_seasons(self):
        self.assertEqual(ph.parse_seasons("2023-2025", 2026), [2023, 2024, 2025])
        self.assertEqual(ph.parse_seasons("last2", 2026), [2024, 2025])
        self.assertEqual(ph.parse_seasons("1999,2025", 2026), [2025])
        self.assertEqual(ph.parse_seasons("", 2026), [])


class Standings(unittest.TestCase):
    SETTINGS = {"league": "L", "teams": [{"id": i, "name": f"T{i}"} for i in (1, 2, 3, 4)],
                "regular_season_weeks": 3, "playoff_teams": 2, "playoff_seeding": "TOTAL_POINTS_SCORED",
                "matchup_period": 2}
    SCHEDULE = [
        {"period": 1, "home_id": 1, "home_pts": 100, "away_id": 2, "away_pts": 90, "winner": "HOME"},
        {"period": 1, "home_id": 3, "home_pts": 80, "away_id": 4, "away_pts": 120, "winner": "AWAY"},
        {"period": 2, "home_id": 1, "home_pts": 50, "away_id": 3, "away_pts": 60, "winner": "UNDECIDED"},
        {"period": 2, "home_id": 2, "home_pts": 0, "away_id": 4, "away_pts": 0, "winner": "UNDECIDED"},
        {"period": 3, "home_id": 1, "home_pts": 0, "away_id": 4, "away_pts": 0, "winner": "UNDECIDED"},
        {"period": 4, "home_id": 1, "home_pts": 0, "away_id": 2, "away_pts": 0, "winner": "UNDECIDED"},
    ]

    def test_order_is_wins_then_points_for(self):
        t = standings.table(self.SETTINGS, self.SCHEDULE)
        self.assertEqual([r["id"] for r in t["order"]], [4, 1, 2, 3])
        self.assertEqual(len(t["remaining"][1]), 2)     # playoff period 4 excluded

    def test_report_shows_live_score_and_no_probability(self):
        text = standings.report(self.SETTINGS, self.SCHEDULE, 3)
        self.assertIn("IN PROGRESS 60-50", text)
        self.assertIn("-- playoff line --", text)
        self.assertIn("no playoff probability", text)
        self.assertNotIn("%", text)


class LeaguePoints(unittest.TestCase):
    def test_rows_owner_and_open_weeks(self):
        lg = Mock()
        rows = {1: [{"id": 7, "name": "Kick A", "pos": "K", "team": "GB", "espn_actual": 9.0,
                     "on_team_id": 2, "status": "ONTEAM", "pct_owned": 80.0, "waiver": False},
                    {"id": 8, "name": "Kick B", "pos": "K", "team": "TB", "espn_actual": 12.0,
                     "on_team_id": 0, "status": "WAIVERS", "pct_owned": 5.0, "waiver": True}],
                2: [{"id": 8, "name": "Kick B", "pos": "K", "team": "TB", "espn_actual": None,
                     "on_team_id": 0, "status": "WAIVERS", "pct_owned": 5.0, "waiver": True}]}
        settings = {"league": "L", "scoring_format": "std", "teams": [{"id": 2, "name": "Rival"}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(league_points, "CACHE", Path(tmp)):
            lg.player_points.side_effect = lambda w, slots: rows[w]
            text = league_points.report(lg, settings, 2026, [1, 2], "K", open_weeks={2})
            only = league_points.report(lg, settings, 2026, [1, 2], "K", available_only=True)
        self.assertIn("Rival", text)
        self.assertIn("WAIVERS", text)
        self.assertIn("still in progress", text)
        self.assertNotIn("Kick A", only)
        self.assertEqual(lg.player_points.call_count, 2)   # second report reused the cache
        self.assertIn("position must be", league_points.report(lg, settings, 2026, [1], "XX"))


class TargetShareText(unittest.TestCase):
    USAGE = [
        {"week": w, "team": "LA", "player_id": pid, "name": name, "position": pos,
         "tgt": tgt, "team_targets": 30, "snap_share": ""}
        for w, pid, name, pos, tgt in [(1, "a", "Star WR", "WR", 10), (1, "b", "Tight End", "TE", 5),
                                       (2, "b", "Tight End", "TE", 9)]]

    def test_league_line_is_one_per_team_with_flags(self):
        result = {**ts.build(self.USAGE, []), "season": 2026}
        text = ts.league_text(result)
        self.assertEqual(sum(ln.startswith("  LA") for ln in text.splitlines()), 1)
        self.assertIn("historical flags: Star WR WR .33 (no usage in week 2)", text)
        self.assertIn("no team matches", ts.league_text(result, position="RB", flagged_only=True))

    def test_team_and_player_views(self):
        result = {**ts.build(self.USAGE, []), "season": 2026}
        team = ts.team_text("LA", result["teams"]["LA"])
        self.assertIn("tgt 5/9", team)
        self.assertIn("FLAG: no usage in week 2", team)
        self.assertIn("Tight End", ts.team_text("LA", result["teams"]["LA"], "TE"))
        self.assertNotIn("Star WR  ", ts.team_text("LA", result["teams"]["LA"], "TE"))
        who = ts.players_text(result, ["tight end", "Nobody"], ph.norm)
        self.assertIn("LA (team targets 30/30", who)
        self.assertIn("Nobody: no target", who)


class Findings(unittest.TestCase):
    def test_index_rows_and_studies_match_all_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f, r = root / "findings", root / "research" / "kick-study"
            f.mkdir()
            r.mkdir(parents=True)
            (f / "04-kickers.md").write_text("# Kickers\nkicker noise")
            (f / "README.md").write_text("| [04](04-kickers.md) | Kicker scoring is noise | data | High |\n")
            (r / "README.md").write_text("# Kicker streaming study\nkicker wind")
            with patch.object(findings_index, "FINDINGS", f), \
                    patch.object(findings_index, "RESEARCH", root / "research"), \
                    patch.object(findings_index, "ROOT", root):
                out = findings_index.search("kicker")
                self.assertIn("finding 04 [High] Kicker scoring is noise", out)
                self.assertIn("study kick-study", out)
                self.assertIn("no finding", findings_index.search("kicker quantum"))


class Transactions(unittest.TestCase):
    def test_pick_by_name_exact_partial_and_ambiguous(self):
        pool = [{"id": 1, "name": "Kyle Williams", "pos": "WR", "team": "NE"},
                {"id": 2, "name": "Savion Williams", "pos": "WR", "team": "GB"},
                {"id": 3, "name": "Darnell Washington", "pos": "TE", "team": "PIT"}]
        self.assertEqual(S._pick(pool, "darnell washington")[0]["id"], 3)
        self.assertEqual(S._pick(pool, "Savion")[0]["id"], 2)
        hit, why = S._pick(pool, "Williams")
        self.assertIsNone(hit)
        self.assertIn("ambiguous", why)
        self.assertEqual(S._pick(pool, "Nobody"), (None, "no match"))

    def test_week_range(self):
        self.assertEqual(S._week_range("", 1, 3), (1, 3))
        self.assertEqual(S._week_range("4-9", 1, 3), (4, 9))
        self.assertEqual(S._week_range("5", 1, 3), (5, 5))
        with self.assertRaises(ValueError):
            S._week_range("9-4", 1, 3)


if __name__ == "__main__":
    unittest.main()
