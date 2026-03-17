#!/usr/bin/env python3
"""Proxy: Claude Code CLI -> OpenRouter.

Model translation + SSE cleanup + thinking block filtering.
Reads config from environment:
  - LLM_API_KEY: OpenRouter API key (required)
  - CLAUDE_CODE_PROXY_PORT: listen port (default 9999)
"""
import json
import http.server
import http.client
import os
import ssl
import sys
import socketserver

OPENROUTER_HOST = "openrouter.ai"
API_KEY = os.environ.get("LLM_API_KEY", "")

PROXY_PORT = int(os.environ.get("CLAUDE_CODE_PROXY_PORT", "9999"))

MODEL_MAP = {
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4.6",
    "claude-opus-4-6": "anthropic/claude-opus-4.6",
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4.5",
    "claude-sonnet-4-5-20250929": "anthropic/claude-sonnet-4.5",
    "claude-opus-4-5": "anthropic/claude-opus-4.5",
    "claude-haiku-4-5": "anthropic/claude-haiku-4.5",
    "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
    "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
    "claude-3-7-sonnet": "anthropic/claude-3.7-sonnet",
}

MODELS_RESP = json.dumps({
    "data": [
        {"id": k, "object": "model", "display_name": k, "created": 0}
        for k in MODEL_MAP
    ]
}).encode()

CTX = ssl.create_default_context()


def _clean_json(raw):
    """Clean OpenRouter JSON: remove nulls, strip model prefix."""
    try:
        obj = json.loads(raw)
    except Exception:
        return raw

    def _clean(d):
        if isinstance(d, dict):
            out = {}
            for k, v in d.items():
                if v is None and k not in ("stop_reason", "stop_sequence"):
                    continue
                out[k] = _clean(v)
            return out
        elif isinstance(d, list):
            return [_clean(i) for i in d]
        return d

    obj = _clean(obj)
    if "message" in obj and "model" in obj["message"]:
        m = obj["message"]["model"]
        if "/" in m:
            obj["message"]["model"] = m.split("/", 1)[1]
    return json.dumps(obj)


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[proxy] {fmt % args}", flush=True)

    def do_GET(self):
        if "/models" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(MODELS_RESP))
            self.end_headers()
            self.wfile.write(MODELS_RESP)
            return
        self._fwd("GET")

    def do_POST(self):
        self._fwd("POST")

    def _fwd(self, method):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        is_stream = False
        if body:
            try:
                data = json.loads(body)
                if "model" in data:
                    orig = data["model"]
                    data["model"] = MODEL_MAP.get(orig, orig)
                    print(f"[proxy] model: {orig} -> {data['model']}", flush=True)
                is_stream = data.get("stream", False)
                body = json.dumps(data).encode()
            except Exception:
                pass

        conn = http.client.HTTPSConnection(
            OPENROUTER_HOST, context=CTX, timeout=120
        )
        remote_path = "/api" + self.path
        hdrs = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": self.headers.get("Content-Type", "application/json"),
        }
        for h in ("anthropic-version", "anthropic-beta", "x-api-key"):
            v = self.headers.get(h)
            if v:
                hdrs[h] = v

        print(f"[proxy] {method} {remote_path} stream={is_stream}", flush=True)
        conn.request(method, remote_path, body=body, headers=hdrs)
        resp = conn.getresponse()
        print(f"[proxy] upstream {resp.status}", flush=True)

        if is_stream and resp.status == 200:
            self._handle_stream(resp)
        else:
            self._handle_non_stream(resp)
        conn.close()

    def _handle_stream(self, resp):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        buf = b""
        current_event = None
        thinking_index = set()

        while True:
            chunk = resp.read(1)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\r")

                if line.startswith("event: "):
                    current_event = line[7:].strip()
                    if current_event == "data":
                        current_event = "__skip__"
                        continue
                elif line.startswith("data: "):
                    if current_event == "__skip__":
                        current_event = None
                        continue

                    raw_data = line[6:]
                    cleaned = _clean_json(raw_data)
                    if cleaned is None:
                        continue

                    # Filter thinking/redacted_thinking blocks
                    try:
                        evt = json.loads(cleaned)
                        evt_type = evt.get("type", "")

                        if evt_type == "content_block_start":
                            cb = evt.get("content_block", {})
                            cb_type = cb.get("type", "")
                            if cb_type in ("thinking", "redacted_thinking"):
                                thinking_index.add(evt.get("index", -1))
                                continue
                        elif evt_type == "content_block_delta":
                            if evt.get("index", -1) in thinking_index:
                                continue
                        elif evt_type == "content_block_stop":
                            if evt.get("index", -1) in thinking_index:
                                continue
                    except Exception:
                        pass

                    try:
                        if current_event:
                            self.wfile.write(
                                f"event: {current_event}\n".encode()
                            )
                        self.wfile.write(f"data: {cleaned}\n".encode())
                    except BrokenPipeError:
                        return
                elif line == "":
                    if current_event != "__skip__":
                        try:
                            self.wfile.write(b"\n")
                            self.wfile.flush()
                        except BrokenPipeError:
                            return
                    current_event = None
                else:
                    try:
                        self.wfile.write((line + "\n").encode())
                    except BrokenPipeError:
                        return

    def _handle_non_stream(self, resp):
        resp_body = resp.read()
        if resp.status == 200 and resp_body:
            try:
                obj = json.loads(resp_body)
                if "model" in obj and "/" in obj["model"]:
                    obj["model"] = obj["model"].split("/", 1)[1]
                # Remove thinking blocks from non-streaming response
                if "content" in obj:
                    obj["content"] = [
                        b
                        for b in obj["content"]
                        if b.get("type") not in ("thinking", "redacted_thinking")
                    ]
                resp_body = json.dumps(obj).encode()
            except Exception:
                pass
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            kl = k.lower()
            if kl in (
                "transfer-encoding",
                "connection",
                "content-encoding",
                "content-length",
            ):
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", len(resp_body))
        self.end_headers()
        self.wfile.write(resp_body)


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    if not API_KEY:
        print("[proxy] ERROR: LLM_API_KEY environment variable is required", flush=True)
        sys.exit(1)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PROXY_PORT
    s = ThreadedServer(("127.0.0.1", port), ProxyHandler)
    print(f"[proxy] http://127.0.0.1:{port}", flush=True)
    s.serve_forever()
