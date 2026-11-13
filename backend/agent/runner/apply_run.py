"""Runs one application, which means reading the form, answering it, filling it and sending it."""
import time
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

CONFIRM_TIMEOUT_S = 15  # how long to wait for the site's thank-you page after Submit
CONFIRM_POLL_MS = 500  # how often to look for it meanwhile
CODE_TIMEOUT_S = 20  # after the agent types an emailed code, how long to wait for the thank-you
CONFIRMED = "The site confirmed the application."
NOT_CONFIRMED = "Pressed Submit but never saw a confirmation."
ASKED_FOR_CODE = "The site asked for the verification code it emailed."
CODE_REJECTED = ("The site didn't take that code. Check that it's from the newest email the "
                 "site sent, and try again.")
NO_CODE_PROMPT = "The form window isn't asking for a code anymore, so nothing was typed."
WINDOW_CLOSED = "The form window was closed before the application was confirmed."
FORM_GONE = ("The form window doesn't show the form anymore, so the agent didn't press Submit. "
             "Finish it in that window, or close the window to have the form filled again.")


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
    asked_for_code: bool = False  # no confirmation, and the site is asking for an emailed code
    pressed: bool = False  # Submit was pressed (so the application may have gone out)
    window_closed: bool = False  # the page or browser went away (closed by the person)


class Cancelled(Exception):
    """Raised inside a run when should_stop() says to stop."""


class ApplyRun:  # pylint: disable=too-many-instance-attributes
    """Takes one form from link to submitted.

    on_event(kind, **data) hears about progress: "phase" (name: opening, filling, submitting or
    confirming), "field" (label) before each fill, and "filled" (label, value, source, confidence)
    after it. should_stop() is checked before each field; when it returns True the run ends
    with status "cancelled" and the browser is closed.

    hold=True (with submit=False) keeps the browser open when the fill ends `ready`: the result's
    `held` is a HeldForm that can press Submit later and stays open until its owner closes it.
    Playwright objects belong to the thread that made them, so `held` must be used and closed
    from the thread that called run().
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
            if not form.shows(page, form_field):
                continue
            self.emit("field", label=form_field.label)
            value = form.fill(page, form_field, answer.value) or answer.value
            result.filled.append((form_field.label, value, answer.source))
            result.filled_detail.append((form_field.label, value, answer.source,
                                         answer.confidence))
            self.emit("filled", label=form_field.label, value=value,
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
    """A filled form left open by ApplyRun(hold=True), waiting to be sent.

    Use it only from the thread that ran the fill (Playwright's sync API is thread-bound).
    Nothing here closes the window on its own: `submit` leaves it open whatever happens, and
    only the owner calls `close()` (after a confirmed submit whose screenshot was saved).
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

    def window_open(self):
        """True while the page is still open (False once the person closed it, or it crashed)."""
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

    def usable(self):
        """True while the window is open and still shows the filled form."""
        if not self.window_open():
            return False
        try:
            return self.form.is_open(self.page)
        except PlaywrightError:
            return False

    def confirmed(self, timeout_ms=250):
        """True if the page shows the site's thank-you page right now."""
        if self.closed:
            return False
        try:
            return bool(self.form.is_confirmed(self.page, timeout_ms=timeout_ms))
        except PlaywrightError:
            return False

    def save_screenshot(self, result=None):
        """Screenshot the window to result_shot. Returns True if the file was saved."""
        return take_screenshot(self.page, self.result_shot, result or RunResult(""))

    def submit(self, on_event=None, should_stop=None, should_abort=None,
               confirm_timeout_s=None):
        """Press Submit on the filled page and wait for the confirmation. Never closes anything.

        should_stop() is checked once before Submit (True: "cancelled", nothing pressed).
        should_abort() is checked while waiting for the confirmation, to give up early.
        A page that already shows the thank-you page counts as submitted without pressing; one
        that shows neither the form nor a confirmation is left alone ("failed", not pressed).
        After a press, the window is saved to result_shot (result.screenshot says if it was).
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
            if not self.form.is_open(self.page):
                if self.confirmed():
                    result.status, result.reason = "submitted", CONFIRMED
                else:
                    result.status, result.reason = "failed", FORM_GONE
            else:
                send(self.page, self.form, result, on_event or (lambda kind, **data: None),
                     timeout, should_abort)
        except PlaywrightError as error:
            result.status = "failed"
            result.reason = f"Something went wrong on the page: {error.message}"
            if not self.window_open():
                result.window_closed = True
                result.reason = WINDOW_CLOSED
        if result.status == "submitted" or (result.pressed and not result.window_closed):
            take_screenshot(self.page, self.result_shot, result)
        return result

    def enter_code(self, code, should_abort=None, confirm_timeout_s=CODE_TIMEOUT_S):
        """Type the code the site emailed into its prompt, send it, and wait for the confirmation.

        For a window whose Submit was pressed and that now asks for a code (`asks_for_code`).
        Never closes anything. Not confirmed: "failed", with `asked_for_code` True while the
        site still asks (a wrong or expired code), so the person can try another one.
        Confirmed: "submitted", and the window is saved to result_shot.
        """
        filled = self.filled
        result = RunResult("", filled=list(filled.filled),
                           filled_detail=list(filled.filled_detail),
                           screenshot=filled.filled_screenshot,
                           filled_screenshot=filled.filled_screenshot, pressed=True)
        try:
            if self.confirmed():
                result.status, result.reason = "submitted", CONFIRMED
            elif not self.form.asks_for_code(self.page):
                result.status, result.reason = "failed", NO_CODE_PROMPT
            else:
                # An error still showing from an earlier try says nothing about this code.
                old_error = self.form.code_rejected(self.page)
                self.form.enter_code(self.page, code)

                def give_up():
                    return bool(should_abort and should_abort()) or (
                        not old_error and self.form.code_rejected(self.page))
                if wait_for_confirmation(self.page, self.form, confirm_timeout_s, give_up):
                    result.status, result.reason = "submitted", CONFIRMED
                else:
                    result.status = "failed"
                    result.asked_for_code = self.form.asks_for_code(self.page)
                    result.reason = CODE_REJECTED if result.asked_for_code else NOT_CONFIRMED
        except PlaywrightError as error:
            result.status = "failed"
            result.reason = f"Something went wrong on the page: {error.message}"
            if not self.window_open():
                result.window_closed = True
                result.reason = WINDOW_CLOSED
        if not result.window_closed:
            take_screenshot(self.page, self.result_shot, result)
        return result

    def close(self):
        """Close the browser. Safe to call more than once, and on a browser that's gone."""
        if self.closed:
            return
        self.closed = True
        close_quietly(self.browser.close)
        close_quietly(self.playwright.stop)


def send(page, form, result, emit, confirm_timeout_s, should_abort=None):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Press Submit, then wait for the confirmation page. Sets result's status and reason.

    Stops waiting as soon as the site asks for a code it emailed: no confirmation can come
    until someone types it, and the agent can do that later (HeldForm.enter_code).
    """
    emit("phase", name="submitting")
    form.submit(page)
    result.pressed = True
    emit("phase", name="confirming")

    def give_up():
        return bool(should_abort and should_abort()) or form.asks_for_code(page)
    if wait_for_confirmation(page, form, confirm_timeout_s, give_up):
        result.status, result.reason = "submitted", CONFIRMED
        return
    result.status, result.reason = "failed", NOT_CONFIRMED
    if form.asks_for_code(page):
        result.asked_for_code = True
        result.reason = ASKED_FOR_CODE


def wait_for_confirmation(page, form, timeout_s, should_abort=None):
    """Look for the thank-you page until it shows up, timeout_s runs out, or should_abort()."""
    deadline = time.monotonic() + timeout_s
    while True:
        left_ms = (deadline - time.monotonic()) * 1000
        if form.is_confirmed(page, timeout_ms=max(1, min(CONFIRM_POLL_MS, left_ms))):
            return True
        if time.monotonic() >= deadline or (should_abort and should_abort()):
            return False


def take_screenshot(page, path, result):
    """Save a full-page screenshot and record it as the run's latest one. True if saved."""
    try:
        page.screenshot(path=path, full_page=True)
        result.screenshot = str(path)
        return True
    except PlaywrightError:
        return False


def close_quietly(close):
    """Run a close/stop call, ignoring a browser or driver that's already gone."""
    try:
        close()
    except Exception:  # pylint: disable=broad-except
        pass
