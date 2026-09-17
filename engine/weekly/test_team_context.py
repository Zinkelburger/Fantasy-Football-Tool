"""Metric definitions, percentiles and week pooling; no network."""
import unittest

import polars as pl

import team_context as tc


def play(*flags, **kw):
    """One play. `flags` are 0/1 columns to set — "pass" is a keyword, so
    they are positional strings rather than kwargs."""
    base = {"season": 2026, "week": 1, "game_id": "g", "season_type": "REG",
            "posteam": "DET", "qb_kneel": 0, "qb_spike": 0, "two_point_attempt": 0,
            "pass": 0, "rush": 0, "qb_dropback": 0, "pass_attempt": 0,
            "down": 1, "epa": 0.0, "success": 0, "pass_oe": 0.0, "cpoe": None,
            "yards_gained": 0, "sack": 0, "air_yards": None}
    unknown = [f for f in flags if f not in base]
    assert not unknown, f"no such play column: {unknown}"
    return {**base, **{f: 1 for f in flags}, **kw}


def frame(plays):
    return pl.DataFrame(plays, schema_overrides={"epa": pl.Float64, "cpoe": pl.Float64,
                                                 "air_yards": pl.Float64,
                                                 "pass_oe": pl.Float64})


class Metrics(unittest.TestCase):
    def test_scramble_counts_as_a_dropback_not_a_designed_rush(self):
        rows = frame([
            play("rush", "qb_dropback", epa=3.0, yards_gained=25),   # scramble
            play("rush", epa=-1.0, yards_gained=1),                  # designed run
        ])
        r = tc.team_game(rows).to_dicts()[0]
        self.assertEqual((r["dropbacks"], r["rushes"]), (1, 1))
        self.assertAlmostEqual(r["epa_pass"], 3.0)
        self.assertAlmostEqual(r["epa_rush"], -1.0)
        # 25 yards on the scramble is an explosive dropback, not a rush
        self.assertAlmostEqual(r["expl_pass"], 1.0)
        self.assertAlmostEqual(r["expl_rush"], 0.0)

    def test_kneels_spikes_and_two_point_tries_are_excluded(self):
        rows = frame([
            play("pass", "qb_dropback", "pass_attempt", epa=1.0),
            play("rush", "qb_kneel", epa=-2.0),
            play("pass", "qb_spike", epa=-2.0),
            play("pass", "two_point_attempt", epa=-2.0),
        ])
        r = tc.team_game(rows).to_dicts()[0]
        self.assertEqual(r["plays"], 1)
        self.assertAlmostEqual(r["epa_pass"], 1.0)

    def test_a_metrics_count_is_its_own_non_null_total(self):
        # nflfastR leaves cpoe and air_yards null on some attempts, so the
        # attempt count is the wrong denominator for them.
        rows = frame([
            play("pass", "qb_dropback", "pass_attempt", cpoe=10.0, air_yards=12.0),
            play("pass", "qb_dropback", "pass_attempt"),   # throwaway: both null
        ])
        r = tc.team_game(rows).to_dicts()[0]
        self.assertEqual(r["attempts"], 2)
        self.assertEqual((r["cpoe_n"], r["aypa_n"]), (1, 1))
        self.assertAlmostEqual(r["cpoe"], 10.0)     # not 5.0
        self.assertAlmostEqual(r["aypa"], 12.0)

    def test_sack_is_a_dropback_and_no_attempt(self):
        rows = frame([play("pass", "qb_dropback", "pass_attempt", "sack", epa=-2.0, yards_gained=-7)])
        r = tc.team_game(rows).to_dicts()[0]
        self.assertEqual((r["dropbacks"], r["attempts"]), (1, 0))
        self.assertAlmostEqual(r["sack_rate"], 1.0)
        self.assertIsNone(r["cpoe"])


class Percentiles(unittest.TestCase):
    def test_percentile_walks_the_breakpoints_and_clamps(self):
        bp = [float(i) for i in range(101)]      # p0=0 ... p100=100
        self.assertEqual(tc.percentile(bp, 0.0), 0)
        self.assertEqual(tc.percentile(bp, 50.0), 50)
        self.assertEqual(tc.percentile(bp, 1000.0), 100)
        self.assertIsNone(tc.percentile(bp, None))

    def test_baseline_is_committed_and_covers_every_metric(self):
        b = tc.load_baseline()
        for m in tc.METRICS:
            self.assertEqual(len(b["breakpoints"][m]), 101, m)
            self.assertEqual(b["breakpoints"][m], sorted(b["breakpoints"][m]), m)
        self.assertGreater(b["team_games"], 2000)


class Pooling(unittest.TestCase):
    """The weighted mean the MCP server uses to pool several weeks."""

    def pooled(self, rows, metric):
        num = sum(r[metric] * r[f"{metric}_n"] for r in rows)
        den = sum(r[f"{metric}_n"] for r in rows)
        return num / den

    def test_weeks_pool_by_each_metrics_own_count(self):
        # A 10-dropback week and a 40-dropback week must not weigh the same.
        wk1 = frame([play("pass", "qb_dropback", "pass_attempt", week=1, epa=1.0)] * 10)
        wk2 = frame([play("pass", "qb_dropback", "pass_attempt",
                          week=2, game_id="h", epa=-1.0)] * 40)
        rows = tc.team_game(pl.concat([wk1, wk2])).to_dicts()
        self.assertEqual([r["epa_pass_n"] for r in rows], [10, 40])
        self.assertAlmostEqual(self.pooled(rows, "epa_pass"), (10 - 40) / 50)
        # the average of the two weekly averages would have been 0.0
        self.assertNotAlmostEqual(self.pooled(rows, "epa_pass"), 0.0)


if __name__ == "__main__":
    unittest.main()
