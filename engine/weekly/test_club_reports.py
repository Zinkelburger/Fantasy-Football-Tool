"""Parser tests for club_reports.py, offline: the fixture is the shape the
league CMS renders, including the two quirks of the opponent's table."""
import unittest
import json
import tempfile
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import club_reports as cr

# Two tables, as a club page serves them: the host club's own report
# (Position in its own column, UNSPECIFIED until Friday) and the
# opponent's (position inside the name cell, "(-)" for undesignated).
PAGE = """
<img src="https://static.www.nfl.com/t_q-best/league/api/clubs/logos/BAL">
<span class="nfl-o-injury-report__club-name">Baltimore Ravens</span>
<table><thead><tr><th>Player</th><th>Position</th><th>Injury</th>
<th>Wed</th><th>Thu</th><th>Fri</th><th>Game Status</th></tr></thead>
<tbody>
<tr><td><a href="/x">Zay Flowers</a></td><td>WR</td><td><span>Hamstring</span></td>
<td>DNP</td><td>LP</td><td></td><td class="g">UNSPECIFIED</td></tr>
<tr><td>Calais Campbell</td><td>DL</td><td>NIR - Rest</td>
<td>DNP</td><td></td><td></td><td>UNSPECIFIED</td></tr>
</tbody></table>
<img src="https://static.www.nfl.com/t_q-best/league/api/clubs/logos/AZ">
<span class="nfl-o-injury-report__club-name">Arizona Cardinals</span>
<table><thead><tr><th>Player</th><th>Position</th><th>Injury</th>
<th>Wed</th><th>Thu</th><th>Fri</th><th>Game Status</th></tr></thead>
<tbody>
<tr><td>Trey McBride, TE</td><td></td><td>Ankle</td>
<td>LP</td><td></td><td></td><td>(-)</td></tr>
<tr><td>Somebody Doubtful, QB</td><td></td><td>Knee</td>
<td>DNP</td><td>DNP</td><td>DNP</td><td>DOUBTFUL</td></tr>
</tbody></table>
"""


class ParseTest(unittest.TestCase):
    def rows(self):
        with patch.object(cr, "_get", return_value=PAGE):
            return cr.injury_report("BAL", 2)

    def test_thursday_game_preserves_monday_and_tuesday(self):
        page = PAGE.replace("<th>Wed</th><th>Thu</th><th>Fri</th>",
                            "<th>Mon</th><th>Tue</th><th>Wed</th>")
        with patch.object(cr, "_get", return_value=page):
            row = cr.injury_report("BAL", 2)[0]
        self.assertEqual((row["mon"], row["tue"], row["wed"]), ("DNP", "LP", ""))
        self.assertEqual(cr.latest_practice_day(row), ("tue", "LP"))

    def test_rows_are_attributed_to_their_own_table(self):
        by_name = {r["player"]: r for r in self.rows()}
        self.assertEqual(by_name["Zay Flowers"]["team"], "BAL")
        # The opponent's table belongs to the opponent, not to the host,
        # and the CDN's AZ is nflverse's ARI.
        self.assertEqual(by_name["Trey McBride"]["team"], "ARI")
        self.assertTrue(all(r["page_team"] == "BAL" for r in self.rows()))

    def test_opponent_table_position_comes_out_of_the_name(self):
        row = next(r for r in self.rows() if r["player"] == "Trey McBride")
        self.assertEqual(row["position"], "TE")
        self.assertEqual(row["injury"], "Ankle")

    def test_undesignated_is_empty_in_both_spellings(self):
        rows = {r["player"]: r["game_status"] for r in self.rows()}
        self.assertEqual(rows["Zay Flowers"], "")      # UNSPECIFIED
        self.assertEqual(rows["Trey McBride"], "")     # (-)
        self.assertEqual(rows["Somebody Doubtful"], "DOUBTFUL")

    def test_practice_days_and_latest_filled_day(self):
        row = next(r for r in self.rows() if r["player"] == "Zay Flowers")
        self.assertEqual((row["wed"], row["thu"], row["fri"]), ("DNP", "LP", ""))
        # Friday is blank because it has not posted, so Thursday is latest.
        self.assertEqual(cr.latest_practice_day(row), ("thu", "LP"))
        self.assertEqual(cr.latest_practice_day({"wed": "", "thu": "", "fri": ""}),
                         ("", ""))

    def test_every_club_has_a_host(self):
        from common import TEAMS
        self.assertEqual(sorted(cr.CLUB_HOSTS), sorted(TEAMS))


ARTICLE = """
<h1>Saints Wednesday Injury Report: Week 2 vs. Ravens</h1>
<h2>NEW ORLEANS SAINTS</h2>
<table><thead><tr><th>Position</th><th>Name</th><th>Injury</th>
<th>Wednesday</th><th>Thursday</th></tr></thead><tbody>
<tr><td>TE</td><td>Saint Player</td><td>Illness</td><td>DNP</td><td></td></tr>
</tbody></table>
<h2>BALTIMORE RAVENS</h2>
<table><thead><tr><th>Player</th><th>Position</th><th>Injury</th><th>Wednesday</th></tr></thead>
<tbody><tr><td>Other Player</td><td>WR</td><td>Knee</td><td>LP</td></tr></tbody></table>
"""
ARTICLE_URL = "https://www.neworleanssaints.com/news/week-2-injury-report"
GAME = {"game_date": "2026-09-20", "opponent": "BAL"}


def item(title="Saints Injury Report: Week 2 vs. Ravens", url=ARTICLE_URL,
         published="Wed, 16 Sep 2026 20:41:53 GMT"):
    return f"<item><title>{title}</title><link>{url}</link><pubDate>{published}</pubDate></item>"


def feed(*items):
    return "<rss><channel>" + "".join(items) + "</channel></rss>"


class ArticleFallback(unittest.TestCase):
    def test_heading_attribution_and_full_weekday_headers(self):
        rows = cr.parse_article(ARTICLE, "NO", 2, ARTICLE_URL)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["player"], "Saint Player")
        self.assertEqual((rows[0]["wed"], rows[0]["thu"]), ("DNP", ""))
        self.assertEqual(rows[0]["source_kind"], "club_article")
        self.assertEqual(rows[0]["source"], ARTICLE_URL)
        self.assertEqual(cr.latest_practice_day(rows[0]), ("wed", "DNP"))

    def test_jets_shape_and_opponent_game_status_typo(self):
        page = ARTICLE.replace("NEW ORLEANS SAINTS", "New York Jets").replace(
            "BALTIMORE RAVENS", "Green Bay Packers").replace("<th>Name</th>", "<th>Player</th>")
        rows = cr.parse_article(page, "NYJ", 2, "https://www.newyorkjets.com/news/example")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["team"], "NYJ")
        self.assertEqual(cr.parse_article(page.replace("New York Jets", "Unknown Club"),
                                         "NYJ", 2, ARTICLE_URL), [])

    def test_rss_rejects_wrong_week_season_opponent_and_host(self):
        rejected = [item(title="Injury Report Week 1 vs. Ravens"),
                    item(published="Wed, 17 Sep 2025 20:41:53 GMT"),
                    item(title="Injury Report Week 2 vs. Lions"),
                    item(title="Preseason Injury Report Week 2 vs. Ravens"),
                    item(url="https://example.com/news/report")]
        for candidate in rejected:
            with self.subTest(candidate=candidate), patch.object(cr, "_get", return_value=feed(candidate)) as get:
                rows, _ = cr.article_report("NO", 2, GAME)
                self.assertEqual(rows, [])
                self.assertEqual(get.call_count, 1)
        with patch.object(cr, "_get", side_effect=[feed(item(), *rejected), ARTICLE]) as get:
            rows, meta = cr.article_report("NO", 2, GAME)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.args[0], ARTICLE_URL)
        self.assertEqual(meta["status"], "available")
        self.assertEqual(rows[0]["published_at"], "2026-09-16T20:41:53+00:00")

    def test_newest_report_wins_even_when_rss_is_unsorted(self):
        newer = ARTICLE_URL + "-thursday"
        rss = feed(item(), item(url=newer, published="Thu, 17 Sep 2026 21:00:00 GMT"))
        with patch.object(cr, "_get", side_effect=[rss, ARTICLE.replace("<td>DNP</td><td></td>",
                                                                    "<td>DNP</td><td>LP</td>")]) as get:
            rows, _ = cr.article_report("NO", 2, GAME)
        self.assertEqual(get.call_args.args[0], newer)
        self.assertEqual(cr.latest_practice_day(rows[0]), ("thu", "LP"))

    def test_week_can_be_in_article_slug_instead_of_title(self):
        rss = feed(item(title="Injury Report: Saints vs. Ravens"))
        with patch.object(cr, "_get", side_effect=[rss, ARTICLE]):
            rows, _ = cr.article_report("NO", 2, GAME)
        self.assertEqual(len(rows), 1)

    def test_build_falls_back_when_grid_only_contains_opponent(self):
        opponent = cr.parse_article(ARTICLE, "BAL", 2, ARTICLE_URL)
        with tempfile.TemporaryDirectory() as tmp, patch.object(cr, "DATA", Path(tmp)), \
                patch.object(cr, "nfl_state", return_value={"season": 2026}), \
                patch.object(cr, "injury_report", return_value=opponent), \
                patch.object(cr, "_game_schedule", return_value={"NO": GAME}), \
                patch.object(cr, "_get", side_effect=[feed(item()), ARTICLE]):
            df = cr.build(2026, 2, ["NO"])
            manifest = json.loads(cr.report_path(2026, 2, ["NO"]).with_suffix(".sources.json").read_text())
            self.assertIn("NO", df["team"].to_list())
            self.assertEqual(manifest["missing_teams"], [])
            self.assertEqual(manifest["coverage"]["NO"]["status"], "available")
            self.assertEqual(manifest["teams"]["NO"]["article_fallback"]["status"], "available")

    def test_failed_fallback_is_recorded_and_does_not_erase_opponent(self):
        opponent = cr.parse_article(ARTICLE, "BAL", 2, ARTICLE_URL)
        with tempfile.TemporaryDirectory() as tmp, patch.object(cr, "DATA", Path(tmp)), \
                patch.object(cr, "nfl_state", return_value={"season": 2026}), \
                patch.object(cr, "injury_report", return_value=opponent), \
                patch.object(cr, "_game_schedule", return_value={"NO": GAME}), \
                patch.object(cr, "_get", side_effect=urllib.error.URLError("offline")):
            df = cr.build(2026, 2, ["NO"])
            manifest = json.loads(cr.report_path(2026, 2, ["NO"]).with_suffix(".sources.json").read_text())
            self.assertEqual(df["team"].to_list(), ["BAL"])
            self.assertEqual(manifest["unavailable_teams"], ["NO"])
            self.assertEqual(manifest["teams"]["NO"]["article_fallback"]["status"], "failed")

    def test_monday_game_pending_is_distinct_from_failure_or_overdue(self):
        games = {"LA": {"game_date": "2026-09-21", "opponent": "NYG"}}
        sources = {"LA": {"status": "no_report", "article_fallback": {"status": "not_found"}}}
        now = datetime(2026, 9, 17, 12, tzinfo=ZoneInfo("America/New_York"))
        info = cr.coverage(["LA"], [], sources, games, now)["LA"]
        self.assertEqual(info["status"], "pending")
        self.assertEqual(info["expected_first_report_date"], "2026-09-17")
        self.assertEqual(cr.coverage(["LA"], [], sources, games, now.replace(day=18))["LA"]["status"], "unavailable")
        sources["LA"]["article_fallback"]["status"] = "failed"
        self.assertEqual(cr.coverage(["LA"], [], sources, games, now)["LA"]["status"], "unavailable")

    def test_skill_only_view_does_not_make_a_defense_only_report_missing(self):
        rows = cr.parse_article(ARTICLE, "BAL", 2, ARTICLE_URL)
        rows[0]["position"] = "CB"
        with tempfile.TemporaryDirectory() as tmp, patch.object(cr, "DATA", Path(tmp)), \
                patch.object(cr, "nfl_state", return_value={"season": 2026}), \
                patch.object(cr, "injury_report", return_value=rows):
            self.assertEqual(cr.build(2026, 2, ["BAL"], skill_only=True).height, 0)
            manifest = json.loads(cr.report_path(2026, 2, ["BAL"], True).with_suffix(".sources.json").read_text())
            self.assertEqual(manifest["coverage"]["BAL"]["status"], "available")
            self.assertEqual(manifest["missing_teams"], [])


if __name__ == "__main__":
    unittest.main()
