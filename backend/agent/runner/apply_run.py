"""Runs one application, which means reading the form, answering it, filling it and sending it."""
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from agent.answers.answerer import Answerer
from agent.browser import LocalBrowser, page_address
from agent.forms.base_form import AtsForm
from agent.forms.form_field import FieldKind
from agent.forms.protected import ProtectedFieldDetector, handoff_reason, merge
from agent.runner.held_form import HeldForm
from agent.runner.page_helpers import close_quietly, take_screenshot
from agent.runner.run_result import (CANCELLED, CODE_REJECTED, FORM_GONE, NO_CODE_PROMPT,
                                     NOT_CONFIRMED, WINDOW_CLOSED, RunResult, RunStatus)
from agent.runner.submitter import Submitter

# Names other code imports from here, though they now live next door
__all__ = ["CODE_REJECTED", "FORM_GONE", "NO_CODE_PROMPT", "NOT_CONFIRMED", "WINDOW_CLOSED",
           "ApplyRun", "Cancelled", "HeldForm", "RunResult", "RunStatus"]

CONFIRM_TIMEOUT_S = 15  # how long to wait for the site's thank-you page after Submit
PAGE_TIMEOUT_MS = 15000
NOT_SENT = "Filled in but not sent (SUBMIT_REAL_FORM is off)."


class Cancelled(Exception):
    """Raised inside a run when should_stop() says to stop."""


class ApplyRun:  # pylint: disable=too-many-instance-attributes  # one setting per run option
    """Takes one form from link to submitted.

    on_event(kind, **data) hears "phase" (name), "browser" (page: a PageAddress), "field"
    (label) and "filled" (label, value, source, confidence); should_stop() ends the run as
    cancelled. hold=True keeps a `ready` or `handoff` form open as the result's `held`.
    """

    def __init__(  # pylint: disable=too-many-arguments  # independent options, all by keyword
            self, answerer: Answerer, screenshot_dir, *, submit: bool = False,
            show: bool = False, on_event=None, should_stop=None, slow_mo: int = 0,
            hold: bool = False, confirm_timeout_s: float = CONFIRM_TIMEOUT_S,
            detector: ProtectedFieldDetector | None = None, browser=None):
        """Set up a run with the answerer, the screenshot folder and the run's options."""
        self.answerer = answerer
        self.screenshot_dir = Path(screenshot_dir)
        self.submit = submit
        self.show = show
        self.on_event = on_event
        self.should_stop = should_stop
        self.slow_mo = slow_mo
        self.hold = hold
        self.confirm_timeout_s = confirm_timeout_s
        self.detector = detector or ProtectedFieldDetector()
        self.protected = []  # Handoffs for the questions run() left alone
        # Where the browser comes from (agent.browser); by default one is launched here
        self.browser = browser or LocalBrowser(show=show, slow_mo=slow_mo, expose=False)

    def _emit(self, kind: str, **data) -> None:
        """Tell the caller what the run is doing, if it asked."""
        if self.on_event:
            self.on_event(kind, **data)

    def _check_stop(self) -> None:
        """Stop the run if the caller asked to."""
        if self.should_stop and self.should_stop():
            raise Cancelled

    def run(self, form: AtsForm, shot_name: str | None = None) -> RunResult:
        """Answer every field first, and only open the browser once nothing is missing."""
        try:
            fields = form.read_fields()
        except OSError as error:
            return RunResult(RunStatus.FAILED, f"Couldn't read the form's questions: {error}")

        answered, questions = [], []
        try:
            self._plan_answers(fields, answered, questions)
        except Cancelled:
            return RunResult(RunStatus.CANCELLED, CANCELLED, answered=answered)
        if questions:
            return RunResult(RunStatus.NEEDS_INPUT,
                             f"{len(questions)} question(s) need your answer.",
                             questions=questions, answered=answered)

        # Upload the resume first, since some sites fill other fields from it
        in_fill_order = sorted(answered, key=lambda pair: pair[0].kind is not FieldKind.FILE)
        result = self.fill_and_send(form, in_fill_order,
                                    shot_name or f"{form.link.company}-{form.link.job_id}")
        result.answered = answered
        return result

    def _plan_answers(self, fields: list, answered: list, questions: list) -> None:
        """Sort each field into answered, questions for the applicant, or protected steps."""
        self.protected = []
        for form_field in fields:
            self._check_stop()
            # A protected field is never answered, and the applicant isn't asked for it
            # either, so its answer can't be saved
            handoff = self.detector.check_question(form_field)
            if handoff:
                merge(self.protected, [handoff])
                continue
            answer = self.answerer.answer(form_field)
            if answer:
                answered.append((form_field, answer))
            elif form_field.required:
                questions.append(form_field)

    def fill_and_send(self, form: AtsForm, answered: list, shot_name: str) -> RunResult:
        """Open the form, fill it, and submit it if allowed."""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        filled_shot = self.screenshot_dir / f"{shot_name}-filled.png"
        result_shot = self.screenshot_dir / f"{shot_name}-result.png"
        result = RunResult(RunStatus.PENDING, protected=list(self.protected))
        page = None
        playwright = sync_playwright().start()
        try:
            self._emit("phase", name="opening")
            browser, endpoint = self.browser.open(playwright)
            try:
                page = browser.new_page()
                if endpoint:
                    self._emit("browser", page=page_address(page, endpoint))
                page.set_default_timeout(PAGE_TIMEOUT_MS)
                self._drive(page, form, answered, result, filled_shot)
            except Cancelled:
                return RunResult(RunStatus.CANCELLED, CANCELLED, filled=result.filled,
                                 filled_detail=result.filled_detail,
                                 screenshot=result.screenshot,
                                 filled_screenshot=result.filled_screenshot)
            except PlaywrightError as error:
                result.end(RunStatus.FAILED, f"Something went wrong on the page: {error.message}")
            finally:
                if page is not None and result.status in (RunStatus.SUBMITTED, RunStatus.FAILED):
                    take_screenshot(page, result_shot, result)
                if self.hold and result.status in (RunStatus.READY, RunStatus.HANDOFF):
                    result.held = HeldForm(playwright, browser, page, form=form,
                                           result_shot=result_shot, filled=result,
                                           confirm_timeout_s=self.confirm_timeout_s,
                                           detector=self.detector)
                else:
                    close_quietly(browser.close)
        finally:
            if result.held is None:
                close_quietly(playwright.stop)
        return result

    def _drive(self, page, form: AtsForm, answered: list, result: RunResult,
               filled_shot: Path) -> None:
        """Fill every field on the open page, then submit it if allowed. Updates result."""
        page.goto(form.form_url())
        form.wait_until_ready(page)
        merge(result.protected, self.detector.scan_page(page))
        self._emit("phase", name="filling")
        for form_field, answer in answered:
            self._check_stop()
            if form.shows(page, form_field):
                self._fill_one(page, form, form_field, answer, result)

        take_screenshot(page, filled_shot, result)
        result.filled_screenshot = result.screenshot
        merge(result.protected, self.detector.scan_page(page))  # steps that showed up meanwhile
        if result.protected:
            result.end(RunStatus.HANDOFF, handoff_reason(result.protected))
            return
        if not self.submit:
            result.end(RunStatus.READY, NOT_SENT)
            return
        self._check_stop()
        Submitter(form, self.detector, self.confirm_timeout_s).send(page, result, self._emit)

    def _fill_one(self, page, form: AtsForm, form_field, answer, result: RunResult) -> None:
        """Fill one field and record what went in."""
        self._emit("field", label=form_field.label)
        value = form.fill(page, form_field, answer.value) or answer.value
        result.filled.append((form_field.label, value, answer.source))
        result.filled_detail.append((form_field.label, value, answer.source, answer.confidence))
        self._emit("filled", label=form_field.label, value=value,
                   source=answer.source, confidence=answer.confidence)
