"""Target share by week, absence flags and vacated share; no network."""
import unittest

import target_share as ts


def use(week, pid, name, tgt, team_targets, team="LA", pos="WR", snaps=""):
    return {"week": week, "team": team, "player_id": pid, "name": name, "position": pos,
            "tgt": tgt, "team_targets": team_targets, "snap_share": snaps}


def report(week, pid, status, injury="Hip"):
    return {"week": week, "team": "LA", "gsis_id": pid, "full_name": pid, "position": "WR",
            "report_status": status, "report_primary_injury": injury,
            "practice_status": "Did Not Participate In Practice"}


USAGE = [
    use(1, "star", "Star WR", 10, 30, snaps=.9), use(1, "te", "Tight End", 3, 30, pos="TE"),
    use(1, "fringe", "Fringe WR", 1, 30),
    use(2, "te", "Tight End", 9, 30, pos="TE"),
    use(2, "other", "Other Team", 5, 25, team="SEA"),
]


class TargetShare(unittest.TestCase):
    def test_shares_use_that_weeks_team_targets(self):
        la = ts.build(USAGE, [])["teams"]["LA"]
        te = next(p for p in la["players"] if p["name"] == "Tight End")
        self.assertEqual(te["share"], {"1": 0.1, "2": 0.3})
        self.assertEqual(te["share_all_weeks"], 0.2)
        star = next(p for p in la["players"] if p["name"] == "Star WR")
        # share when active divides by week 1 only, when he had usage
        self.assertAlmostEqual(star["share_when_active"], 0.333)
        self.assertEqual(star["no_usage_weeks"], [2])
        self.assertEqual(star["snap_pct"], {"1": 0.9, "2": None})

    def test_missing_latest_week_flags_only_real_roles(self):
        la = ts.build(USAGE, [])["teams"]["LA"]
        self.assertEqual([f["name"] for f in la["flagged"]], ["Star WR"])
        self.assertEqual(la["flagged"][0]["reasons"], ["no usage in week 2"])
        self.assertAlmostEqual(la["vacated_share"], 0.333)

    def test_injury_report_flags_and_labels_its_week(self):
        injuries = [report(2, "star", "Out"), report(2, "te", "Doubtful", "Knee")]
        la = ts.build(USAGE, injuries)["teams"]["LA"]
        flags = {f["name"]: f["reasons"] for f in la["flagged"]}
        self.assertEqual(flags["Star WR"], ["no usage in week 2 (reported Out)",
                                            "Out on week 2 report"])
        self.assertEqual(flags["Tight End"], ["Doubtful on week 2 report"])
        star = next(p for p in la["players"] if p["name"] == "Star WR")
        self.assertEqual(star["reported_out_weeks"], [2])
        self.assertEqual(star["latest_report"]["week"], 2)

    def test_team_filter_last_weeks_and_min_share(self):
        result = ts.build(USAGE, [], team="LA", last=1)
        self.assertEqual(result["weeks_requested"], [2])
        self.assertEqual(list(result["teams"]), ["LA"])
        self.assertEqual([p["name"] for p in result["teams"]["LA"]["players"]], ["Tight End"])
        hidden = ts.build(USAGE, [], team="LA", min_share=0.05)["teams"]["LA"]
        self.assertNotIn("Fringe WR", [p["name"] for p in hidden["players"]])
        self.assertEqual(hidden["team_targets"], {"1": 30.0, "2": 30.0})


if __name__ == "__main__":
    unittest.main()
