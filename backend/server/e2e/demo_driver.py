"""Walks the web app through the whole demo in a browser, saving a picture of every step."""
import re
from pathlib import Path

from playwright.sync_api import Page, expect

from e2e_paths import RESUME, WEB_URL

FAKE_URL = "https://job-boards.greenhouse.io/fakecompany/jobs/1001"
COMPANY = "Fake Company"
SPONSORSHIP = "Will you now or in the future require visa sponsorship to work in the United States?"
WHY_HERE = "Why do you want to work here?"
WHY_TEXT = "I like building tools that people use every day."

STEP_TIMEOUT_MS = 60_000  # an agent run (launch Chromium, fill the form) takes a few seconds


class Shots:  # pylint: disable=too-few-public-methods  # it only takes pictures
    """Numbered PNGs of the page, one per step."""

    def __init__(self, page: Page, folder: Path):
        self.page = page
        self.folder = folder
        self.count = 0
        folder.mkdir(parents=True, exist_ok=True)

    def take(self, name: str) -> None:
        """Save a picture of the page for the step that just passed."""
        self.count += 1
        path = self.folder / f"{self.count:02d}-{name}.png"
        self.page.screenshot(path=str(path), full_page=True, animations="disabled")
        print(f"  step {self.count:02d} {name}: ok", flush=True)


class DemoDriver:
    """Walks the web app through the demo; each step raises if it doesn't do what it should."""

    def __init__(self, page: Page, shots: Shots, submit_real_form: bool):
        self.page = page
        self.shots = shots
        self.submit_real_form = submit_real_form

    def drive(self) -> None:
        """Run every step of the demo in order."""
        self.page.set_default_timeout(STEP_TIMEOUT_MS)
        expect.set_options(timeout=STEP_TIMEOUT_MS)
        self.set_up_profile()
        self.add_and_apply()
        self.answer_questions()
        self.review_and_submit()
        self.check_applications()
        self.check_answer_bank()

    def _job_row(self):
        """Return the Inbox row of the fake job."""
        return self.page.locator("li[id^='job-']").filter(has_text=COMPANY)

    def set_up_profile(self) -> None:
        """Sign in, upload the resume, check the profile, answer the common questions, confirm."""
        page = self.page
        page.goto(WEB_URL + "/")
        page.get_by_role("button", name="Begin Onboarding").click()
        page.wait_for_url("**/setup/resume")
        expect(page.get_by_role("heading", name="Start with your resume")).to_be_visible()
        self.shots.take("signed-in")

        page.locator("#resume-file").set_input_files(str(RESUME))
        expect(page.get_by_text("Read example_resume.pdf")).to_be_visible()
        self.shots.take("resume-parsed")

        next_button = page.get_by_role("button", name="Check what we pulled")
        expect(next_button).to_be_enabled()
        next_button.click()
        page.wait_for_url("**/setup/profile")
        expect(page.get_by_label("First name")).to_have_value("Jordan")
        expect(page.get_by_label("Middle name (optional)")).to_have_value("")
        expect(page.get_by_label("Last name")).to_have_value("Rivera")
        expect(page.get_by_label("Email")).not_to_have_value("")
        self.shots.take("profile-review")
        self._answer_common_questions()

        page.get_by_role("button", name="Confirm profile and finish").click()
        page.wait_for_url("**/inbox")
        expect(page.get_by_role("heading", name="Inbox")).to_be_visible()
        self.shots.take("inbox")

    def _answer_common_questions(self) -> None:
        """Say yes to work authorization and no to sponsorship."""
        page = self.page
        page.get_by_role("button", name="Looks right, continue").click()
        page.wait_for_url("**/setup/questions")
        authorized = page.get_by_role(
            "radiogroup", name="Are you legally authorized to work in the United States?")
        sponsorship = page.get_by_role(
            "radiogroup", name="Will you now or in the future need visa sponsorship?")
        authorized.get_by_role("radio", name="Yes").click()
        sponsorship.get_by_role("radio", name="No").click()
        expect(authorized.get_by_role("radio", name="Yes")).to_have_attribute("aria-checked",
                                                                            "true")
        expect(sponsorship.get_by_role("radio", name="No")).to_have_attribute("aria-checked",
                                                                            "true")
        self.shots.take("common-questions")

    def add_and_apply(self) -> None:
        """Paste the fake link, then press Apply."""
        page = self.page
        page.locator("#paste-link").fill(FAKE_URL)
        page.get_by_role("button", name="Add job").click()
        row = self._job_row()
        expect(row).to_have_count(1)
        expect(row.get_by_role("checkbox", name=f"Select {COMPANY}")).to_be_checked()
        expect(row.get_by_text("New York, NY", exact=True)).to_be_visible()  # the Where column
        self.shots.take("job-added")

        page.get_by_role("button", name="Apply to 1").click()
        expect(row.get_by_text("Needs you", exact=True)).to_be_visible()
        self.shots.take("needs-you")

    def answer_questions(self) -> None:
        """Pick "No" for sponsorship (every company), then reply to why-here (this company)."""
        row = self._job_row()
        expand = row.get_by_role("button", name=f"Details for {COMPANY}")
        if expand.get_attribute("aria-expanded") != "true":
            expand.click()
        expect(row.get_by_text(SPONSORSHIP, exact=True)).to_be_visible()
        row.get_by_text("Or pick it yourself:").locator("xpath=..") \
            .get_by_role("button", name="No", exact=True).click()
        expect(row.get_by_text("I’ll enter")).to_be_visible()
        row.get_by_role("radio", name="Use for every company that asks").check()
        self.shots.take("sponsorship-picked")
        row.get_by_role("button", name="Use this answer").click()

        expect(row.get_by_text(WHY_HERE, exact=True)).to_be_visible()
        if expand.get_attribute("aria-expanded") != "true":
            expand.click()
        row.get_by_label("Your reply").fill(WHY_TEXT)
        row.get_by_role("button", name="Send").click()
        expect(row.locator("p", has_text=WHY_TEXT)).to_be_visible()
        row.get_by_role("radio", name=f"Only {COMPANY}").check()
        self.shots.take("why-here-replied")
        row.get_by_role("button", name="Use this answer").click()

    def review_and_submit(self) -> None:
        """Wait for the filled form, review what was filled, and submit it."""
        page = self.page
        toast = page.get_by_role("status").filter(
            has_text=f"{COMPANY} is filled and waiting for your review")
        expect(toast).to_be_visible()
        self.shots.take("ready-toast")

        page.get_by_role("button", name="Review", exact=True).click()
        page.wait_for_url("**/applications?filter=ready")
        page.get_by_role("button", name="Review and submit").click()
        dialog = page.get_by_role("dialog", name=re.compile(COMPANY))
        expect(dialog.get_by_text("Nothing has been sent yet")).to_be_visible()
        for label in ("First Name", "Email", "Resume/CV", SPONSORSHIP, WHY_HERE):
            expect(dialog.get_by_text(label, exact=True).first).to_be_visible()
        expect(dialog.get_by_text(WHY_TEXT).first).to_be_visible()
        self.shots.take("review")

        dialog.get_by_role("button", name="Submit application").click()
        expect(dialog).to_be_hidden()
        expect(page.get_by_role("status").filter(has_text=f"Submitted to {COMPANY}")) \
            .to_be_visible()
        self.shots.take("submitted")

    def check_applications(self) -> None:
        """Find the job under Applications, with a screenshot that loads and its timeline."""
        page = self.page
        page.get_by_role("navigation", name="Main").get_by_role("link", name="Applications").click()
        page.wait_for_url(re.compile(r"/applications(\?.*)?$"))
        filters = page.get_by_role("group", name="Filter by status")
        filters.get_by_role("button", name=re.compile("^All")).click()
        app_row = page.locator("li").filter(has_text=COMPANY).filter(
            has=page.get_by_role("button", name="View screenshot"))
        expect(app_row).to_have_count(1)
        expect(app_row.get_by_text("Submission confirmed" if self.submit_real_form else "Sent",
                                   exact=True)).to_be_visible()
        self.shots.take("applications")
        self._check_screenshot(app_row)

        page.get_by_role("dialog").get_by_role("button", name="Close").click()
        app_row.get_by_role("button", name="Details").click()
        drawer = page.get_by_role("dialog", name="Software Engineering Intern")
        expect(drawer.get_by_text("Timeline", exact=True)).to_be_visible()
        last_event = ("Confirmation page received" if self.submit_real_form
                      else "Not sent: SUBMIT_REAL_FORM is off")
        expect(drawer.get_by_text(re.compile(re.escape(last_event)))).to_be_visible()
        self.shots.take("application-details")
        drawer.get_by_role("button", name="Close").first.click()

    def _check_screenshot(self, app_row) -> None:
        """Open the application's screenshot and check the image really loaded."""
        app_row.get_by_role("button", name="View screenshot").click()
        image = self.page.get_by_role("img", name=f"The {COMPANY} application form as submitted")
        expect(image).to_be_visible()
        self.page.wait_for_function("img => img.complete && img.naturalWidth > 0",
                                    arg=image.element_handle())
        width = image.evaluate("img => img.naturalWidth")
        assert width > 0, "the screenshot <img> didn't load"
        self.shots.take("screenshot-loaded")

    def check_answer_bank(self) -> None:
        """Both answers are in the Answer bank."""
        page = self.page
        page.get_by_role("navigation", name="Main").get_by_role("link", name="Answer bank").click()
        page.wait_for_url("**/answers")
        for question in (SPONSORSHIP, WHY_HERE):
            expect(page.locator("b", has_text=question).first).to_be_visible()
        self.shots.take("answer-bank")
