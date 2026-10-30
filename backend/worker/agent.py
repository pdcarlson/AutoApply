"""The browser agent (US6). This is the spike version.

What works: open a fresh browser for one application, load the posting,
and save a screenshot of what it sees.

What doesn't yet: reading the fields and filling them. Until that's built
every application ends up in Needs you with a reason saying so.
"""
import os

from playwright.sync_api import sync_playwright

from app.config import settings
from features.protected_handoff.detector import ProtectedFieldDetector, needs_you_reason


class AgentResult:
    """What happened on one run. status is one of the strings in app.models."""

    def __init__(self, status: str, reason: str = "", screenshot_path: str = ""):
        self.status = status
        self.reason = reason
        self.screenshot_path = screenshot_path


def run_application(app_id: int, url: str) -> AgentResult:
    """Open the posting in a clean browser and (eventually) fill it out."""
    shots_dir = os.path.join(settings.upload_dir, "screenshots")
    os.makedirs(shots_dir, exist_ok=True)
    shot_path = os.path.join(shots_dir, f"application_{app_id}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # new context = empty cookies, so one company never sees another's (US6 notes)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, timeout=30_000)
            page.screenshot(path=shot_path, full_page=True)

            # US8: never type into CAPTCHA, password, login or SSN fields
            handoffs = ProtectedFieldDetector().scan_page(page)
            if handoffs:
                return AgentResult("needs_you", needs_you_reason(handoffs), shot_path)

            # TODO(US6): find each form field (label, type, required, options)
            # TODO(US9): look up an answer in the profile, then the answer bank via
            # features.answer_reuse.AnswerReuse(db, user_id).reuse(question)
            # TODO(US7): score confidence; under the user's threshold -> needs_you
            # US8: call ProtectedFieldDetector().check_field(field) before typing in each one
            # TODO(US6): attach resume, submit, wait for confirmation page
            # TODO(US12): screenshot the confirmation page as the record

            return AgentResult("needs_you",
                               "The agent can open this form but can't fill it in yet.",
                               shot_path)
        except Exception as err:  # pylint: disable=broad-except
            return AgentResult("failed", f"Couldn't load the posting: {err}")
        finally:
            context.close()
            browser.close()
