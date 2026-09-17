"""Parser tests for club_reports.py, offline: the fixture is the shape the
league CMS renders, including the two quirks of the opponent's table."""
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
