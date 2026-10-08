"""start_sit arithmetic/wording and the live line merge. Offline: fetchers are stubbed."""
import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import polars as pl

import lines
import nfl_data
import start_sit as ss


def use(week, pid, name, pos, tgt, rush, team_targets, snap, team="PHI"):
    return {"week": week, "team": team, "player_id": pid, "name": name, "position": pos,
            "tgt": tgt, "rush_att": rush, "team_targets": team_targets, "snap_share": snap}


USAGE = [
    use(2, "te", "Tight End", "TE", 2, 0, 30, 0.25),
    use(2, "wr", "Wide One", "WR", 9, 0, 30, 0.9),
    use(3, "wr", "Wide One", "WR", 6, 0, 20, 0.95),
    use(2, "rb", "Run Back", "RB", 1, 15, 30, 0.6),
    use(3, "rb", "Run Back", "RB", 2, 18, 20, 0.7),
    use(2, "qb", "Quarter Back", "QB", 0, 5, 30, 1.0),
    use(3, "qb", "Quarter Back", "QB", 0, 2, 20, 1.0),
    use(3, "qb2", "Backup Qb", "QB", 0, 0, 20, 0.05),
    use(3, "x", "Other Team", "WR", 9, 0, 40, 0.9, team="DAL"),
    use(5, "wr", "Wide One", "WR", 99, 0, 99, 1.0),       # decision week: never counted
]


class Usage(unittest.TestCase):
    def test_pooled_shares_partial_and_missing_weeks(self):
        tu = ss.team_usage(USAGE, "PHI", 5, 3)
        self.assertEqual(tu["weeks"], [2, 3])
        self.assertEqual(tu["team_targets"], [30.0, 20.0])
        te = ss.player_usage(tu, "te")
        self.assertEqual(te["targets"], [2.0, None])
        self.assertEqual(te["snap_pct"], [25, None])
        self.assertEqual(te["no_usage_weeks"], [3])
        self.assertEqual(te["partial_weeks"], [2])
        self.assertAlmostEqual(te["target_share"], 2 / 50, places=3)
        self.assertEqual(ss.player_usage(tu, None)["targets"], [None, None])

    def test_teammates_come_from_usage_qb_first(self):
        tu = ss.team_usage(USAGE, "PHI", 5, 3)
        self.assertEqual(ss.top_teammates(tu, {"te"}, 2), ["qb", "rb", "wr"])
        self.assertNotIn("x", ss.top_teammates(tu, set(), 6))


class Projection(unittest.TestCase):
    def test_terms_and_official_designation(self):
        p = ss.projection(5.4, 4.5, 22.5, "")
        self.assertEqual((p["matchup_factor"], p["usage_ep_adj"], p["blend"], p["adjusted"]),
                         (1.0, 4.5, 4.95, 4.95))
        self.assertEqual(ss.projection(5.0, None, 30, "Questionable")["adjusted"], 4.0)
        self.assertEqual(ss.projection(5.0, 5.0, 10, "OUT")["adjusted"], 0.0)
        self.assertEqual(ss.projection(5.0, 5.0, 10, "")["matchup_factor"], 0.8)   # clipped
        self.assertIsNone(ss.projection(None, None, 20, "")["adjusted"])
        self.assertIn("-> 4.0", ss.projection_text(ss.projection(5.0, None, 30, "questionable")))


def player(name, adj, status="not_listed", ko=None, locked=False):
    return {"name": name, "status": status, "kickoff_utc": ko, "locked": locked,
            "projection": {"adjusted": adj}}


class Decide(unittest.TestCase):
    NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)

    def test_highest_eligible_and_toss_up(self):
        d = ss.decide([player("A", 4.7), player("B", 4.9)], self.NOW)
        self.assertEqual((d["pick"], d["gap"], d["toss_up"]), ("B", 0.2, True))
        d = ss.decide([player("A", 7.0), player("B", 4.9)], self.NOW)
        self.assertEqual((d["pick"], d["toss_up"]), ("A", False))

    def test_out_doubtful_and_started_games_excluded(self):
        started = self.NOW - timedelta(hours=1)
        d = ss.decide([player("A", 9, "out"), player("B", 8, "doubtful"),
                       player("C", 7, ko=started), player("D", 2)], self.NOW)
        self.assertEqual(d["pick"], "D")
        self.assertEqual(len(d["excluded"]), 3)
        self.assertIsNone(ss.decide([player("A", 9, "out")], self.NOW)["pick"])

    def test_swap_window_uses_inactives_before_other_kickoff(self):
        early = datetime(2026, 10, 11, 13, 30, tzinfo=timezone.utc)
        late = datetime(2026, 10, 11, 17, 0, tzinfo=timezone.utc)
        ps = [player("Early", 1, ko=early), player("Late", 2, ko=late)]
        self.assertIn("can no longer be swapped in", ss.swap_window(ps, "Late"))
        self.assertIn("you can still swap to Late", ss.swap_window(ps, "Early"))


class Flags(unittest.TestCase):
    def test_listed_and_silently_missing_teammates_are_flagged(self):
        base = {"pos": "WR", "weeks": [3, 4], "target_share": 0.25, "carry_share": 0}
        self.assertIn("DNP", ss.teammate_flag({**base, "name": "A", "status": "listed_without_designation",
                                               "report": "Hamstring; Wed DNP", "targets": [5, 6]}))
        self.assertIn("no usage in week 4", ss.teammate_flag({**base, "name": "B", "status": "not_listed",
                                                             "targets": [5, None]}))
        self.assertIsNone(ss.teammate_flag({**base, "name": "C", "status": "not_listed", "targets": [5, 6]}))
        self.assertIsNone(ss.teammate_flag({**base, "name": "D", "target_share": 0.05, "status": "out",
                                            "targets": [1, 1]}))

    def test_results_text(self):
        games = [{"week": 3, "home_team": "CHI", "away_team": "PHI", "home_score": 27, "away_score": 7},
                 {"week": 4, "home_team": "PHI", "away_team": "LA", "home_score": 20, "away_score": 24},
                 {"week": 5, "home_team": "JAX", "away_team": "PHI", "home_score": None, "away_score": None}]
        self.assertEqual(ss.results(games, "PHI", 5, 3), ["wk 3 L 7-27 @CHI", "wk 4 L 20-24 vs LA"])


class LiveLines(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name, value in (("LIVE_DIR", root / "live"), ("DATA", root)):
            p = patch.object(lines, name, value)
            p.start()
            self.addCleanup(p.stop)
        with (root / "lines_2026.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["week", "team", "opp", "home", "imp_own", "imp_opp", "spread",
                                              "total", "dome", "kickoff", "provider", "played"])
            w.writeheader()
            w.writerow({"week": 5, "team": "JAX", "opp": "PHI", "home": "true", "imp_own": 24.5, "imp_opp": 18,
                        "spread": -6.5, "total": 42.5, "dome": "false", "kickoff": "k", "provider": "DK", "played": "false"})
            w.writerow({"week": 5, "team": "PHI", "opp": "JAX", "home": "false", "imp_own": 18, "imp_opp": 24.5,
                        "spread": 6.5, "total": 42.5, "dome": "false", "kickoff": "k", "provider": "DK", "played": "false"})
        sched = pl.DataFrame([{"game_type": "REG", "week": 5, "away_team": "PHI", "home_team": "JAX"}])
        p = patch.object(nfl_data, "schedules", lambda *a, **k: sched)
        p.start()
        self.addCleanup(p.stop)

    def run_live(self, key, espn, oapi):
        with patch("common.load_env", return_value={"ODDS_API_KEY": key} if key else {}), \
             patch.object(nfl_data, "espn_scoreboard_odds", espn), \
             patch.object(nfl_data, "odds_api_lines", oapi):
            return lines.live_week(2026, 5)

    def test_multi_book_line_preferred_and_every_source_kept(self):
        game = {"away": "PHI", "home": "JAX", "kickoff": "2026-10-11T13:30Z"}
        live = self.run_live("k", lambda s, w: [{**game, "spread_home": 7.5, "total": 41.5, "provider": "DraftKings"}],
                             lambda key: ([{**game, "spread_home": 7.5, "total": 42.0, "provider": "Odds API median"},
                                           {"away": "BUF", "home": "LA", "kickoff": "x", "spread_home": 1, "total": 50}],
                                          {"requests_remaining": "490"}))
        phi = live["teams"]["PHI"]
        self.assertEqual((phi["source"], phi["total"], phi["spread"], phi["imp_own"], phi["stale"]),
                         ("oddsapi", 42.0, 7.5, 17.2, False))
        self.assertEqual(set(phi["by_source"]), {"oddsapi", "espn", "saved"})
        self.assertNotIn("BUF", live["teams"])          # other weeks' games are filtered out
        self.assertEqual(live["sources"][0]["quota_remaining"], "490")

    def test_failures_fall_back_to_saved_file_labelled_stale(self):
        def boom(*a, **k):
            raise RuntimeError("down")
        live = self.run_live(None, boom, boom)
        phi = live["teams"]["PHI"]
        self.assertEqual((phi["source"], phi["total"], phi["stale"]), ("saved", 42.5, True))
        self.assertEqual([s["status"] for s in live["sources"]], ["no key", "unavailable", "file"])

    def test_cache_is_reused_within_ttl(self):
        calls = []

        def espn(s, w):
            calls.append(1)
            return [{"away": "PHI", "home": "JAX", "kickoff": "k", "spread_home": 7.5, "total": 41.5}]
        self.run_live(None, espn, None)
        again = self.run_live(None, espn, None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(again["sources"][1]["status"], "cached")


class OddsApiParse(unittest.TestCase):
    def test_median_home_margin_and_team_names(self):
        events = [{"home_team": "Jacksonville Jaguars", "away_team": "Philadelphia Eagles",
                   "commence_time": "t", "bookmakers": [
                       {"markets": [{"key": "spreads", "outcomes": [{"name": "Jacksonville Jaguars", "point": -7.5},
                                                                     {"name": "Philadelphia Eagles", "point": 7.5}]},
                                    {"key": "totals", "outcomes": [{"name": "Over", "point": 42.0}]}]},
                       {"markets": [{"key": "spreads", "outcomes": [{"name": "Jacksonville Jaguars", "point": -6.5}]},
                                    {"key": "totals", "outcomes": [{"name": "Over", "point": 41.5}]}]},
                       {"markets": [{"key": "spreads", "outcomes": [{"name": "Jacksonville Jaguars", "point": -7.5}]}]}]}]

        class Resp:
            headers = {"x-requests-remaining": "9", "x-requests-used": "1"}

            def read(self):
                return json.dumps(events).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        with patch("urllib.request.urlopen", return_value=Resp()):
            rows, quota = nfl_data.odds_api_lines("secret")
        self.assertEqual(rows[0]["home"], "JAX")
        self.assertEqual(rows[0]["away"], "PHI")
        self.assertEqual(rows[0]["spread_home"], 7.5)
        self.assertEqual(rows[0]["total"], 41.75)
        self.assertEqual(quota["requests_remaining"], "9")

    def test_errors_never_carry_the_key(self):
        with patch("urllib.request.urlopen", side_effect=OSError("https://x?apiKey=secret")):
            with self.assertRaises(RuntimeError) as cm:
                nfl_data.odds_api_lines("secret")
        self.assertNotIn("secret", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
