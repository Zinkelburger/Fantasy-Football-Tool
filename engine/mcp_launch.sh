#!/usr/bin/env bash
# Launch one of the repo's MCP servers with whichever venv exists on this
# machine. .mcp.json used to hardcode /home/<user>/... paths, which broke the
# moment the repo was cloned under a different home; this resolves everything
# from its own location instead, so cwd and username do not matter.
#
#   engine/mcp_launch.sh reddit   -> engine/reddit-scraper/mcp_server.py
#   engine/mcp_launch.sh weekly   -> engine/weekly/mcp_server.py
#   engine/mcp_launch.sh youtube  -> engine/youtube/mcp_server.py
#   engine/mcp_launch.sh weather  -> engine/weather/mcp_server.py
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-}" in
  reddit) DIR="$ROOT/engine/reddit-scraper"
          VENVS=("$ROOT/.venv-reddit-scraper" "$DIR/.venv" "$DIR/venv") ;;
  weekly) DIR="$ROOT/engine/weekly"
          VENVS=("$ROOT/.venv-league-sim" "$ROOT/engine/league-sim/.venv" "$DIR/.venv") ;;
  youtube) DIR="$ROOT/engine/youtube"
          VENVS=("$ROOT/.venv-youtube" "$DIR/.venv") ;;
  weather) DIR="$ROOT/engine/weather"   # reads the weekly engine's schedule cache
          VENVS=("$ROOT/.venv-league-sim" "$ROOT/engine/league-sim/.venv") ;;
  *) echo "usage: $0 reddit|weekly|youtube|weather" >&2; exit 2 ;;
esac
for v in "${VENVS[@]}"; do
  if [ -x "$v/bin/python" ]; then
    cd "$DIR" && exec "$v/bin/python" "$DIR/mcp_server.py"
  fi
done
echo "no venv found for $1; tried: ${VENVS[*]}" >&2
exit 1
