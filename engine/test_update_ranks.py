"""Regression coverage for stale main ranks, source gaps and bad feeds."""
import copy
from datetime import date
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import update_ranks as ranks


class RankRefreshTests(unittest.TestCase):
    def test_refresh_reorders_main_board_and_does_not_reuse_missing_values(self):
        previous = [
            dict(Rank='24', Player='Josh Jacobs', Team='GB', Bye='11', POS='RB', ESPN_Rank='68', Sleeper_Rank='22'),
            dict(Rank='55', Player='RJ Harvey', Team='DEN', Bye='10', POS='RB', ESPN_Rank='122', Sleeper_Rank='59'),
            dict(Rank='3', Player='Outside sample', Team='NYJ', Bye='13', POS='WR', ESPN_Rank='3', Sleeper_Rank='3'),
        ]
        fresh = [
            dict(name='A new player', position='WR', team='BUF', bye=7, adp=3.5),
            dict(name='Josh Jacobs', position='RB', team='GB', bye=11, adp=54.1),
            dict(name='Denver Defense', position='DEF', team='DEN', bye=10, adp=100),
            dict(name='RJ Harvey', position='RB', team='DEN', bye=10, adp=121.4),
        ]
        rows = ranks.build_board(previous, fresh, {'rj harvey': 123}, {}, 'adp_std')
        self.assertEqual([r['Player'] for r in rows], ['A new player', 'Josh Jacobs', 'RJ Harvey', 'Outside sample'])
        self.assertEqual([r['Rank'] for r in rows], ['1', '2', '4', ''])
        self.assertEqual(rows[1]['ADP'], '54.1')
        self.assertEqual(rows[2]['ESPN_Rank'], '123')
        self.assertEqual(rows[1]['ESPN_Rank'], '')
        self.assertEqual(rows[-1]['Sleeper_Rank'], '')
        self.assertEqual(previous[0]['Rank'], '24')

    def fixture(self):
        return {'status': 'Success', 'meta': {'type': 'Non-PPR', 'teams': 12,
                'start_date': '2026-08-29', 'end_date': '2026-09-05', 'total_drafts': 1606},
                'players': [dict(name=f'Player {i}', position='RB', adp=i + 1)
                            for i in range(110)]}

    def test_rejects_stale_wrong_format_partial_and_invalid_feeds(self):
        good = self.fixture()
        self.assertEqual(len(ranks.validate_ffc(good, 'standard', date(2026, 9, 6))), 110)
        mutations = [lambda d: d['meta'].update(end_date='2026-08-20'),
                     lambda d: d['meta'].update(type='PPR'),
                     lambda d: d['meta'].update(teams=10),
                     lambda d: d.update(players=d['players'][:5]),
                     lambda d: d['players'][0].update(adp=float('nan')),
                     lambda d: d['players'][1].update(name='Player 0')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                bad = copy.deepcopy(good)
                mutate(bad)
                with self.assertRaises(ValueError):
                    ranks.validate_ffc(bad, 'standard', date(2026, 9, 6))

    def test_failed_primary_fetch_never_writes_boards(self):
        with patch.object(ranks, 'fetch_ffc', side_effect=ValueError('partial feed')), \
             patch.object(ranks, 'update_csvs') as write:
            with self.assertRaises(ValueError):
                ranks.main()
            write.assert_not_called()

    def test_each_format_uses_its_own_feed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ranks, 'RANKS', Path(tmp)):
            for fname in ranks.FORMATS:
                (Path(tmp) / fname).write_text('Rank,Player,Team,Bye,POS,ESPN_Rank,Sleeper_Rank\n24,Josh Jacobs,GB,11,RB,68,22\n')
            feeds = {fmt: [dict(name='Josh Jacobs', position='RB', team='GB', bye=11, adp=adp)]
                     for fmt, adp in [('standard', 54.1), ('half-ppr', 75), ('ppr', 77)]}
            ranks.update_csvs({}, {}, feeds, {})
            import csv
            actual = [next(csv.DictReader((Path(tmp) / f).read_text().splitlines()))['ADP']
                      for f in ranks.FORMATS]
            self.assertEqual(actual, ['54.1', '75', '77'])


if __name__ == '__main__':
    unittest.main()
