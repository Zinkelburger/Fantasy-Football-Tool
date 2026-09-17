"""Coverage failures and feed validation must never look like quiet news."""
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import bluesky
import club_reports
import fftiers
from test_club_reports import PAGE
from test_weekly import FFTIERS_CSV, FFTIERS_DST


class NewsTools(unittest.TestCase):
    def test_offline_lines_build_never_fetches_scoreboard(self):
        import lines
        with tempfile.TemporaryDirectory() as tmp, patch.object(lines, "DATA", Path(tmp)), \
                patch.object(lines, "team_rows_from_schedule", return_value=lines._split(
                    2, "BAL", "NO", 3, 40, "outdoors", "2026-09-20", "cached")), \
                patch.object(lines.nfl_data, "espn_scoreboard_odds") as fetch:
            self.assertEqual(lines.build(2026, 2, refresh=False).height, 2)
            fetch.assert_not_called()

    def test_failed_news_fetch_remains_visible_with_a_name_filter(self):
        with patch.object(bluesky, "author_feed", side_effect=urllib.error.URLError("offline")):
            with self.assertWarnsRegex(RuntimeWarning, "coverage missing for reporter"):
                self.assertEqual(bluesky.wire(handles=["reporter"], match=["Flowers"]), [])

    def test_app_password_can_come_from_environment_without_an_env_file(self):
        with patch.object(Path, "exists", return_value=False), patch.dict(
                "os.environ", {"BSKY_HANDLE": "test.example", "BSKY_APP_PASSWORD": "test-only"}):
            with patch.object(bluesky, "_post", return_value={"accessJwt": "test-token"}) as post:
                self.assertEqual(bluesky.session(), "test-token")
                self.assertEqual(post.call_args.args[1]["identifier"], "test.example")

    def test_keyword_search_uses_the_authenticated_endpoint(self):
        with patch.object(bluesky, "_get", return_value={"posts": []}) as get:
            self.assertEqual(bluesky.search("Test Player", token="test-token"), [])
            self.assertEqual(get.call_args.kwargs["base"], bluesky.AUTH_API)
            self.assertEqual(get.call_args.kwargs["token"], "test-token")
            self.assertEqual(get.call_args.kwargs["q"], "Test Player")

    def test_club_build_records_empty_sources_and_preserves_practice_grid(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(club_reports, "DATA", Path(tmp)), \
                patch.object(club_reports, "nfl_state", return_value={"season": 2026}), \
                patch.object(club_reports, "_get", side_effect=[PAGE, "<html></html>"]):
            df = club_reports.build(2026, 2, ["BAL", "ARI"])
            self.assertEqual(df.height, 4)
            import json
            manifest = json.loads(club_reports.report_path(2026, 2, ["BAL", "ARI"])
                                  .with_suffix(".sources.json").read_text())
            self.assertEqual(manifest["teams"]["ARI"]["status"], "no_report")
            self.assertEqual(manifest["teams"]["BAL"]["reported_teams"], ["ARI", "BAL"])
            self.assertFalse(Path(tmp, "club_injuries_2026_wk02.csv").exists())

    def test_historical_club_season_is_rejected_before_fetch(self):
        with patch.object(club_reports, "nfl_state", return_value={"season": 2026}), \
                patch.object(club_reports, "_get") as get:
            with self.assertRaises(ValueError):
                club_reports.build(2025, 2)
            get.assert_not_called()


class RankingsFetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in [("DATA", Path(self.tmp.name)),
                            ("nfl_state", lambda: {"season": 2026, "week": 2, "season_type": "regular"})]:
            p = patch.object(fftiers, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.schedule = {"PHI": "TEN", "TEN": "PHI", "SF": "MIA", "MIA": "SF",
                         "WAS": "NYG", "NYG": "WAS", "DET": "BUF", "BUF": "DET",
                         "ATL": "CAR", "CAR": "ATL", "BAL": "NO", "NO": "BAL"}

    def feed(self, url):
        return (FFTIERS_DST if "-DST.csv" in url else FFTIERS_CSV, None)

    def test_fetch_round_trip_and_bad_schedule_preserves_previous_file(self):
        with patch.object(fftiers, "http_text", side_effect=self.feed):
            rows = fftiers.fetch(2026, 2, schedule=self.schedule)
            path = Path(self.tmp.name, "ecr_2026_wk02.csv")
            before = path.read_bytes()
            self.assertTrue(rows)
            with self.assertRaises(RuntimeError):
                fftiers.fetch(2026, 2, schedule=dict(self.schedule, PHI="NYG"))
            self.assertEqual(path.read_bytes(), before)

    def test_unverifiable_week_and_missing_dst_never_write(self):
        with patch.object(fftiers, "http_text", side_effect=self.feed):
            with self.assertRaises(ValueError):
                fftiers.fetch(2025, 2, schedule=self.schedule)
            with self.assertRaises(ValueError):
                fftiers.fetch(2026, 2, schedule={})
        def without_dst(url):
            if "-DST.csv" in url:
                raise urllib.error.URLError("offline")
            return self.feed(url)
        with patch.object(fftiers, "http_text", side_effect=without_dst):
            with self.assertRaisesRegex(RuntimeError, "no D/ST"):
                fftiers.fetch(2026, 2, schedule=self.schedule)
        self.assertFalse(list(Path(self.tmp.name).iterdir()))

    def test_team_on_bye_reports_mismatch_without_keyerror(self):
        rows = fftiers.parse(FFTIERS_DST, "DST")
        self.assertTrue(fftiers.off_week(rows, {"TEN": "SF", "SF": "TEN", "MIA": "WAS", "WAS": "MIA"}))


if __name__ == "__main__":
    unittest.main()
