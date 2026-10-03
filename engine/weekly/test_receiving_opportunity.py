"""Decision evidence regressions: partial-game injuries, dates, identity and bounds."""
import unittest
from unittest.mock import Mock, patch

import mcp_server as S
import receiving_opportunity as ro
from test_target_share import use


USAGE = [
    use(w, pid, name, targets, total, team="CAR", pos=pos, snaps=snap)
    for w, total, coker, waller, csnap, wsnap in [(1, 34, 9, 2, .84, .35), (2, 32, 9, 3, .76, .44), (3, 42, 4, 8, .36, .51)]
    for pid, name, targets, pos, snap in [("c", "Jalen Coker", coker, "WR", csnap), ("w", "Darren Waller", waller, "TE", wsnap)]
]


def practice(status="Out", week=4):
    return {"season": 2026, "week": week, "team": "CAR", "retrieval": {"status": "fresh"},
            "report": {"coverage": {"status": "available"}, "rows": [
                {"player": "Jalen Coker", "team": "CAR", "week": week, "game_status": status,
                 "injury": "Quad", "practice_days": "wed,thu", "wed": "DNP", "thu": "Limited"}]}}


class ReceivingOpportunity(unittest.TestCase):
    def rows(self, usage=USAGE):
        return ro.usage_rows(usage, "CAR", 4, 3, "Jalen Coker")

    def test_partial_game_surfaces_without_calling_it_a_confirmed_absence(self):
        weeks, totals, rows, focus = self.rows()
        self.assertEqual((weeks, totals, focus), ([1, 2, 3], [34, 32, 42], "c"))
        coker = next(r for r in rows if r.player_id == focus)
        waller = rows[0]
        self.assertEqual(coker.prior_target_share_pct, 27.27)
        self.assertTrue(coker.signals)
        self.assertEqual(coker.absence, "not_established")
        self.assertEqual(waller.name, "Darren Waller")
        self.assertEqual(waller.targets, [2, 3, 8])
        self.assertEqual(waller.snap_share_pct, [35, 44, 51])
        self.assertEqual(waller.latest_target_share_pct, 19.05)
        self.assertEqual(waller.change_percentage_points, 11.47)

    def test_common_denominator_and_missing_rows_are_not_active_only_shares(self):
        usage = [r for r in USAGE if not (r["player_id"] == "c" and r["week"] == 2)]
        coker = next(r for r in self.rows(usage)[2] if r.player_id == "c")
        self.assertEqual(coker.prior_target_share_pct, 13.64)  # 9 / 66, not 9 / 34
        self.assertEqual(coker.targets, [9, None, 4])

    def test_decision_week_and_future_usage_cannot_leak_into_baseline(self):
        usage = USAGE + [use(4, "c", "Jalen Coker", 40, 50, team="CAR")]
        self.assertEqual(self.rows(usage), self.rows())

    def test_one_game_has_no_invented_baseline(self):
        rows = self.rows([r for r in USAGE if r["week"] == 3])[2]
        self.assertTrue(all(r.prior_target_share_pct is None and r.change_percentage_points is None for r in rows))

    def test_full_unique_concern_name_required(self):
        for concern in ["Coker", "Unknown Player"]:
            with self.assertRaisesRegex(ValueError, "full player name"):
                ro.usage_rows(USAGE, "CAR", 4, 3, concern)
        duplicate = USAGE + [use(3, "other", "Jalen Coker", 1, 42, team="CAR")]
        with self.assertRaises(ValueError):
            self.rows(duplicate)

    def test_only_matching_fresh_week_report_establishes_out(self):
        for status, expected in [("Out", "reported_out"), ("Doubtful", "uncertain"), ("Questionable", "uncertain"), ("", "not_established")]:
            rows = self.rows()[2]
            ro.attach_practice(rows, practice(status), 2026, 4, "CAR")
            self.assertEqual(next(r for r in rows if r.player_id == "c").absence, expected)
        for evidence in [practice(week=3), {**practice(), "retrieval": {"status": "stale"}},
                         {**practice(), "team": "SEA"}, {"state": "pending"}]:
            rows = self.rows()[2]
            ro.attach_practice(rows, evidence, 2026, 4, "CAR")
            self.assertTrue(all(r.practice is None and r.absence == "not_established" for r in rows))

    def test_wrong_row_week_and_partial_name_do_not_match(self):
        for update in [{"week": 3}, {"player": "Jalen Coker Jr Other"}, {"team": "SEA"}]:
            evidence = practice()
            evidence["report"]["rows"][0].update(update)
            rows = self.rows()[2]
            ro.attach_practice(rows, evidence, 2026, 4, "CAR")
            self.assertTrue(all(r.practice is None for r in rows))

    def test_availability_uses_id_or_unique_exact_name_never_substrings(self):
        rows = self.rows()[2]
        pool = [{"id": 1, "name": "Darren Waller", "pos": "TE", "team": "CAR", "status": "WAIVERS"},
                {"id": 2, "name": "Jalen Coker Other", "pos": "WR", "team": "CAR", "status": "FREEAGENT"}]
        ro.attach_availability(rows, pool, {})
        self.assertEqual(rows[0].availability, "waivers")
        self.assertEqual(rows[1].availability, "unknown")
        ro.attach_availability(rows, pool, {"2": "c"})
        self.assertEqual(rows[1].availability, "free_agent")
        rows = self.rows()[2]
        ro.attach_availability(rows, pool + [{**pool[0], "id": 3}], {})
        self.assertEqual(rows[0].availability, "unknown")
        rows = self.rows()[2]
        ro.attach_availability(rows, pool, {"1": "a_different_gsis_id"})
        self.assertEqual(rows[0].availability, "unknown")

    def test_conflicting_denominators_fail_instead_of_misleading_share(self):
        with self.assertRaisesRegex(ValueError, "Conflicting team target totals"):
            self.rows(USAGE + [use(3, "other", "Other WR", 1, 99, team="CAR")])

    def test_large_team_shortlist_is_bounded_and_reports_omissions(self):
        usage = USAGE + [use(3, f"extra{i}", f"Extra Receiver {i}", 1, 42, team="CAR") for i in range(30)]
        with patch.object(S, "_read_csv", return_value=usage), \
                patch.object(S, "practice_report", return_value={"state": "pending"}), \
                patch.object(S, "_league", side_effect=RuntimeError), \
                patch("schedule_view.games", return_value=[]):
            result = S.receiving_opportunity("CAR", 4, 2026, "Jalen Coker", top=8)
            self.assertEqual(len(result.candidates), 8)
            self.assertEqual(result.omitted_players, 23)
            self.assertLess(len(result.model_dump_json()), 7000)

    def test_missing_completed_game_and_bye_are_explicit(self):
        usage = [r for r in USAGE if r["week"] != 2]
        games = [{"week": w, "home_team": "CAR", "away_team": "SEA", "home_score": 10, "away_score": 9}
                 for w in range(1, 4)]
        with patch.object(S, "_read_csv", return_value=usage), \
                patch.object(S, "practice_report", return_value={"state": "pending"}), \
                patch.object(S, "_league", side_effect=RuntimeError), \
                patch("schedule_view.games", return_value=games):
            result = S.receiving_opportunity("CAR", 4, 2026)
            self.assertTrue(any("STALE usage" in n and "[2]" in n for n in result.notes))
            self.assertTrue(any("No scheduled CAR game" in n for n in result.notes))

    def test_wrapper_bounds_output_flags_transferred_player_and_preserves_unknowns(self):
        league = Mock()
        league.settings.return_value = {"scoring_format": "std"}
        league.rosters.return_value = {}
        league.free_agents.return_value = [{"id": 1, "name": "Darren Waller", "pos": "TE", "team": "SEA", "status": "WAIVERS"}]
        with patch.object(S, "_read_csv", return_value=USAGE), \
                patch.object(S, "practice_report", return_value={"state": "pending"}), \
                patch.object(S, "_league", return_value=league), \
                patch.object(S, "_crosswalk", return_value={"1": "w"}), \
                patch("schedule_view.games", return_value=[]):
            result = S.receiving_opportunity("CAR", 4, 2026, "Jalen Coker", top=1)
            self.assertEqual(len(result.candidates), 1)
            self.assertIn("Live ESPN team is SEA", result.candidates[0].signals[0])
            self.assertEqual(result.concern.availability, "unknown")
            self.assertEqual(result.practice_coverage, "pending")
            self.assertEqual(result.scoring_format, "std")
            self.assertLess(len(result.model_dump_json()), 6000)
            league.settings.side_effect = RuntimeError("secret credential should never be returned")
            failed = S.receiving_opportunity("CAR", 4, 2026)
            self.assertEqual(failed.league_status, "unavailable")
            self.assertNotIn("secret credential", failed.model_dump_json())
            self.assertTrue(all(r.availability == "unknown" for r in failed.candidates))
            for kwargs in [{"last": 0}, {"last": 7}, {"top": 9}, {"top": 0}]:
                with self.assertRaises(ValueError):
                    S.receiving_opportunity("CAR", 4, 2026, **kwargs)


if __name__ == "__main__":
    unittest.main()
