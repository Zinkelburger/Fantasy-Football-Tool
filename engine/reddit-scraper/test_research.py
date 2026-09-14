"""Offline regressions; the fake provider fails on hidden comment reads."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import research as N

NOW = 1_800_000_000


class Post:
    def __init__(self, sid='abc', title='Breece Hall limited at practice', age=60,
                 url='https://example.com/report', body='', **extra):
        self.__dict__.update(id=sid, title=title, created_utc=NOW-age, url=url,
                             selftext=body, subreddit='fantasyfootball', score=0,
                             num_comments=0, permalink=f'/comments/{sid}/', **extra)

    @property
    def comments(self):
        raise AssertionError('Discovery must not hydrate comments')


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = NOW
        self.cache = N.ResearchCache(Path(self.temp.name) / 'cache.sqlite3', lambda: self.now)
        self.sub = SimpleNamespace(search=Mock(return_value=[Post()]), new=Mock(return_value=[Post()]))
        self.client = SimpleNamespace(subreddit=Mock(return_value=self.sub))
        self.factory = Mock(return_value=self.client)

    def discover(self, **kwargs):
        return N.discover(self.cache, self.factory, ['nfl', 'fantasyfootball'], 'Breece Hall', **kwargs)

    def test_discovery_metadata_only_and_cache_across_instances(self):
        first = self.discover()
        self.cache = N.ResearchCache(self.cache.path, lambda: self.now)
        second = self.discover()
        self.assertEqual(first['retrieval']['retrieval_operations'], 1)
        self.assertEqual(second['retrieval']['retrieval_operations'], 0)
        self.assertTrue(second['retrieval']['cache_hit'])
        self.factory.assert_called_once()
        self.assertEqual(self.sub.search.call_args.kwargs['limit'], 100)
        self.assertEqual(first['posts'][0]['score'], 0)

    def test_empty_results_cached(self):
        self.sub.search.return_value = []
        self.assertEqual(self.discover()['posts'], [])
        self.assertTrue(self.discover()['retrieval']['cache_hit'])
        self.factory.assert_called_once()

    def test_expiration_and_filter_at_read_time(self):
        self.sub.search.return_value = [Post(age=3 * 86400 - 10)]
        self.assertEqual(len(self.discover()['posts']), 1)
        self.now += 20
        self.assertEqual(self.discover()['posts'], [])
        self.factory.assert_called_once()
        self.now += N.DISCOVERY_TTL
        self.discover()
        self.assertEqual(self.factory.call_count, 2)

    def test_invalid_arguments_never_fetch(self):
        for kwargs in ({'days': 0}, {'days': 32}, {'sort': 'bad'}, {'query': ''}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                N.discover(self.cache, self.factory, ['nfl'], **kwargs)
        with self.assertRaises(ValueError):
            N.discover(self.cache, self.factory, [f'room{i}' for i in range(9)], 'Hall')
        self.factory.assert_not_called()

    def test_failure_is_not_empty_news_or_retried(self):
        self.sub.search.side_effect = RuntimeError('private credential value')
        for _ in range(2):
            with self.assertRaises(N.RetrievalStopped) as cm:
                self.discover()
            self.assertNotIn('private credential', str(cm.exception))
            self.assertIn('incomplete', str(cm.exception))
        self.factory.assert_called_once()

    def test_concurrent_cache_miss_reserved(self):
        def fetch():
            other = N.ResearchCache(self.cache.path, lambda: self.now)
            with self.assertRaisesRegex(N.RetrievalStopped, 'already running'):
                other.get_or_fetch('same', 'discovery', 60, Mock(side_effect=AssertionError))
            return {'posts': []}
        self.cache.get_or_fetch('same', 'discovery', 60, fetch)
        self.assertTrue(self.cache.get_or_fetch('same', 'discovery', 60, Mock())[1]['cache_hit'])

    def test_rolling_budget_allows_cached_reads(self):
        for i in range(N.MAX_FETCHES_PER_HOUR):
            self.cache.get_or_fetch(i, 'discovery', 4000, lambda: {})
        with self.assertRaisesRegex(N.RetrievalStopped, 'budget'):
            self.cache.get_or_fetch('extra', 'discovery', 60, Mock(side_effect=AssertionError))
        self.assertTrue(self.cache.get_or_fetch(0, 'discovery', 4000, Mock())[1]['cache_hit'])
        self.now += 3601
        self.assertEqual(self.cache.get_or_fetch('extra', 'discovery', 60, lambda: {})[1]['retrieval_operations'], 1)

    def test_separate_detail_budget(self):
        for i in range(N.MAX_DETAILS_PER_HOUR):
            self.cache.get_or_fetch(i, 'detail', 60, lambda: {})
        with self.assertRaises(N.RetrievalStopped):
            self.cache.get_or_fetch('extra', 'detail', 60, Mock(side_effect=AssertionError))
        self.cache.get_or_fetch('discovery', 'discovery', 60, lambda: {})

    def test_new_listing_combined_bounded_sample(self):
        self.sub.new.return_value = [Post(sid=str(i)) for i in range(100)]
        result = self.discover(mode='new')
        self.sub.new.assert_called_once_with(limit=100)
        self.assertEqual(self.client.subreddit.call_args.args[0], 'fantasyfootball+nfl')
        self.assertTrue(result['scan_limit_reached'])

    def test_selected_detail_no_expansion_and_cached(self):
        class Forest(list):
            def replace_more(self, limit):
                if limit != 0:
                    raise AssertionError('Expensive comment expansion')
        post = SimpleNamespace(**vars(Post()))
        post.comments = Forest([SimpleNamespace(id='c1', parent_id='t3_abc', body='Observation',
                              score=2, created_utc=NOW, permalink='/comments/abc/c1/')])
        self.client.submission = Mock(return_value=post)
        a = N.read_thread(self.cache, self.factory, 'abc', 5)
        b = N.read_thread(self.cache, self.factory, 'abc', 10)
        self.assertEqual(post.comment_limit, 25)
        self.assertEqual(post.comment_sort, 'top')
        self.assertEqual(a['comments'][0]['parent_id'], 't3_abc')
        self.assertTrue(b['retrieval']['cache_hit'])
        self.client.submission.assert_called_once()

    def test_zero_comment_detail_and_invalid_id(self):
        self.client.submission = Mock(return_value=Post())
        self.assertEqual(N.read_thread(self.cache, self.factory, 'abc', 0)['comments'], [])
        with self.assertRaises(ValueError):
            N.read_thread(self.cache, self.factory, 'https://example.com', 5)

    def test_shortlist_relevance_duplicates_player_coverage(self):
        players = ['Breece Hall', "De'Von Achane"]
        posts = [Post('aaa'), Post('bbb', age=120, url='https://example.com/report?utm_source=reddit'),
                 Post('ccc', 'Breece Hall hype train'), Post('ddd', 'Josh Allen injury report'),
                 Post('eee', 'Breece Hall is my favorite player'),
                 Post('fff', 'Breece Hall game thread', body='injury'),
                 Post('ggg', "De'Von Achane gets 70 percent of snaps", url='https://example.com/snaps')]
        result = N.shortlist([N.post_record(p) for p in posts], players,
                             lambda text: {p for p in players if p in text}, limit=2)
        self.assertEqual({p['id'] for p in result['threads']}, {'aaa', 'ggg'})
        self.assertEqual(result['players_without_selected_evidence'], [])
        self.assertEqual(result['filtered']['duplicate_story'], 1)
        self.assertEqual(result['filtered']['generic_or_noise'], 2)
        self.assertEqual(result['filtered']['unrelated_player'], 1)
        self.assertTrue(all(p['evidence_status'] == 'unverified_report' for p in result['threads']))

    def test_focus_and_missing_coverage(self):
        result = N.shortlist([N.post_record(Post(title='Breece Hall gets all the snaps'))],
                             ['Breece Hall'], lambda _: {'Breece Hall'}, focus='injury')
        self.assertEqual(result['threads'], [])
        self.assertEqual(result['players_without_selected_evidence'], ['Breece Hall'])

    def test_story_urls_preserve_article_ids(self):
        self.assertNotEqual(N.story_key(N.post_record(Post(url='https://example.com/article?id=1'))),
                            N.story_key(N.post_record(Post(url='https://example.com/article?id=2'))))

    def test_roundup_does_not_assign_another_players_injury(self):
        post = N.post_record(Post(title='Weekly data roundup', body=(
            'Josh Allen left with a hamstring injury.\n\n' + 'Introduction. ' * 100 +
            '\n\nBreece Hall played 80 percent of snaps.')))
        match = lambda text: {'Breece Hall'} if 'Breece Hall' in text else set()
        injury = N.shortlist([post], ['Breece Hall'], match, focus='injury')
        self.assertEqual(injury['threads'], [])
        usage = N.shortlist([post], ['Breece Hall'], match, focus='usage')
        self.assertEqual(usage['threads'][0]['signals'], ['usage'])
        self.assertIn('Breece Hall played', usage['threads'][0]['excerpt'])
        self.assertNotIn('Josh Allen', usage['threads'][0]['excerpt'])

    def test_latest_update_beats_old_rumor_and_personal_advice(self):
        posts = [Post('old', 'Breece Hall injury could change his usage role after signing',
                      age=3600, url='https://example.com/rumor'),
                 Post('new', 'Breece Hall cleared', age=30),
                 Post('ask', 'Should I drop Breece Hall after his injury?', age=10)]
        result = N.shortlist([N.post_record(p) for p in posts], ['Breece Hall'],
                             lambda _: {'Breece Hall'}, limit=1)
        self.assertEqual(result['threads'][0]['id'], 'new')
        self.assertEqual(result['filtered']['generic_or_noise'], 1)


class ToolIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import mcp_server
        cls.server = mcp_server

    def test_tool_schema(self):
        tools = {t.name: t for t in asyncio.run(self.server.mcp.list_tools())}
        self.assertIn('research_brief', tools)
        self.assertIn('read_research_thread', tools)
        self.assertNotIn('_age_str', tools)
        for name in ['search_reddit', 'latest_threads']:
            self.assertEqual(tools[name].input_schema['properties']['comments_per_thread']['default'], 0)
        self.assertIn('injury', tools['research_brief'].input_schema['properties']['focus']['enum'])
        self.assertIsNotNone(tools['research_brief'].output_schema)

    def test_real_pool_names_and_safe_query(self):
        s = self.server
        data = {'posts': [N.post_record(Post(title="De'Von Achane limited in practice")),
                          N.post_record(Post('xyz', 'Braelon Allen limited in practice', url='https://example.com/2'))],
                'retrieval': {'cache_hit': False}, 'scanned': 2}
        with patch.object(s.NEWS, 'discover', return_value=data) as fetch:
            result = s.research_brief(["De'Von Achane", 'Josh Allen', 'Jordan Love'])
        self.assertEqual(len(result['threads']), 1)
        query = fetch.call_args.args[3]
        self.assertIn('"achane"', query)
        self.assertNotIn('"allen"', query)
        self.assertNotIn('"love"', query)

    def test_unknown_current_player(self):
        data = {'posts': [N.post_record(Post(title='Example Newcomer promoted to starter'))], 'retrieval': {}, 'scanned': 1}
        with patch.object(self.server.NEWS, 'discover', return_value=data):
            self.assertEqual(len(self.server.research_brief(['Example Newcomer'])['threads']), 1)

    def test_failure_returns_gap(self):
        with patch.object(self.server.NEWS, 'discover', side_effect=N.RetrievalStopped('budget')):
            result = self.server.research_brief(['Breece Hall'])
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['players_without_selected_evidence'], ['Breece Hall'])

    def test_name_validation_before_discovery(self):
        with patch.object(self.server.NEWS, 'discover') as fetch:
            for names in ([], ['Hall'], ['Breece Hall OR title:injury']):
                with self.assertRaises(ValueError):
                    self.server.research_brief(names)
            fetch.assert_not_called()

    def test_protocol_call_returns_structured_content(self):
        with patch.object(self.server.NEWS, 'discover', side_effect=N.RetrievalStopped('budget')):
            result = asyncio.run(self.server.mcp.call_tool('research_brief', {'players': ['Breece Hall']}))
        self.assertEqual(result.structured_content['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
