"""Tests for the steps the agent leaves to the applicant: CAPTCHA, sign-in, password and SSN.

The fake page's ?protect=ssn|password|captcha variants add one such step to the form.
"""
import copy

import pytest

from agent.answers.answerer import Answerer
from agent.forms.greenhouse_form import GreenhouseForm
from agent.forms.protected import (CAPTCHA, LOGIN, PASSWORD, SSN, CaptchaCheck, LoginCheck,
                                   PageField, PasswordCheck, ProtectedFieldDetector, SsnCheck,
                                   handoff_reason)
from agent.runner.apply_run import ApplyRun
from agent.tests.test_apply_run_events import WHY_HERE
from agent.tests.test_greenhouse import API_DATA, LINK, example_profile, fake_claude, fake_form


class FakeCaptcha(CaptchaCheck):
    """Treats the local fake CAPTCHA page like a real CAPTCHA frame."""

    FRAME_HOSTS = ("fake_captcha.html",)


def fake_detector():
    """Return a detector that also knows the fake CAPTCHA frame."""
    return ProtectedFieldDetector([FakeCaptcha(), SsnCheck(), PasswordCheck(), LoginCheck()])


def protected_form(kind):
    """Return the fake form with one protected step of this kind on it."""
    form = fake_form()
    form.url += f"?protect={kind}"
    return form


def answerer():
    """Return an Answerer that knows every answer the fake form needs."""
    return Answerer(example_profile(WHY_HERE), fake_claude)


@pytest.mark.parametrize("page_field, kind", [
    (PageField(label="Social Security Number"), SSN),
    (PageField(name="social_security_number"), SSN),
    (PageField(label="SSN (last 4 digits)"), SSN),
    (PageField(label="Create a password", input_type="password"), PASSWORD),
    (PageField(label="Password *"), PASSWORD),
    (PageField(autocomplete="new-password"), PASSWORD),
    (PageField(label="Username"), LOGIN),
    (PageField(label="Enter the verification code we emailed you"), LOGIN),
    (PageField(autocomplete="one-time-code"), LOGIN),
    (PageField(name="g-recaptcha-response"), CAPTCHA),
])
def test_protected_fields_are_recognized(page_field, kind):
    """Each kind of protected field is found from what describes it."""
    assert ProtectedFieldDetector().check_field(page_field).kind == kind


@pytest.mark.parametrize("label", [
    "GitHub username", "LinkedIn Profile", "Email", "Why do you want to work here?",
    "Are you legally authorized to work in the United States?", "How did you sign up?",
])
def test_normal_questions_are_not_protected(label):
    """Ordinary application questions stay with the agent."""
    assert ProtectedFieldDetector().check_field(PageField(label=label)) is None


def test_invisible_captcha_frames_are_not_a_step():
    """An invisible reCAPTCHA only shows a badge, so there's nothing to hand off."""
    check = CaptchaCheck()
    assert check.matches_frame("https://www.google.com/recaptcha/api2/anchor?k=abc&size=normal")
    assert not check.matches_frame(
        "https://www.google.com/recaptcha/enterprise/anchor?k=abc&size=invisible")
    assert not check.matches_frame("https://job-boards.greenhouse.io/embed/job_app")


def test_reason_has_one_sentence_per_kind():
    """Two fields of the same kind give one sentence, not two."""
    detector = ProtectedFieldDetector()
    handoffs = [detector.check_field(PageField(label=label))
                for label in ("SSN", "Social Security Number", "Username")]
    assert handoff_reason(handoffs) == f"{SsnCheck.message} {LoginCheck.message}"


@pytest.mark.parametrize("kind", ["ssn", "password", "captcha"])
def test_form_with_a_protected_step_is_filled_but_never_sent(tmp_path, kind):
    """The agent fills everything else, leaves the protected step alone and doesn't press Submit."""
    run = ApplyRun(answerer(), tmp_path, submit=True, hold=True, detector=fake_detector())
    result = run.run(protected_form(kind))
    try:
        assert result.status == "handoff", result.reason
        assert [handoff.kind for handoff in result.protected] == [kind]
        assert not result.pressed
        assert len(result.filled) == len(result.answered)
        page = result.held.page
        assert page.locator("#application-form").count() == 1  # still the form, not sent
        if kind != "captcha":
            box = page.locator("#question_2099, #account_password")
            assert box.input_value() == ""
    finally:
        result.held.close()


def test_plain_form_has_nothing_protected(tmp_path):
    """The usual fake form has no protected step, so it ends ready as before."""
    result = ApplyRun(answerer(), tmp_path, detector=fake_detector()).run(fake_form())
    assert result.status == "ready" and not result.protected


def test_protected_question_is_never_answered_or_asked(tmp_path):
    """A required SSN question from the site isn't answered, and the applicant isn't asked."""
    job_data = copy.deepcopy(API_DATA)
    job_data["questions"].append({
        "label": "Social Security Number", "required": True,
        "fields": [{"name": "question_2099", "type": "input_text", "values": []}]})
    form = GreenhouseForm(LINK, job_data=job_data, url=protected_form("ssn").url)
    result = ApplyRun(answerer(), tmp_path).run(form)
    assert result.status == "handoff", result.reason
    assert not result.questions
    assert all(form_field.key != "question_2099" for form_field, _answer in result.answered)
    assert [handoff.kind for handoff in result.protected] == [SSN]
