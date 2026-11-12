"""Runs one application, which means reading the form, answering it, filling it and sending it."""
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


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


class Cancelled(Exception):
    """Raised inside a run when should_stop() says to stop."""


class ApplyRun:  # pylint: disable=too-many-instance-attributes
    """Takes one form from link to submitted.

    on_event(kind, **data) hears about progress: "phase" (name: opening, filling, submitting or
    confirming), "field" (label) before each fill, and "filled" (label, value, source, confidence)
    after it. should_stop() is checked before each field; when it returns True the run ends
    with status "cancelled" and the browser is closed.
    """

    def __init__(self, answerer, screenshot_dir, submit=False, show=False,  # pylint: disable=too-many-arguments,too-many-positional-arguments
                 on_event=None, should_stop=None, slow_mo=0):
        self.answerer = answerer
        self.screenshot_dir = Path(screenshot_dir)
        self.submit = submit
        self.show = show
        self.on_event = on_event
        self.should_stop = should_stop
        self.slow_mo = slow_mo

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
        with sync_playwright() as playwright:
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
                browser.close()
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
        self.emit("phase", name="submitting")
        form.submit(page)
        self.emit("phase", name="confirming")
        if form.is_confirmed(page):
            result.status, result.reason = "submitted", "The site confirmed the application."
        else:
            result.status, result.reason = "failed", "Pressed Submit but never saw a confirmation."


def take_screenshot(page, path, result):
    """Save a full-page screenshot and record it as the run's latest one."""
    try:
        page.screenshot(path=path, full_page=True)
        result.screenshot = str(path)
    except PlaywrightError:
        pass
