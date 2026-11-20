"""Fakes and saved data the agent's tests share: the fake form, profile, Claude and browser spy."""
import json
from pathlib import Path

from playwright.sync_api import Browser, BrowserType, sync_playwright

from agent.applicant.profile import Profile
from agent.forms.form_field import AnswerSource, FieldAnswer
from agent.forms.greenhouse_form import GreenhouseForm
from agent.jobs.job_link import JobLink
from agent.settings import AGENT_DIR

FAKE_FORMS = Path(__file__).parent / "fake_forms"
API_DATA = json.loads((FAKE_FORMS / "greenhouse_api.json").read_text(encoding="utf-8"))
LINK = JobLink.parse("https://job-boards.greenhouse.io/fakecompany/jobs/1001")
WHY_HERE = "I like building tools people use."


def fake_form() -> GreenhouseForm:
    """Return a GreenhouseForm that uses the saved API data and the fake form page."""
    return GreenhouseForm(LINK, job_data=API_DATA,
                          url=(FAKE_FORMS / "greenhouse_form.html").resolve().as_uri())


def variant(query: str) -> GreenhouseForm:
    """Return the fake form, with a test-only variant picked by `query`.

    ?confirm_ms=N confirms N ms after Submit, ?code=1 asks for an emailed code (its Verify
    button, or confirm_ms running out, confirms), ?code=boxes asks for it in one box per
    character, and ?protect=ssn|password|captcha adds a protected step. All zeros is a wrong
    code.
    """
    form = fake_form()
    form.url += f"?{query}"
    return form


def bare_form() -> GreenhouseForm:
    """Return a GreenhouseForm for a made-up job, with no saved data, for filling one box."""
    return GreenhouseForm(JobLink.parse("https://job-boards.greenhouse.io/fakecompany/jobs/1"))


def open_page(html: str, timeout_ms: float | None = None):
    """Yield a browser page showing `html`, and close the browser afterwards."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        if timeout_ms is not None:
            page.set_default_timeout(timeout_ms)
        page.set_content(html)
        yield page
        browser.close()


def example_profile(why_here: str = "") -> Profile:
    """Load a fresh copy of the fake profile, with an answer to the essay question if given."""
    profile = Profile.load(AGENT_DIR / "applicant" / "example_profile.json")
    if why_here:
        profile.save_answer("Why do you want to work here?", why_here)
    return profile


def fake_claude(form_field, _facts) -> FieldAnswer:
    """Answer only the sponsorship question, like Claude would from the profile."""
    if "sponsorship" in form_field.label:
        return FieldAnswer("No", AnswerSource.CLAUDE, 95, "Profile says no sponsorship needed.")
    return FieldAnswer("", AnswerSource.CLAUDE, 0, "Not in the profile.")


class Recorder:
    """Collects every on_event call as (kind, data)."""

    def __init__(self):
        """Start with no events."""
        self.events = []

    def __call__(self, kind, **data):
        """Record one event."""
        self.events.append((kind, data))

    def kinds(self) -> list[str]:
        """Return the events as short strings like 'phase:opening' or 'field'."""
        return [f"phase:{data['name']}" if kind == "phase" else kind for kind, data in self.events]


def spy_on_browsers(monkeypatch) -> dict:
    """Record how each browser is launched and whether it's closed."""
    seen = {"launch": [], "closed": 0}
    launch, close = BrowserType.launch, Browser.close

    def spy_launch(self, *args, **kwargs):
        """Record the launch options, then launch."""
        seen["launch"].append(kwargs)
        return launch(self, *args, **kwargs)

    def spy_close(self, *args, **kwargs):
        """Count the close, then close."""
        seen["closed"] += 1
        return close(self, *args, **kwargs)

    monkeypatch.setattr(BrowserType, "launch", spy_launch)
    monkeypatch.setattr(Browser, "close", spy_close)
    return seen
