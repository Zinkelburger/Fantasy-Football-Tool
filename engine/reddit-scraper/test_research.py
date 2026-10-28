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

    def test_retained_thread_reads_offline_without_becoming_current(self):
        key = ['detail-v1', 'abc', False]
        self.cache.get_or_fetch(key, 'detail', N.DETAIL_TTL,
                                lambda: {'thread': {'id': 'abc'}, 'comments': []})
        self.now += N.DETAIL_TTL + 1
        result = N.read_thread(self.cache, self.factory, 'abc', 0, cache_only=True)
        self.assertTrue(result['retrieval']['stale'])
        self.assertEqual(result['retrieval']['retrieval_operations'], 0)
        self.factory.assert_not_called()
        with self.assertRaises(N.RetrievalStopped):
            N.read_thread(self.cache, self.factory, 'missing', 0, cache_only=True)
        self.factory.assert_not_called()

    def test_refresh_obeys_budget_and_negative_cache(self):
        fetch = Mock(return_value={'thread': {'id': 'abc'}, 'comments': []})
        key = ['detail-v1', 'abc', False]
        self.cache.get_or_fetch(key, 'detail', 300, fetch)
        self.cache.get_or_fetch(key, 'detail', 300, fetch, refresh=True)
        self.assertEqual(fetch.call_count, 2)
        for i in range(N.MAX_DETAILS_PER_HOUR - 2):
            self.cache.get_or_fetch(i, 'detail', 300, lambda: {})
        with self.assertRaisesRegex(N.RetrievalStopped, 'budget'):
            self.cache.get_or_fetch(key, 'detail', 300, fetch, refresh=True)
        self.assertTrue(self.cache.get_or_fetch(key, 'detail', 300, fetch)[1]['cache_hit'])
        fail = Mock(side_effect=OSError('private credential'))
        for _ in range(2):
            with self.assertRaises(N.RetrievalStopped):
                self.cache.get_or_fetch('bad', 'discovery', 300, fail, refresh=True)
        fail.assert_called_once()

    def test_retention_limit_removes_old_snapshots(self):
        key = ['detail-v1', 'abc', False]
        self.cache.get_or_fetch(key, 'detail', 300, lambda: {})
        self.now += N.RETENTION + 1
        with self.assertRaises(N.RetrievalStopped):
            self.cache.get_or_fetch(key, 'detail', 300, Mock(), cache_only=True)

    def test_failed_refresh_retains_prior_snapshot_for_offline_review(self):
        key = ['detail-v1', 'abc', False]
        self.cache.get_or_fetch(key, 'detail', 300,
                                lambda: {'thread': {'id': 'abc'}, 'comments': []})
        self.now += 301
        with self.assertRaises(N.RetrievalStopped):
            self.cache.get_or_fetch(key, 'detail', 300, Mock(side_effect=OSError()), refresh=True)
        result = N.read_thread(self.cache, self.factory, 'abc', 0, cache_only=True)
        self.assertEqual(result['thread']['id'], 'abc')
        self.assertTrue(result['retrieval']['stale'])
        self.factory.assert_not_called()

    def test_local_thread_search_excludes_discovery_and_expired_retention(self):
        detail = {'thread': {'id': 'abc', 'title': 'Breece Hall update', 'posted_at': 'original'},
                  'comments': [{'body': 'Practice report'}]}
        self.cache.get_or_fetch(['detail-v1', 'abc', True], 'detail', 300, lambda: detail)
        self.cache.get_or_fetch(['discovery-v1'], 'discovery', 300, lambda: detail)
        self.now += 301
        result = self.cache.saved_threads('breece hall')
        self.assertEqual(len(result['threads']), 1)
        self.assertTrue(result['threads'][0]['stale'])
        self.assertEqual(result['threads'][0]['posted_at'], 'original')
        self.assertEqual(result['retrieval_operations'], 0)
        self.assertEqual(self.cache.saved_threads('not here')['threads'], [])
        self.now += N.RETENTION
        self.assertEqual(self.cache.saved_threads()['threads'], [])
        self.factory.assert_not_called()

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

    def test_pasted_permalink_reuses_the_id_cache_without_fetching_the_url(self):
        self.client.submission = Mock(return_value=Post())
        N.read_thread(self.cache, self.factory, 'abc', 0)
        for link in ['https://www.reddit.com/r/nfl/comments/abc/title/?utm_source=x', 'https://redd.it/abc']:
            self.assertTrue(N.read_thread(self.cache, self.factory, link, 0)['retrieval']['cache_hit'])
        self.client.submission.assert_called_once_with(id='abc')
        for link in ['https://reddit.com.evil.test/comments/abc/', 'https://user@reddit.com/comments/abc/',
                     'https://www.reddit.com/r/nfl/s/opaque', 'file:///comments/abc']:
            with self.assertRaises(ValueError):
                N.submission_id(link)

    def test_shortlist_relevance_duplicates_player_coverage(self):
        players = ['Breece Hall', "De'Von Achane"]
        posts = [Post('aaa'), Post('bbb', age=120, url='https://example.com/report?utm_source=reddit'),
                 Post('ccc', 'Breece Hall hype train'), Post('ddd', 'Josh Allen injury report'),
                 # Titled after the player, so eligible on the title signal alone,
                 # but outranked by the posts carrying injury/usage language.
                 Post('eee', 'Breece Hall is my favorite player', url='https://example.com/fav'),
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


    def test_usage_title_without_keyword_is_kept_and_drops_are_listed(self):
        # The Perine thread: titled after the player, "touch share" in the
        # title, no body, external source. focus=usage used to drop it silently.
        posts = [Post('ts', "Bengals will 'continually assess' touch share between Perine, Chase Brown",
                      url='https://example.com/touch-share'),
                 Post('hyp', 'Samaje Perine hype train', age=30),
                 Post('fav', 'Samaje Perine is my favourite player', age=20)]
        match = lambda text: {'Samaje Perine'} if 'Perine' in text else set()
        result = N.shortlist([N.post_record(p) for p in posts], ['Samaje Perine'], match, focus='usage')
        self.assertEqual([p['id'] for p in result['threads']], ['ts'])
        self.assertIn('usage', result['threads'][0]['signals'])
        listed = {d['id']: d['reason'] for d in result['filtered_titles']['Samaje Perine']}
        self.assertEqual(listed, {'hyp': 'generic_or_noise', 'fav': 'no_usage_signal'})
        # With the weekly focus a post titled after the player is evidence on its own.
        weekly = N.shortlist([N.post_record(posts[2])], ['Samaje Perine'], match)
        self.assertEqual(weekly['threads'][0]['signals'], ['title'])


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

    def test_search_terms_include_nicknames_and_unique_first_names(self):
        s = self.server
        data = {'posts': [], 'retrieval': {'cache_hit': False}, 'scanned': 0}
        with patch.object(s.NEWS, 'discover', return_value=data) as fetch:
            result = s.research_brief(['Jameson Williams', 'Bijan Robinson', 'Josh Allen'])
        query = fetch.call_args.args[3]
        for term in ('"jamo"', '"bijan"', '"Josh Allen"'):
            self.assertIn(term, query)
        for term in ('"williams"', '"allen"', '"jwilliams"', '"brobinson"'):
            self.assertNotIn(term, query)
        self.assertEqual(result['query_terms'], sorted(set(result['query_terms'])))
        self.assertIn('filtered_titles', result)

    def test_nickname_column_is_clean_and_collisions_are_caught(self):
        import copy
        R = self.server.R
        players = self.server.pool()[0]
        self.assertEqual(R.nickname_collisions(players), [])
        trial = [copy.copy(p) for p in players]
        hubbard = next(p for p in trial if p.player_name == 'Chuba Hubbard')
        hubbard.player_nickname = 'Chubb|Allen|Bengals|Skat'
        found = {nick: why for nick, who, why in R.nickname_collisions(trial) if who == 'Chuba Hubbard'}
        self.assertEqual(found['Chubb'], 'surname of a registered non-player')
        self.assertTrue(found['Allen'].startswith('name of '))
        self.assertEqual(found['Bengals'], 'team word')
        self.assertEqual(found['Skat'], 'name of Cam Skattebo')

    def test_staff_surname_places_a_shared_surname(self):
        R = self.server.R
        players, aliases, keys, cap, defaults, firsts = self.server.pool()
        self.assertIn('pitcher', R.PEOPLE_CONTEXT.get('CIN', set()))
        # Zac Taylor is CIN staff, but "Taylor" is a player surname: never team evidence.
        self.assertNotIn('taylor', R.PEOPLE_CONTEXT.get('CIN', set()))
        def resolve(text):
            return [(m.player.player_name, m.tier) for m in R.scan(
                text, aliases, keys, cap_required=cap, defaults=defaults, first_names=firsts)
                if m.alias == 'brown']
        self.assertEqual(resolve('Pitcher said Brown keeps the lead role this week.'),
                         [('Chase Brown', 'context')])
        self.assertEqual([t for _, t in resolve('I think Brown keeps the lead role this week.')],
                         ['ambiguous'])

    def test_add_nickname_refuses_collisions_and_writes_the_pool(self):
        import shutil
        s = self.server
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        copy_csv = temp / 'pool.csv'
        shutil.copy(s.POOL_CSV, copy_csv)
        with patch.object(s, 'POOL_CSV', copy_csv):
            s._pool = None
            self.assertTrue(s.add_nickname('Chuba Hubbard', 'Chubb').startswith('refused'))
            self.assertTrue(s.add_nickname('Chuba Hubbard', 'Allen').startswith('refused'))
            self.assertIn('not in the pool', s.add_nickname('Example Newcomer', 'Newk'))
            self.assertTrue(s.add_nickname('Chuba Hubbard', 'Chuubs').startswith('added'))
            self.assertEqual(s.add_nickname('Chuba Hubbard', 'Chuubs'), "'Chuubs' is already a nickname for Chuba Hubbard")
            self.assertEqual(s._names_in('I think Chuubs looked great in the fourth quarter'), {'Chuba Hubbard'})
            self.assertIn('Chuubs', copy_csv.read_text())
        s._pool = None
        self.assertNotIn('Chuubs', s.POOL_CSV.read_text())

    def test_shared_nickname_has_no_default_and_is_adjudicated_by_context(self):
        s = self.server
        R = s.R
        players, aliases, keys, cap, defaults, firsts = s.pool()
        self.assertEqual({p.player_name for p in aliases['jj']}, {'Justin Jefferson', 'J.J. McCarthy'})
        self.assertNotIn('jj', defaults)
        def tiers(text):
            return [(m.player.player_name, m.tier) for m in R.scan(
                text, aliases, keys, cap_required=cap, defaults=defaults, first_names=firsts)
                if m.alias == 'jj']
        self.assertEqual([t for _, t in tiers('Praying JJ learns the playbook this week')], ['ambiguous'])
        self.assertEqual(tiers('Our QB JJ learns the playbook this week'), [('J.J. McCarthy', 'context')])
        self.assertEqual(tiers('Start JJ at WR this week'), [('Justin Jefferson', 'context')])
        # promote() must not recreate a default for a token recorded as shared.
        import adjudicate as A
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'ov.json'
            path.write_text('{"jj": ["Justin Jefferson", "J.J. McCarthy"]}')
            decisions = {str(i): {'token': 'jj', 'player': 'Justin Jefferson'} for i in range(5)}
            self.assertEqual(A.promote(decisions, players, path), [])
            self.assertIsInstance(__import__('json').loads(path.read_text())['jj'], list)

    def test_default_only_resolution_is_labelled_not_context(self):
        s = self.server
        R = s.R
        players, aliases, keys, cap, defaults, firsts = s.pool()
        self.assertEqual(defaults.get('allen'), 'Josh Allen')
        [m] = [m for m in R.scan('Allen is a lock this week.', aliases, keys, cap_required=cap,
                                 defaults=defaults, first_names=firsts) if m.alias == 'allen']
        self.assertEqual((m.player.player_name, m.tier), ('Josh Allen', 'default'))
        self.assertNotIn('Josh Allen', s._names_in('Allen is a lock this week.'))

    def test_staff_context_needs_a_capital(self):
        s = self.server
        R = s.R
        players, aliases, keys, cap, defaults, firsts = s.pool()
        def brown(text):
            return [(m.player.player_name, m.tier) for m in R.scan(
                text, aliases, keys, cap_required=cap, defaults=defaults, first_names=firsts)
                if m.alias == 'brown']
        self.assertEqual(brown('Coach Pitcher trusts Brown in the red zone.'), [('Chase Brown', 'context')])
        self.assertEqual([t for _, t in brown('What a pitcher; anyway Brown in the red zone.')], ['ambiguous'])

    def test_search_aliases_skip_team_words_and_dictionary_nicknames(self):
        s = self.server
        _, aliases, _, cap, _, _ = s.pool()
        self.assertNotIn('dallas', s._search_aliases('Dallas Goedert', aliases, cap))
        self.assertIn('goedert', s._search_aliases('Dallas Goedert', aliases, cap))
        self.assertNotIn('hock', s._search_aliases('T.J. Hockenson', aliases, cap))
        self.assertIn('hockenson', s._search_aliases('T.J. Hockenson', aliases, cap))
        self.assertIn('perine', s._search_aliases('Samaje Perine', aliases, cap))

    def test_ambiguous_surname_posts_are_listed_not_dropped(self):
        s = self.server
        data = {'posts': [N.post_record(Post('amb', 'Brown struggles against the Ravens secondary', url='https://example.com/b')),
                          N.post_record(Post('sure', 'Chase Brown gets 62% of the carries', url='https://example.com/c'))],
                'retrieval': {'cache_hit': False}, 'scanned': 2}
        with patch.object(s.NEWS, 'discover', return_value=data):
            result = s.research_brief(['Chase Brown'], focus='usage')
        self.assertEqual([t['id'] for t in result['threads']], ['sure'])
        [lead] = result['ambiguous_titles']['Chase Brown']
        self.assertEqual((lead['id'], lead['token']), ('amb', 'Brown'))
        self.assertIn('Chase Brown', lead['candidates'])
        self.assertGreater(len(lead['candidates']), 1)
        self.assertIn('never attribute', result['next_step'])

    def test_window_full_triggers_bounded_per_player_followups(self):
        s = self.server
        first = {'posts': [N.post_record(Post('a', 'Jameson Williams scores twice', url='https://example.com/a'))],
                 'retrieval': {'cache_hit': False}, 'scanned': 100, 'scan_limit_reached': True}
        second = {'posts': [N.post_record(Post('b', 'Perine takes over the Bengals backfield', url='https://example.com/b'))],
                  'retrieval': {'cache_hit': False}, 'scanned': 3, 'scan_limit_reached': False}
        with patch.object(s.NEWS, 'discover', side_effect=[first, second, N.RetrievalStopped('budget')]) as fetch:
            result = s.research_brief(['Jameson Williams', 'Samaje Perine', 'Bijan Robinson'])
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(result['extra_queries'], 1)
        self.assertEqual({t['id'] for t in result['threads']}, {'a', 'b'})
        self.assertEqual(result['players_without_selected_evidence'], ['Bijan Robinson'])
        self.assertIn('stopped: budget', result['next_step'])
        # The follow-up query is the quiet player's own terms only.
        q = fetch.call_args_list[1].args[3]
        self.assertIn('"perine"', q)
        self.assertNotIn('Jameson', q)
        # No follow-up when the window did not fill.
        with patch.object(s.NEWS, 'discover', return_value=dict(first, scan_limit_reached=False)) as fetch:
            result = s.research_brief(['Jameson Williams', 'Samaje Perine'])
        self.assertEqual((fetch.call_count, result['extra_queries']), (1, 0))

    def test_misspelled_title_still_matches_a_unique_surname(self):
        s = self.server
        data = {'posts': [N.post_record(Post('m', 'Cam Skatebo tweaks hamstring in OT', url='https://example.com/m'))],
                'retrieval': {'cache_hit': False}, 'scanned': 1}
        with patch.object(s.NEWS, 'discover', return_value=data):
            result = s.research_brief(['Cam Skattebo'], focus='injury')
        self.assertEqual([t['id'] for t in result['threads']], ['m'])

    def test_live_mentions_lists_shared_names_as_unsettled(self):
        s = self.server
        now = __import__('time').time()
        comments = [SimpleNamespace(created_utc=now - 60, link_id='t3_x1', link_title='WDIS', score=3,
                                    body='Brown is a lock this week'),
                    SimpleNamespace(created_utc=now - 30, link_id='t3_x2', link_title='WDIS', score=1,
                                    body='Chase Brown gets the Titans, start him')]
        sub = SimpleNamespace(comments=lambda limit: comments)
        fake = SimpleNamespace(reddit=SimpleNamespace(subreddit=lambda name: sub))
        with patch.object(s, '_reddit', return_value=fake):
            text = s.live_mentions('Chase Brown', hours=1)
        self.assertIn('Chase Brown  x1', text)
        self.assertIn('unsettled', text)
        self.assertIn("'Brown'", text)
        self.assertIn('NOT attributed', text)

    def test_latest_threads_labels_ambiguous_posts_for_a_player_filter(self):
        s = self.server
        data = {'posts': [N.post_record(Post('p1', 'Brown struggles against the Ravens secondary', age=10)),
                          N.post_record(Post('p2', 'Chase Brown gets 62% of the carries', age=20)),
                          N.post_record(Post('p3', 'Bijan Robinson is fine', age=30))],
                'retrieval': {'cache_hit': False, 'fetched_at': 'now', 'remaining_hourly_operations': 9},
                'scanned': 3, 'scan_limit': 100, 'sources': ['fantasyfootball'], 'coverage_note': ''}
        with patch.object(s.NEWS, 'discover', return_value=data), \
                patch.object(s.time, 'time', return_value=NOW):
            text = s.latest_threads(player='Chase Brown', hours=24)
        self.assertIn('[ambiguous:', text)
        self.assertIn('Chase Brown gets 62%', text)
        self.assertNotIn('Bijan', text)

    def test_expand_pool_adds_only_missing_skill_players(self):
        import expand_pool as X
        pool = [{'Player': 'Marvin Harrison', 'Team': 'HOU', 'Bye': '14', 'POS': 'WR34', 'Average_ADP': '84.0',
                 'Depth': 'WR2', 'Depth_Rank': '2', 'Nickname': 'MHJ', 'espn_id': ''}]
        depth = [{'player_name': 'Marvin Harrison Jr.', 'team': 'HOU', 'pos_abb': 'WR', 'pos_rank': '1', 'espn_id': '1'},
                 {'player_name': 'Kendrick Bourne', 'team': 'HOU', 'pos_abb': 'WR', 'pos_rank': '3', 'espn_id': '2'},
                 {'player_name': '', 'team': 'NYG', 'pos_abb': 'TE', 'pos_rank': '3', 'espn_id': '3'},
                 {'player_name': 'Some Lineman', 'team': 'NYG', 'pos_abb': 'OT', 'pos_rank': '1', 'espn_id': '4'}]
        new, skipped = X.expand(pool, depth)
        self.assertEqual([r['Player'] for r in new], ['Kendrick Bourne'])
        self.assertEqual((new[0]['Average_ADP'], new[0]['Depth'], new[0]['Bye'], new[0]['espn_id']),
                         ('999', 'WR3', '14', '2'))
        self.assertEqual(dict(skipped), {'already in pool': 1, 'blank name': 1, 'position OT': 1})


if __name__ == '__main__':
    unittest.main()
