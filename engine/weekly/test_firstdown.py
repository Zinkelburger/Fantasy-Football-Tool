"""First Down Studio: parse saved pages only, never another week's."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import firstdown


def _row(name, pos, team, opp, std, **extra):
    return {"name": name, "position": pos, "team": team, "opponent": opp,
            "game_details": f"{team} vs {opp}", "standard": std, "halfppr": std + 1,
            "ppr": std + 2, "standard_erc": 1, "injury_status": None,
            "kickoff_at": "2026-09-27T17:00:00+00:00", "sleeper_id": "1",
            "projected_fields": [], **extra}


def page(season=2026, week=3, generated="2026-09-24T20:57:03+00:00", rows=None):
    """A Next.js page with the snapshot split across two RSC chunks, the
    way First Down serves it (JSON escaped inside a JS string)."""
    rows = rows or [
        _row("Jahmyr Gibbs", "RB", "DET", "NYJ", 19.5, rushing_yards=87.5,
             rushing_attempts=18.7, expected_touchdowns=1.2),
        _row("Jameson Williams", "WR", "DET", "NYJ", 8.1, receiving_yards=55.5, receptions=3.4,
             projected_fields=["rushing_yards", "projected_points"]),
        _row("Josh Allen", "QB", "BUF", "LAC", 24.1, passing_yards=238.5),
    ]
    payload = '3:[["$","$L1d","3",' + json.dumps({"data": {"snapshot": {
        "snapshot_id": "x", "season": season, "week": week, "generated_at": generated,
        "scoring_version": "v2", "rows": rows}}}) + "]]"
    half = len(payload) // 2
    chunks = "".join(f'<script>self.__next_f.push([1,{json.dumps(p)}])</script>'
                     for p in (payload[:half], payload[half:]))
    return f"<html><title>Week {week} Vegas RB Rankings | First Down Studio</title>{chunks}</html>"


SCHEDULE = {"DET": "NYJ", "NYJ": "DET", "BUF": "LAC", "LAC": "BUF"}


class FirstDown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saves = Path(self.tmp.name) / "saves"
        self.saves.mkdir()
        self.cache = patch.object(firstdown, "CACHE", Path(self.tmp.name))
        self.cache.start()

    def tearDown(self):
        self.cache.stop()
        self.tmp.cleanup()

    def save(self, name, html):
        (self.saves / name).write_text(html)

    def test_parse_joins_chunks_and_keeps_standard_points_and_filled_fields(self):
        snap = firstdown.parse(page())
        self.assertEqual((snap["season"], snap["week"]), (2026, 3))
        jamo = next(r for r in snap["rows"] if r["name"] == "Jameson Williams")
        self.assertEqual(jamo["points_std"], 8.1)
        self.assertEqual(jamo["not_from_props"], ["rushing_yards"])
        self.assertTrue(jamo["home"])

    def test_page_without_a_snapshot_parses_to_none(self):
        self.assertIsNone(firstdown.parse("<html>First Down Studio home</html>"))

    def test_import_ignores_other_weeks_and_takes_the_newest_snapshot(self):
        self.save("old.html", page(generated="2026-09-23T10:00:00+00:00"))
        self.save("new.html", page(generated="2026-09-24T20:57:03+00:00"))
        self.save("lastweek.html", page(week=2, generated="2026-09-30T00:00:00+00:00"))
        data = firstdown.import_saved(2026, 3, dirs=[self.saves], schedule=SCHEDULE)
        self.assertEqual(data["generated_at"], "2026-09-24T20:57:03+00:00")
        self.assertTrue(data["source_file"].endswith("new.html"))
        self.assertTrue(firstdown.path(2026, 3).exists())

    def test_import_refuses_matchups_that_disagree_with_the_schedule(self):
        self.save("p.html", page())
        with self.assertRaisesRegex(RuntimeError, "disagree"):
            firstdown.import_saved(2026, 3, dirs=[self.saves], schedule={"DET": "GB", "GB": "DET"})
        self.assertFalse(firstdown.path(2026, 3).exists())

    def test_no_save_explains_how_to_get_one_and_never_fetches(self):
        with patch("urllib.request.urlopen") as fetch:
            with self.assertRaisesRegex(FileNotFoundError, "save it"):
                firstdown.load(2026, 3, dirs=[self.saves])
            fetch.assert_not_called()

    def test_freshness_asks_for_a_new_save_after_the_sunday_checkpoint(self):
        data = {"generated_at": "2026-09-24T20:57:03+00:00"}          # Thu 16:57 ET
        thu_night = datetime(2026, 9, 25, 1, 0, tzinfo=timezone.utc)   # Thu 21:00 ET
        sun_morning = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)  # Sun 10:00 ET
        self.assertIsNone(firstdown.freshness(data, thu_night))
        self.assertRegex(firstdown.freshness(data, sun_morning), "Sun 09:00")

    def test_flex_is_rb_wr_te_by_standard_points(self):
        rows = firstdown.parse(page())["rows"]
        self.assertEqual([r["name"] for r in firstdown.select(rows, "FLEX")],
                         ["Jahmyr Gibbs", "Jameson Williams"])


if __name__ == "__main__":
    unittest.main()
