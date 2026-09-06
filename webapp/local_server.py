#!/usr/bin/env python3
"""Personal draft dashboard + streaming Claude Code bridge (stdlib only).

Run: python3 webapp/local_server.py
Uses the installed Claude Code subscription login. No API key is accepted.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import selectors
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

WEBAPP = Path(__file__).resolve().parent
MAX_BODY = 300_000
TIMEOUT = 150


def claude_env():
    env = os.environ.copy()
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                "CLAUDE_CODE_USE_FOUNDRY", "CLAUDECODE"):
        env.pop(key, None)
    return env


def claude_command(system):
    return [shutil.which("claude") or "claude", "-p", "--model", "sonnet",
            "--output-format", "stream-json", "--verbose",
            "--include-partial-messages", "--safe-mode", "--tools", "",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--no-session-persistence", "--system-prompt", system]


def login_status():
    if not shutil.which("claude"):
        return {"ready": False, "error": "Claude Code is not installed. Install it, then run claude auth login."}
    try:
        result = subprocess.run(["claude", "auth", "status"], env=claude_env(),
                                capture_output=True, text=True, timeout=10)
        auth = json.loads(result.stdout)
        ready = bool(auth.get("loggedIn") and auth.get("authMethod") == "claude.ai")
        return {"ready": ready, "model": "sonnet", "error": "" if ready else
                "Run claude auth login in your terminal and sign in with your Claude subscription."}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"ready": False, "error": "Could not check Claude Code login. Run claude auth status in your terminal."}


def stream_claude(messages):
    """Yield only public answer text/status; never relay CLI init/auth metadata."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    prompt = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
    with tempfile.TemporaryDirectory(prefix="ff-draft-") as work, tempfile.TemporaryFile() as errors, tempfile.TemporaryFile() as input_file:
        input_file.write(prompt.encode())
        input_file.seek(0)
        proc = subprocess.Popen(claude_command(system), stdin=input_file,
                                stdout=subprocess.PIPE, stderr=errors, cwd=work,
                                env=claude_env(), start_new_session=True)
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(proc.stdout, selectors.EVENT_READ)
                started = time.monotonic()
                buffer = b""
                answer = ""
                last_ping = started
                while time.monotonic() - started < TIMEOUT:
                    if not sel.select(1):
                        if time.monotonic() - last_ping >= 5:
                            yield {"waiting": True}
                            last_ping = time.monotonic()
                        continue
                    chunk = os.read(proc.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line.strip():
                            continue
                        item = json.loads(line)
                        if item.get("type") == "system" and item.get("subtype") == "init":
                            yield {"model": item.get("model", "sonnet")}
                        elif item.get("type") == "stream_event":
                            delta = item.get("event", {}).get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                answer += text
                                yield {"text": text}
                        elif item.get("type") == "result":
                            if item.get("is_error"):
                                message = item.get("result") or "; ".join(item.get("errors", []))
                                raise RuntimeError(message or "Claude Code could not answer. Check your subscription usage and login.")
                            final = item.get("result", "")
                            if not answer and final:
                                yield {"text": final}
                            elif final.startswith(answer) and len(final) > len(answer):
                                yield {"text": final[len(answer):]}
                            if not answer and not final:
                                raise RuntimeError("Claude returned an empty answer. Try again.")
                            yield {"done": True}
                            return
                if time.monotonic() - started >= TIMEOUT:
                    raise RuntimeError("Claude took too long. Try again; draft tracking still works.")
                raise RuntimeError("Claude Code exited before completing. Check claude auth status and try again.")
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
            proc.stdout.close()


class DraftServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.token = secrets.token_urlsafe(32)
        self.ai_lock = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEBAPP), **kwargs)

    def local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return host in hosts and (origin is None or origin == f"http://{host}")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.local_request():
            return self.send_json(403, {"error": "Open the dashboard on localhost."})
        path = urlsplit(self.path).path
        if path == "/api/claude/status":
            return self.send_json(200, {"service": "ffda-claude", "token": self.server.token,
                                        **login_status()})
        return super().do_GET()

    def do_HEAD(self):
        if not self.local_request():
            return self.send_json(403, {"error": "Local requests only."})
        return super().do_HEAD()

    def send_head(self):
        # Serve only dashboard assets, not Python source, tests or directory listings.
        path = Path(self.translate_path(self.path)).resolve()
        if path == WEBAPP:
            path = WEBAPP / "index.html"
        if (not path.is_relative_to(WEBAPP) or not path.is_file()
                or path.suffix not in {".html", ".js", ".css", ".png", ".svg", ".ico"}):
            self.send_error(404)
            return None
        return super().send_head()

    def do_POST(self):
        if (not self.local_request() or not secrets.compare_digest(
                self.headers.get("X-FFDA-Token", ""), self.server.token)):
            return self.send_json(403, {"error": "Reload your local dashboard and try again."})
        if urlsplit(self.path).path != "/api/claude/chat":
            return self.send_json(404, {"error": "Unknown endpoint."})
        if self.headers.get_content_type() != "application/json":
            return self.send_json(415, {"error": "Expected JSON."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                return self.send_json(413, {"error": "Draft request is too large or empty."})
            self.connection.settimeout(15)
            body = json.loads(self.rfile.read(size))
            messages = body.get("messages")
            if (not isinstance(messages, list) or not 1 <= len(messages) <= 4
                    or any(not isinstance(m, dict) or m.get("role") not in {"system", "user"}
                           or not isinstance(m.get("content"), str) for m in messages)
                    or not any(m["role"] == "user" and m["content"].strip() for m in messages)):
                raise ValueError("Invalid messages")
        except (ValueError, AttributeError, OSError):
            return self.send_json(400, {"error": "Invalid draft request."})
        if not self.server.ai_lock.acquire(blocking=False):
            return self.send_json(409, {"error": "Claude is already answering a draft question. Wait for it to finish."})
        try:
            auth = login_status()
            if not auth["ready"]:
                return self.send_json(503, {"error": auth["error"]})
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            stream = stream_claude(messages)
            try:
                for event in stream:
                    self.wfile.write((json.dumps(event) + "\n").encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            except (RuntimeError, OSError, ValueError) as e:
                self.wfile.write((json.dumps({"error": str(e)}) + "\n").encode())
                self.wfile.flush()
            finally:
                stream.close()
        finally:
            self.server.ai_lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = DraftServer(("127.0.0.1", args.port))
    status = login_status()
    print(f"Draft dashboard: http://localhost:{server.server_port}", flush=True)
    print("Claude Sonnet: " + ("subscription login ready" if status["ready"] else status["error"]), flush=True)
    print("Keep this terminal open. Ctrl+C stops the local server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
