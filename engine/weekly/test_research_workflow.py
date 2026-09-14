"""MCP integration checks for weekly research; no network or league credentials."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import mcp_server as S


class ResearchWorkflow(unittest.TestCase):
    def test_checklist_uses_canonical_runbook(self):
        self.assertEqual(S.weekly_checklist(), Path(S.__file__).with_name('RESEARCH.md').read_text())
        self.assertIn('research_brief', S.weekly_checklist())

    def test_same_week_from_old_season_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'latest.json').write_text(json.dumps({
                'season': 2025, 'week': 1, 'label': '2025 Week 1',
                'generated': '2025-09-01T00:00:00Z', 'skill': []}))
            with patch.object(S, 'DATA', Path(tmp)), patch.object(S, '_state', return_value=(2026, 1)), patch.object(S, 'load_env', return_value={}):
                self.assertIn('stale season/week', S.week_status())


if __name__ == '__main__':
    unittest.main()
