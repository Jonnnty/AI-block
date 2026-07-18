#!/usr/bin/env python3
"""Local server for splat placement editor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PLACEMENTS = ROOT / "placements.json"


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/placement_editor.html")
            self.end_headers()
            return
        if path == "/api/placements":
            if PLACEMENTS.exists():
                self._json(200, json.loads(PLACEMENTS.read_text(encoding="utf-8")))
            else:
                self._json(200, [])
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "configVersion": 2})
            return
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/placements":
            data = self._read_json()
            if isinstance(data, list):
                payload = data
            elif isinstance(data, dict) and (
                data.get("version", 0) >= 2 or isinstance(data.get("placements"), list)
            ):
                payload = data
            else:
                self._json(400, {"error": "expected JSON list or v2 config object"})
                return
            try:
                PLACEMENTS.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError as e:
                self._json(500, {"error": f"cannot write placements.json: {e}"})
                return
            count = len(payload) if isinstance(payload, list) else len(payload.get("placements", []))
            self._json(200, {"ok": True, "count": count, "configVersion": 2 if isinstance(payload, dict) else 1})
            return
        if path == "/api/merge":
            data = self._read_json() if self.headers.get("Content-Length") else {}
            out = data.get("out", "scene.ply") if isinstance(data, dict) else "scene.ply"
            cmd = [
                sys.executable,
                str(ROOT / "place_buildings.py"),
                "--config", "placements.json",
                "--out", out,
            ]
            try:
                subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                self._json(500, {"error": e.stderr or str(e)})
                return
            self._json(200, {"ok": True, "out": out})
            return

        self._json(404, {"error": "not found"})


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "127.0.0.1")
    httpd = ReusableThreadingHTTPServer((host, port), Handler)
    print(f"摆放器: http://{host}:{port}/placement_editor.html")
    print("  拖入 PLY 模型开始摆放")
    print("  Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
