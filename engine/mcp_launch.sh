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
#   engine/mcp_launch.sh setup [name...]   build/sync venvs only, no launch
#
# If no venv exists, the first one listed is created from the server's
# requirements.txt, so a fresh clone works out of the box. A venv is re-synced
# whenever that requirements.txt changes. All output goes to stderr: stdout is
# the MCP JSON-RPC channel.
#
# Claude Code waits ~30s for a server to start, and a cold build can take
# longer (~50s for youtube; weekly pulls polars/pyarrow). On a new machine run
# `setup` once, or reconnect with /mcp after a first attempt times out.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

resolve() {
  case "$1" in
    reddit) DIR="$ROOT/engine/reddit-scraper"; REQ="$DIR/requirements.txt"
            VENVS=("$ROOT/.venv-reddit-scraper" "$DIR/.venv" "$DIR/venv") ;;
    weekly) DIR="$ROOT/engine/weekly"; REQ="$DIR/requirements.txt"
            VENVS=("$ROOT/.venv-league-sim" "$ROOT/engine/league-sim/.venv" "$DIR/.venv") ;;
    youtube) DIR="$ROOT/engine/youtube"; REQ="$DIR/requirements.txt"
            VENVS=("$ROOT/.venv-youtube" "$DIR/.venv") ;;
    weather) DIR="$ROOT/engine/weather"   # reads the weekly engine's schedule cache
            REQ="$ROOT/engine/weekly/requirements.txt"
            VENVS=("$ROOT/.venv-league-sim" "$ROOT/engine/league-sim/.venv") ;;
    *) echo "usage: $0 reddit|weekly|youtube|weather | setup [name...]" >&2; exit 2 ;;
  esac
}

# Sets PY to a ready interpreter, creating or syncing the venv as needed.
# .ff-building marks a venv whose build was interrupted; .ff-requirements
# holds the hash of the requirements.txt it was last synced against.
ensure_venv() {
  local v="" cand want
  for cand in "${VENVS[@]}"; do
    if [ -x "$cand/bin/python" ]; then v="$cand"; break; fi
  done
  [ -n "$v" ] || v="${VENVS[0]}"
  want="$(sha256sum "$REQ" | cut -d' ' -f1)"
  if [ -x "$v/bin/python" ] && [ ! -e "$v/.ff-building" ] \
     && [ "$(cat "$v/.ff-requirements" 2>/dev/null)" = "$want" ]; then
    PY="$v/bin/python"; return
  fi
  # weekly and weather share a venv and Claude Code starts them together.
  exec 9>"$v.lock"
  flock 9
  # An interrupted build (e.g. Claude Code's startup timeout) is resumed, not
  # restarted: pip skips what is already installed, so each retry gets further.
  if [ ! -x "$v/bin/python" ]; then
    echo "[mcp_launch] building $v from ${REQ#$ROOT/}" >&2
    rm -rf "$v"
    python3 -m venv "$v" >&2
    touch "$v/.ff-building"
  elif [ -e "$v/.ff-building" ]; then
    echo "[mcp_launch] resuming interrupted build of $v" >&2
  elif [ "$(cat "$v/.ff-requirements" 2>/dev/null)" != "$want" ]; then
    echo "[mcp_launch] syncing $v with ${REQ#$ROOT/}" >&2
  fi
  if [ "$(cat "$v/.ff-requirements" 2>/dev/null)" != "$want" ] || [ -e "$v/.ff-building" ]; then
    "$v/bin/pip" install -q --disable-pip-version-check -r "$REQ" >&2
    echo "$want" > "$v/.ff-requirements"
    rm -f "$v/.ff-building"
  fi
  exec 9>&-
  PY="$v/bin/python"
}

if [ "${1:-}" = "setup" ]; then
  shift
  names=("$@"); [ ${#names[@]} -gt 0 ] || names=(reddit weekly youtube weather)
  for n in "${names[@]}"; do
    resolve "$n"; ensure_venv; echo "$n: $PY" >&2
  done
  exit 0
fi

resolve "${1:-}"
ensure_venv
cd "$DIR" && exec "$PY" "$DIR/mcp_server.py"
