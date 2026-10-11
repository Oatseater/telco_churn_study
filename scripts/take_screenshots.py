"""Capture README screenshots of the running dashboard (optional dev tool).

Requires Playwright (not in requirements.txt, to keep the runtime minimal):
    pip install playwright && playwright install chromium
Usage (with the app running on port 8501):
    python scripts/take_screenshots.py [--out assets/screenshots] [--url http://localhost:8501]
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGES = {
    "overview": "",
    "retention": "retention",
    "segments": "segments",
    "calculator": "calculator",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--out", default="assets/screenshots")
    ap.add_argument("--full", action="store_true", help="full-page screenshots")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1250}, device_scale_factor=1)
        for name, path in PAGES.items():
            page.goto(f"{args.url}/{path}", wait_until="networkidle")
            page.wait_for_selector(".page-header", timeout=30000)
            page.wait_for_timeout(2500)  # let Plotly finish drawing
            exc = page.locator('[data-testid="stException"]').count()
            disclaimer = page.locator(".disclaimer").count()
            if exc or not disclaimer:
                errors.append(name)
            page.screenshot(path=str(out / f"{name}.png"), full_page=args.full)
            print(f"{name}: saved | exceptions: {exc} | disclaimer shown: {bool(disclaimer)}")
        browser.close()
    if errors:
        print(f"Problems on: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
