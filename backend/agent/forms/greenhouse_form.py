"""Fills Greenhouse application forms."""
import json
import re
from urllib.request import urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from agent.forms.base_form import AtsForm
from agent.forms.form_field import FormField

API_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}?questions=true"
# The embed page is just the form, and it stays on Greenhouse instead of
# redirecting to the company's own careers site like some job links do.
EMBED_URL = "https://job-boards.greenhouse.io/embed/job_app?for={company}&token={job_id}"

KINDS = {
    "input_text": "text",
    "textarea": "textarea",
    "input_file": "file",
    "multi_value_single_select": "select",
    "multi_value_multi_select": "multi_select",
}
PROFILE_FIELDS = {
    "first_name": "first_name",
    "last_name": "last_name",
    "preferred_name": "preferred_name",
    "email": "email",
    "phone": "phone",
    "resume": "resume_path",
}
CONFIRMATION = re.compile(r"thank you for applying|application (has been )?received", re.IGNORECASE)


def fields_from_api(job):
    """Turn the Job Board API's question list into FormFields."""
    fields = []
    for question in job.get("questions", []):
        items = question.get("fields", [])
        has_file = any(item["type"] == "input_file" for item in items)
        for item in items:
            # File questions also offer a "type it in instead" box, and the file is enough
            if has_file and item["type"] != "input_file":
                continue
            kind = KINDS.get(item["type"])
            if kind is None:
                continue
            fields.append(FormField(
                key=item["name"],
                label=question["label"].strip(),
                kind=kind,
                required=question.get("required", False),
                options=[value["label"] for value in item.get("values", [])],
                profile_key=PROFILE_FIELDS.get(item["name"], ""),
            ))
    # The city box is listed separately, and on the page its id is candidate-location
    for question in job.get("location_questions", []):
        if any(item["name"] == "location" for item in question.get("fields", [])):
            fields.append(FormField("candidate-location", question["label"], "location",
                                    question.get("required", False), profile_key="location"))
    # The phone box comes with a required country dropdown that the API doesn't list
    if any(form_field.key == "phone" for form_field in fields):
        fields.append(FormField("country", "Country", "select", True, profile_key="country"))
    return fields


def choose_option(page, value):
    """Click the open dropdown's option that matches the value exactly, or else starts with it."""
    page.get_by_role("option").first.wait_for()
    exact = page.get_by_role("option", name=value, exact=True)
    if exact.count():
        exact.first.click()
    else:
        # Some options add extra text, like "United States +1" in the phone country list
        starts = re.compile("^" + re.escape(value), re.IGNORECASE)
        page.get_by_role("option").filter(has_text=starts).first.click()


class GreenhouseForm(AtsForm):
    """A Greenhouse form. Its questions come from Greenhouse's public Job Board API."""

    def __init__(self, link, job_data=None, url=None):
        super().__init__(link)
        # Tests pass in saved API data and a fake form instead of going online
        self.job_data = job_data
        self.url = url

    def form_url(self):
        """Return the embed page for this job."""
        return self.url or EMBED_URL.format(company=self.link.company, job_id=self.link.job_id)

    def read_fields(self):
        """Ask the Job Board API for the form's questions."""
        if self.job_data is None:
            url = API_URL.format(company=self.link.company, job_id=self.link.job_id)
            with urlopen(url, timeout=15) as response:
                self.job_data = json.load(response)
        return fields_from_api(self.job_data)

    def wait_until_ready(self, page):
        """Wait for the application form."""
        page.locator("#application-form").wait_for(state="attached")
        # The resume upload breaks if a file goes in before the page's scripts finish loading
        page.wait_for_load_state("networkidle")

    def fill(self, page, form_field, value):
        """Type, pick or upload one answer, by the field's id."""
        box = page.locator(f'[id="{form_field.key}"]')
        if form_field.kind == "file":
            box.set_input_files(value)
        elif form_field.kind == "multi_select":
            group = page.locator(f'fieldset:has([name="{form_field.key}"])')
            group.get_by_label(value, exact=True).check()
        elif form_field.kind == "select" and box.evaluate("element => element.tagName") == "SELECT":
            box.select_option(label=value)
        elif form_field.kind == "select":
            # Greenhouse's own dropdowns only show their options after a click
            box.click()
            box.fill(value)
            choose_option(page, value)
        elif form_field.kind == "location":
            # The city box only suggests places while you type, so type the city and
            # pick the suggestion that matches, like "Troy, New York, United States"
            box.click()
            box.press_sequentially(value.split(",")[0], delay=50)
            choose_option(page, value)
        else:
            box.fill(value)

    def submit(self, page):
        """Press Submit application."""
        page.get_by_role("button", name=re.compile("submit", re.IGNORECASE)).first.click()

    def is_confirmed(self, page):
        """Wait for Greenhouse's thank-you message."""
        try:
            page.get_by_text(CONFIRMATION).first.wait_for()
            return True
        except PlaywrightTimeout:
            return "confirmation" in page.url
