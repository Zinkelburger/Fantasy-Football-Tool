import unittest
import polars as pl
import player_plays


def play(**changes):
    row = dict(season_type='REG', week=1, game_id='2026_01_A_B', play_id=1,
               play_type='pass', posteam='A', passer_player_id='qb',
               receiver_player_id='wr', pass_attempt=1, sack=0,
               complete_pass=1, receiving_yards=30, passing_yards=30,
               yards_gained=45, desc='30-yard catch with a penalty.', penalty=1)
    return row | changes


class PlayerPlayTests(unittest.TestCase):
    def test_credited_yards_not_total_with_penalty(self):
        row = play()
        self.assertEqual(player_plays.summarize(row, ['target'])[0], '30-yard catch')
        self.assertEqual(player_plays.summarize(row, ['pass'])[0], '30-yard completed pass')

    def test_incomplete_does_not_invent_drop(self):
        row = play(complete_pass=0, incomplete_pass=1)
        self.assertEqual(player_plays.summarize(row, ['target'])[0], 'Incomplete target')
        row['interception'] = 1
        self.assertEqual(player_plays.summarize(row, ['target'])[0], 'Target intercepted')

    def test_context_plays_do_not_inflate_usage(self):
        for row, role in [(play(sack=1), 'pass'),
                          (play(play_type='no_play'), 'target'),
                          (play(play_type='qb_kneel', qb_kneel=1), 'run')]:
            self.assertEqual(player_plays.summarize(row, [role])[3], [])
        self.assertEqual(player_plays.summarize(play(), ['target'])[3], ['target'])

    def test_touchdown_belongs_to_participant(self):
        row = play(pass_touchdown=1, td_player_id='wr')
        self.assertIn('Touchdown', player_plays.summarize(row, ['target'])[2])
        self.assertIn('Touchdown', player_plays.summarize(row, ['pass'])[2])
        self.assertNotIn('Touchdown', player_plays.summarize(row | {'td_player_id': 'other'}, ['target'])[2])
        self.assertNotIn('Touchdown', player_plays.summarize(row | {'play_type': 'no_play'}, ['pass'])[2])

    def test_order_identity_deduplication_and_season_scope(self):
        rows = [play(play_id=2), play(play_id=1, fumbled_1_player_id='wr'),
                play(play_id=3, season_type='POST'), play(play_id=4, week=2)]
        weekly = pl.DataFrame({'player_id': ['wr'], 'week': [1]})
        data = player_plays.build(pl.DataFrame(rows), weekly, 2026)
        self.assertEqual(list(data['players']), ['wr'])
        plays = data['players']['wr']['weeks']['1']['plays']
        self.assertEqual([p['id'] for p in plays], [1, 2])
        self.assertEqual(plays[0]['countsAs'], ['target'])
        self.assertIn('Fumble', plays[0]['flags'])
        with self.assertRaisesRegex(ValueError, 'Duplicate source play'):
            player_plays.build(pl.DataFrame([play(), play()]), weekly, 2026)


if __name__ == '__main__':
    unittest.main()
