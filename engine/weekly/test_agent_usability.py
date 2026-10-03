"""Small-model failure scenarios: concrete paths, bounded reads and no guessed facts."""
import ast
import inspect
import re
import unittest
from unittest.mock import Mock, patch

import agent_guide
import mcp_server as S


class GuidedCalls(unittest.TestCase):
    def test_default_guides_and_each_task_fit_a_small_context(self):
        self.assertLess(len(S.weekly_checklist()), 1600)
        self.assertLess(len(S.research_sources()), 1300)
        for task in agent_guide.ROUTES:
            guide = S.weekly_checklist(task)
            self.assertLess(len(guide), 2000, task)
            self.assertIn("STOP:", guide)

    def test_documented_call_arguments_exist_on_actual_functions(self):
        for task in ["quick", *agent_guide.ROUTES]:
            for name, args in re.findall(r"\b([a-z_]+)\(([^()]*)\)", S.weekly_checklist(task)):
                if not hasattr(S, name):  # Explicitly named ff-reddit tools.
                    self.assertIn(name, {"research_brief", "read_research_thread"})
                    continue
                call = ast.parse(f"{name}({args})", mode="eval").body
                parameters = inspect.signature(getattr(S, name)).parameters
                self.assertTrue({k.arg for k in call.keywords} <= set(parameters), (task, name, args))

    def test_bad_team_is_repairable_input_not_an_invitation_to_refresh(self):
        with patch.object(S, "_state", return_value=(2026, 4)):
            for call in [lambda: S.target_share(team="ZZ"), lambda: S.depth_chart(team="ZZ"),
                         lambda: S.practice_report(team="ZZ", week=4, season=2026)]:
                with self.assertRaisesRegex(S.InputError, "Invalid teams cannot be fixed"):
                    call()


class Availability(unittest.TestCase):
    def setUp(self):
        self.league = Mock()
        self.settings = {"scoring_format": "std", "my_team_id": 1, "teams": [{"id": 2, "name": "Other"}]}
        self.league.settings.return_value = self.settings
        self.league.rosters.return_value = {2: [{"id": 2, "name": "James Williams", "pos": "WR", "team": "DET"}]}
        self.league.free_agents.return_value = [
            {"id": 1, "name": "Darren Waller", "pos": "TE", "team": "CAR", "status": "WAIVERS"},
            {"id": 3, "name": "Kyle Williams", "pos": "WR", "team": "NE", "status": "FREEAGENT"}]

    def test_exact_availability_needs_no_model_files_or_my_roster(self):
        with patch.object(S, "_state", return_value=(2026, 4)), patch.object(S, "_league", return_value=self.league), \
                patch.object(S, "_projected_roster", side_effect=AssertionError("must not load projection model")):
            out = S.free_agents(names="Darren Waller", week=4)
        self.assertIn("ON WAIVERS", out)
        self.assertIn("id=1", out)
        self.assertNotIn("proj", out)

    def test_ambiguous_surname_does_not_pick_first_owned_or_free_player(self):
        out = S._availability(self.league, self.settings, self.league.free_agents.return_value, 4, ["Williams"])[0]
        self.assertIn("UNKNOWN", out)
        self.assertIn("ambiguous", out)
        self.assertIn("James Williams", out)
        self.assertIn("Kyle Williams", out)
        self.assertNotIn("FREE AGENT", out)

    def test_unknown_name_does_not_establish_unowned(self):
        out = S._availability(self.league, self.settings, [], 4, ["Nobody Here"])[0]
        self.assertIn("UNKNOWN", out)
        self.assertNotIn("on no league roster", out)


class ProposalPreview(unittest.TestCase):
    def test_preview_is_explicit_and_never_serializes_transport_credentials(self):
        league = Mock()
        league.add_drop.return_value = {"would_post": {"memberId": "SYNTHETIC_SECRET"}}
        settings = {"league": "Test League", "my_team_id": 1}
        add = {"id": 1, "name": "New TE", "pos": "TE", "team": "CAR", "proj": 5, "value": 6, "waiver": True}
        drop = {"id": 2, "name": "Old TE", "pos": "TE", "team": "SEA", "value": 3}
        with patch.object(S, "_state", return_value=(2026, 4)), \
                patch.object(S, "_projected_roster", return_value=(league, settings, [drop], [add])), \
                patch.object(S, "_save_proposal", return_value="test-token"):
            text = S.propose_transaction(add_id=1, drop_id=2, bid=7, week=4)
        self.assertIn("approval_required: true", text)
        self.assertIn("waiver bid 7", text)
        self.assertIn('"week": 4', text)
        self.assertNotIn("SYNTHETIC_SECRET", text)
        self.assertNotIn("memberId", text)
        league.add_drop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
