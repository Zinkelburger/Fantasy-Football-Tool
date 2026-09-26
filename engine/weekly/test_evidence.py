"""Offline regressions for evidence reuse, failure visibility and week isolation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

import evidence
import club_reports
import mcp_server as S
from evidence_cache import EvidenceCache
from espn_league import League, EspnError


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 100000
        self.path = Path(self.tmp.name) / 'evidence.sqlite3'
        self.cache = EvidenceCache(self.path, lambda: self.now)

    def test_persistence_expiry_and_week_isolation(self):
        fetch = Mock(return_value={'status': 'OUT'})
        first = self.cache.read(['practice', 2026, 2], fetch, 300)
        other = EvidenceCache(self.path, lambda: self.now)
        self.now += 20
        cached = other.read(['practice', 2026, 2], fetch, 300)
        self.assertEqual(cached['retrieval']['fetched_at'], first['retrieval']['fetched_at'])
        self.assertEqual(cached['retrieval']['age_seconds'], 20)
        fetch.assert_called_once()
        self.assertIsNone(other.read(['practice', 2026, 3], fetch, 300, cache_only=True)['data'])
        self.now += 301
        old = other.read(['practice', 2026, 2], fetch, 300, cache_only=True)
        self.assertEqual(old['retrieval']['status'], 'stale')
        fetch.assert_called_once()
        other.read(['practice', 2026, 2], fetch, 300)
        self.assertEqual(fetch.call_count, 2)

    def test_failed_refresh_does_not_relabel_old_success_or_leak_error(self):
        key = ['news', 2026, 3]
        self.cache.read(key, lambda: ['old'], 300)
        self.now += 301
        fail = Mock(side_effect=OSError('private credential'))
        result = self.cache.read(key, fail, 300, refresh=True)
        self.assertEqual(result['retrieval']['status'], 'unavailable')
        self.assertIsNone(result['data'])
        self.assertNotIn('private credential', json.dumps(result))
        self.cache.read(key, fail, 300, refresh=True)
        fail.assert_called_once()
        old = self.cache.read(key, fail, 300, cache_only=True)
        self.assertEqual(old['data'], ['old'])
        self.assertEqual(old['retrieval']['status'], 'stale')

    def test_force_refresh_and_invalid_modes(self):
        f = Mock(return_value=[])
        self.cache.read('a', f, 300)
        self.cache.read('a', f, 300, refresh=True)
        self.assertEqual(f.call_count, 2)
        with self.assertRaises(ValueError):
            self.cache.read('a', f, 300, refresh=True, cache_only=True)


class EvidenceTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = EvidenceCache(Path(self.tmp.name) / 'cache.sqlite3')
        p = patch.object(evidence, 'cache', return_value=self.store)
        p.start()
        self.addCleanup(p.stop)

    def test_practice_filters_opponent_rows_and_reuses_team_fetch(self):
        df = Mock()
        df.to_dicts.return_value = [
            {'team': 'BAL', 'player': 'Player One', 'wed': 'DNP', 'thu': '', 'game_status': ''},
            {'team': 'BAL', 'player': 'Player Two', 'wed': 'LP', 'thu': '', 'game_status': ''},
            {'team': 'DAL', 'player': 'Opponent', 'wed': 'DNP'},
        ]
        meta = {'coverage': {'BAL': {'status': 'available'}}, 'teams': {}, 'generated_at': 'dated'}
        with patch.object(club_reports, 'collect', return_value=(df, meta)) as get:
            one = evidence.practice('BAL', 2026, 3, 'Player One')
            two = evidence.practice('BAL', 2026, 3, 'Player Two')
            missing = evidence.practice('BAL', 2026, 2, cache_only=True)
        get.assert_called_once_with(2026, 3, ['BAL'])
        self.assertEqual(len(one['report']['rows']), 1)
        self.assertEqual(one['report']['rows'][0]['thu'], '')
        self.assertEqual(two['report']['rows'][0]['game_status'], '')
        self.assertTrue(two['retrieval']['cache_hit'])
        self.assertIsNone(missing['report'])

    def test_news_shared_between_names_and_coverage_failure_visible(self):
        now = datetime.now(timezone.utc)
        posts = [{'url': 'https://example.test/post', 'text': 'Player One and Player Two practice',
                  'created_at': now.isoformat()}]
        with patch.object(evidence.bluesky, 'ACCOUNTS', {'good': '', 'bad': ''}), \
                patch.object(evidence.bluesky, 'author_feed', side_effect=[posts, OSError('secret')]) as fetch:
            one = evidence.news('Player One', 2026, 3)
            two = evidence.news('Player Two', 2026, 3)
            old = evidence.news('Player One', 2026, 2, cache_only=True)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(one['posts']), 1)
        self.assertEqual(two['unavailable_accounts'], ['bad'])
        self.assertEqual(old['posts'], [])
        self.assertNotIn('secret', json.dumps(two))

    def test_cached_news_is_refiltered_for_requested_time_window(self):
        post = {'url': 'https://example.test/post', 'text': 'Player One out',
                'created_at': (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()}
        with patch.object(evidence.bluesky, 'ACCOUNTS', {'reporter': ''}), \
                patch.object(evidence.bluesky, 'author_feed', return_value=[post]) as fetch:
            self.assertEqual(len(evidence.news('Player One', 2026, 3, hours=48)['posts']), 1)
            self.assertEqual(evidence.news('Player One', 2026, 3, hours=24)['posts'], [])
        fetch.assert_called_once()

    def test_offline_news_revisits_the_original_snapshot_window(self):
        old = datetime.now(timezone.utc) - timedelta(days=10)
        post = {'url': 'https://example.test/old', 'text': 'Player One out',
                'created_at': old.isoformat()}
        historical = EvidenceCache(self.store.path, lambda: old.timestamp())
        historical.read(['wire-v1', 2026, 2, 'reporter'], lambda: [post], 600)
        with patch.object(evidence.bluesky, 'ACCOUNTS', {'reporter': ''}), \
                patch.object(evidence.bluesky, 'author_feed', side_effect=AssertionError('offline')):
            result = evidence.news('Player One', 2026, 2, cache_only=True)
        self.assertEqual(len(result['posts']), 1)
        self.assertEqual(result['window_reference'], "each saved feed's retrieval time")
        self.assertEqual(result['retrieval']['reporter']['status'], 'stale')
        self.assertEqual(result['posts'][0]['created_at'], old.isoformat())

    def test_wrong_week_practice_never_fetches_live(self):
        with patch.object(S, '_state', return_value=(2026, 3)), patch.object(evidence, 'practice') as get:
            for season, week in [(2026, 2), (2026, 4), (2025, 3)]:
                with self.assertRaises(ValueError):
                    S.practice_report('BAL', week=week, season=season)
            get.assert_not_called()
            S.practice_report('BAL', week=2, season=2026, cache_only=True)
            get.assert_called_once()

    def test_explicit_week_cache_only_needs_no_state_network(self):
        with patch.object(S, '_state', side_effect=AssertionError('offline')):
            result = S.practice_report('BAL', season=2025, week=2, cache_only=True)
            self.assertEqual(result['retrieval']['status'], 'missing')
            result = S.player_news('Player One', season=2025, week=2, cache_only=True)
            self.assertEqual(result['posts'], [])

    def test_team_roster_preserves_locks_without_creating_a_proposal(self):
        player = {'name': 'Player One', 'id': 1, 'pos': 'RB', 'team': 'BAL',
                  'slot': 2, 'proj': 10.0, 'locked': True, 'eligible_slots': [2, 3]}
        league = Mock()
        league.rosters.return_value = {5: [player]}
        settings = {'teams': [{'id': 5, 'name': 'Opponent'}], 'slots': {2: 1}, 'scoring_format': 'std'}
        with patch.object(S, '_state', return_value=(2026, 3)), \
                patch.object(S, 'projector', return_value=(league, settings, lambda p: p)), \
                patch.object(S, '_save_proposal') as save:
            report = S.team_roster(5, week=3)
        self.assertIn('Current starters: 10.0', report)
        self.assertIn('locks retained', report)
        self.assertTrue(player['locked'])
        save.assert_not_called()
        league.rosters.assert_called_once_with(3)


class WeekSelection(unittest.TestCase):
    def test_bundle_reads_exact_week_and_season(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(S, 'DATA', Path(tmp)), \
                patch.object(S, '_state', return_value=(2026, 3)):
            Path(tmp, 'latest.json').write_text(json.dumps({'season': 2026, 'week': 2}))
            for tool in [S.injury_report, S.dst_rankings, S.kicker_rankings]:
                with self.assertRaisesRegex(ValueError, 'No saved bundle'):
                    tool(week=3)
            Path(tmp, 'week_2026_wk03.json').write_text(json.dumps({
                'season': 2026, 'week': 3, 'label': '2026 Week 3', 'generated': 'Friday',
                'injuries': [], 'dst': [], 'k': []}))
            self.assertIn('Week 3', S.dst_rankings(week=3))
            self.assertIn('not clearance', S.injury_report(week=3))
            with self.assertRaises(ValueError):
                S.dst_rankings(week=3, season=2025)

    def test_future_matchup_uses_requested_period_not_current(self):
        league = object.__new__(League)
        league.settings = Mock(return_value={
            'my_team_id': 1, 'current_week': 2, 'matchup_period': 2,
            'matchup_periods': {'2': [2], '3': [3, 4]},
            'teams': [{'id': 1, 'name': 'Me'}, {'id': 2, 'name': 'Old'}, {'id': 3, 'name': 'Next'}]})
        league.get = Mock(return_value={'schedule': [
            {'matchupPeriodId': 2, 'home': {'teamId': 1}, 'away': {'teamId': 2}},
            {'matchupPeriodId': 3, 'home': {'teamId': 1}, 'away': {'teamId': 3}},
        ]})
        result = league.matchup(4)
        self.assertEqual(result['opponent'], 'Next')
        self.assertEqual(result['matchup_period'], 3)
        with self.assertRaises(EspnError):
            league.matchup(5)
        league.get.assert_called_once()

    def test_unknown_period_only_allows_verified_current_week(self):
        league = object.__new__(League)
        league.settings = Mock(return_value={
            'my_team_id': 1, 'current_week': 3, 'matchup_period': 2, 'teams': []})
        league.get = Mock(return_value={'schedule': []})
        self.assertIsNone(league.matchup(3))
        with self.assertRaises(EspnError):
            league.matchup(2)
        league.get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
