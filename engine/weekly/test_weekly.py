"""Unit tests for the deterministic parts of the weekly engine.

Runs on plain python3 (no polars/nflreadpy): advisor.py and common.py
are stdlib-only, and the latest.json check reads committed data.
"""
import json
import unittest
from pathlib import Path

import advisor
import fftiers
from common import ROOT

LATEST = ROOT / "data" / "weekly" / "latest.json"


def P(pid, name, pos, proj, slot=20, slots=None, **kw):
    elig = slots or {"QB": [0, 20], "RB": [2, 3, 20], "WR": [3, 4, 20],
                     "TE": [6, 20], "K": [17, 20], "DST": [16, 20]}[pos]
    return {"id": pid, "name": name, "pos": pos, "team": kw.get("team", "ATL"),
            "eligible_slots": elig, "slot": slot, "proj": proj,
            "value": kw.get("value", proj), "locked": kw.get("locked", False),
            "injury": kw.get("injury", "ACTIVE"), "pct_owned": kw.get("own", 50),
            "pct_change": kw.get("chg", 0), "sources": kw.get("sources", {}),
            "matchup": {"kickoff": kw["kickoff"]} if "kickoff" in kw else None}


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


# One position's file as the bucket serves it, including the quoting and
# the "vs." with a dot. No network in these tests.
FFTIERS_CSV = (
    '"Rank","Player.Name","Matchup","Best.Rank","Worst.Rank","Avg.Rank","Std.Dev","Tier"\n'
    '1,"Jahmyr Gibbs","at BUF",1,6,1.33,0.89,"1"\n'
    '2,"Bijan Robinson","vs. CAR",1,4,2.15,0.7,"1"\n'
    '3,"Derrick Henry","vs. NO",1,9,3.19,1.25,"2"\n')
FFTIERS_DST = (
    '"Rank","Player.Name","Matchup","Best.Rank","Worst.Rank","Avg.Rank","Std.Dev","Tier"\n'
    '1,"Philadelphia Eagles","at TEN",1,6,1.5,0.92,"1"\n'
    '2,"San Francisco 49ers","vs. MIA",1,9,3.15,1.37,"1"\n'
    '3,"Washington Commanders","vs. NYG",2,11,4.0,1.4,"2"\n')


class FFTiers(unittest.TestCase):
    def test_urls_split_by_format_only_where_the_bucket_does(self):
        self.assertEqual(fftiers.url("RB", "half"),
                         fftiers.BASE + "/weekly-RB-HALF.csv")
        self.assertEqual(fftiers.url("RB", "std"), fftiers.BASE + "/weekly-RB.csv")
        # QB/K/DST tiers do not move with receptions: one file each.
        for pos in ("QB", "K", "DST"):
            self.assertEqual(fftiers.url(pos, "ppr"),
                             fftiers.url(pos, "std"), pos)

    def test_parse_maps_onto_the_ecr_contract(self):
        rows = fftiers.parse(FFTIERS_CSV, "RB")
        self.assertEqual([r["name"] for r in rows],
                         ["Jahmyr Gibbs", "Bijan Robinson", "Derrick Henry"])
        self.assertEqual(set(rows[0]), set(fftiers.FIELDS))
        self.assertEqual(rows[0]["opp"], "BUF")
        self.assertEqual(rows[0]["tier"], "1")
        self.assertEqual(rows[2]["tier"], "2")
        # The bucket has no team and no grade for a skill player.
        self.assertEqual(rows[0]["team"], "")
        self.assertEqual(rows[0]["start_sit_grade"], "")

    def test_matchup_side_and_home(self):
        self.assertEqual(fftiers.parse_matchup("at BUF"), ("BUF", False))
        self.assertEqual(fftiers.parse_matchup("vs. CAR"), ("CAR", True))
        self.assertEqual(fftiers.parse_matchup("BYE"), (None, None))
        self.assertEqual(fftiers.parse_matchup(None), (None, None))
        # nflverse spells the Rams LA, not LAR.
        self.assertEqual(fftiers.parse_matchup("at LAR")[0], "LA")

    def test_dst_rows_get_espns_spelling_and_a_team(self):
        rows = fftiers.parse(FFTIERS_DST, "DST")
        self.assertEqual([(r["name"], r["team"]) for r in rows],
                         [("Eagles D/ST", "PHI"), ("49ers D/ST", "SF"),
                          ("Commanders D/ST", "WAS")])

    def test_wrong_week_is_caught_by_the_pairings(self):
        rows = fftiers.parse(FFTIERS_DST, "DST")
        right = {"PHI": "TEN", "SF": "MIA", "WAS": "NYG",
                 "TEN": "PHI", "MIA": "SF", "NYG": "WAS"}
        self.assertEqual(fftiers.off_week(rows, right), [])
        # Same teams, different week: every team still plays, so only the
        # pairing gives it away.
        wrong = dict(right, PHI="NYG", NYG="PHI", WAS="SF", SF="WAS")
        self.assertEqual(len(fftiers.off_week(rows, wrong)), 3)
        # An opponent on a bye that week.
        self.assertTrue(fftiers.off_week(rows, {"PHI": "TEN", "TEN": "PHI"}))
        # No schedule to check against: accept rather than block the build.
        self.assertEqual(fftiers.off_week(rows, None), [])


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



# Kickoff stamps as the two sources actually write them: nflverse is naive
# Eastern, the ESPN scoreboard overlay is UTC with a Z.
THU = "2026-09-10T20:15"          # Thursday night
SUN_EARLY = "2026-09-13T13:00"    # Sunday 1pm
SUN_LATE = "2026-09-13T16:25"     # Sunday afternoon
SNF = "2026-09-14T00:20Z"         # Sunday night, as ESPN writes it
MNF = "2026-09-15T00:15Z"         # Monday night, as ESPN writes it


class SlotTiming(unittest.TestCase):
    """Open slots hold the latest kickoff. See docs/LINEUP-SLOTTING.md."""

    def roster(self, **when):
        # Same lineup as Lineup.roster(); only the kickoffs are interesting.
        k = {"QB1": SUN_EARLY, "RB1": MNF, "RB2": THU, "RB3": SUN_EARLY,
             "WR1": SUN_EARLY, "WR2": SUN_EARLY, "WR3": SUN_LATE,
             "TE1": SUN_EARLY, "K": SUN_EARLY, "DST": SUN_EARLY}
        k.update(when)
        return [P(1, "QB1", "QB", 18, slot=0, kickoff=k["QB1"]), P(2, "QB2", "QB", 14, kickoff=k["QB1"]),
                P(3, "RB1", "RB", 15, slot=2, kickoff=k["RB1"]),
                P(4, "RB2", "RB", 9, slot=2, kickoff=k["RB2"]),
                P(5, "RB3", "RB", 12, kickoff=k["RB3"]),
                P(6, "WR1", "WR", 14, slot=4, kickoff=k["WR1"]),
                P(7, "WR2", "WR", 8, slot=4, kickoff=k["WR2"]),
                P(8, "WR3", "WR", 11, slot=3, kickoff=k["WR3"]),
                P(9, "TE1", "TE", 7, slot=6, kickoff=k["TE1"]),
                P(10, "K", "K", 8, slot=17, kickoff=k["K"]),
                P(11, "DST", "DST", 6, slot=16, kickoff=k["DST"])]

    def test_naive_eastern_and_utc_are_the_same_kickoff(self):
        # 13:00 ET and 17:00Z are one game; a raw string sort puts them
        # four hours apart in the wrong direction.
        self.assertEqual(advisor.kickoff_dt({"matchup": {"kickoff": "2026-09-13T13:00"}}),
                         advisor.kickoff_dt({"matchup": {"kickoff": "2026-09-13T17:00Z"}}))
        self.assertIsNone(advisor.kickoff_dt({"matchup": None}))
        self.assertIsNone(advisor.kickoff_dt({"matchup": {"kickoff": "not a date"}}))
        self.assertEqual(advisor.kickoff_label({"matchup": {"kickoff": MNF}}), "Mon 20:15 ET")

    def test_latest_kickoff_takes_the_open_slot(self):
        res = advisor.optimal_lineup(self.roster(), SLOTS)
        at = {p["name"]: slot for slot, p in res["starters"] if p}
        self.assertEqual(at["RB1"], 3)        # Monday night -> RB/WR flex
        self.assertEqual(at["RB2"], 2)        # Thursday -> dedicated RB
        self.assertEqual(at["RB3"], 2)

    def test_slotting_does_not_change_who_starts_or_the_total(self):
        blind = advisor.optimal_lineup([dict(p, matchup=None) for p in self.roster()], SLOTS)
        timed = advisor.optimal_lineup(self.roster(), SLOTS)
        self.assertAlmostEqual(blind["total"], timed["total"])
        self.assertEqual({p["id"] for _, p in blind["starters"] if p},
                         {p["id"] for _, p in timed["starters"] if p})

    def test_thursday_starter_never_sits_in_an_open_slot(self):
        # Three startable WRs for two WR slots and the flex, so the flex is
        # a WR contest. WR3 plays Thursday, WR1 plays Sunday night.
        r = self.roster(WR3=THU, WR1=SNF, WR2=SUN_EARLY,
                        RB1=SUN_EARLY, RB2=SUN_EARLY, RB3=SUN_EARLY)
        next(p for p in r if p["name"] == "WR2")["proj"] = 10.0   # beats RB2 for the flex
        res = advisor.optimal_lineup(r, SLOTS)
        at = {p["name"]: slot for slot, p in res["starters"] if p}
        self.assertEqual(at["WR1"], 3)       # Sunday night -> flex
        self.assertEqual(at["WR3"], 4)       # Thursday -> dedicated WR

    def test_timing_moves_are_labelled_as_such(self):
        res = advisor.optimal_lineup(self.roster(), SLOTS)
        by_name = {m["name"]: m for m in res["moves"]}
        self.assertTrue(by_name["RB1"]["timing"])      # RB -> RB/WR, same points
        self.assertFalse(by_name["RB3"]["timing"])     # RB3 starts on merit

    def test_no_kickoff_data_leaves_the_slotting_alone(self):
        before = advisor.optimal_lineup(Lineup().roster(), SLOTS)["starters"]
        self.assertEqual(advisor.reslot_by_kickoff(list(before)), before)

    def test_locked_starter_keeps_his_slot(self):
        r = self.roster()
        r[2]["locked"] = True                          # RB1, Monday night, locked
        res = advisor.optimal_lineup(r, SLOTS)
        at = {p["name"]: slot for slot, p in res["starters"] if p}
        self.assertEqual(at["RB1"], 2)
        self.assertFalse(any(m["name"] == "RB1" for m in res["moves"]))

    def test_timing_note_flags_a_forced_early_flex(self):
        # Every starter plays Thursday except the TE, who cannot fill RB/WR.
        r = self.roster(**{n: THU for n in ("QB1", "RB1", "RB2", "RB3", "WR1", "WR2", "WR3", "K", "DST")})
        res = advisor.optimal_lineup(r, SLOTS)
        note = "\n".join(advisor.timing_note(res["starters"]))
        self.assertIn("RB/WR", note)
        self.assertIn("forced", note)


if __name__ == "__main__":
    unittest.main()
