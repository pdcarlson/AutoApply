"""Browser end-to-end check: the real frontend and backend, driven through the fake form."""
import argparse
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

# Run by path, so these sibling modules are found next to this file.
from demo_driver import DemoDriver, Shots
from e2e_paths import API_HEALTH, API_PORT, WEB_PORT, WEB_URL
from processes import (e2e_env, ensure_node_modules, port_in_use, start_processes, stop,
                       stop_server, wait_for_http)

DESCRIPTION = """\
Starts `python -m server` (backend/) and `npm run dev:api` (frontend/, no MSW mock) on a fresh
temp data dir, then drives the web app in headless Chromium through the whole demo: sign in,
upload the resume, check the profile, answer the common questions, confirm, paste the fake
link, Apply, answer the agent's two questions, Review, Submit, and find the job with a loaded
screenshot under Applications. A PNG of every step goes to <data dir>/e2e-shots/.

Only the local fake form is ever filled (FAKE_GREENHOUSE=true), and Claude is off, so the agent
asks instead of guessing. Exits 0 when every step passed, 1 otherwise. Ports 8080 and 5173 must
be free. Run it from backend/: .venv/Scripts/python.exe server/e2e/run_browser_e2e.py
"""

def browse(shots_dir: Path, is_headed: bool, submit_real_form: bool) -> bool:
    """Drive the demo in a fresh Chromium; return True when every step passed."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not is_headed)
        try:
            page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
            page.on("pageerror", lambda error: print(f"  page error: {error}", flush=True))
            page.on("console", lambda msg: msg.type == "error" and print(
                f"  console error: {msg.text} {msg.location.get('url', '')}", flush=True))
            shots = Shots(page, shots_dir)
            try:
                DemoDriver(page, shots, submit_real_form).drive()
                return True
            except Exception as error:  # pylint: disable=broad-exception-caught  # any failed step
                print(f"FAIL at step {shots.count + 1}: {error}", flush=True)
                try:
                    page.screenshot(path=str(shots_dir / f"{shots.count + 1:02d}-FAILED.png"),
                                    full_page=True)
                except Exception:  # pylint: disable=broad-exception-caught  # best effort only
                    pass
                return False
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=DESCRIPTION,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="SUBMIT_REAL_FORM=false (default: true, against the fake form only)")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    parser.add_argument("--data-dir", type=Path,
                        help="use this (empty) data dir instead of a fresh temp one")
    return parser.parse_args()


def main() -> int:
    """Run the check; return the exit code."""
    args = _parse_args()
    submit_real_form = not args.dry_run
    for port in (API_PORT, WEB_PORT):
        if port_in_use(port):
            print(f"FAIL: port {port} is already in use. Stop whatever is running there first.")
            return 1
    ensure_node_modules()

    data_dir = (args.data_dir or Path(tempfile.mkdtemp(prefix="autoapply-e2e-"))).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    shots_dir = data_dir / "e2e-shots"
    print(f"Data dir: {data_dir}\nSUBMIT_REAL_FORM={str(submit_real_form).lower()}", flush=True)

    server = vite = None
    log_files = ()
    is_ok = False
    try:
        server, vite, log_files = start_processes(data_dir, e2e_env(data_dir, submit_real_form))
        wait_for_http(API_HEALTH, server, "the backend (python -m server)")
        wait_for_http(WEB_URL + "/", vite, "the frontend (npm run dev:api)")
        print("Backend and frontend are up. Driving the browser.", flush=True)
        is_ok = browse(shots_dir, args.headed, submit_real_form)
    except Exception as error:  # pylint: disable=broad-exception-caught  # reported as FAIL
        print(f"FAIL: {error}", flush=True)
    finally:
        stop(vite)
        if not stop_server(server):
            print("FAIL: the backend didn't shut down cleanly; it was force-stopped", flush=True)
            is_ok = False
        for log_file in log_files:
            log_file.close()

    print(f"Screenshots: {shots_dir}\nLogs: {data_dir / 'logs'}")
    print("PASS" if is_ok else "FAIL")
    return 0 if is_ok else 1


if __name__ == "__main__":
    sys.exit(main())
