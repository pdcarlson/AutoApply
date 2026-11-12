"""Runs one application, which means reading the form, answering it, filling it and sending it."""
import time
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

CONFIRM_TIMEOUT_S = 15  # how long to wait for the site's thank-you page after Submit
CONFIRM_POLL_MS = 500  # how often to look for it meanwhile
NOT_CONFIRMED = "Pressed Submit but never saw a confirmation."


@dataclass
class RunResult:  # pylint: disable=too-many-instance-attributes
    """How a run ended."""

    status: str  # needs_input, ready, submitted, failed or cancelled
    reason: str = ""
    questions: list = field(default_factory=list)  # FormFields the applicant has to answer
    filled: list = field(default_factory=list)  # (label, value, source) for each filled field
    screenshot: str = ""  # the last screenshot taken
    # (FormField, FieldAnswer) for every field the agent has an answer for, set on every return
    answered: list = field(default_factory=list)
    filled_detail: list = field(default_factory=list)  # (label, value, source, confidence)
    filled_screenshot: str = ""  # taken after the last field is filled, before Submit
    held: "HeldForm | None" = None  # the still-open form, for a `ready` run with hold=True
    asked_for_code: bool = False  # no confirmation, and the site asked for an emailed code


class Cancelled(Exception):
    """Raised inside a run when should_stop() says to stop."""


class ApplyRun:  # pylint: disable=too-many-instance-attributes
    """Takes one form from link to submitted.

    on_event(kind, **data) hears about progress: "phase" (name: opening, filling, submitting or
    confirming), "field" (label) before each fill, and "filled" (label, value, source, confidence)
    after it. should_stop() is checked before each field; when it returns True the run ends
    with status "cancelled" and the browser is closed.

    hold=True (with submit=False) keeps the browser open when the fill ends `ready`: the result's
    `held` is a HeldForm that can press Submit later. Playwright objects belong to the thread
    that made them, so `held` must be used and closed from the thread that called run().
    After Submit, the run waits up to confirm_timeout_s seconds for the thank-you page.
    """

    def __init__(self, answerer, screenshot_dir, submit=False, show=False,  # pylint: disable=too-many-arguments,too-many-positional-arguments
                 on_event=None, should_stop=None, slow_mo=0, hold=False,
                 confirm_timeout_s=CONFIRM_TIMEOUT_S):
        self.answerer = answerer
        self.screenshot_dir = Path(screenshot_dir)
        self.submit = submit
        self.show = show
        self.on_event = on_event
        self.should_stop = should_stop
        self.slow_mo = slow_mo
        self.hold = hold
        self.confirm_timeout_s = confirm_timeout_s

    def emit(self, kind, **data):
        """Tell the caller what the run is doing, if it asked."""
        if self.on_event:
            self.on_event(kind, **data)

    def check_stop(self):
        """Stop the run if the caller asked to."""
        if self.should_stop and self.should_stop():
            raise Cancelled

    def run(self, form, shot_name=None):
        """Answer every field first, and only open the browser once nothing is missing."""
        try:
            fields = form.read_fields()
        except OSError as error:
            return RunResult("failed", f"Couldn't read the form's questions: {error}")

        answered, questions = [], []
        try:
            for form_field in fields:
                self.check_stop()
                answer = self.answerer.answer(form_field)
                if answer:
                    answered.append((form_field, answer))
                elif form_field.required:
                    questions.append(form_field)
        except Cancelled:
            return RunResult("cancelled", "Cancelled.", answered=answered)
        if questions:
            return RunResult("needs_input", f"{len(questions)} question(s) need your answer.",
                             questions=questions, answered=answered)

        # Upload the resume first, since some sites fill other fields from it
        in_fill_order = sorted(answered, key=lambda pair: pair[0].kind != "file")
        result = self.fill_and_send(form, in_fill_order,
                                    shot_name or f"{form.link.company}-{form.link.job_id}")
        result.answered = answered
        return result

    def fill_and_send(self, form, answered, shot_name):
        """Open the form, fill it, and submit it if allowed."""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        filled_shot = self.screenshot_dir / f"{shot_name}-filled.png"
        result_shot = self.screenshot_dir / f"{shot_name}-result.png"
        result = RunResult("")  # drive() sets the status
        page = None
        playwright = sync_playwright().start()
        try:
            self.emit("phase", name="opening")
            browser = playwright.chromium.launch(headless=not self.show, slow_mo=self.slow_mo)
            try:
                page = browser.new_page()
                page.set_default_timeout(15000)
                self.drive(page, form, answered, result, filled_shot)
            except Cancelled:
                return RunResult("cancelled", "Cancelled.", filled=result.filled,
                                 filled_detail=result.filled_detail,
                                 screenshot=result.screenshot,
                                 filled_screenshot=result.filled_screenshot)
            except PlaywrightError as error:
                result.status = "failed"
                result.reason = f"Something went wrong on the page: {error.message}"
            finally:
                if page is not None and result.status in ("submitted", "failed"):
                    take_screenshot(page, result_shot, result)
                if self.hold and result.status == "ready":
                    result.held = HeldForm(playwright, browser, page, form, result_shot, result,
                                           self.confirm_timeout_s)
                else:
                    close_quietly(browser.close)
        finally:
            if result.held is None:
                close_quietly(playwright.stop)
        return result

    def drive(self, page, form, answered, result, filled_shot):  # pylint: disable=too-many-arguments,too-many-positional-arguments
        """Fill every field on the open page, then submit it if allowed. Updates result."""
        page.goto(form.form_url())
        form.wait_until_ready(page)
        self.emit("phase", name="filling")
        for form_field, answer in answered:
            self.check_stop()
            self.emit("field", label=form_field.label)
            form.fill(page, form_field, answer.value)
            result.filled.append((form_field.label, answer.value, answer.source))
            result.filled_detail.append((form_field.label, answer.value, answer.source,
                                         answer.confidence))
            self.emit("filled", label=form_field.label, value=answer.value,
                      source=answer.source, confidence=answer.confidence)

        take_screenshot(page, filled_shot, result)
        result.filled_screenshot = result.screenshot
        if not self.submit:
            result.status = "ready"
            result.reason = "Filled in but not sent (SUBMIT_REAL_FORM is off)."
            return
        self.check_stop()
        send(page, form, result, self.emit, self.confirm_timeout_s)


class HeldForm:  # pylint: disable=too-many-instance-attributes
    """A filled form left open by ApplyRun(hold=True), waiting to be sent or closed.

    Use it only from the thread that ran the fill (Playwright's sync API is thread-bound).
    """

    def __init__(self, playwright, browser, page, form, result_shot, filled,  # pylint: disable=too-many-arguments,too-many-positional-arguments
                 confirm_timeout_s):
        self.playwright = playwright
        self.browser = browser
        self.page = page
        self.form = form
        self.result_shot = result_shot
        self.filled = filled  # the fill's RunResult
        self.confirm_timeout_s = confirm_timeout_s
        self.closed = False

    def usable(self):
        """True while the browser, the page and the filled form are all still there."""
        if self.closed:
            return False
        try:
            if self.page.is_closed() or not self.browser.is_connected():
                return False
            self.page.evaluate("1")  # raises if the page crashed
            return self.form.is_open(self.page)
        except PlaywrightError:
            return False

    def submit(self, on_event=None, should_stop=None, should_abort=None,
               confirm_timeout_s=None):
        """Press Submit on the filled page, wait for the confirmation, then close the browser.

        should_stop() is checked once before Submit (True: "cancelled", nothing pressed).
        should_abort() is checked while waiting for the confirmation, to give up early.
        """
        filled = self.filled
        result = RunResult("", filled=list(filled.filled),
                           filled_detail=list(filled.filled_detail),
                           screenshot=filled.filled_screenshot,
                           filled_screenshot=filled.filled_screenshot)
        timeout = self.confirm_timeout_s if confirm_timeout_s is None else confirm_timeout_s
        try:
            if should_stop and should_stop():
                result.status, result.reason = "cancelled", "Cancelled."
                return result
            send(self.page, self.form, result, on_event or (lambda kind, **data: None),
                 timeout, should_abort)
        except PlaywrightError as error:
            result.status = "failed"
            result.reason = f"Something went wrong on the page: {error.message}"
        finally:
            if result.status in ("submitted", "failed"):
                take_screenshot(self.page, self.result_shot, result)
            self.close()
        return result

    def close(self):
        """Close the browser. Safe to call more than once, and on a browser that's gone."""
        if self.closed:
            return
        self.closed = True
        close_quietly(self.browser.close)
        close_quietly(self.playwright.stop)


def send(page, form, result, emit, confirm_timeout_s, should_abort=None):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Press Submit, then wait for the confirmation page. Sets result's status and reason."""
    emit("phase", name="submitting")
    form.submit(page)
    emit("phase", name="confirming")
    if wait_for_confirmation(page, form, confirm_timeout_s, should_abort):
        result.status, result.reason = "submitted", "The site confirmed the application."
        return
    result.status, result.reason = "failed", NOT_CONFIRMED
    if form.asks_for_code(page):
        result.asked_for_code = True
        result.reason = ("The site asked for the verification code it emailed, and no "
                         f"confirmation came within {confirm_timeout_s:g} seconds.")


def wait_for_confirmation(page, form, timeout_s, should_abort=None):
    """Look for the thank-you page until it shows up or timeout_s runs out.

    Returns as soon as it's seen, so a person can type an emailed code meanwhile.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        left_ms = (deadline - time.monotonic()) * 1000
        if form.is_confirmed(page, timeout_ms=max(1, min(CONFIRM_POLL_MS, left_ms))):
            return True
        if time.monotonic() >= deadline or (should_abort and should_abort()):
            return False


def take_screenshot(page, path, result):
    """Save a full-page screenshot and record it as the run's latest one."""
    try:
        page.screenshot(path=path, full_page=True)
        result.screenshot = str(path)
    except PlaywrightError:
        pass


def close_quietly(close):
    """Run a close/stop call, ignoring a browser or driver that's already gone."""
    try:
        close()
    except Exception:  # pylint: disable=broad-except
        pass
