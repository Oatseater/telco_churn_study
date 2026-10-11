"""Canary check: one command that proves the project still works end to end.

It copies the repo to a temporary folder without any generated files, then:
  1. runs the pipeline from scratch,
  2. runs the test suite,
  3. checks the committed README.md and memo.md match a fresh render,
  4. starts the dashboard and drives every page in a headless browser: clicks every
     dimension and comparison option, changes calculator inputs, and checks for
     errors, the disclaimer, and that the numbers on screen match reports/metrics.json.

Usage:
    python scripts/canary.py            # full check (browser step needs Playwright)
    python scripts/canary.py --no-browser

Playwright is a dev-only dependency: pip install playwright && playwright install chromium
Exit code is 0 only if every step passes.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)


def clean_copy(dest: Path) -> None:
    """Copy the repo without generated output (data/processed, reports) or caches."""
    def ignore(dirpath, names):
        rel = Path(dirpath).relative_to(ROOT)
        skip = {n for n in names if n in {"__pycache__", ".pytest_cache", ".git", "venv", ".venv"}}
        if rel == Path("."):
            skip |= {n for n in names if n == "reports"}
        if rel == Path("data"):
            skip |= {n for n in names if n == "processed"}
        return skip
    shutil.copytree(ROOT, dest, ignore=ignore)


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def strip_date(text: str) -> str:
    return re.sub(r"Generated \d{4}-\d{2}-\d{2}", "Generated <date>", text)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_healthy(url: str, timeout: float = 60) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def browser_checks(url: str, metrics: dict) -> None:
    from playwright.sync_api import sync_playwright

    o = metrics["overview"] if "overview" in metrics else metrics["overall"]
    rec = metrics["scenarios"]["recommended"]
    expected_overview = [f"{o['customers']:,.0f}", f"{o['churn_rate']:.1%}",
                         f"${o['annual_revenue_at_risk']:,.0f}"]
    expected_calc = [f"${rec['net_benefit']:,.0f}", f"{rec['break_even_save_rate']:.1%}"]

    def settle(page, ms=1500):
        """Wait until Streamlit has finished running and every chart has drawn, so
        controls are not still moving when we click them."""
        page.wait_for_timeout(300)
        try:
            page.wait_for_function(
                "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=15000)
            page.wait_for_function(
                "() => [...document.querySelectorAll('[data-testid=\"stPlotlyChart\"]')]"
                ".every(c => c.querySelector('.main-svg'))", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(ms)

    def choose(page, combobox, option: str) -> None:
        """Open a select and pick an option, retrying if the first click lands while
        the page is still settling."""
        for _ in range(3):
            combobox.click()
            target = page.get_by_role("option", name=option, exact=True)
            try:
                target.wait_for(state="visible", timeout=2500)
                target.click()
                return
            except Exception:
                page.keyboard.press("Escape")
                settle(page, 500)
        raise RuntimeError(f"could not open the select to choose {option!r}")

    def problems(page) -> list[str]:
        out = []
        if page.locator('[data-testid="stException"]').count():
            out.append("exception on page: " + page.locator('[data-testid="stException"]').first.inner_text()[:200])
        if not page.get_by_text("Public dataset. Analysis illustrates method", exact=False).count():
            out.append("disclaimer missing")
        return out

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        console_errors: list[str] = []
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        # Overview
        page.goto(url + "/", wait_until="networkidle")
        page.wait_for_selector("h1", timeout=30000)
        settle(page)
        txt = page.inner_text("body")
        missing = [v for v in expected_overview if v not in txt]
        record("Overview loads and KPIs match metrics.json", not problems(page) and not missing,
               "; ".join(problems(page) + [f"not on screen: {missing}"] * bool(missing)))
        group = page.locator('[data-testid="stButtonGroup"]').first
        bad = []
        if group.count():
            options = [b.inner_text().strip() for b in group.locator("button").all()]
            for opt in options:
                group.get_by_text(opt, exact=True).click()
                settle(page, 900)
                bad += [f"{opt}: {x}" for x in problems(page)]
            record(f"Overview: all {len(options)} dimension views render", not bad, "; ".join(bad))
        else:
            record("Overview: dimension selector present", False, "no button group found")

        # Retention
        page.goto(url + "/retention", wait_until="networkidle")
        page.wait_for_selector("h1", timeout=30000)
        settle(page)
        record("Retention loads", not problems(page), "; ".join(problems(page)))
        bad = []
        compare = page.locator('[data-testid="stSelectbox"] [role="combobox"]').first
        for opt in ["Internet service", "Payment type", "Segment", "Contract"]:
            choose(page, compare, opt)
            settle(page, 900)
            bad += [f"compare by {opt}: {x}" for x in problems(page)]
        ms = page.locator('[data-testid="stMultiSelect"]')
        if ms.count() >= 2:
            ms.nth(1).click()
            page.get_by_role("option", name="Fiber optic", exact=True).click()
            page.keyboard.press("Escape")
            settle(page, 900)
            bad += [f"filter fiber: {x}" for x in problems(page)]
        record("Retention: every comparison and a filter render", not bad, "; ".join(bad))

        # Segments
        page.goto(url + "/segments", wait_until="networkidle")
        page.wait_for_selector("h1", timeout=30000)
        settle(page)
        txt = page.inner_text("body")
        seg_missing = [s["segment"] for s in metrics["segments"] if s["segment"] not in txt]
        record("Segments loads with all segments listed", not problems(page) and not seg_missing,
               "; ".join(problems(page) + [f"missing: {seg_missing}"] * bool(seg_missing)))

        # Calculator
        page.goto(url + "/calculator", wait_until="networkidle")
        page.wait_for_selector("h1", timeout=30000)
        settle(page)
        txt = page.inner_text("body")
        missing = [v for v in expected_calc if v not in txt]
        record("Calculator loads and default scenario matches metrics.json",
               not problems(page) and not missing,
               "; ".join(problems(page) + [f"not on screen: {missing}"] * bool(missing)))
        bad = []
        sel = page.locator('[data-testid="stSelectbox"] [role="combobox"]').first
        for s in metrics["segments"]:
            choose(page, sel, s["segment"])
            settle(page, 700)
            bad += [f"{s['segment']}: {x}" for x in problems(page)]
        cb = page.locator('[data-testid="stCheckbox"]').first
        if cb.count():
            cb.click()
            settle(page, 700)
            bad += [f"month-to-month toggle: {x}" for x in problems(page)]
        slider = page.locator('[data-testid="stSlider"] [role="slider"]').first
        if slider.count():
            slider.focus()
            for _ in range(10):
                page.keyboard.press("ArrowRight")
            settle(page, 700)
            bad += [f"slider moved: {x}" for x in problems(page)]
        record("Calculator: every segment, toggle and slider render", not bad, "; ".join(bad))

        record("No JavaScript errors in the browser", not console_errors, "; ".join(console_errors[:3]))
        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the temporary copy for inspection")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="churn-canary-"))
    work = tmp / "repo"
    print(f"Canary check in a clean copy: {work}\n")
    server = None
    try:
        clean_copy(work)
        has_generated = (work / "data" / "processed").exists() or (work / "reports").exists()
        record("Clean copy has no generated files", not has_generated)

        r = run([sys.executable, "run_pipeline.py"], work)
        record("Pipeline runs from scratch", r.returncode == 0,
               "" if r.returncode == 0 else (r.stderr or r.stdout)[-400:])
        if r.returncode != 0:
            return finish(tmp, args.keep)

        r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        record("Test suite passes", r.returncode == 0, last if r.returncode == 0 else r.stdout[-800:])

        for name in ("README.md", "memo.md"):
            same = strip_date((work / name).read_text()) == strip_date((ROOT / name).read_text())
            record(f"Committed {name} matches a fresh render", same,
                   "" if same else "re-run python run_pipeline.py and commit the result")

        if args.no_browser:
            record("Browser checks", True, "skipped (--no-browser)")
            return finish(tmp, args.keep)
        try:
            import playwright  # noqa: F401
        except ImportError:
            record("Browser checks", False, "Playwright not installed (pip install playwright)")
            return finish(tmp, args.keep)

        port = free_port()
        url = f"http://127.0.0.1:{port}"
        log = open(tmp / "streamlit.log", "w")
        server = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
             "--server.port", str(port), "--browser.gatherUsageStats", "false"],
            cwd=work, stdout=log, stderr=subprocess.STDOUT)
        ok = wait_healthy(url)
        record("Dashboard server starts", ok)
        if ok:
            metrics = json.loads((work / "reports" / "metrics.json").read_text())
            browser_checks(url, metrics)
            log.flush()
            server_log = (tmp / "streamlit.log").read_text()
            tb = "Traceback" in server_log
            record("No server-side tracebacks", not tb, server_log[-400:] if tb else "")
    finally:
        if server:
            server.terminate()
            try:
                server.wait(10)
            except subprocess.TimeoutExpired:
                server.kill()
    return finish(tmp, args.keep)


def finish(tmp: Path, keep: bool) -> int:
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed.")
    if failed:
        print("FAILED: " + ", ".join(r[0] for r in failed))
    if keep:
        print(f"Kept: {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
