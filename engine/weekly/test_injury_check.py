"""injury_check helpers: next game, report timing, absences, summary; no network."""
import unittest
from datetime import datetime, timezone

import injury_check as ic

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

    def test_bye_week_is_reported_on_the_way(self):
        lines = [r for r in LINES if not (r["team"] == "LA" and r["week"] == 4)]
        game = ic.next_game("LA", lines, MONDAY, 3)
        self.assertEqual((game["week"], game["byes_before"]), (5, [4]))


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


if __name__ == "__main__":
    unittest.main()
