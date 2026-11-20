"""Presses Submit on a filled form and waits for the site's thank-you page."""
import time

from playwright.sync_api import Error as PlaywrightError

from agent.forms.base_form import AtsForm
from agent.forms.protected import ProtectedFieldDetector, handoff_reason
from agent.runner.run_result import ASKED_FOR_CODE, CONFIRMED, NOT_CONFIRMED, RunResult, RunStatus

CONFIRM_POLL_MS = 500  # how often to look for the thank-you page while waiting


class Submitter:
    """Sends one filled form and watches for the site to confirm it."""

    def __init__(self, form: AtsForm, detector: ProtectedFieldDetector, confirm_timeout_s: float):
        """Store the form to send, the protected-step detector and the confirmation wait."""
        self.form = form
        self.detector = detector
        self.confirm_timeout_s = confirm_timeout_s

    def send(self, page, result: RunResult, emit, should_abort=None) -> None:
        """Press Submit, then wait for the confirmation page. Sets result's status and reason.

        Stops waiting as soon as the site asks for a code it emailed: no confirmation can come
        until someone types it, and that can happen later (HeldForm.enter_code). A CAPTCHA the
        site shows after Submit is left for the applicant (result.protected).
        """
        emit("phase", name="submitting")
        self.form.submit(page)
        result.pressed = True
        emit("phase", name="confirming")

        def give_up():
            """Return True to stop waiting early."""
            return bool(should_abort and should_abort()) or self.form.asks_for_code(page)
        if self.wait_for_confirmation(page, give_up):
            result.end(RunStatus.SUBMITTED, CONFIRMED)
            return
        result.end(RunStatus.FAILED, NOT_CONFIRMED)
        if self.form.asks_for_code(page):
            result.asked_for_code = True
            result.reason = ASKED_FOR_CODE
        else:
            self._note_captcha(page, result)

    def wait_for_confirmation(self, page, should_abort=None) -> bool:
        """Look for the thank-you page until it shows up, the time runs out, or should_abort()."""
        deadline = time.monotonic() + self.confirm_timeout_s
        while True:
            left_ms = (deadline - time.monotonic()) * 1000
            if self.form.is_confirmed(page, timeout_ms=max(1, min(CONFIRM_POLL_MS, left_ms))):
                return True
            if time.monotonic() >= deadline or (should_abort and should_abort()):
                return False

    def _note_captcha(self, page, result: RunResult) -> None:
        """Record a CAPTCHA the site showed after Submit as the reason it isn't confirmed."""
        try:
            result.protected = self.detector.scan_captchas(page)
        except PlaywrightError:
            result.protected = []  # the window went away; the caller notices that itself
        if result.protected:
            result.reason = (f"{handoff_reason(result.protected)} The site showed one after "
                             "Submit, so the application isn't confirmed yet.")
