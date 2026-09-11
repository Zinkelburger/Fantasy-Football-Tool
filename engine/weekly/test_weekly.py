"""Unit tests for the deterministic parts of the weekly engine.

Runs on plain python3 (no polars/nflreadpy): advisor.py and common.py
are stdlib-only, and the latest.json check reads committed data.
"""
import json
import unittest
from pathlib import Path

import advisor
from common import ROOT

LATEST = ROOT / "data" / "weekly" / "latest.json"


def P(pid, name, pos, proj, slot=20, slots=None, **kw):
    elig = slots or {"QB": [0, 20], "RB": [2, 3, 20], "WR": [3, 4, 20],
                     "TE": [6, 20], "K": [17, 20], "DST": [16, 20]}[pos]
    return {"id": pid, "name": name, "pos": pos, "team": kw.get("team", "ATL"),
            "eligible_slots": elig, "slot": slot, "proj": proj,
            "value": kw.get("value", proj), "locked": kw.get("locked", False),
            "injury": kw.get("injury", "ACTIVE"), "pct_owned": kw.get("own", 50),
            "pct_change": kw.get("chg", 0), "sources": kw.get("sources", {})}


SLOTS = {0: 1, 2: 2, 3: 1, 4: 2, 6: 1, 16: 1, 17: 1, 20: 7}


class Projection(unittest.TestCase):
    def test_matchup_factor_is_mild_and_clipped(self):
        self.assertEqual(advisor.matchup_factor(None), 1.0)
        self.assertAlmostEqual(advisor.matchup_factor(22.5), 1.0)
        self.assertEqual(advisor.matchup_factor(60), 1.2)
        self.assertEqual(advisor.matchup_factor(5), 0.8)

    def test_project_blends_sources_and_applies_injury(self):
        p = {"id": 1, "name": "A", "pos": "RB", "team": "ATL", "espn_proj": 12.0,
             "injury": "QUESTIONABLE", "injury_mult": 0.8, "eligible_slots": [2, 20]}
        r = advisor.project(p, {"ewma_ep_std": 10.0}, {"imp_own": 22.5, "opp": "PIT", "home": True}, "std")
        self.assertAlmostEqual(r["sources"]["ep_adj"], 10.0)
        self.assertAlmostEqual(r["proj"], 11.0 * 0.8, places=2)
        self.assertEqual(r["value"], 11.0)
        self.assertIn("QUESTIONABLE", r["flags"])

    def test_bye_zeroes_projection_but_not_value(self):
        p = {"id": 1, "name": "A", "pos": "WR", "team": "ATL", "espn_proj": 15.0, "eligible_slots": [4, 20]}
        r = advisor.project(p, {"ewma_ep_std": 13.0}, None, "std", on_bye=True)
        self.assertEqual(r["proj"], 0.0)
        self.assertEqual(r["value"], 14.0)
        self.assertIn("BYE", r["flags"])

    def test_kicker_uses_espn_only(self):
        p = {"id": 1, "name": "K", "pos": "K", "team": "ATL", "espn_proj": 8.0, "eligible_slots": [17, 20]}
        r = advisor.project(p, None, {"imp_own": 30}, "std")
        self.assertEqual(r["proj"], 8.0)


class Lineup(unittest.TestCase):
    def roster(self):
        return [P(1, "QB1", "QB", 18, slot=0), P(2, "QB2", "QB", 14),
                P(3, "RB1", "RB", 15, slot=2), P(4, "RB2", "RB", 9, slot=2), P(5, "RB3", "RB", 12),
                P(6, "WR1", "WR", 14, slot=4), P(7, "WR2", "WR", 8, slot=4), P(8, "WR3", "WR", 11, slot=3),
                P(9, "TE1", "TE", 7, slot=6), P(10, "K", "K", 8, slot=17), P(11, "DST", "DST", 6, slot=16)]

    def test_flex_goes_to_best_leftover(self):
        res = advisor.optimal_lineup(self.roster(), SLOTS)
        starters = {p["name"]: slot for slot, p in res["starters"] if p}
        self.assertEqual(starters["RB1"], 2)
        self.assertEqual(starters["RB3"], 2)          # 12 beats RB2's 9
        self.assertEqual(starters["WR3"], 4)          # 11 beats WR2's 8
        self.assertEqual(starters["RB2"], 3)          # flex: RB2 9 > WR2 8
        self.assertAlmostEqual(res["total"], 18 + 15 + 12 + 14 + 11 + 9 + 7 + 8 + 6)
        moves = {(m["name"], m["to"]) for m in res["moves"]}
        self.assertIn(("RB3", "RB"), moves)
        self.assertIn(("WR2", "BE"), moves)
        # bench-outs are listed before bench-ins
        self.assertEqual(res["moves"][0]["to_slot"], 20)

    def test_locked_players_stay_put(self):
        r = self.roster()
        r[3]["locked"] = True          # RB2 in slot 2, game underway
        res = advisor.optimal_lineup(r, SLOTS)
        starters = {p["name"]: slot for slot, p in res["starters"] if p}
        self.assertEqual(starters["RB2"], 2)
        self.assertEqual(starters["RB3"], 3)          # RB3 takes flex instead
        self.assertFalse(any(m["name"] == "RB2" for m in res["moves"]))

    def test_locked_bench_player_cannot_start(self):
        r = self.roster()
        r[4]["locked"] = True          # RB3 on bench, locked
        res = advisor.optimal_lineup(r, SLOTS)
        self.assertNotIn(5, {p["id"] for _, p in res["starters"] if p})

    def test_deterministic(self):
        a = advisor.optimal_lineup(self.roster(), SLOTS)
        b = advisor.optimal_lineup(list(reversed(self.roster())), SLOTS)
        self.assertEqual(a["total"], b["total"])
        self.assertEqual({p["id"] for _, p in a["starters"] if p}, {p["id"] for _, p in b["starters"] if p})


class Waivers(unittest.TestCase):
    def test_needs_and_proposals(self):
        roster = [P(1, "QB1", "QB", 18, slot=0), P(3, "RB1", "RB", 15, slot=2),
                  P(4, "RB2", "RB", 9, slot=2, injury="OUT"), P(5, "RB3", "RB", 3),
                  P(6, "WR1", "WR", 14, slot=4), P(7, "WR2", "WR", 8, slot=4), P(8, "WR3", "WR", 5, slot=3),
                  P(9, "TE1", "TE", 7, slot=6), P(10, "K", "K", 8, slot=17), P(11, "DST", "DST", 6, slot=16)]
        fas = [P(100, "FA RB", "RB", 10, own=30, chg=12, sources={"last_ep": 12, "last_pts": 6}),
               P(101, "FA WR", "WR", 6), P(102, "FA K", "K", 7), P(103, "FA TE", "TE", 2)]
        lineup = advisor.optimal_lineup(roster, SLOTS)
        needs = advisor.positional_needs(roster, fas, SLOTS, byes_next={"ATL": 5})
        kinds = {(n["pos"], n["kind"]) for n in needs}
        self.assertIn(("RB", "injured"), kinds)
        self.assertIn(("RB", "thin"), kinds)
        drops = advisor.drop_candidates(roster, lineup, fas)
        self.assertEqual(drops[0]["name"], "RB3")
        self.assertFalse(any(d["pos"] in ("K", "DST") for d in drops))
        props = advisor.proposals(roster, lineup, fas, SLOTS)
        self.assertEqual(props[0]["add"], "FA RB")
        self.assertEqual(props[0]["drop"], "RB3")
        self.assertIn("+12% owned this week", props[0]["notes"])
        self.assertTrue(any("usage ahead" in n for n in props[0]["notes"]))
        self.assertFalse(any(p["add"] == "FA TE" for p in props))   # worse than TE1
        self.assertFalse(any(p["add_pos"] == "QB" for p in props))   # no need behind a healthy QB1

    def test_kicker_and_dst_are_never_thin(self):
        roster = [P(10, "K", "K", 8.2, slot=17), P(11, "DST", "DST", 6.0, slot=16)]
        fas = [P(102, "FA K1", "K", 9.0), P(103, "FA K2", "K", 8.6), P(104, "FA D1", "DST", 6.5), P(105, "FA D2", "DST", 6.4)]
        needs = advisor.positional_needs(roster, fas, SLOTS)
        self.assertFalse(any(n["pos"] in ("K", "DST") for n in needs))

    def test_locked_players_are_not_drop_candidates(self):
        roster = [P(1, "QB1", "QB", 18, slot=0), P(3, "RB1", "RB", 15, slot=2), P(4, "RB2", "RB", 12, slot=2),
                  P(6, "WR1", "WR", 10, slot=4), P(8, "WR2", "WR", 9, slot=4), P(9, "WR3", "WR", 8, slot=3),
                  P(5, "RB3", "RB", 1, locked=True), P(7, "RB4", "RB", 2)]
        lineup = advisor.optimal_lineup(roster, SLOTS)
        drops = advisor.drop_candidates(roster, lineup, [])
        self.assertEqual([d["name"] for d in drops], ["RB4"])

    def test_backup_qb_is_not_proposed(self):
        roster = [P(1, "QB1", "QB", 18, slot=0), P(3, "RB1", "RB", 15, slot=2), P(4, "RB2", "RB", 12, slot=2),
                  P(6, "WR1", "WR", 10, slot=4), P(8, "WR2", "WR", 9, slot=4), P(9, "WR3", "WR", 8, slot=3),
                  P(5, "RB3", "RB", 3)]
        fas = [P(200, "FA QB", "QB", 17), P(201, "FA RB", "RB", 8)]
        lineup = advisor.optimal_lineup(roster, SLOTS)
        props = advisor.proposals(roster, lineup, fas, SLOTS)
        self.assertEqual([p["add"] for p in props], ["FA RB"])


class Bundle(unittest.TestCase):
    @unittest.skipUnless(LATEST.exists(), "data/weekly/latest.json not built")
    def test_latest_json_shape(self):
        d = json.loads(LATEST.read_text())
        for k in ("season", "week", "label", "lines", "dst", "k", "skill", "injuries", "model"):
            self.assertIn(k, d)
        self.assertEqual(len(d["dst"]), len(d["k"]))
        self.assertTrue(all(r["ewma"]["half"] >= 0 for r in d["skill"]))
        positions = {r["pos"] for r in d["skill"]}
        self.assertEqual(positions, {"QB", "RB", "WR", "TE"})
        imps = [r["imp"] for r in d["dst"]]
        self.assertEqual(imps, sorted(imps))


if __name__ == "__main__":
    unittest.main()
