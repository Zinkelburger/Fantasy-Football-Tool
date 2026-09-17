"""Source coverage, join safety and definition tests; no network."""
import unittest
import polars as pl
import advanced_usage as au


class AdvancedUsageTests(unittest.TestCase):
    def setUp(self):
        self.pbp = pl.DataFrame({
            "season": [2026]*4, "week": [1]*4, "game_id": ["g"]*4,
            "play_id": [1., 2., 3., 4.], "season_type": ["REG"]*4,
            "play_type": ["pass", "pass", "pass", "run"], "posteam": ["DET"]*4,
            "receiver_player_id": ["wr", "wr", "other", None],
            "rusher_player_id": [None, None, None, "rb"],
            "passer_player_id": ["qb", "qb", "qb", None],
            "pass_attempt": [1, 1, 1, 0], "sack": [0]*4,
            "yardline_100": [20., 19., 50., 30.], "air_yards": [5., -2., 10., None]})
        self.stats = pl.DataFrame({"season": [2026]*2, "week": [1]*2,
            "season_type": ["REG"]*2, "player_id": ["wr", "rb"],
            "player_display_name": ["Receiver", "Runner"], "position": ["WR", "RB"],
            "receptions": [1, 0], "rushing_yards": [0, 5], "receiving_yards": [5, 0]})
        self.ftn = pl.DataFrame({"nflverse_game_id": ["g"]*2,
            "nflverse_play_id": [1, 2], "is_catchable_ball": [True, False], "is_drop": [False, False]})

    def row(self, result, pid="wr"):
        return result.filter(pl.col("player_id") == pid).to_dicts()[0]

    def test_all_team_targets_negative_air_and_red_zone_boundary(self):
        r = self.row(au.build(self.pbp, self.stats, self.ftn))
        self.assertAlmostEqual(r["target_share"], 2/3)
        self.assertEqual((r["tgt_rz"], r["tgt_rz_lt20"], r["air_yds"]), (2, 1, 3))
        self.assertEqual((r["ftn_catchable_targets"], r["ftn_drops"]), (1, 0))

    def test_partial_missing_and_no_target_are_not_zero(self):
        for ftn in [None, self.ftn.head(1)]:
            r = self.row(au.build(self.pbp, self.stats, ftn))
            self.assertIsNone(r["ftn_catchable_targets"])
            self.assertIsNone(r["ftn_drops"])
        r = self.row(au.build(self.pbp, self.stats, self.ftn.head(1)))
        self.assertEqual(r["ftn_target_coverage"], .5)
        r = self.row(au.build(self.pbp, self.stats, self.ftn), "rb")
        self.assertIsNone(r["ftn_target_coverage"])
        self.assertIsNone(r["pfr_yards_before_contact"])

    def test_duplicate_chart_play_rejected(self):
        with self.assertRaises(pl.exceptions.ComputeError):
            au.build(self.pbp, self.stats, pl.concat([self.ftn, self.ftn.head(1)]))

    def test_pfr_identity_and_carry_mismatch(self):
        ids = pl.DataFrame({"gsis_id": ["rb"], "pfr_id": ["Runner01"]})
        pfr = pl.DataFrame({"season": [2026], "week": [1], "game_id": ["g"],
            "game_type": ["REG"], "team": ["DET"], "pfr_player_id": ["Runner01"],
            "carries": [1.], "rushing_yards_before_contact": [0.]})
        r = self.row(au.build(self.pbp, self.stats, pfr=pfr, ids=ids), "rb")
        self.assertEqual(r["pfr_yards_before_contact"], 0.)
        pfr = pfr.with_columns(pl.lit(2.).alias("carries"))
        r = self.row(au.build(self.pbp, self.stats, pfr=pfr, ids=ids), "rb")
        self.assertEqual(r["pfr_status"], "carry_mismatch")
        self.assertIsNone(r["pfr_yards_before_contact"])

    def test_snaps_join_on_the_pfr_crosswalk_and_stay_null_when_absent(self):
        ids = pl.DataFrame({"gsis_id": ["wr", "rb"], "pfr_id": ["Recv01", "Runner01"]})
        snaps = pl.DataFrame({"season": [2026], "week": [1], "game_id": ["g"],
            "game_type": ["REG"], "team": ["DET"], "pfr_player_id": ["Recv01"],
            "offense_snaps": [42.], "offense_pct": [.72]})
        out = au.build(self.pbp, self.stats, ids=ids, snaps=snaps)
        r = self.row(out)
        self.assertEqual((r["snaps_off"], r["snap_share"]), (42., .72))
        self.assertEqual(r["snap_status"], "available")
        # A player PFR has no snap row for is unavailable, not zero snaps.
        rb = self.row(out, "rb")
        self.assertIsNone(rb["snaps_off"])
        self.assertEqual(rb["snap_status"], "unavailable")

    def test_snaps_absent_entirely_is_not_a_failure(self):
        r = self.row(au.build(self.pbp, self.stats))
        self.assertIsNone(r["snaps_off"])
        self.assertEqual(r["snap_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
