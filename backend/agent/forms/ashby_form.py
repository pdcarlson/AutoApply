"""Fills Ashby application forms."""
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from agent.forms.base_form import AtsForm, PostingClosed
from agent.forms.dates import parse_date
from agent.forms.form_field import FormField
from agent.forms.greenhouse_form import choose_location, choose_option

# The job page loads its form from this endpoint, and the agent reads it the same way
API_URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting"
FORM_URL = "https://jobs.ashbyhq.com/{company}/{job_id}/application"
# Ashby turns away Python's default User-Agent, so the agent says who it is instead
USER_AGENT = "AutoApply/1.0 (job application assistant)"
QUERY = """
query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) {
  jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName,
             jobPostingId: $jobPostingId) {
    id title locationName
    applicationForm { sections { title fieldEntries {
      ... on FormFieldEntry { id field isRequired isHidden }
    } } }
  }
}"""

# Ashby field types the agent can fill. Others (scores, education history) are left for the
# person.
KINDS = {
    "String": "text",
    "Email": "text",
    "Phone": "text",
    "Number": "text",
    "Url": "text",
    "LongText": "textarea",
    "File": "file",
    "Boolean": "select",
    "ValueSelect": "select",
    "MultiValueSelect": "multi_select",
    "Location": "location",
    "Date": "date",
}
PROFILE_FIELDS = {
    "_systemfield_name": "full_name",
    "_systemfield_email": "email",
    "_systemfield_phone": "phone",
    "_systemfield_resume": "resume_path",
    "_systemfield_location": "location",
}
QUESTION_TITLE = ".ashby-application-form-question-title"
SUCCESS = ".ashby-application-form-success-container"
CONFIRMATION = re.compile(r"application was successfully submitted|thank(s| you) for applying",
                          re.IGNORECASE)
READY_WAIT_MS = 10000  # Ashby's page keeps a reCAPTCHA connection open, so don't wait forever


def fields_from_api(posting):
    """Turn an Ashby job posting's application form into FormFields."""
    fields = []
    for section in (posting.get("applicationForm") or {}).get("sections", []):
        for entry in section.get("fieldEntries", []):
            item = entry.get("field") or {}
            kind = KINDS.get(item.get("type"))
            if entry.get("isHidden") or item.get("isDeactivated") or kind is None:
                continue
            if item["type"] == "Boolean":
                options = ["Yes", "No"]
            else:
                options = [value["label"] for value in item.get("selectableValues") or []]
            path = item["path"]
            fields.append(FormField(
                key=path,
                label=item.get("title", "").strip(),
                kind=kind,
                required=bool(entry.get("isRequired")),
                options=options,
                profile_key=PROFILE_FIELDS.get(path, "phone" if item["type"] == "Phone" else ""),
            ))
    return fields


def fetch_posting(company, job_id):
    """Ask Ashby for one job posting and its application form."""
    body = json.dumps({
        "operationName": "ApiJobPosting",
        "variables": {"organizationHostedJobsPageName": company, "jobPostingId": job_id},
        "query": QUERY,
    }).encode()
    request = Request(API_URL, body, {"Content-Type": "application/json",
                                      "User-Agent": USER_AGENT})
    with urlopen(request, timeout=15) as response:
        data = json.load(response)
    if data.get("errors"):
        raise ValueError(f"Ashby didn't return the form: {data['errors'][0].get('message')}")
    posting = (data.get("data") or {}).get("jobPosting")
    if posting is None:
        raise PostingClosed("Ashby has no open posting at that link.")
    return posting


class AshbyForm(AtsForm):
    """An Ashby form. Its questions come from the same endpoint the job page uses."""

    def __init__(self, link, job_data=None, url=None):
        super().__init__(link)
        # Tests pass in a saved posting and a fake form instead of going online
        self.job_data = job_data
        self.url = url

    def form_url(self):
        """Return the posting's application page, keeping any tracking tags that were pasted."""
        if self.url:
            return self.url
        query = urlsplit(self.link.pasted).query if self.link.pasted else ""
        url = FORM_URL.format(company=self.link.company, job_id=self.link.job_id)
        return f"{url}?{query}" if query else url

    def read_fields(self):
        """Ask Ashby for the form's questions."""
        if self.job_data is None:
            self.job_data = fetch_posting(self.link.company, self.link.job_id)
        return fields_from_api(self.job_data)

    def posting(self):
        """Return the posting's title and location."""
        data = self.job_data or {}
        return {"company": "", "title": data.get("title") or "",
                "location": data.get("locationName") or ""}

    def wait_until_ready(self, page):
        """Wait for the questions, then for the page's scripts to settle."""
        page.locator(QUESTION_TITLE).first.wait_for(state="attached")
        try:
            page.wait_for_load_state("networkidle", timeout=READY_WAIT_MS)
        except PlaywrightTimeout:
            pass

    @staticmethod
    def entry(page, form_field):
        """The box around one question: its title label sits right inside it."""
        return page.locator(f'label[for="{form_field.key}"]').locator("xpath=..")

    def fill(self, page, form_field, value):
        """Type, pick or upload one answer."""
        if form_field.kind in ("text", "textarea", "file"):
            box = page.locator(f'[id="{form_field.key}"]')
            if form_field.kind == "file":
                box.set_input_files(value)
            else:
                box.fill(value)
            return
        entry = self.entry(page, form_field)
        if form_field.kind == "date":
            # A calendar box with no id. It reads typed dates month first; typed as YYYY-MM-DD
            # they're read as midnight UTC and land a day early.
            box = entry.locator("input")
            box.fill(parse_date(value).strftime("%m/%d/%Y"))
            box.press("Escape")  # close the calendar so it doesn't cover the next question
        elif form_field.kind == "location":
            # Like Greenhouse, it suggests places such as "Troy, New York, United States"
            box = entry.get_by_role("combobox")
            box.click()
            box.press_sequentially(value.split(",")[0], delay=50)
            choose_location(page, value)
        elif entry.get_by_role("button", name=value, exact=True).count():
            entry.get_by_role("button", name=value, exact=True).click()  # Yes / No questions
        elif entry.get_by_role("combobox").count():
            box = entry.get_by_role("combobox")  # long option lists are a type-to-search box
            box.click()
            box.fill(value)
            choose_option(page, value)
        else:
            self.check(entry, value)  # short option lists are radio buttons or checkboxes

    @staticmethod
    def check(entry, value):
        """Tick the radio button or checkbox labeled value, by clicking its label."""
        choice = entry.get_by_label(value, exact=True)
        if not choice.is_checked():
            entry.locator(f'label[for="{choice.get_attribute("id")}"]').click()

    def submit(self, page):
        """Press Submit Application."""
        page.get_by_role("button", name=re.compile("submit application", re.IGNORECASE)) \
            .first.click()

    def is_confirmed(self, page, timeout_ms=None):
        """Wait for Ashby's success message, up to timeout_ms (the page's default if None)."""
        try:
            page.locator(SUCCESS).or_(page.get_by_text(CONFIRMATION)).first \
                .wait_for(timeout=timeout_ms)
            return True
        except PlaywrightTimeout:
            return False

    def is_open(self, page):
        """Return True while the application form is still on the page."""
        return page.locator(QUESTION_TITLE).count() > 0 and page.locator(SUCCESS).count() == 0
