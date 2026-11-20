"""Fills Greenhouse application forms."""
import json
import re
from urllib.parse import urlencode
from urllib.request import urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from agent.forms.base_form import AtsForm
from agent.forms.form_field import FieldKind, FormField
from agent.forms.greenhouse_code import GreenhouseCodePrompt
from agent.forms.greenhouse_education import (EDUCATION_KEYS, education_config_from_page,
                                              education_fields)
from agent.forms.greenhouse_questions import compliance_keys, fields_from_api
from agent.forms.pickers import choose_location, choose_option, choose_school
from agent.jobs.job_link import JobLink

API_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}?questions=true"
# The Education section's dropdown choices; kind is "degrees" or "disciplines"
EDUCATION_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/education/{kind}"
# The embed page is just the form, and it stays on Greenhouse instead of
# redirecting to the company's own careers site like some job links do.
EMBED_URL = "https://job-boards.greenhouse.io/embed/job_app?for={company}&token={job_id}"
# How long to look for the form on the pasted link's page before using the embed page
FORM_WAIT_MS = 15000
API_TIMEOUT_S = 15
FORM = "#application-form"
CONFIRMATION = re.compile(r"thank you for applying|application (has been )?received", re.IGNORECASE)


class GreenhouseForm(AtsForm):
    """A Greenhouse form. Its questions come from Greenhouse's public Job Board API."""

    def __init__(self, link: JobLink, job_data: dict | None = None, url: str | None = None,
                 education_options: dict | None = None, education_config: dict | None = None):
        """Store the job link and any saved API data, and whether to read the Education setup."""
        super().__init__(link)
        # Tests pass in saved API data and a fake form instead of going online
        self.job_data = job_data
        self.url = url
        self.education_options = education_options
        self.education_config = education_config
        # Only read the config from the page when the API data is read too, so tests stay offline
        self.reads_education_config = job_data is None and education_config is None

    def embed_url(self) -> str:
        """Return Greenhouse's form-only page for this job."""
        return EMBED_URL.format(company=self.link.company, job_id=self.link.job_id)

    def form_url(self) -> str:
        """Return the link the user pasted, or the embed page if there isn't one."""
        return self.url or self.link.pasted or self.embed_url()

    def read_fields(self) -> list[FormField]:
        """Ask the Job Board API for the form's questions."""
        if self.job_data is None:
            url = API_URL.format(company=self.link.company, job_id=self.link.job_id)
            with urlopen(url, timeout=API_TIMEOUT_S) as response:
                self.job_data = json.load(response)
        if education_fields(self.job_data, {}):
            if self.education_options is None:
                self.education_options = self._read_education_options()
            if self.reads_education_config:
                self.reads_education_config = False
                self.education_config = self._read_education_config()
        return fields_from_api(self.job_data, self.education_options, self.education_config)

    def _read_education_config(self) -> dict | None:
        """Read which Education boxes the form shows and requires from its embed page, or None."""
        url = EMBED_URL.format(company=self.link.company, job_id=self.link.job_id)
        try:
            with urlopen(url, timeout=API_TIMEOUT_S) as response:
                html = response.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return None
        return education_config_from_page(html)

    def _read_education_options(self) -> dict:
        """Ask the Job Board API for the degree and discipline choices.

        A list the API doesn't give stays empty, and the box gets the profile's wording.
        """
        return {kind: self._read_education_list(kind) for kind in ("degrees", "disciplines")}

    def _read_education_list(self, kind: str) -> list[str]:
        """Read every page of one Education list ("degrees" or "disciplines"), or []."""
        items, page = [], 1
        try:
            while True:
                url = (EDUCATION_URL.format(company=self.link.company, kind=kind)
                       + "?" + urlencode({"page": page}))
                with urlopen(url, timeout=API_TIMEOUT_S) as response:
                    data = json.load(response)
                items += [item["text"] for item in data.get("items", [])]
                total = data.get("meta", {}).get("total_count", 0)
                if not data.get("items") or len(items) >= total:
                    return items
                page += 1
        except (OSError, ValueError, KeyError):
            return []

    def posting(self) -> dict:
        """Return the company, job title and location from the Job Board API."""
        data = self.job_data or {}
        return {"company": data.get("company_name") or "", "title": data.get("title") or "",
                "location": (data.get("location") or {}).get("name") or ""}

    def wait_until_ready(self, page) -> None:
        """Wait for the application form, opening the embed page if the link doesn't show it.

        Some posting links redirect to the company's own careers site, which shows the form
        inside a frame the agent can't fill.
        """
        form = page.locator(FORM)
        try:
            form.wait_for(state="attached", timeout=FORM_WAIT_MS)
        except PlaywrightTimeout:
            if self.url or page.url == self.embed_url():
                raise
            page.goto(self.embed_url())
            form.wait_for(state="attached")
        # The resume upload breaks if a file goes in before the page's scripts finish loading
        page.wait_for_load_state("networkidle")

    def shows(self, page, form_field: FormField) -> bool:
        """Return False for an Education or compliance box this form left out.

        The compliance section lists a race question, but the page only shows it after
        "No" to Hispanic/Latino, so it's often not there.
        """
        maybe = EDUCATION_KEYS | compliance_keys(self.job_data or {})
        if form_field.key not in maybe:
            return True
        return page.locator(f'[id="{form_field.key}"]').count() > 0

    def fill(self, page, form_field: FormField, value: str) -> str | None:
        """Type, pick or upload one answer, by the field's id."""
        box = page.locator(f'[id="{form_field.key}"]')
        if form_field.kind is FieldKind.SCHOOL:
            return choose_school(page, box, value)
        if form_field.kind is FieldKind.FILE:
            box.set_input_files(value)
        elif form_field.kind is FieldKind.MULTI_SELECT:
            self._fill_multi_select(page, box, form_field, value)
        elif form_field.kind is FieldKind.SELECT:
            self._fill_select(page, box, value)
        elif form_field.kind is FieldKind.LOCATION:
            # The city box only suggests places while you type, so type the city and
            # pick the suggestion that matches, like "Troy, New York, United States"
            box.click()
            box.press_sequentially(value.split(",")[0], delay=50)
            choose_location(page, value)
        else:
            box.fill(value)
        return None

    @staticmethod
    def _fill_multi_select(page, box, form_field: FormField, value: str) -> None:
        """Tick the checkbox for the value, or pick it from a dropdown."""
        group = page.locator(f'fieldset:has([name="{form_field.key}"])')
        if group.count():
            group.get_by_label(value, exact=True).check()
        else:
            # Some forms show a pick-several question as a dropdown, like Discord's
            # "Race or Ethnicity (optional)"
            box.click()
            choose_option(page, value)

    @staticmethod
    def _fill_select(page, box, value: str) -> None:
        """Pick the value in a plain <select> or in one of Greenhouse's own dropdowns."""
        if box.evaluate("element => element.tagName") == "SELECT":
            box.select_option(label=value)
            return
        # Greenhouse's own dropdowns only show their options after a click
        box.click()
        box.fill(value)
        choose_option(page, value)

    def submit(self, page) -> None:
        """Press Submit application."""
        page.get_by_role("button", name=re.compile("submit", re.IGNORECASE)).first.click()

    def is_confirmed(self, page, timeout_ms: float | None = None) -> bool:
        """Wait up to timeout_ms for Greenhouse's thank-you message (the page's default if None)."""
        try:
            page.get_by_text(CONFIRMATION).first.wait_for(timeout=timeout_ms)
            return True
        except PlaywrightTimeout:
            return "confirmation" in page.url

    def is_open(self, page) -> bool:
        """Return True while the application form is still on the page."""
        return page.locator(FORM).count() > 0

    def asks_for_code(self, page) -> bool:
        """Return True if Greenhouse is asking for the verification code it emailed."""
        return GreenhouseCodePrompt(page).is_showing()

    def enter_code(self, page, code: str) -> None:
        """Type the emailed code into Greenhouse's code boxes and send it."""
        GreenhouseCodePrompt(page).enter(code)

    def code_rejected(self, page) -> bool:
        """Return True if Greenhouse says the code was wrong or expired."""
        return GreenhouseCodePrompt(page).is_rejected()
