"""MCP integration checks for weekly research; no network or league credentials."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import mcp_server as S


class ResearchWorkflow(unittest.TestCase):
    def test_rankings_distinguish_missing_team_from_opponent(self):
        # The keyless source has opponents but no skill-player team field.
        # Keep that absence explicit rather than implying WAS is the team.
        rows = [
            dict(pos='WR', rank_ecr='1', name='Receiver A', team='', opp='WAS',
                 rank_min='1', rank_max='2', rank_std='0.5', source='fftiers'),
            dict(pos='WR', rank_ecr='2', name='Receiver B', team='WAS', opp='SEA',
                 rank_min='1', rank_max='3', rank_std='0.8', source='fantasypros'),
            dict(pos='WR', rank_ecr='3', name='Receiver C', team='', opp='',
                 rank_min='2', rank_max='4', rank_std='1.0', source='fftiers'),
        ]
        with patch.object(S, '_week', return_value=(2026, 3)), patch.object(S, '_read_csv', return_value=rows):
            report = S.fantasypros_rankings('WR', week=3)
        self.assertIn('team=unknown opp=WAS', report)
        self.assertIn('team=WAS opp=SEA', report)
        self.assertIn('team=unknown opp=unknown', report)

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
