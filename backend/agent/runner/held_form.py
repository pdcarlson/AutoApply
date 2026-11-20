"""A filled form left open in its browser window, waiting to be sent."""
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

from agent.forms.base_form import AtsForm
from agent.forms.protected import ProtectedFieldDetector
from agent.runner.page_helpers import close_quietly, take_screenshot
from agent.runner.run_result import (CANCELLED, CODE_REJECTED, CONFIRMED, FORM_GONE,
                                     NO_CODE_PROMPT, NOT_CONFIRMED, WINDOW_CLOSED, RunResult,
                                     RunStatus)
from agent.runner.submitter import Submitter

CODE_TIMEOUT_S = 20  # after the agent types an emailed code, how long to wait for the thank-you


class HeldForm:  # pylint: disable=too-many-instance-attributes  # the open browser's whole state
    """A filled form left open by ApplyRun(hold=True), waiting to be sent.

    Use it only from the thread that ran the fill (Playwright's sync API is thread-bound).
    Nothing here closes the window on its own: only the owner calls `close()`.
    """

    def __init__(  # pylint: disable=too-many-arguments  # the parts of one open window
            self, playwright, browser, page, *, form: AtsForm, result_shot: Path,
            filled: RunResult, confirm_timeout_s: float,
            detector: ProtectedFieldDetector | None = None):
        """Store the open window and the filled form's result, ready for Submit."""
        self.playwright = playwright
        self.browser = browser
        self.page = page
        self.form = form
        self.result_shot = result_shot
        self.filled = filled  # the fill's RunResult
        self.confirm_timeout_s = confirm_timeout_s
        self.detector = detector or ProtectedFieldDetector()
        self.closed = False

    def window_open(self) -> bool:
        """Return True while the page is still open (not closed by the person, and not crashed)."""
        if self.closed:
            return False
        try:
            self.page.evaluate("1")  # also lets Playwright notice a closed page or browser
        except PlaywrightError:
            pass  # e.g. mid-navigation; only a closed page or browser counts as gone
        try:
            return not self.page.is_closed() and self.browser.is_connected()
        except PlaywrightError:
            return False

    def usable(self) -> bool:
        """Return True while the window is open and still shows the filled form."""
        if not self.window_open():
            return False
        try:
            return self.form.is_open(self.page)
        except PlaywrightError:
            return False

    def confirmed(self, timeout_ms: float = 250) -> bool:
        """Return True if the page shows the site's thank-you page right now."""
        if self.closed:
            return False
        try:
            return bool(self.form.is_confirmed(self.page, timeout_ms=timeout_ms))
        except PlaywrightError:
            return False

    def save_screenshot(self, result: RunResult | None = None) -> bool:
        """Screenshot the window to result_shot. Returns True if the file was saved."""
        return take_screenshot(self.page, self.result_shot,
                               result or RunResult(RunStatus.PENDING))

    def submit(self, on_event=None, should_stop=None, should_abort=None,
               confirm_timeout_s: float | None = None) -> RunResult:
        """Press Submit on the filled page and wait for the confirmation. Never closes anything.

        should_stop() is checked once before Submit; should_abort() while waiting, to give up
        early. A page already showing the thank-you page counts as submitted without a press,
        and one showing neither it nor the form is left alone.
        """
        result = self.filled.copy_filled()
        timeout = self.confirm_timeout_s if confirm_timeout_s is None else confirm_timeout_s
        try:
            if should_stop and should_stop():
                result.end(RunStatus.CANCELLED, CANCELLED)
                return result
            if not self.form.is_open(self.page):
                if self.confirmed():
                    result.end(RunStatus.SUBMITTED, CONFIRMED)
                else:
                    result.end(RunStatus.FAILED, FORM_GONE)
            else:
                Submitter(self.form, self.detector, timeout).send(
                    self.page, result, on_event or _ignore_event, should_abort)
        except PlaywrightError as error:
            self._note_page_error(result, error)
        if result.status is RunStatus.SUBMITTED or (result.pressed and not result.window_closed):
            take_screenshot(self.page, self.result_shot, result)
        return result

    def enter_code(self, code: str, should_abort=None,
                   confirm_timeout_s: float = CODE_TIMEOUT_S) -> RunResult:
        """Type the code the site emailed into its prompt, send it, and wait for the confirmation.

        Never closes anything. When not confirmed, `asked_for_code` stays True while the site
        still asks (a wrong or expired code), so the person can try another one.
        """
        result = self.filled.copy_filled()
        result.pressed = True
        try:
            if self.confirmed():
                result.end(RunStatus.SUBMITTED, CONFIRMED)
            elif not self.form.asks_for_code(self.page):
                result.end(RunStatus.FAILED, NO_CODE_PROMPT)
            else:
                self._send_code(code, result, should_abort, confirm_timeout_s)
        except PlaywrightError as error:
            self._note_page_error(result, error)
        if not result.window_closed:
            take_screenshot(self.page, self.result_shot, result)
        return result

    def _send_code(self, code: str, result: RunResult, should_abort, timeout_s: float) -> None:
        """Type the code, then wait for the thank-you page or the site's rejection."""
        # An error still showing from an earlier try says nothing about this code
        old_error = self.form.code_rejected(self.page)
        self.form.enter_code(self.page, code)

        def give_up():
            """Return True to stop waiting early."""
            return bool(should_abort and should_abort()) or (
                not old_error and self.form.code_rejected(self.page))
        if Submitter(self.form, self.detector, timeout_s).wait_for_confirmation(self.page, give_up):
            result.end(RunStatus.SUBMITTED, CONFIRMED)
            return
        result.asked_for_code = self.form.asks_for_code(self.page)
        result.end(RunStatus.FAILED, CODE_REJECTED if result.asked_for_code else NOT_CONFIRMED)

    def _note_page_error(self, result: RunResult, error: PlaywrightError) -> None:
        """Record a page error, or that the window was closed if that's what caused it."""
        result.end(RunStatus.FAILED, f"Something went wrong on the page: {error.message}")
        if not self.window_open():
            result.window_closed = True
            result.reason = WINDOW_CLOSED

    def close(self) -> None:
        """Close the browser. Safe to call more than once, and on a browser that's gone."""
        if self.closed:
            return
        self.closed = True
        close_quietly(self.browser.close)
        close_quietly(self.playwright.stop)


def _ignore_event(kind, **data):  # pylint: disable=unused-argument  # matches on_event's shape
    """Ignore one progress event."""
