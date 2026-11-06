"""Runs one application, which means reading the form, answering it, filling it and sending it."""
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


@dataclass
class RunResult:
    """How a run ended."""

    status: str  # needs_input, ready, submitted or failed
    reason: str = ""
    questions: list = field(default_factory=list)  # FormFields the applicant has to answer
    filled: list = field(default_factory=list)  # (label, value, source) for each filled field
    screenshot: str = ""


class ApplyRun:
    """Takes one form from link to submitted."""

    def __init__(self, answerer, screenshot_dir, submit=False, show=False):
        self.answerer = answerer
        self.screenshot_dir = Path(screenshot_dir)
        self.submit = submit
        self.show = show

    def run(self, form):
        """Answer every field first, and only open the browser once nothing is missing."""
        try:
            fields = form.read_fields()
        except OSError as error:
            return RunResult("failed", f"Couldn't read the form's questions: {error}")

        answered, questions = [], []
        for form_field in fields:
            answer = self.answerer.answer(form_field)
            if answer:
                answered.append((form_field, answer))
            elif form_field.required:
                questions.append(form_field)
        if questions:
            return RunResult("needs_input", f"{len(questions)} question(s) need your answer.",
                             questions=questions)

        # Upload the resume first, since some sites fill other fields from it
        answered.sort(key=lambda pair: pair[0].kind != "file")
        return self.fill_and_send(form, answered)

    def fill_and_send(self, form, answered):
        """Open the form, fill it, and submit it if allowed."""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        shot = self.screenshot_dir / f"{form.link.company}-{form.link.job_id}.png"
        filled = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not self.show)
            page = browser.new_page()
            page.set_default_timeout(15000)
            try:
                page.goto(form.form_url())
                form.wait_until_ready(page)
                for form_field, answer in answered:
                    form.fill(page, form_field, answer.value)
                    filled.append((form_field.label, answer.value, answer.source))

                if not self.submit:
                    status, reason = "ready", "Filled in but not sent (SUBMIT_REAL_FORM is off)."
                else:
                    form.submit(page)
                    if form.is_confirmed(page):
                        status, reason = "submitted", "The site confirmed the application."
                    else:
                        status, reason = "failed", "Pressed Submit but never saw a confirmation."
            except PlaywrightError as error:
                status, reason = "failed", f"Something went wrong on the page: {error.message}"

            page.screenshot(path=shot, full_page=True)
            browser.close()
        return RunResult(status, reason, filled=filled, screenshot=str(shot))
