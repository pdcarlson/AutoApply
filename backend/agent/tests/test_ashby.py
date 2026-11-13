"""Tests for reading Ashby forms and running a whole application on a fake one."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile
from agent.forms import form_for
from agent.forms.ashby_form import AshbyForm, fields_from_api
from agent.forms.form_field import FieldAnswer
from agent.jobs.job_link import JobLink
from agent.runner.apply_run import ApplyRun
from agent.settings import AGENT_DIR

FAKE_FORMS = Path(__file__).parent / "fake_forms"
API_DATA = json.loads((FAKE_FORMS / "ashby_api.json").read_text(encoding="utf-8"))
LINK = JobLink.parse("https://jobs.ashbyhq.com/fakecompany/00000000-0000-4000-8000-000000001001")
SPONSORSHIP = "Will you now or in the future require visa sponsorship to work in the United States?"
TEAM = "Which team interests you most?"
WHY = "Why do you want to work here?"


def fake_form():
    """Return an AshbyForm that uses the saved posting and the fake form page."""
    return AshbyForm(LINK, job_data=API_DATA,
                     url=(FAKE_FORMS / "ashby_form.html").resolve().as_uri())


def example_profile(**answers):
    """A fresh copy of the example profile, with saved answers to the given questions."""
    profile = Profile.load(AGENT_DIR / "applicant" / "example_profile.json")
    for question, answer in answers.items():
        profile.save_answer(question, answer)
    return profile


def full_profile():
    """The example profile with an answer to every required question Claude won't answer."""
    return example_profile(**{TEAM: "Developer Tools", WHY: "I like building tools people use."})


def fake_claude(form_field, _facts):
    """Answer only the sponsorship question, like Claude would from the profile."""
    if "sponsorship" in form_field.label:
        return FieldAnswer("No", "claude", 95, "Profile says no sponsorship needed.")
    return FieldAnswer("", "claude", 0, "Not in the profile.")


def test_ashby_links_get_an_ashby_form():
    """Ashby links are filled now, and the application page keeps pasted tracking tags."""
    link = JobLink.parse("https://jobs.ashbyhq.com/acme/0a1b2c3d?utm_source=x")
    form = form_for(link)
    assert isinstance(form, AshbyForm)
    assert form.form_url() == "https://jobs.ashbyhq.com/acme/0a1b2c3d/application?utm_source=x"
    plain = form_for(JobLink.parse("https://jobs.ashbyhq.com/acme/0a1b2c3d/application"))
    assert plain.form_url() == "https://jobs.ashbyhq.com/acme/0a1b2c3d/application"


def test_fields_from_api():
    """System fields map to the profile, Yes/No questions become dropdowns, and hidden or
    unsupported questions (like dates) are left out."""
    fields = {form_field.key: form_field for form_field in fields_from_api(API_DATA)}
    assert fields["_systemfield_name"].profile_key == "full_name"
    assert fields["_systemfield_resume"].kind == "file"
    assert fields["_systemfield_resume"].profile_key == "resume_path"
    assert fields["_systemfield_location"].kind == "location"
    assert fields["_systemfield_phone"].profile_key == "phone"
    sponsorship = fields["a1000000-0000-4000-8000-000000000002"]
    assert (sponsorship.kind, sponsorship.options, sponsorship.required) == \
        ("select", ["Yes", "No"], True)
    assert fields["a1000000-0000-4000-8000-000000000004"].kind == "multi_select"
    assert fields["a1000000-0000-4000-8000-000000000003"].options == \
        ["LinkedIn", "A friend", "Other"]
    assert "a1000000-0000-4000-8000-000000000007" not in fields  # a Date question
    assert "a1000000-0000-4000-8000-000000000008" not in fields  # hidden


def test_url_questions_are_text_boxes():
    """Some companies ask for links with Ashby's Url type; they're filled like any text box."""
    posting = {"applicationForm": {"sections": [{"fieldEntries": [
        {"isRequired": False, "field": {"path": "u1", "title": "LinkedIn", "type": "Url"}},
        {"isRequired": False, "field": {"path": "e1", "title": "Education",
                                        "type": "EducationHistory"}}]}]}}
    fields = fields_from_api(posting)
    assert [(f.key, f.kind) for f in fields] == [("u1", "text")]


def test_posting_summary():
    assert fake_form().posting() == {"company": "", "title": "Software Engineering Intern",
                                     "location": "Troy, NY"}


def test_full_name():
    assert example_profile().full_name == "Jordan Rivera"


def test_missing_answer_stops_before_the_browser(tmp_path):
    """Required questions with no answer come back as questions, and nothing is filled."""
    result = ApplyRun(Answerer(example_profile(), fake_claude), tmp_path).run(fake_form())
    assert result.status == "needs_input"
    assert [form_field.label for form_field in result.questions] == [TEAM, WHY]
    assert not result.filled


def test_fills_every_kind_of_question(tmp_path):  # pylint: disable=unused-argument
    """Each Ashby input type gets its answer: text, file, location, Yes/No buttons, radio
    buttons, checkboxes and the type-to-search dropdown."""
    profile = full_profile()
    profile.save_answer("Which languages do you speak?", "French")
    profile.save_answer("How did you hear about this job?", "LinkedIn")
    answerer = Answerer(profile, fake_claude)
    form = fake_form()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.goto(form.form_url())
        form.wait_until_ready(page)
        assert form.is_open(page)
        for form_field in form.read_fields():
            answer = answerer.answer(form_field)
            if answer:
                form.fill(page, form_field, answer.value)
        answers = page.evaluate("window.answers()")
        browser.close()
    assert answers == {
        "name": "Jordan Rivera", "email": "jordan.rivera@example.com", "phone": "555-010-0123",
        "resume": 1, "location": "Troy, New York, United States",
        "linkedin": "https://www.linkedin.com/in/jordan-rivera-example", "sponsorship": "No",
        "hear": ["LinkedIn"], "languages": ["French"], "team": "Developer Tools",
        "why": "I like building tools people use.",
    }


def test_fills_and_submits_the_fake_form(tmp_path):
    """With every answer known, the agent fills the fake form, submits it and sees the success
    message."""
    profile = full_profile()
    result = ApplyRun(Answerer(profile, fake_claude), tmp_path, submit=True).run(fake_form())
    assert result.status == "submitted", result.reason
    assert ("Resume", profile.resume_path, "profile") == result.filled[0]
    assert (SPONSORSHIP, "No", "claude") in result.filled
    assert Path(result.screenshot).exists()


def test_dry_run_fills_but_doesnt_submit(tmp_path):
    result = ApplyRun(Answerer(full_profile(), fake_claude), tmp_path).run(fake_form())
    assert result.status == "ready", result.reason


@pytest.mark.parametrize("payload, error", [
    ({"data": {"jobPosting": None}}, "PostingClosed"),
    ({"errors": [{"message": "boom"}]}, "ValueError"),
])
def test_read_fields_errors(monkeypatch, payload, error):
    """A posting Ashby doesn't have is PostingClosed; any other API error is a ValueError."""
    class Response:  # pylint: disable=too-few-public-methods
        """A stand-in for urlopen's response."""
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):  # pylint: disable=unused-argument
            return json.dumps(payload).encode()

    seen = {}

    def fake_urlopen(request, timeout):  # pylint: disable=unused-argument
        seen["agent"] = request.get_header("User-agent")
        return Response()

    monkeypatch.setattr("agent.forms.ashby_form.urlopen", fake_urlopen)
    with pytest.raises(Exception) as caught:
        AshbyForm(LINK).read_fields()
    assert type(caught.value).__name__ == error
    assert seen["agent"].startswith("AutoApply/")
