"""Fills Lever application forms."""
import re
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from agent.forms.base_form import AtsForm
from agent.forms.form_field import FormField
from agent.forms.greenhouse_form import STATE_CODES, split_place

APPLY_URL = "https://jobs.lever.co/{company}/{job_id}/apply"
# Lever has no public API for a form's questions, so they're read from the apply page itself
USER_AGENT = "Mozilla/5.0 (compatible; AutoApply)"

PROFILE_FIELDS = {
    "resume": "resume_path",
    "name": "full_name",
    "email": "email",
    "phone": "phone",
    "location": "location",
    "org": "current_company",
    "urls[LinkedIn]": "linkedin",
    "urls[GitHub]": "github",
    "urls[Portfolio]": "website",
}
# Optional extras the agent leaves alone: demographic surveys and the pronoun checkboxes
SKIPPED = re.compile(r"^(eeo\[|pronouns$)")
CONFIRMATION = re.compile(r"application submitted|thanks for applying", re.IGNORECASE)
# What Lever shows, above the form again, when its hCaptcha turns an application away
BLOCKED = re.compile(r"error verifying your application", re.IGNORECASE)
QUIET_WAIT_MS = 5000  # how long to wait for the network to go quiet before filling anyway
RESUME_WAIT_MS = 30000  # Lever reads the resume after it's attached, which can take a while


class ApplyPage(HTMLParser):  # pylint: disable=too-many-instance-attributes
    """Reads a Lever apply page: the job's title and location, and every question on the form.

    Each question is a dict with its label, whether it's marked required, and its controls
    (name, type, required and, for dropdowns, the options).
    """

    def __init__(self):
        super().__init__()
        self.title = ""
        self.location = ""
        self.questions = []
        self.question = None  # the <li class="application-question"> being read
        self.inner_items = 0  # <li>s open inside it (each radio button and checkbox sits in one)
        self.capture = ""  # which text is being collected: title, location, label or option
        self.depth = 0  # how deep inside the element being captured
        self.skip = 0  # inside the required-mark <span>, whose star isn't part of the label

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if self.capture in ("label", "location"):
            self.depth += tag not in ("input", "br", "img")
            if "required" in classes and self.question is not None:
                self.question["required"] = True
                self.skip = self.depth
            return
        if tag == "title":
            self.capture = "title"
        elif tag == "li" and "application-question" in classes:
            self.question = {"label": "", "required": False, "controls": []}
            self.questions.append(self.question)
        elif "posting-category" in classes and "location" in classes and not self.location:
            self.capture, self.depth = "location", 1
        elif self.question is None:
            return
        elif tag == "li":
            self.inner_items += 1
        elif "application-label" in classes:
            self.capture, self.depth = "label", 1
        elif tag in ("input", "textarea", "select") and attrs.get("type") != "hidden":
            self.question["controls"].append({
                "name": attrs.get("name") or "", "type": attrs.get("type") or tag,
                "value": attrs.get("value") or "", "required": "required" in attrs,
                "options": []})
        elif tag == "option" and attrs.get("value") and self.question["controls"]:
            self.capture = "option"
            self.question["controls"][-1]["options"].append("")

    def handle_endtag(self, tag):
        if self.capture in ("label", "location"):
            if self.skip == self.depth:
                self.skip = 0
            self.depth -= 1
            if self.depth == 0:
                self.capture = ""
        elif self.capture in ("title", "option") and tag in ("title", "option", "select"):
            self.capture = ""
        elif tag == "li" and self.inner_items:
            self.inner_items -= 1
        elif tag == "li":
            self.question = None

    def handle_data(self, data):
        if self.capture == "title":
            self.title += data
        elif self.capture == "location":
            self.location += data
        elif self.capture == "label" and not self.skip:
            self.question["label"] += data
        elif self.capture == "option":
            self.question["controls"][-1]["options"][-1] += data


def parse_page(html):
    """Turn a Lever apply page into job data: company_name, title, location and fields.

    The keys match what Greenhouse's API gives, and each field is a FormField as a dict, so the
    result can be saved and passed back in as job_data.
    """
    page = ApplyPage()
    page.feed(html)
    company, _, title = " ".join(page.title.split()).partition(" - ")
    fields = []
    for question in page.questions:
        form_field = field_from_question(question)
        if form_field:
            fields.append(vars(form_field))
    return {"company_name": company, "title": title,
            "location": {"name": " ".join(page.location.split())}, "fields": fields}


def field_from_question(question):
    """Return the FormField for one question on the page, or None for ones the agent skips."""
    controls = [control for control in question["controls"] if control["name"]]
    if not controls or SKIPPED.match(controls[0]["name"]):
        return None
    first = controls[0]
    if first["type"] == "file":
        kind, options = "file", []
    elif first["type"] == "textarea":
        kind, options = "textarea", []
    elif first["type"] == "select":
        kind, options = "select", [" ".join(option.split()) for option in first["options"]]
    elif first["type"] == "radio":
        kind, options = "select", [control["value"] for control in controls]
    elif first["type"] == "checkbox":
        kind, options = "multi_select", [control["value"] for control in controls]
    elif first["name"] == "location":
        kind, options = "location", []
    else:
        kind, options = "text", []
    return FormField(
        key=first["name"],
        label=" ".join(question["label"].split()),
        kind=kind,
        required=question["required"] or any(control["required"] for control in controls),
        options=options,
        profile_key=PROFILE_FIELDS.get(first["name"], ""),
    )


def choose_location(page, value):
    """Click the place suggestion for a "City, State" value.

    Lever suggests places like "Troy, NY, USA", so a state written out in full is matched by
    its two-letter code. Never picks a same-named city in another state: with no match it
    raises, so the run stops instead of sending a wrong location.
    """
    options = page.locator(".dropdown-results .dropdown-location")
    options.first.wait_for()
    city, state = split_place(value)
    states = {state, STATE_CODES.get(state, state)} - {""}
    seen = []
    for index in range(options.count()):
        text = options.nth(index).inner_text()
        seen.append(text)
        parts = [part.strip().lower() for part in text.split(",")]
        if parts[0] == city and (not states or (len(parts) > 1 and parts[1] in states)):
            # Lever picks a suggestion on mouse-down. Sent to the element itself, it works
            # even with a cookie banner pinned over the page.
            options.nth(index).dispatch_event("mousedown")
            return
    raise PlaywrightError(f'No location suggestion matches "{value}". Suggestions: {seen}')


def pick(choice):
    """Turn on one radio button or checkbox.

    It's clicked on the element itself, not with the mouse: a cookie banner pinned over the
    page would catch a mouse click meant for a choice underneath it.
    """
    if not choice.is_checked():
        choice.evaluate("element => element.click()")
    if not choice.is_checked():
        raise PlaywrightError("A choice on the form didn't stay selected.")


def wait_for_resume(page):
    """Wait until Lever has read the attached resume, since it fills boxes from it.

    Lever shows "Analyzing resume..." and then a success or a couldn't-read note. Either one
    means it's done; if neither shows up in time, the fill carries on with the file attached.
    """
    try:
        page.locator(".resume-upload-success, .resume-upload-failure").locator(
            "visible=true").first.wait_for(timeout=RESUME_WAIT_MS)
    except PlaywrightTimeout:
        pass


class LeverForm(AtsForm):
    """A Lever form. Its questions are read from the job's public apply page."""

    def __init__(self, link, job_data=None, url=None):
        super().__init__(link)
        # Tests pass in saved page data and a fake form instead of going online
        self.job_data = job_data
        self.url = url

    def form_url(self):
        """Return the apply page for this job."""
        return self.url or APPLY_URL.format(company=self.link.company, job_id=self.link.job_id)

    def read_fields(self):
        """Read the form's questions from the apply page."""
        if self.job_data is None:
            request = Request(self.form_url(), headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=15) as response:
                self.job_data = parse_page(response.read().decode("utf-8", errors="replace"))
        return [FormField(**form_field) for form_field in self.job_data["fields"]]

    def wait_until_ready(self, page):
        """Wait for the application form and the page's scripts.

        The resume upload needs Lever's scripts, so the page has to finish loading. Waiting for
        the network to go quiet only helps a little: tracking pixels on some postings never
        stop, so that wait is cut short instead of failing the run.
        """
        page.locator("#application-form").wait_for(state="attached")
        page.wait_for_load_state("load")
        try:
            page.wait_for_load_state("networkidle", timeout=QUIET_WAIT_MS)
        except PlaywrightTimeout:
            pass

    def fill(self, page, form_field, value):
        """Type, pick or upload one answer, by the field's name."""
        box = page.locator(f'[name="{form_field.key}"]')
        if form_field.kind == "file":
            box.set_input_files(value)
            if form_field.key == "resume":
                wait_for_resume(page)
        elif form_field.kind == "location":
            # The box only suggests places while you type, so type the city and pick the
            # suggestion that matches, like "Troy, NY, USA"
            box.focus()
            box.fill("")  # Lever may have put the resume's city in already
            box.press_sequentially(split_place(value)[0], delay=50)
            choose_location(page, value)
        elif box.first.evaluate("element => element.tagName") == "SELECT":
            box.select_option(label=value)
        elif form_field.kind in ("select", "multi_select"):
            # Radio buttons and checkboxes share a name, and the answer is one's value
            for index in range(box.count()):
                if box.nth(index).get_attribute("value") == value:
                    pick(box.nth(index))
                    return
            raise PlaywrightError(f'"{form_field.label}" has no choice "{value}".')
        else:
            box.fill(value)

    def submit(self, page):
        """Press Submit application."""
        page.locator("#btn-submit").click()

    def is_confirmed(self, page, timeout_ms=None):
        """Wait for Lever's thank-you page, up to timeout_ms (the page's default if None)."""
        try:
            page.get_by_text(CONFIRMATION).first.wait_for(timeout=timeout_ms)
            return True
        except PlaywrightTimeout:
            return page.url.rstrip("/").endswith("/thanks")

    def is_open(self, page):
        """Return True while the application form is still on the page."""
        return page.locator("#application-form").count() > 0

    def is_blocked(self, page):
        """Return True if Lever says it couldn't verify the application (its bot check)."""
        try:
            return page.get_by_text(BLOCKED).first.is_visible()
        except PlaywrightError:
            return False
