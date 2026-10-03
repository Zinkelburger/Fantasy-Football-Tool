"""Offline transcript pagination and discovery contracts; no YouTube requests."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mcp_server as S


class TranscriptPages(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.vid = 'abcdefghijk'
        self.text = ''.join(str(i % 10) for i in range(15000))
        (self.root / f'{self.vid}.json').write_text(json.dumps({
            'language': 'en', 'generated': True, 'snippets': [[0, self.text]]}))
        for p in [patch.object(S, 'TRANSCRIPTS', self.root), patch.object(S, '_metadata', return_value={
                'title': 'Fixture only', 'channel': 'Test', 'handle': '@test', 'upload_date': '20260930', 'duration': 60})]:
            p.start()
            self.addCleanup(p.stop)

    def test_default_page_is_bounded_with_an_exact_continuation(self):
        result = S.video_transcript(self.vid)
        self.assertLess(len(result), 6800)
        self.assertIn('next_offset=6000', result)
        self.assertIn('6000 of 15000', result)
        self.assertIn('not verified current injury status', result)

    def test_pages_reconstruct_the_complete_text_without_silent_truncation(self):
        pages = []
        for offset in [0, 6000, 12000]:
            result = S.video_transcript(self.vid, offset=offset)
            page = result.split('\n\n', 1)[1].rsplit('\n', 1)[0]
            pages.append(page)
        self.assertEqual(''.join(pages), self.text)
        self.assertIn('End of transcript.', result)

    def test_invalid_sizes_and_offsets_are_actionable(self):
        for kwargs in [{'offset': -1}, {'offset': 16000}, {'max_chars': 40000}, {'max_chars': 0}]:
            with self.assertRaises(ValueError):
                S.video_transcript(self.vid, **kwargs)

    def test_discovery_exposes_bounds_and_defaults(self):
        tools = {t.name: t for t in asyncio.run(S.mcp.list_tools())}
        props = tools['video_transcript'].input_schema['properties']
        self.assertEqual(props['max_chars']['default'], 6000)
        self.assertEqual(props['max_chars']['maximum'], 12000)
        self.assertEqual(props['offset']['minimum'], 0)
        self.assertEqual(tools['player_videos'].input_schema['properties']['per_channel']['default'], 3)


if __name__ == '__main__':
    unittest.main()
