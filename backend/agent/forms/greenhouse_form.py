"""Fills Greenhouse application forms."""
import json
import re
from calendar import month_name
from urllib.parse import urlencode
from urllib.request import urlopen

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from agent.forms.base_form import AtsForm
from agent.forms.form_field import FormField

API_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}?questions=true"
# The Education section's dropdown choices; kind is "degrees" or "disciplines"
EDUCATION_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/education/{kind}"
# The embed page is just the form, and it stays on Greenhouse instead of
# redirecting to the company's own careers site like some job links do.
EMBED_URL = "https://job-boards.greenhouse.io/embed/job_app?for={company}&token={job_id}"
# How long to look for the form on the pasted link's page before using the embed page
FORM_WAIT_MS = 15000

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
# The Education section isn't in the API's question list. The API only says whether the form
# has one ("education_optional" or "education_required"), not which of these boxes it shows
# or requires, so all of them are read and the ones a form leaves out are skipped while
# filling. Each is (box id, label, kind, profile attribute, required when education_required).
# The required ones are those real forms were seen requiring (Duolingo requires all five).
EDUCATION = [
    ("school--0", "School", "school", "school", True),
    ("degree--0", "Degree", "select", "degree", True),
    ("discipline--0", "Discipline", "select", "major", True),
    ("start-month--0", "Education start date month", "select", "school_start_month", False),
    ("start-year--0", "Education start date year", "text", "school_start_year", False),
    ("end-month--0", "Education end date month", "select", "graduation_month", True),
    ("end-year--0", "Education end date year", "text", "graduation_year", True),
]
EDUCATION_KEYS = {key for key, *_ in EDUCATION}
# Compliance box id -> the profile's self-ID answer for it
SELF_ID_FIELDS = {
    "gender": "gender",
    "hispanic_ethnicity": "hispanic_latino",
    "race": "race",
    "veteran_status": "veteran",
    "disability_status": "disability",
}
# The Hispanic/Latino box the page shows above race, which the API leaves out
HISPANIC = ("hispanic_ethnicity", "Are you Hispanic/Latino?",
            ["Yes", "No", "Decline To Self Identify"])
MONTHS = list(month_name)[1:]
# What the school box offers for a school that isn't on Greenhouse's list
OTHER_SCHOOL = "Other"
# How long to wait for the school to show up in the box's search before picking Other
SCHOOL_WAIT_MS = 5000
# After Submit, Greenhouse sometimes emails a code: "A verification code was sent to ...
# Enter the 8-character code to confirm you're a human."
CODE_PROMPT = re.compile(r"verification code|enter the \d+-character code", re.IGNORECASE)


def fields_from_api(job, education_options=None):
    """Turn the Job Board API's question list into FormFields.

    education_options has the Education section's {"degrees": [...], "disciplines": [...]}.
    """
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
                options=[value["label"].strip() for value in item.get("values", [])],
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
    return (fields + education_fields(job, education_options or {})
            + demographic_fields(job) + compliance_fields(job))


def demographic_fields(job):
    """Return the questions in the API's demographic_questions section.

    Despite the name, forms use this section for questions like "Are you legally authorized
    to work in the United States?", and they can be required. They're shaped differently
    from the main questions: an id instead of a field name (the box on the page has that
    id), and answer_options instead of values.
    """
    fields = []
    for question in (job.get("demographic_questions") or {}).get("questions", []):
        kind = KINDS.get(question.get("type", ""))
        if kind is None:
            continue
        fields.append(FormField(
            key=str(question["id"]),
            label=question["label"].strip(),
            kind=kind,
            required=question.get("required", False),
            # Labels can have stray spaces, like "No " on SingleStore's sponsorship question
            options=[option["label"].strip() for option in question.get("answer_options", [])],
        ))
    return fields


def compliance_fields(job):
    """Return the EEOC questions (gender, race, veteran status, disability) in the API's
    compliance section. On the page each box's id is the field's name, like veteran_status.

    The page asks "Are you Hispanic/Latino?" before race and only shows race after "No". The
    API doesn't list that box, so it's added in front of race.
    """
    fields = []
    for section in job.get("compliance") or []:
        for question in section.get("questions", []):
            for item in question.get("fields", []):
                kind = KINDS.get(item["type"])
                if kind is None:
                    continue
                if item["name"] == "race":
                    key, label, options = HISPANIC
                    fields.append(FormField(key, label, "select", options=list(options),
                                            profile_key=SELF_ID_FIELDS[key]))
                fields.append(FormField(
                    key=item["name"],
                    # The API writes some labels run together, like "VeteranStatus"
                    label=re.sub(r"(?<=[a-z])(?=[A-Z])", " ", question["label"].strip()),
                    kind=kind,
                    required=question.get("required", False),
                    options=[value["label"].strip() for value in item.get("values", [])],
                    profile_key=SELF_ID_FIELDS.get(item["name"], ""),
                ))
    return fields


def compliance_keys(job):
    """The ids of the compliance boxes, some of which a page only shows after other answers."""
    return {form_field.key for form_field in compliance_fields(job)}


def education_fields(job, options):
    """Return the Education section's boxes, or nothing if the form doesn't have one."""
    setting = job.get("education", "")
    if setting not in ("education_optional", "education_required"):
        return []
    choices = {"degree--0": options.get("degrees", []),
               "discipline--0": options.get("disciplines", []),
               "start-month--0": MONTHS, "end-month--0": MONTHS}
    return [FormField(key, label, kind, required and setting == "education_required",
                      options=list(choices.get(key, [])), profile_key=attribute)
            for key, label, kind, attribute, required in EDUCATION]


def read_education_options(company):
    """Ask the Job Board API for the degree and discipline choices.

    If the API doesn't answer, the lists stay empty and the boxes get the profile's wording.
    """
    options = {}
    for kind in ("degrees", "disciplines"):
        items, page = [], 1
        try:
            while True:
                url = (EDUCATION_URL.format(company=company, kind=kind)
                       + "?" + urlencode({"page": page}))
                with urlopen(url, timeout=15) as response:
                    data = json.load(response)
                items += [item["text"] for item in data.get("items", [])]
                total = data.get("meta", {}).get("total_count", 0)
                if not data.get("items") or len(items) >= total:
                    break
                page += 1
        except (OSError, ValueError, KeyError):
            items = []
        options[kind] = items
    return options


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


US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def choose_location(page, value):
    """Click the city suggestion for a "City, State" value.

    Greenhouse suggests places like "Mechanicville, New York, United States", so a state
    written as "NY" is matched by its full name. Never picks a same-named city in another
    state: with no match it raises, so the run stops instead of sending a wrong location.
    """
    page.get_by_role("option").first.wait_for()
    city, _, state = (part.strip() for part in value.partition(","))
    states = {state.lower(), US_STATES.get(state.upper(), state).lower()} - {""}
    options = page.get_by_role("option")
    seen = []
    for index in range(options.count()):
        text = options.nth(index).inner_text()
        seen.append(text)
        parts = [part.strip().lower() for part in text.split(",")]
        if parts[0] == city.lower() and (not states or (len(parts) > 1 and parts[1] in states)):
            options.nth(index).click()
            return
    raise PlaywrightError(f'No location suggestion matches "{value}". Suggestions: {seen}')


def menu_option(page, text):
    """The open dropdown's option named exactly `text`, ignoring case and extra spaces."""
    words = r"\s+".join(re.escape(word) for word in text.split())
    return page.locator(".select__menu").get_by_role(
        "option", name=re.compile(f"^{words}$", re.IGNORECASE)).first


def choose_school(page, box, school):
    """Type the school and pick it from Greenhouse's list, or pick "Other" if it isn't there.

    The list comes from a search as you type, so this waits up to SCHOOL_WAIT_MS for the
    school to show up. Returns "Other" when it picked that, else None.
    """
    box.click()
    box.fill(school)
    try:
        menu_option(page, school).click(timeout=SCHOOL_WAIT_MS)
        return None
    except PlaywrightTimeout:
        pass
    box.fill(OTHER_SCHOOL)
    menu_option(page, OTHER_SCHOOL).click()
    return OTHER_SCHOOL


class GreenhouseForm(AtsForm):
    """A Greenhouse form. Its questions come from Greenhouse's public Job Board API."""

    def __init__(self, link, job_data=None, url=None, education_options=None):
        super().__init__(link)
        # Tests pass in saved API data and a fake form instead of going online
        self.job_data = job_data
        self.url = url
        self.education_options = education_options

    def embed_url(self):
        """Greenhouse's form-only page for this job."""
        return EMBED_URL.format(company=self.link.company, job_id=self.link.job_id)

    def form_url(self):
        """Return the link the user pasted, or the embed page if there isn't one."""
        return self.url or self.link.pasted or self.embed_url()

    def read_fields(self):
        """Ask the Job Board API for the form's questions."""
        if self.job_data is None:
            url = API_URL.format(company=self.link.company, job_id=self.link.job_id)
            with urlopen(url, timeout=15) as response:
                self.job_data = json.load(response)
        if self.education_options is None and education_fields(self.job_data, {}):
            self.education_options = read_education_options(self.link.company)
        return fields_from_api(self.job_data, self.education_options)

    def wait_until_ready(self, page):
        """Wait for the application form.

        Some posting links redirect to the company's own careers site, which shows the form
        inside a frame the agent can't fill. If the form isn't on the pasted link's page,
        open Greenhouse's form-only page for the same job instead.
        """
        form = page.locator("#application-form")
        try:
            form.wait_for(state="attached", timeout=FORM_WAIT_MS)
        except PlaywrightTimeout:
            if self.url or page.url == self.embed_url():
                raise
            page.goto(self.embed_url())
            form.wait_for(state="attached")
        # The resume upload breaks if a file goes in before the page's scripts finish loading
        page.wait_for_load_state("networkidle")

    def shows(self, page, form_field):
        """Education and compliance boxes vary by form, so skip the ones this form left out.

        The compliance section lists a race question, but the page only shows it after
        "No" to Hispanic/Latino, so it's often not there.
        """
        maybe = EDUCATION_KEYS | compliance_keys(self.job_data or {})
        if form_field.key not in maybe:
            return True
        return page.locator(f'[id="{form_field.key}"]').count() > 0

    def fill(self, page, form_field, value):
        """Type, pick or upload one answer, by the field's id."""
        box = page.locator(f'[id="{form_field.key}"]')
        if form_field.kind == "school":
            return choose_school(page, box, value)
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
            choose_location(page, value)
        else:
            box.fill(value)
        return None

    def submit(self, page):
        """Press Submit application."""
        page.get_by_role("button", name=re.compile("submit", re.IGNORECASE)).first.click()

    def is_confirmed(self, page, timeout_ms=None):
        """Wait for Greenhouse's thank-you message, up to timeout_ms (the page's default if None)."""
        try:
            page.get_by_text(CONFIRMATION).first.wait_for(timeout=timeout_ms)
            return True
        except PlaywrightTimeout:
            return "confirmation" in page.url

    def is_open(self, page):
        """Return True while the application form is still on the page."""
        return page.locator("#application-form").count() > 0

    def asks_for_code(self, page):
        """Return True if Greenhouse is asking for the verification code it emailed."""
        try:
            return page.get_by_text(CODE_PROMPT).first.is_visible()
        except PlaywrightError:
            return False
