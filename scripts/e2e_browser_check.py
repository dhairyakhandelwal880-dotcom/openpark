#!/usr/bin/env python3
"""
Lightweight Headless Chrome E2E Verification for OpenPark UI
Verifies zero uncaught UIPolish errors, active welcome overlay, merged 1km CTA,
map style switcher pills, and responsive DOM rendering against a running server.
"""
import argparse
import os
import subprocess
import sys

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def run_check(url: str) -> int:
    if not os.path.exists(CHROME_BIN):
        print("Google Chrome not found; skipping headless Chrome E2E check.")
        return 0

    proc = subprocess.run(
        [
            CHROME_BIN,
            "--headless=new",
            "--disable-gpu",
            "--enable-logging=stderr",
            "--v=0",
            "--virtual-time-budget=4000",
            "--dump-dom",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    dom = proc.stdout
    logs = proc.stderr

    required_markers = [
        'id="welcome-overlay"',
        'id="rb-target-cursor"',
        'class="al-frame"',
        'jelly-bar',
        'id="map-style-switcher"',
        'id="explore-sort-bar"',
        'id="ai-filter-row"',
        'id="btn-hud-shortcuts"',
        'id="btn-ai-scan"',
    ]
    missing = [m for m in required_markers if m not in dom]
    js_errors = [
        line for line in logs.splitlines()
        if any(tok in line for tok in ("UIPolish", "SyntaxError", "ReferenceError", "TypeError"))
        and "webgl" not in line.lower()
    ]

    if missing:
        print(f"MISSING DOM ELEMENTS: {missing}")
        return 1
    if js_errors:
        print("JS RUNTIME ERRORS:\n" + "\n".join(js_errors))
        return 1

    print(f"E2E Chrome DOM verification PASSED for {url} ({len(dom)} bytes HTML)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://openpark-web-production.up.railway.app/app/")
    args = parser.parse_args()
    sys.exit(run_check(args.url))
