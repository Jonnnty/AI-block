#!/usr/bin/env python3
"""Local server for splat placement editor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
PLACEMENTS = ROOT / "placements.json"
OUTPUTS = Path(r"D:\Downloads\outputs")
if not OUTPUTS.is_dir():
    OUTPUTS = ROOT / "outputs"
OUTPUTS_50 = Path(r"D:\Downloads\outputs_50pct")
if not OUTPUTS_50.is_dir():
    OUTPUTS_50 = ROOT / "outputs_50pct"


def guess_asset_path(asset_name: str) -> Path | None:
    name = Path(asset_name).name
    if not name or name != asset_name or ".." in asset_name:
        return None
    for candidate in (
        OUTPUTS_50 / name,
        ROOT / "outputs_50pct" / name,
        OUTPUTS / name,
        ROOT / "outputs" / name,
        ROOT / name,
    ):
        if candidate.is_file():
            return candidate
    return None


def resolve_asset_file(path_str: str) -> Path | None:
    if not path_str or ".." in path_str:
        return None
    try:
        p = Path(path_str).expanduser()
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        else:
            p = p.resolve()
    except (OSError, ValueError):
        return None
    if not p.is_file() or p.suffix.lower() != ".ply":
        return None
    return p


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
                self._json(200, {"version": 3, "activeSceneId": None, "scenes": []})
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "configVersion": 3})
            return
        if path == "/api/asset/file":
            qs = parse_qs(urlparse(self.path).query)
            path_str = unquote(qs.get("path", [""])[0])
            asset_path = resolve_asset_file(path_str)
            if not asset_path:
                self._json(404, {"error": f"asset not found: {path_str}"})
                return
            data = asset_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/asset/guess":
            qs = parse_qs(urlparse(self.path).query)
            asset_name = unquote(qs.get("asset", [""])[0])
            asset_path = guess_asset_path(asset_name)
            if not asset_path:
                self._json(404, {"error": f"asset not found: {asset_name}"})
                return
            self._json(200, {"path": str(asset_path).replace("\\", "/")})
            return
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/placements":
            data = self._read_json()
            if isinstance(data, list):
                payload = data
            elif isinstance(data, dict) and (
                data.get("version", 0) >= 3
                or data.get("version", 0) >= 2
                or isinstance(data.get("placements"), list)
                or isinstance(data.get("scenes"), list)
            ):
                payload = data
            else:
                self._json(400, {"error": "expected JSON list, v2 config, or v3 scenes store"})
                return
            try:
                PLACEMENTS.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError as e:
                self._json(500, {"error": f"cannot write placements.json: {e}"})
                return
            if isinstance(payload, list):
                count = len(payload)
                version = 1
            elif payload.get("version", 0) >= 3:
                count = len(payload.get("scenes", []))
                version = 3
            else:
                count = len(payload.get("placements", []))
                version = 2
            self._json(200, {"ok": True, "count": count, "configVersion": version})
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
    print(f"场景编辑器: http://{host}:{port}/placement_editor.html")
    print("  拖入 PLY 模型开始摆放")
    print("  Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
