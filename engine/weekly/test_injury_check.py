"""injury_check helpers: next game, report timing, absences, summary; no network."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import injury_check as ic
import mcp_server as S

LINES = [
    {"week": 3, "team": "LA", "opp": "DEN", "home": "false", "kickoff": "2026-09-27T20:20", "played": "true"},
    {"week": 4, "team": "LA", "opp": "PHI", "home": "false", "kickoff": "2026-10-04T17:00Z", "played": "false"},
    {"week": 3, "team": "PHI", "opp": "CHI", "home": "false", "kickoff": "2026-09-28T20:15", "played": "false"},
    {"week": 4, "team": "PHI", "opp": "LA", "home": "true", "kickoff": "2026-10-04T17:00Z", "played": "false"},
    {"week": 5, "team": "LA", "opp": "SF", "home": "true", "kickoff": "2026-10-08T20:15", "played": "false"},
]
MONDAY = datetime(2026, 9, 28, 16, tzinfo=timezone.utc)


class NextGame(unittest.TestCase):
    def test_monday_question_rolls_to_next_week_only_for_teams_already_done(self):
        self.assertEqual(ic.next_game("LA", LINES, MONDAY, 3)["week"], 4)
        self.assertEqual(ic.next_game("PHI", LINES, MONDAY, 3)["week"], 3)

    def test_naive_eastern_kickoff_counts_as_started(self):
        after_mnf = datetime(2026, 9, 29, 1, tzinfo=timezone.utc)  # 21:00 ET Monday
        self.assertEqual(ic.next_game("PHI", LINES, after_mnf, 3)["week"], 4)

    def test_missing_odds_never_establish_a_bye(self):
        lines = [r for r in LINES if not (r["team"] == "LA" and r["week"] == 4)]
        game = ic.next_game("LA", lines, MONDAY, 3)
        self.assertEqual((game["week"], game["byes_before"], game["unknown_weeks_before"]), (5, [], [4]))

    def test_schedule_supplies_a_game_with_no_betting_line(self):
        game = ic.next_game("PHI", [], MONDAY, 4, SCHEDULE)
        self.assertEqual((game["week"], game["opp"], game["byes_before"]), (4, "CAR", []))
        self.assertEqual(game["kickoff_utc"], "2026-10-04T17:00:00+00:00")

    def test_complete_team_schedule_establishes_a_real_bye(self):
        schedule = [{**SCHEDULE[0], "week": w} for w in range(1, 19) if w != 4]
        game = ic.next_game("PHI", [], MONDAY, 4, schedule)
        self.assertEqual((game["week"], game["byes_before"]), (5, [4]))

    def test_explicit_week_does_not_silently_roll_forward(self):
        game = ic.next_game("LA", LINES, MONDAY, 3, exact_week=True)
        self.assertEqual(game["week"], 3)


class Timeline(unittest.TestCase):
    def test_report_days_follow_game_day(self):
        sunday = ic.timeline(ic.kickoff("2026-10-04T17:00Z"))
        self.assertIn("Wed 2026-09-30", sunday["first_practice_report"])
        self.assertIn("Fri 2026-10-02", sunday["final_report_with_designation"])
        self.assertEqual(sunday["inactives_about"], "Sun Oct 04 11:30 ET")
        thursday = ic.timeline(ic.kickoff("2026-10-08T20:15"))
        self.assertIn("Mon 2026-10-05", thursday["first_practice_report"])
        self.assertIn("Wed 2026-10-07", thursday["final_report_with_designation"])
        monday = ic.timeline(ic.kickoff("2026-09-28T20:15"))
        self.assertIn("Thu 2026-09-24", monday["first_practice_report"])
        self.assertIn("Sat 2026-09-26", monday["final_report_with_designation"])


class Evidence(unittest.TestCase):
    def test_resolve_prefers_exact_and_ignores_suffixes(self):
        players = [{"name": "Ollie Gordon II"}, {"name": "Josh Gordon"}]
        self.assertEqual(ic.resolve("ollie gordon", players), [players[0]])
        self.assertEqual(len(ic.resolve("gordon", players)), 2)

    def test_report_row_and_absences(self):
        report = {"report": {"coverage": {"status": "available"}, "rows": [
            {"player": "Puka Nacua", "week": 3, "injury": "Hip", "practice_days": "wed,thu,fri",
             "wed": "DNP", "thu": "DNP", "fri": "LP", "game_status": "DOUBTFUL", "source": "u"}]}}
        row = ic.report_row(report, "Puka Nacua")
        self.assertEqual(row["practice"], {"wed": "DNP", "thu": "DNP", "fri": "LP"})
        self.assertEqual(row["designation"], "DOUBTFUL")
        self.assertIsNone(ic.report_row(report, "Davante Adams"))
        self.assertEqual(ic.report_state(report), "available")
        usage = [{"week": w, "team": "LA", "player_id": "x" if w != 1 else "puka"} for w in (1, 2, 3)]
        injuries = [{"week": 3, "gsis_id": "puka", "report_status": "Out"}]
        self.assertEqual(ic.missed("puka", "LA", usage, injuries),
                         {"team_weeks_on_file": [1, 2, 3], "no_usage_weeks": [2, 3],
                          "reported_out_weeks": [3]})

    def test_summary_states_facts_and_news_without_odds(self):
        game = {"week": 4, "opp": "PHI", "home": False}
        times = ic.timeline(ic.kickoff("2026-10-04T17:00Z"))
        gone = {"no_usage_weeks": [2, 3], "reported_out_weeks": []}
        text = ic.summary("Puka Nacua", "WR", "LA", game, None, "not published yet", None,
                          gone, "OUT", times,
                          [{"at": "2026-09-27T23:10:23Z", "by": "wire", "text": "Puka inactive"}])
        for fact in ("No usage in week(s) 2, 3", "@PHI", "first report Wed 2026-09-30",
                     "ESPN tag: OUT", "Puka inactive"):
            self.assertIn(fact, text)
        self.assertNotIn("%", text)
        quiet = ic.summary("X", "WR", "LA", game, None, "available", None, gone, None, times, [])
        self.assertIn("not listed is not clearance", quiet)
        self.assertIn("not evidence of health", quiet)

    def test_fetch_failure_is_not_described_as_report_not_yet_published(self):
        game = {"week": 4, "opp": "PHI", "home": False}
        times = ic.timeline(ic.kickoff("2026-10-04T17:00Z"))
        for state in ["unavailable", "stale", "fetch failed: TimeoutError"]:
            text = ic.summary("X", "WR", "LA", game, None, state, None,
                              {"no_usage_weeks": [], "reported_out_weeks": []}, None, times)
            self.assertIn("could not be verified", text)
            self.assertNotIn("not out yet", text)

    def test_current_status_precedes_old_out_designation(self):
        previous = {"week": 3, "injury": "Ankle", "practice": {"fri": "DNP"}, "designation": "Out"}
        text = ic.summary("Player", "WR", "PHI", {"week": 4, "home": True, "opp": "CAR"},
                          None, "pending", previous, {"no_usage_weeks": [], "reported_out_weeks": []},
                          None, ic.timeline(ic.kickoff("2026-10-04T17:00Z")))
        self.assertLess(text.index("Week 4 report"), text.index("Week 3 report"))

    def test_stale_reports_and_mismatched_rows_are_not_current(self):
        report = {"season": 2026, "week": 4, "team": "PHI", "retrieval": {"status": "stale"},
                  "report": {"coverage": {"status": "available"}, "rows": [
                      {"player": "Lane Johnson", "team": "PHI", "week": 3, "game_status": "Out"}]}}
        self.assertEqual(ic.report_state(report), "stale")
        self.assertIsNone(ic.report_row(report, "Lane Johnson"))
        self.assertEqual(ic.current_status(None, "available"), "not_listed")
        self.assertEqual(ic.current_status(None, "pending"), "pending")
        self.assertEqual(ic.current_status(None, "unavailable"), "unavailable")


SCHEDULE = [{"week": 4, "home_team": "PHI", "away_team": "CAR", "gameday": "2026-10-04",
             "gametime": "13:00", "home_score": None, "away_score": None}]


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 9, 30, 21, tzinfo=timezone.utc).astimezone(tz)


class BroadInjuryLookup(unittest.TestCase):
    def setUp(self):
        self.league = Mock()
        self.league.rosters.return_value = {1: [{"id": 1, "name": "Eddy Pineiro", "pos": "K", "team": "CAR", "injury": "ACTIVE"}]}
        self.league.free_agents.return_value = []
        self.league.settings.return_value = {"my_team_id": 1, "teams": [{"id": 1, "name": "Test Team"}]}
        self.files = {"injuries_2026.csv": [{"week": 3, "team": "PHI", "gsis_id": "lane", "full_name": "Lane Johnson", "position": "T"}],
                      "depth_2026.csv": [{"dt": "2026-09-28", "team": "PHI", "gsis_id": "rookie", "espn_id": "20", "player_name": "Unused Rookie", "pos_abb": "WR"}]}
        self.calls = []

        def practice(team, season, week, player, refresh=False, cache_only=False):
            self.calls.append((team, week, refresh, cache_only))
            return {"season": season, "week": week, "team": team, "retrieval": {"status": "fresh"},
                    "report": {"coverage": {"status": "available"}, "rows": [
                        {"player": "Lane Johnson", "position": "T", "team": "PHI", "week": week,
                         "game_status": "Questionable", "injury": "Ankle", "practice_days": "wed", "wed": "Limited"},
                        {"player": "New Signing", "position": "LB", "team": "PHI", "week": week,
                         "game_status": "Out", "practice_days": "wed", "wed": "DNP"}]}}

        for p in [patch.object(S, "_state", return_value=(2026, 4)),
                  patch.object(S, "_read_csv", side_effect=lambda path: self.files.get(path.name, [])),
                  patch.object(S, "_league", return_value=self.league),
                  patch("schedule_view.games", return_value=SCHEDULE),
                  patch("evidence.practice", side_effect=practice),
                  patch("evidence.news", return_value={"posts": [], "coverage_note": "test sample"}),
                  patch("datetime.datetime", FixedClock)]:
            p.start()
            self.addCleanup(p.stop)

    def test_kicker_lineman_and_zero_usage_rookie_resolve_without_opportunity_file(self):
        result = S.injury_check("Eddy Piñeiro,Lane Johnson,Unused Rookie", week=4, season=2026, detail=True)
        kicker, lineman, rookie = result["players"]
        self.assertTrue(all(p["found"] for p in result["players"]))
        self.assertEqual((kicker["pos"], kicker["status"]), ("K", "not_listed"))
        self.assertEqual((lineman["pos"], lineman["status"]), ("T", "questionable"))
        self.assertEqual(rookie["status"], "not_listed")
        self.assertEqual(kicker["absences"]["no_usage_weeks"], [])
        self.assertEqual(lineman["absences"]["no_usage_weeks"], [])
        self.assertEqual(lineman["next_game"]["source"], "saved NFL schedule")

    def test_team_hint_checks_unindexed_name_without_inventing_identity(self):
        found = S.injury_check("New Signing", team="PHI", week=4)["players"][0]
        self.assertTrue(found["found"])
        self.assertEqual(found["status"], "out")
        self.assertEqual(found["pos"], "LB")
        missing = S.injury_check("Invented Name", team="PHI", week=4)["players"][0]
        self.assertFalse(missing["found"])
        self.assertEqual(missing["status"], "identity_unverified")
        self.assertNotIn("news_72h", found)

    def test_roster_kicker_and_refresh_share_one_report_per_team(self):
        self.league.rosters.return_value[1].append({"id": 2, "name": "Other Kicker", "pos": "K", "team": "CAR"})
        result = S.injury_check(roster="mine", week=4, refresh=True)
        self.assertEqual(len(result["players"]), 2)
        self.assertEqual(self.calls, [("CAR", 4, True, False)])

    def test_canonical_names_are_used_for_news(self):
        with patch("evidence.news", return_value={"posts": []}) as news:
            S.injury_check("Johnson", week=4)
            self.assertEqual(news.call_args.args[0], "Lane Johnson")

    def test_news_failure_does_not_leak_error_or_imply_no_news(self):
        with patch("evidence.news", side_effect=RuntimeError("secret credential")):
            result = S.injury_check("Lane Johnson", week=4)
            self.assertIn("News unavailable (RuntimeError)", result["news_note"])
            self.assertNotIn("secret credential", str(result))

    def test_historical_request_uses_cache_only(self):
        with patch("evidence.news", return_value={"posts": []}) as news:
            S.injury_check("Lane Johnson", week=4, season=2025, team="PHI", refresh=True)
            self.assertTrue(news.call_args.kwargs["cache_only"])
            self.assertEqual(self.calls, [("PHI", 4, False, True)])

    def test_same_exact_name_with_two_ids_requires_disambiguation(self):
        self.league.rosters.return_value[1] += [
            {"id": 2, "name": "Same Name", "pos": "WR", "team": "PHI"},
            {"id": 3, "name": "Same Name", "pos": "WR", "team": "CAR"}]
        self.assertEqual(S.injury_check("Same Name", week=4)["players"][0]["status"], "ambiguous")
        self.assertTrue(S.injury_check("Same Name", week=4, team="CAR")["players"][0]["found"])

    def test_live_team_replaces_old_usage_team(self):
        self.files["advanced_usage_2026_weekly.csv"] = [{"name": "Eddy Pineiro", "position": "K", "player_id": "k", "team": "PHI", "week": 2}]
        result = S.injury_check("Eddy Pineiro", week=4)["players"][0]
        self.assertEqual(result["team"], "CAR")

    def test_live_free_agent_team_replaces_saved_depth_identity(self):
        self.league.free_agents.return_value = [{"id": 20, "name": "Unused Rookie", "pos": "WR", "team": "CAR"}]
        result = S.injury_check("Unused Rookie", week=4)["players"][0]
        self.assertEqual(result["team"], "CAR")
        self.assertEqual(result["identity_source"], "live ESPN league roster/pool")

    def test_report_failure_is_unavailable_not_pending(self):
        with patch("evidence.practice", return_value={"retrieval": {"status": "unavailable"}}):
            result = S.injury_check("Lane Johnson", week=4)["players"][0]
            self.assertEqual(result["status"], "unavailable")
            self.assertIn("could not be verified", result["summary"])
            self.assertNotIn("not out yet", result["summary"])


if __name__ == "__main__":
    unittest.main()
