"""Exercise the weekly tools through the real MCP stdio transport."""
import asyncio
import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import mcp_server as server


def csv_file(root, name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (root / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class ToolIntegration(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        csv_file(self.root, "team_context_2026.csv", [
            {"week": 1, "team": "DET", "plays": 50, "dropbacks": 30, "rushes": 20,
             "attempts": 28, "epa_pass": 1.0, "epa_pass_n": 30,
             "epa_rush": 0, "cpoe": "", "proe": ""},
            {"week": 1, "team": "BUF", "plays": 60, "dropbacks": 40, "rushes": 20,
             "attempts": 38, "epa_pass": 0, "epa_pass_n": 40},
            {"week": 2, "team": "DET", "plays": 80, "dropbacks": 60, "rushes": 20,
             "attempts": 58, "epa_pass": -1.0, "epa_pass_n": 60},
        ])
        csv_file(self.root, "lines_2026.csv", [
            {"week": w, "team": t} for w in (1, 2) for t in ("DET", "BUF")])
        csv_file(self.root, "ecr_2026_wk02.csv", [{
            "pos": "RB", "rank_ecr": 1, "name": "Jahmyr Gibbs", "team": "DET",
            "opp": "BUF", "tier": 1, "rank_min": 1, "rank_max": 6,
            "rank_std": 0.89, "source": "fftiers"}])

    def test_pooling_uses_production_denominators_and_handles_empty_range(self):
        with patch.object(server, "DATA", self.root):
            rows, weeks = server._team_context(2026, 2, last=2)
            self.assertEqual(weeks, [1, 2])
            self.assertAlmostEqual(rows["DET"]["epa_pass"], -1 / 3)
            self.assertEqual(server._team_context(2026, -1), ({}, []))
            rows, weeks = server._team_context(2026, 0)
            self.assertEqual(weeks, [1])

    def test_player_lookup_accepts_legacy_and_partial_snap_exports(self):
        player = {"player_id": "p", "name": "Test Player", "pos": "WR", "team": "DET",
                  "games": 0, "ewma_ep_std": 1., "ewma_ep_half": 2., "ewma_ep_ppr": 3.}
        with patch.object(server, "DATA", self.root), \
                patch.object(server, "_state", return_value=(2026, 2)), \
                patch.object(server, "_opportunity", return_value={"p": player}), \
                patch.object(server, "_lines_week", return_value={}):
            for extra in ({}, {"snaps_off": 20, "snap_share": ""},
                          {"snaps_off": 20, "snap_share": .5}):
                csv_file(self.root, "advanced_usage_2026_weekly.csv",
                         [{"player_id": "p", "week": 1, **extra}])
                result = server.player_lookup("Test Player")
                self.assertIn("Test Player", result)
                self.assertEqual("snaps:" in result, extra.get("snap_share") == .5)

    def test_stdio_discovery_and_read_tools(self):
        async def run():
            code = (
                "import sys; from pathlib import Path; import mcp_server as s; "
                "s.DATA=Path(sys.argv[1]); s._state=lambda:(2026,2); "
                "s.load_env=lambda:{}; s.mcp.run()")
            params = StdioServerParameters(
                command=sys.executable, args=["-c", code, str(self.root)],
                cwd=str(Path(server.__file__).parent))
            with tempfile.TemporaryFile(mode="w+") as errors:
                async with stdio_client(params, errlog=errors) as (read, write):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        names = {t.name for t in (await client.list_tools()).tools}
                        self.assertTrue({"team_context", "fantasypros_rankings", "player_lookup"} <= names)
                        for name, args, expected in [
                            ("team_context", {}, "week 1 offences"),
                            ("team_context", {"team": "DET", "week": 2, "last": 2}, "weeks 1-2 pooled"),
                            ("fantasypros_rankings", {"position": "RB", "week": 2}, "tier 1"),
                            ("week_status", {}, "expert consensus: 1 ranked"),
                        ]:
                            result = await client.call_tool(name, args)
                            self.assertFalse(result.is_error, result)
                            output = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                            self.assertIn(expected, output)
        asyncio.run(asyncio.wait_for(run(), timeout=30))


if __name__ == "__main__":
    unittest.main()
