"""Browser end-to-end check: the real frontend and backend against the fake Greenhouse form.

Starts `python -m server` (backend/) and `npm run dev:api` (frontend/, no MSW mock) on a fresh
temp data dir, then drives http://localhost:5173 in headless Chromium through the whole demo:
sign in, upload the resume, check the profile, answer the common questions, confirm, paste the
fake link, Apply, answer the agent's two questions in the Inbox, Review, Submit, and find the job
with a loaded screenshot under Applications. A PNG of every step goes to <data dir>/e2e-shots/.

Only the local fake form is ever filled: FAKE_GREENHOUSE=true routes the fake link to
backend/agent/tests/fake_forms, and Claude is off (ANTHROPIC_API_KEY empty, USE_CLAUDE=false)
so the agent asks instead of guessing.

    cd backend
    .venv/Scripts/python.exe server/e2e/run_browser_e2e.py            # Submit on the fake form
    .venv/Scripts/python.exe server/e2e/run_browser_e2e.py --dry-run  # SUBMIT_REAL_FORM=false
    .venv/Scripts/python.exe server/e2e/run_browser_e2e.py --headed   # watch it

Exits 0 when every step passed, 1 otherwise. Ports 8080 and 5173 must be free.
"""
import argparse
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
FRONTEND = REPO / "frontend"
RESUME = BACKEND / "agent" / "applicant" / "example_resume.pdf"

API_PORT = 8080
WEB_PORT = 5173
API_HEALTH = f"http://127.0.0.1:{API_PORT}/api/health"
WEB_URL = f"http://localhost:{WEB_PORT}"

FAKE_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1001"
COMPANY = "Fake Company"
SPONSORSHIP = "Will you now or in the future require visa sponsorship to work in the United States?"
WHY_HERE = "Why do you want to work here?"
WHY_TEXT = "I like building tools that people use every day."

STEP_TIMEOUT_MS = 60_000  # an agent run (launch Chromium, fill the form) takes a few seconds


class Shots:  # pylint: disable=too-few-public-methods
    """Numbered PNGs of the page, one per step."""

    def __init__(self, page: Page, folder: Path):
        self.page = page
        self.folder = folder
        self.count = 0
        folder.mkdir(parents=True, exist_ok=True)

    def take(self, name: str) -> None:
        self.count += 1
        path = self.folder / f"{self.count:02d}-{name}.png"
        self.page.screenshot(path=str(path), full_page=True, animations="disabled")
        print(f"  step {self.count:02d} {name}: ok", flush=True)


def port_in_use(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def wait_for_http(url: str, proc: subprocess.Popen, what: str, timeout: float = 90.0) -> None:
    """Polls `url` until it answers 2xx. Fails early if the process died."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{what} exited with code {proc.returncode} before it was ready")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # local only
                if 200 <= response.status < 300:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{what} didn't answer {url} within {timeout:.0f}s")


def stop(proc: subprocess.Popen | None) -> None:
    """Stops a process and everything it started (npm starts node, which starts esbuild)."""
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)  # pylint: disable=no-member
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def stop_server(proc: subprocess.Popen | None) -> bool:
    """Asks the backend to shut down the way Ctrl+C does, so the lifespan stops the agent
    worker. Returns False (after force-stopping it) when it didn't exit by itself."""
    if proc is None or proc.poll() is not None:
        return True
    try:
        if sys.platform == "win32":
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)  # needs CREATE_NEW_PROCESS_GROUP
        else:
            os.killpg(proc.pid, signal.SIGINT)  # pylint: disable=no-member
        proc.wait(timeout=20)
        return True
    except (OSError, subprocess.TimeoutExpired):
        stop(proc)
        return False


def e2e_env(data_dir: Path, submit_real_form: bool) -> dict:
    env = dict(os.environ)
    env.update({
        "AUTOAPPLY_DATA_DIR": str(data_dir),
        "FAKE_GREENHOUSE": "true",
        "ANTHROPIC_API_KEY": "",  # set but empty: agent/.env doesn't override it
        "USE_CLAUDE": "false",
        "SEED_BANK_FROM_PROFILE": "false",
        "RESUME_PARSE_STEP_MS": "0",
        "SUBMIT_REAL_FORM": "true" if submit_real_form else "false",
        "AGENT_SHOW_BROWSER": "false",
        "PYTHONUNBUFFERED": "1",
        "BROWSER": "none",  # Vite: don't open a browser window
    })
    return env


def start_processes(data_dir: Path, env: dict):
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32"
             else {"start_new_session": True})
    # pylint: disable=consider-using-with
    server_log = open(logs / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen([sys.executable, "-m", "server"], cwd=BACKEND, env=env,
                              stdout=server_log, stderr=subprocess.STDOUT, **group)
    npm = shutil.which("npm") or "npm"
    vite_log = open(logs / "vite.log", "w", encoding="utf-8")
    vite = subprocess.Popen([npm, "run", "dev:api", "--", "--strictPort"], cwd=FRONTEND, env=env,
                            stdout=vite_log, stderr=subprocess.STDOUT, **group)
    return server, vite, (server_log, vite_log)


def ensure_node_modules() -> None:
    if (FRONTEND / "node_modules").is_dir():
        return
    print("frontend/node_modules is missing: running npm install", flush=True)
    npm = shutil.which("npm") or "npm"
    subprocess.run([npm, "install"], cwd=FRONTEND, check=True)


def job_row(page: Page):
    return page.locator("li[id^='job-']").filter(has_text=COMPANY)


def drive(page: Page, shots: Shots, submit_real_form: bool) -> None:  # pylint: disable=too-many-statements,too-many-locals
    """The demo, step by step. Raises on the first step that doesn't do what it should."""
    page.set_default_timeout(STEP_TIMEOUT_MS)
    expect.set_options(timeout=STEP_TIMEOUT_MS)

    # 1. Sign in.
    page.goto(WEB_URL + "/")
    page.get_by_role("button", name="Begin Onboarding").click()
    page.wait_for_url("**/setup/resume")
    expect(page.get_by_role("heading", name="Start with your resume")).to_be_visible()
    shots.take("signed-in")

    # 2. Upload the resume and wait for the parse.
    page.locator("#resume-file").set_input_files(str(RESUME))
    expect(page.get_by_text("Read example_resume.pdf")).to_be_visible()
    shots.take("resume-parsed")

    # 3. Check what we pulled.
    next_button = page.get_by_role("button", name="Check what we pulled")
    expect(next_button).to_be_enabled()
    next_button.click()
    page.wait_for_url("**/setup/profile")
    expect(page.get_by_label("Full name")).to_have_value("Jordan Rivera")
    expect(page.get_by_label("Email")).not_to_have_value("")
    shots.take("profile-review")

    # 4. Common questions.
    page.get_by_role("button", name="Looks right, continue").click()
    page.wait_for_url("**/setup/questions")
    authorized = page.get_by_role(
        "radiogroup", name="Are you legally authorized to work in the United States?")
    sponsorship = page.get_by_role(
        "radiogroup", name="Will you now or in the future need visa sponsorship?")
    authorized.get_by_role("radio", name="Yes").click()
    sponsorship.get_by_role("radio", name="No").click()
    expect(authorized.get_by_role("radio", name="Yes")).to_have_attribute("aria-checked", "true")
    expect(sponsorship.get_by_role("radio", name="No")).to_have_attribute("aria-checked", "true")
    shots.take("common-questions")

    # 5. Confirm.
    page.get_by_role("button", name="Confirm profile and finish").click()
    page.wait_for_url("**/inbox")
    expect(page.get_by_role("heading", name="Inbox")).to_be_visible()
    shots.take("inbox")

    # 6. Paste the fake link.
    page.locator("#paste-link").fill(FAKE_URL)
    page.get_by_role("button", name="Add job").click()
    row = job_row(page)
    expect(row).to_have_count(1)
    expect(row.get_by_role("checkbox", name=f"Select {COMPANY}")).to_be_checked()
    expect(row.get_by_text("New York, NY", exact=True)).to_be_visible()  # the Where column
    shots.take("job-added")

    # 7. Apply.
    page.get_by_role("button", name="Apply to 1").click()
    expect(row.get_by_text("Needs you", exact=True)).to_be_visible()
    shots.take("needs-you")

    # 8. First question: sponsorship. Pick "No", use it for every company.
    expand = row.get_by_role("button", name=f"Details for {COMPANY}")
    if expand.get_attribute("aria-expanded") != "true":
        expand.click()
    expect(row.get_by_text(SPONSORSHIP, exact=True)).to_be_visible()
    row.get_by_text("Or pick it yourself:").locator("xpath=..") \
        .get_by_role("button", name="No", exact=True).click()
    expect(row.get_by_text("I’ll enter")).to_be_visible()
    row.get_by_role("radio", name="Use for every company that asks").check()
    shots.take("sponsorship-picked")
    row.get_by_role("button", name="Use this answer").click()

    # 9. Second question: why here. Reply in words, keep it to this company.
    expect(row.get_by_text(WHY_HERE, exact=True)).to_be_visible()
    if expand.get_attribute("aria-expanded") != "true":
        expand.click()
    row.get_by_label("Your reply").fill(WHY_TEXT)
    row.get_by_role("button", name="Send").click()
    expect(row.locator("p", has_text=WHY_TEXT)).to_be_visible()
    row.get_by_role("radio", name=f"Only {COMPANY}").check()
    shots.take("why-here-replied")
    row.get_by_role("button", name="Use this answer").click()

    # 10. The agent fills the form and stops for review.
    toast = page.get_by_role("status").filter(
        has_text=f"{COMPANY} is filled and waiting for your review")
    expect(toast).to_be_visible()
    shots.take("ready-toast")

    # 11. Review.
    page.get_by_role("button", name="Review", exact=True).click()
    page.wait_for_url("**/applications?filter=ready")
    page.get_by_role("button", name="Review and submit").click()
    dialog = page.get_by_role("dialog", name=re.compile(COMPANY))
    expect(dialog.get_by_text("Nothing has been sent yet")).to_be_visible()
    for label in ("First Name", "Email", "Resume/CV", SPONSORSHIP, WHY_HERE):
        expect(dialog.get_by_text(label, exact=True).first).to_be_visible()
    expect(dialog.get_by_text(WHY_TEXT).first).to_be_visible()
    shots.take("review")

    # 12. Submit.
    dialog.get_by_role("button", name="Submit application").click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role("status").filter(has_text=f"Submitted to {COMPANY}")).to_be_visible()
    shots.take("submitted")

    # 13. Applications shows the job, with a screenshot that loads.
    page.get_by_role("navigation", name="Main").get_by_role("link", name="Applications").click()
    page.wait_for_url(re.compile(r"/applications(\?.*)?$"))
    filters = page.get_by_role("group", name="Filter by status")
    filters.get_by_role("button", name=re.compile("^All")).click()
    app_row = page.locator("li").filter(has_text=COMPANY).filter(
        has=page.get_by_role("button", name="View screenshot"))
    expect(app_row).to_have_count(1)
    expect(app_row.get_by_text("Submission confirmed" if submit_real_form else "Sent",
                               exact=True)).to_be_visible()
    shots.take("applications")
    app_row.get_by_role("button", name="View screenshot").click()
    image = page.get_by_role("img", name=f"The {COMPANY} application form as submitted")
    expect(image).to_be_visible()
    page.wait_for_function("img => img.complete && img.naturalWidth > 0",
                           arg=image.element_handle())
    width = image.evaluate("img => img.naturalWidth")
    assert width > 0, "the screenshot <img> didn't load"
    shots.take("screenshot-loaded")

    # 14. The application's details show how it was sent.
    page.get_by_role("dialog").get_by_role("button", name="Close").click()
    app_row.get_by_role("button", name="Details").click()
    drawer = page.get_by_role("dialog", name="Software Engineering Intern")
    expect(drawer.get_by_text("Timeline", exact=True)).to_be_visible()
    last_event = ("Confirmation page received" if submit_real_form
                  else "Not sent: SUBMIT_REAL_FORM is off")
    expect(drawer.get_by_text(re.compile(re.escape(last_event)))).to_be_visible()
    shots.take("application-details")
    drawer.get_by_role("button", name="Close").first.click()

    # 15. Both answers are in the Answer bank.
    page.get_by_role("navigation", name="Main").get_by_role("link", name="Answer bank").click()
    page.wait_for_url("**/answers")
    for question in (SPONSORSHIP, WHY_HERE):
        expect(page.locator("b", has_text=question).first).to_be_visible()
    shots.take("answer-bank")


def browse(shots_dir: Path, headed: bool, submit_real_form: bool) -> bool:
    """Runs `drive` in a fresh Chromium. Returns True when every step passed."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        try:
            page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
            page.on("pageerror", lambda error: print(f"  page error: {error}", flush=True))
            page.on("console", lambda msg: msg.type == "error" and print(
                f"  console error: {msg.text} {msg.location.get('url', '')}", flush=True))
            shots = Shots(page, shots_dir)
            try:
                drive(page, shots, submit_real_form)
                return True
            except Exception as error:  # pylint: disable=broad-exception-caught
                print(f"FAIL at step {shots.count + 1}: {error}", flush=True)
                try:
                    page.screenshot(path=str(shots_dir / f"{shots.count + 1:02d}-FAILED.png"),
                                    full_page=True)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
                return False
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="SUBMIT_REAL_FORM=false (default: true, against the fake form only)")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    parser.add_argument("--data-dir", type=Path,
                        help="use this (empty) data dir instead of a fresh temp one")
    args = parser.parse_args()
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
    ok = False
    try:
        server, vite, log_files = start_processes(data_dir, e2e_env(data_dir, submit_real_form))
        wait_for_http(API_HEALTH, server, "the backend (python -m server)")
        wait_for_http(WEB_URL + "/", vite, "the frontend (npm run dev:api)")
        print("Backend and frontend are up. Driving the browser.", flush=True)
        ok = browse(shots_dir, args.headed, submit_real_form)
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"FAIL: {error}", flush=True)
    finally:
        stop(vite)
        if not stop_server(server):
            print("FAIL: the backend didn't shut down cleanly; it was force-stopped", flush=True)
            ok = False
        for log in log_files:
            log.close()

    print(f"Screenshots: {shots_dir}\nLogs: {data_dir / 'logs'}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
