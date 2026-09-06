"""Run with: python3 -m unittest discover -s webapp -p 'test_*.py'."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import local_server as L


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = L.DraftServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None, headers=None):
        req = Request(self.url + path, data=None if body is None else json.dumps(body).encode(),
                      headers=headers or {})
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as e:
            response = e
        with response:
            return response.status, response.read().decode()

    def test_only_dashboard_assets_are_served(self):
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn('id="set-use-claude"', body)
        for path in ["/local_server.py", "/../.mcp.json", "/data/", "/../../.env"]:
            self.assertEqual(self.request(path)[0], 404)

    def test_browser_cannot_invoke_cli_from_another_origin(self):
        body = {"messages": [{"role": "user", "content": "test"}]}
        base = {"Content-Type": "application/json", "X-FFDA-Token": self.server.token}
        for extra in [{"Origin": "https://example.com"}, {"Host": "attacker.example"},
                      {"X-FFDA-Token": "wrong"}]:
            with patch.object(L, "stream_claude") as invoke:
                self.assertEqual(self.request("/api/claude/chat", body, base | extra)[0], 403)
                invoke.assert_not_called()

    def test_streaming_and_errors_reach_client(self):
        headers = {"Content-Type": "application/json", "X-FFDA-Token": self.server.token}
        body = {"messages": [{"role": "user", "content": "Who should I draft?"}]}

        def answer(messages):
            yield {"text": "One "}
            yield {"text": "answer"}
            yield {"done": True}

        with patch.object(L, "login_status", return_value={"ready": True}), patch.object(L, "stream_claude", answer):
            status, text = self.request("/api/claude/chat", body, headers)
            self.assertEqual(status, 200)
            events = [json.loads(line) for line in text.splitlines()]
            self.assertEqual("".join(e.get("text", "") for e in events), "One answer")
            self.assertTrue(events[-1]["done"])

        def failed(messages):
            yield {"text": "Partial"}
            raise RuntimeError("Subscription limit reached")

        with patch.object(L, "login_status", return_value={"ready": True}), patch.object(L, "stream_claude", failed):
            _, text = self.request("/api/claude/chat", body, headers)
            self.assertIn("Subscription limit reached", text)
            self.assertFalse(self.server.ai_lock.locked())

    def test_validation_and_busy_state(self):
        headers = {"Content-Type": "application/json", "X-FFDA-Token": self.server.token}
        self.assertEqual(self.request("/api/claude/chat", {"messages": "wrong"}, headers)[0], 400)
        self.server.ai_lock.acquire()
        try:
            self.assertEqual(self.request("/api/claude/chat", {"messages": [{"role": "user", "content": "hi"}]}, headers)[0], 409)
        finally:
            self.server.ai_lock.release()

    def test_no_api_key_or_provider_override_in_child(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fixture", "ANTHROPIC_BASE_URL": "fixture"}):
            env = L.claude_env()
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertNotIn("ANTHROPIC_BASE_URL", env)
        cmd = L.claude_command("test")
        self.assertEqual(cmd[cmd.index("--model") + 1], "sonnet")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertIn("--safe-mode", cmd)
        self.assertNotIn("--bare", cmd)  # bare mode would disable subscription auth

    def test_cli_events_are_filtered_and_not_duplicated(self):
        events = [
            {"type": "system", "subtype": "init", "model": "sonnet", "private": "do not expose"},
            {"type": "stream_event", "event": {"delta": {"type": "thinking_delta", "thinking": "hidden"}}},
            {"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": "Answer"}}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Answer"}]}},
            {"type": "result", "result": "Answer", "is_error": False},
        ]
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "fake_cli.py"
            script.write_text("import sys\nsys.stdin.read()\n" + "\n".join(f"print({json.dumps(e)!r}, flush=True)" for e in events))
            with patch.object(L, "claude_command", return_value=[sys.executable, str(script)]):
                result = list(L.stream_claude([{"role": "user", "content": "fixture"}]))
        self.assertEqual(result, [{"model": "sonnet"}, {"text": "Answer"}, {"done": True}])


if __name__ == "__main__":
    unittest.main()
