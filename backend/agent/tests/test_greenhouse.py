"""Tests for reading Greenhouse forms and running a whole application on a fake one."""
import json
from pathlib import Path

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile
from agent.forms.form_field import FieldAnswer
from agent.forms.greenhouse_form import GreenhouseForm, fields_from_api
from agent.jobs.job_link import JobLink
from agent.runner.apply_run import ApplyRun
from agent.settings import AGENT_DIR

FAKE_FORMS = Path(__file__).parent / "fake_forms"
API_DATA = json.loads((FAKE_FORMS / "greenhouse_api.json").read_text(encoding="utf-8"))
LINK = JobLink.parse("https://job-boards.greenhouse.io/fakecompany/jobs/1001")


def fake_form():
    """Return a GreenhouseForm that uses the saved API data and the fake form page."""
    return GreenhouseForm(LINK, job_data=API_DATA,
                          url=(FAKE_FORMS / "greenhouse_form.html").resolve().as_uri())


def example_profile(why_here=""):
    """Load a fresh copy of the fake profile, with an answer to the essay question if given."""
    profile = Profile.load(AGENT_DIR / "applicant" / "example_profile.json")
    if why_here:
        profile.save_answer("Why do you want to work here?", why_here)
    return profile


def fake_claude(form_field, _facts):
    """Answer only the sponsorship question, like Claude would from the profile."""
    if "sponsorship" in form_field.label:
        return FieldAnswer("No", "claude", 95, "Profile says no sponsorship needed.")
    return FieldAnswer("", "claude", 0, "Not in the profile.")


def test_fields_from_api():
    """The resume is one file field, and dropdown options come through."""
    fields = {form_field.key: form_field for form_field in fields_from_api(API_DATA)}
    assert "resume_text" not in fields
    assert fields["resume"].kind == "file"
    assert fields["resume"].profile_key == "resume_path"
    assert fields["question_2002"].options == ["Yes", "No"]
    assert fields["question_2004"].required


def test_missing_answer_stops_before_the_browser(tmp_path):
    """A required question with no answer comes back as a question, and nothing is filled."""
    run = ApplyRun(Answerer(example_profile(), fake_claude), tmp_path, submit=True)
    result = run.run(fake_form())
    assert result.status == "needs_input"
    labels = [form_field.label for form_field in result.questions]
    assert labels == ["Why do you want to work here?"]
    assert not result.filled


def test_fills_and_submits_the_fake_form(tmp_path):
    """With every answer known, the agent fills the fake form, submits it and sees the thank-you."""
    profile = example_profile("I like building tools people use.")
    run = ApplyRun(Answerer(profile, fake_claude), tmp_path, submit=True)
    result = run.run(fake_form())
    assert result.status == "submitted", result.reason
    assert ("Resume/CV", profile.resume_path, "profile") == result.filled[0]
    assert ("Will you now or in the future require visa sponsorship to work in the United States?",
            "No", "claude") in result.filled
    assert Path(result.screenshot).exists()


def test_dry_run_fills_but_doesnt_submit(tmp_path):
    """With submitting off, the form is filled and left ready."""
    profile = example_profile("I like building tools people use.")
    result = ApplyRun(Answerer(profile, fake_claude), tmp_path).run(fake_form())
    assert result.status == "ready"
