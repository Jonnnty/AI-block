#!/usr/bin/env python3
"""Recover placements.json from Edge localStorage (UTF-16) log."""
from __future__ import annotations

import json
import re
from pathlib import Path

EDGE_LOG = Path(
    r"C:\Users\23094\AppData\Local\Microsoft\Edge\User Data\Default\Local Storage\leveldb\000182.log"
)
KEY = b"placement_editor_v3_scenes"
OUT_REPO = Path(__file__).resolve().parent / "placements.json"
OUT_DL = Path.home() / "Downloads" / "placements.json"


def extract_text(blob: bytes) -> str:
    idx = blob.find(KEY)
    if idx < 0:
        raise RuntimeError("placement_editor_v3_scenes not found in Edge log")
    tail = blob[idx + len(KEY) :]
    brace = tail.find(b"{\x00")
    if brace < 0:
        raise RuntimeError("UTF-16 JSON start not found")
    return tail[brace : brace + 2_000_000].decode("utf-16-le", errors="ignore")


def recover_store(text: str) -> dict:
    start = text.find('{"version":3')
    if start < 0:
        raise RuntimeError("v3 store header not found")
    body = text[start:]
    # Log record may append other origins; keep scene1 only (complete in blob).
    cut = body.find('},{"id":"scene-2"')
    if cut > 0:
        body = body[:cut] + "}]}"
    else:
        end = body.rfind('"}]}')
        if end > 0:
            body = body[: end + 4] + "}"
        else:
            raise RuntimeError("could not locate scene boundary")
    store = json.loads(body)
    if store.get("version", 0) < 3:
        raise RuntimeError("not a v3 store")
    return store


def fix_source_paths(store: dict) -> None:
    root = Path(r"D:\Downloads\outputs_50pct")
    for scene in store.get("scenes") or []:
        cfg = scene.get("config") or {}
        for p in cfg.get("placements") or []:
            rel = p.get("sourcePath") or ""
            name = p.get("asset") or Path(rel).name
            if name and (root / name).is_file():
                p["sourcePath"] = str(root / name).replace("\\", "/")


def main() -> None:
    text = extract_text(EDGE_LOG.read_bytes())
    store = recover_store(text)
    fix_source_paths(store)
    body = json.dumps(store, ensure_ascii=False, indent=2)
    OUT_REPO.write_text(body, encoding="utf-8")
    OUT_DL.write_text(body, encoding="utf-8")
    n = len(((store["scenes"][0].get("config") or {}).get("placements")) or [])
    print(f"[ok] scene1 restored with {n} models")
    print(f"[write] {OUT_REPO}")
    print(f"[write] {OUT_DL}")


if __name__ == "__main__":
    main()
