"""Tests for reading Lever apply pages and running a whole application on a fake one."""
from pathlib import Path

from agent.answers.answerer import Answerer
from agent.forms import form_for
from agent.forms.form_field import FieldAnswer
from agent.forms.lever_form import LeverForm, parse_page
from agent.jobs.job_link import JobLink
from agent.runner.apply_run import ApplyRun
from agent.tests.test_greenhouse import example_profile

FAKE_PAGE = Path(__file__).parent / "fake_forms" / "lever_form.html"
LINK = JobLink.parse("https://jobs.lever.co/fakelever/0a1b2c3d-4e5f")
WHY_HERE = "Why do you want to work here?"
SCHOOL = "Which school do you attend?"


def fake_form():
    """Return a LeverForm that reads and fills the local fake apply page."""
    page = FAKE_PAGE.read_text(encoding="utf-8")
    return LeverForm(LINK, job_data=parse_page(page), url=FAKE_PAGE.resolve().as_uri())


def profile():
    """The example profile, with saved answers for the fake form's own questions."""
    applicant = example_profile("I like building tools people use.")
    applicant.save_answer(SCHOOL, "Rensselaer Polytechnic Institute")
    return applicant


def fake_claude(form_field, _facts):
    """Answer only the work authorization question, like Claude would from the profile."""
    if "authorized" in form_field.label:
        return FieldAnswer("Yes", "claude", 95, "Profile says authorized.")
    return FieldAnswer("", "claude", 0, "Not in the profile.")


def test_links_get_a_lever_form():
    """A Lever link now gets a form the agent can fill."""
    assert isinstance(form_for(LINK), LeverForm)
    assert LINK.url == "https://jobs.lever.co/fakelever/0a1b2c3d-4e5f"
    assert form_for(LINK).form_url() == "https://jobs.lever.co/fakelever/0a1b2c3d-4e5f/apply"


def test_page_is_read_into_fields():
    """Labels lose their required star, standard boxes map to the profile, and demographic
    questions and pronouns are left out."""
    data = parse_page(FAKE_PAGE.read_text(encoding="utf-8"))
    assert data["company_name"] == "Fake Lever Company"
    assert data["title"] == "Software Engineering Intern"
    assert data["location"] == {"name": "Troy, NY"}
    fields = {f["label"]: f for f in data["fields"]}
    assert list(fields) == ["Resume/CV", "Full name", "Email", "Phone", "Current location",
                            "LinkedIn URL", "Are you legally authorized to work in the "
                            "United States?", SCHOOL, "Which languages do you speak?", WHY_HERE]
    assert fields["Resume/CV"]["kind"] == "file" and fields["Resume/CV"]["required"]
    assert fields["Full name"]["profile_key"] == "full_name"
    assert fields["Current location"]["kind"] == "location"
    assert not fields["Phone"]["required"]
    authorized = fields["Are you legally authorized to work in the United States?"]
    assert authorized["kind"] == "select" and authorized["options"] == ["Yes", "No"]
    assert fields[SCHOOL]["options"] == ["Hudson Valley Institute of Technology",
                                         "Rensselaer Polytechnic Institute"]
    assert fields["Which languages do you speak?"]["kind"] == "multi_select"
    assert fields[WHY_HERE]["kind"] == "textarea" and fields[WHY_HERE]["required"]


def test_missing_answer_stops_before_the_browser(tmp_path):
    """A required question with no answer comes back as a question, and nothing is filled."""
    run = ApplyRun(Answerer(example_profile(), fake_claude), tmp_path, submit=True)
    result = run.run(fake_form())
    assert result.status == "needs_input"
    assert [form_field.label for form_field in result.questions] == [SCHOOL, WHY_HERE]
    assert not result.filled


def test_fills_and_submits_the_fake_form(tmp_path):
    """With every answer known, the agent fills the fake form, submits it and sees the thank-you."""
    applicant = profile()
    result = ApplyRun(Answerer(applicant, fake_claude), tmp_path, submit=True).run(fake_form())
    assert result.status == "submitted", result.reason
    filled = {label: (value, source) for label, value, source in result.filled}
    assert filled["Resume/CV"] == (applicant.resume_path, "profile")
    assert filled["Full name"] == ("Jordan Rivera", "profile")
    assert filled["Current location"] == ("Troy, New York", "profile")
    assert filled["Are you legally authorized to work in the United States?"] == ("Yes", "claude")
    assert filled[SCHOOL] == ("Rensselaer Polytechnic Institute", "saved")
    assert Path(result.screenshot).exists()


def test_dry_run_leaves_every_answer_on_the_page(tmp_path):
    """With submitting off, the held page shows each answer where Lever reads it."""
    run = ApplyRun(Answerer(profile(), fake_claude), tmp_path, hold=True)
    result = run.run(fake_form())
    try:
        assert result.status == "ready", result.reason
        page = result.held.page
        assert page.locator('[name="name"]').input_value() == "Jordan Rivera"
        assert page.locator("#location-input").input_value() == "Troy, NY, USA"
        assert "Troy, NY, USA" in page.locator("#selected-location").input_value()
        assert page.locator('[name="cards[abc][field0]"][value="Yes"]').is_checked()
        assert page.locator('[name="cards[abc][field1]"]').evaluate(
            "select => select.selectedOptions[0].text") == "Rensselaer Polytechnic Institute"
        assert page.locator('[name="cards[abc][field3]"]').input_value() \
            == "I like building tools people use."
        assert page.locator(".resume-upload-success").is_visible()
        assert page.locator('[name="eeo[gender]"]').input_value() == ""  # left alone
    finally:
        result.held.close()


def test_bot_check_rejection_is_recognized(tmp_path):
    """When Lever's bot check turns the application away, the run says so instead of a plain
    "no confirmation"."""
    form = fake_form()
    form.url += "?verify=fail"
    run = ApplyRun(Answerer(profile(), fake_claude), tmp_path, submit=True, confirm_timeout_s=1)
    result = run.run(form)
    assert result.status == "failed" and result.pressed and result.blocked
    assert result.reason == "The site's bot check turned the application away after Submit."


def test_busy_page_is_still_filled(tmp_path):
    """A page whose network never goes quiet (tracking pixels) is filled after a short wait
    instead of failing."""
    form = fake_form()
    form.url += "?busy=1"
    result = ApplyRun(Answerer(profile(), fake_claude), tmp_path).run(form)
    assert result.status == "ready", result.reason


def test_choices_under_a_cookie_banner_are_still_picked(tmp_path):
    """A banner pinned over the page doesn't stop radio buttons from being selected."""
    form = fake_form()
    form.url += "?banner=1"
    run = ApplyRun(Answerer(profile(), fake_claude), tmp_path, hold=True)
    result = run.run(form)
    try:
        assert result.status == "ready", result.reason
        assert result.held.page.locator('[name="cards[abc][field0]"][value="Yes"]').is_checked()
    finally:
        result.held.close()


def test_location_typed_without_a_comma_is_still_matched(tmp_path):
    """"Troy NY" (how a person answers the question) picks "Troy, NY, USA", not Troy, MI."""
    applicant = profile()
    applicant.city, applicant.state = "", ""
    applicant.save_answer("Current location", "Troy NY")
    run = ApplyRun(Answerer(applicant, fake_claude), tmp_path, hold=True)
    result = run.run(fake_form())
    try:
        assert result.status == "ready", result.reason
        assert result.held.page.locator("#location-input").input_value() == "Troy, NY, USA"
    finally:
        result.held.close()
