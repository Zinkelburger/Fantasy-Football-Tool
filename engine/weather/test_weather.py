"""Offline tests for ff-weather: the venue map, window parsing, summaries.

    .venv-league-sim/bin/python -m unittest engine/weather/test_weather.py
"""
import glob
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weather as W  # noqa: E402
import mcp_server as S  # noqa: E402

UTC = timezone.utc


class VenueMap(unittest.TestCase):
    def test_every_team_has_one_home(self):
        from common import TEAMS
        homes = [t for s in W.stadiums().values() for t in s["home"]]
        self.assertEqual(sorted(homes), sorted(TEAMS))

    def test_entries_are_complete(self):
        for sid, s in W.stadiums().items():
            self.assertIn(s["roof"], ("outdoor", "retractable", "fixed"), sid)
            self.assertTrue(-90 <= s["lat"] <= 90 and -180 <= s["lon"] <= 180, sid)
            ZoneInfo(s["tz"])

    def test_cached_schedules_all_map(self):
        import polars as pl
        files = glob.glob(str(W.ROOT / "engine/weekly/cache/schedules_*.parquet"))
        if not files:
            self.skipTest("no cached schedule")
        for f in files:
            for g in pl.read_parquet(f).iter_rows(named=True):
                v = W.venue_for_game(g["stadium_id"], g["stadium"], g["home_team"])
                self.assertIsNotNone(v, f"{f}: {g['stadium_id']} {g['stadium']}")

    def test_name_beats_reused_id(self):
        sid, _ = W.venue_for_game("JAX00", "Tottenham Hotspur Stadium", "JAX")
        self.assertEqual(sid, "LON02")
        sid, _ = W.venue_for_game("JAX00", "EverBank Stadium", "JAX")
        self.assertEqual(sid, "JAX00")

    def test_find_stadium(self):
        self.assertEqual(W.find_stadium("GB")[0], "GNB00")
        self.assertEqual(W.find_stadium("Packers")[0], "GNB00")
        self.assertEqual(W.find_stadium("lambeau")[0], "GNB00")
        self.assertEqual(W.find_stadium("Heinz Field")[0], "PIT00")
        self.assertIsNone(W.find_stadium("Chicago, IL"))


class Parsing(unittest.TestCase):
    def test_mph(self):
        self.assertEqual(W._mph("5 to 10 mph"), 10)
        self.assertEqual(W._mph("7 mph"), 7)
        self.assertIsNone(W._mph(None))

    def test_window(self):
        ct = ZoneInfo("America/Chicago")
        b, e = S._window("2026-09-27", 0, ct)
        self.assertEqual((b.hour, e - b), (0, timedelta(hours=24)))
        b, e = S._window("2026-09-27 13:00", 3, ct)
        self.assertEqual(b.astimezone(UTC).hour, 18)
        self.assertEqual(e - b, timedelta(hours=3))

    def test_latlon_place(self):
        p = W.resolve_place("44.5, -88.06")
        self.assertEqual((p["lat"], p["lon"]), (44.5, -88.06))

    def test_geocode_state_qualifier(self):
        fake = {"results": [
            {"name": "Buffalo", "admin1": "Minnesota", "country_code": "US",
             "latitude": 45.1, "longitude": -93.8, "timezone": "America/Chicago"},
            {"name": "Buffalo", "admin1": "New York", "country_code": "US",
             "latitude": 42.9, "longitude": -78.9, "timezone": "America/New_York"}]}
        with mock.patch.object(W, "_get_json", return_value=fake), \
             mock.patch.object(W, "_disk", return_value={}), \
             mock.patch.object(W, "_disk_put"):
            self.assertEqual(W.geocode("Buffalo NY")["lat"], 42.9)
            self.assertEqual(W.geocode("Buffalo, New York")["lat"], 42.9)
            self.assertEqual(W.geocode("Buffalo")["lat"], 45.1)


class Summary(unittest.TestCase):
    def rows(self, **kw):
        t = datetime(2026, 9, 27, 17, tzinfo=UTC)
        base = {"t": t, "temp_f": 60, "wind_mph": 5, "wind_dir": "N", "gust_mph": None,
                "precip_pct": 0, "precip_in": None, "sky": "Clear"}
        return [{**base, "t": t + timedelta(hours=i), **kw} for i in range(4)]

    def test_calm(self):
        self.assertEqual(W.summarise(self.rows())["flags"], [])

    def test_flags(self):
        s = W.summarise(self.rows(wind_mph=18, gust_mph=30, precip_pct=70, temp_f=28))
        self.assertEqual(len(s["flags"]), 4)

    def test_rain_amount_without_probability(self):
        s = W.summarise(self.rows(precip_pct=None, precip_in=0.05))
        self.assertIn("precipitation likely", s["flags"])


class SourceChoice(unittest.TestCase):
    def test_abroad_skips_nws(self):
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        om = {"rows": [{"t": now, "temp_f": 60}], "issued": None, "kind": "forecast"}
        with mock.patch.object(W, "nws_hours") as nws, \
             mock.patch.object(W, "open_meteo_hours", return_value=om):
            src, _, rows = W.hours(51.5, -0.1, now, now + timedelta(hours=1), False)
        nws.assert_not_called()
        self.assertTrue(src.startswith("Open-Meteo"))

    def test_nws_failure_falls_back(self):
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        om = {"rows": [{"t": now, "temp_f": 60}], "issued": None, "kind": "forecast"}
        with mock.patch.object(W, "nws_hours", side_effect=OSError("down")), \
             mock.patch.object(W, "open_meteo_hours", return_value=om):
            src, _, _ = W.hours(44.5, -88.0, now, now + timedelta(hours=1), True)
        self.assertIn("fell back", src)

    def test_beyond_horizon(self):
        far = datetime.now(UTC) + timedelta(days=30)
        with self.assertRaises(LookupError):
            W.hours(44.5, -88.0, far, far + timedelta(hours=3), True)


if __name__ == "__main__":
    unittest.main()
