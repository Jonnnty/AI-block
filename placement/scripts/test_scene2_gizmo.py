#!/usr/bin/env python3
"""scene2 autotest: load mannequin, verify gizmo buttons + move, screenshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8080/placement_editor.html?autotest=scene2"
OUT = Path(__file__).resolve().parent.parent / "editor_scene2_gizmo_test.png"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("pageerror", lambda err: print("PAGEERROR:", err))

        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        page.wait_for_selector("body[data-autotest-ready='1']", timeout=180_000)
        page.wait_for_timeout(800)

        result = json.loads(page.title())
        print(json.dumps(result, indent=2, ensure_ascii=False))

        page.locator("#viewMain").screenshot(path=str(OUT))
        print("screenshot:", OUT)

        browser.close()

    if not result.get("ok"):
        print("FAIL", result)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
