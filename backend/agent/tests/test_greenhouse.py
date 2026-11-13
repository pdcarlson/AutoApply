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


# Trimmed from SingleStore's real API data (job 8205389): its work authorization questions
# are in demographic_questions, and its EEOC ones in compliance.
WORK_AUTH_DATA = {
    "questions": [],
    "demographic_questions": {
        "header": "U.S. Standard Work Authorization",
        "questions": [
            {"id": 61945, "label": "Are you legally authorized to work in the United States?",
             "required": True, "type": "multi_value_single_select",
             "answer_options": [{"id": 1, "label": "Yes"}, {"id": 2, "label": "No"},
                                {"id": 3, "label": "I don't wish to answer"}]},
            {"id": 61946, "label": "Do you currently, or will you in the future, require "
                                   "sponsorship for employment authorization?",
             "required": True, "type": "multi_value_single_select",
             "answer_options": [{"id": 4, "label": "Yes"}, {"id": 5, "label": "No "},
                                {"id": 6, "label": "I don't wish to answer"}]},
        ],
    },
    "compliance": [
        {"type": "eeoc", "questions": [{"required": False, "label": "VeteranStatus", "fields": [
            {"name": "veteran_status", "type": "multi_value_single_select",
             "values": [{"label": "I don't wish to answer", "value": "3"},
                        {"label": "I am not a protected veteran", "value": "1"}]}]}]},
    ],
}


def test_demographic_questions_are_read():
    """Required work authorization questions in demographic_questions become fields."""
    fields = {form_field.key: form_field for form_field in fields_from_api(WORK_AUTH_DATA)}
    authorized, sponsorship = fields["61945"], fields["61946"]
    assert authorized.label == "Are you legally authorized to work in the United States?"
    assert authorized.kind == "select"
    assert authorized.required
    assert authorized.options == ["Yes", "No", "I don't wish to answer"]
    # "No " loses its stray space, so an answer of "No" fits
    assert sponsorship.options == ["Yes", "No", "I don't wish to answer"]


def test_compliance_questions_are_read():
    """EEOC questions come through with a readable label, and stay optional."""
    fields = {form_field.key: form_field for form_field in fields_from_api(WORK_AUTH_DATA)}
    veteran = fields["veteran_status"]
    assert veteran.label == "Veteran Status"
    assert not veteran.required
    assert veteran.options == ["I don't wish to answer", "I am not a protected veteran"]


def test_work_authorization_is_answered_from_the_profile():
    """With the questions read, the answerer fills them instead of leaving them blank."""
    def claude(form_field, _facts):
        value = "No" if "sponsorship" in form_field.label else "Yes"
        return FieldAnswer(value, "claude", 95, "From the profile.")

    answerer = Answerer(example_profile(), claude)
    fields = {form_field.key: form_field for form_field in fields_from_api(WORK_AUTH_DATA)}
    assert answerer.answer(fields["61945"]).value == "Yes"
    assert answerer.answer(fields["61946"]).value == "No"


def test_no_demographic_section():
    """Forms without the sections (or with them set to null) read as before."""
    data = dict(API_DATA, demographic_questions=None, compliance=None)
    assert [f.key for f in fields_from_api(data)] == [f.key for f in fields_from_api(API_DATA)]
