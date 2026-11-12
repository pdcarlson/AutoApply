"""Tests for picking answers."""
import copy

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile
from agent.forms.form_field import FieldAnswer, FormField
from agent.settings import AGENT_DIR

PROFILE = Profile.load(AGENT_DIR / "applicant" / "example_profile.json")
SPONSORSHIP = FormField("question_1", "Do you need sponsorship?", "select", True, ["Yes", "No"])


def claude_says(value, confidence):
    """Return a fake ask_claude that always gives the same answer."""
    return lambda _form_field, _facts: FieldAnswer(value, "claude", confidence)


def test_standard_fields_come_from_the_profile():
    """Email and LinkedIn are filled from the profile without asking Claude."""
    answerer = Answerer(PROFILE, claude_says("wrong", 100))
    email = answerer.answer(FormField("email", "Email", "text", profile_key="email"))
    linkedin = answerer.answer(FormField("question_1", "LinkedIn Profile", "text"))
    assert (email.value, email.source) == ("jordan.rivera@example.com", "profile")
    assert linkedin.value == PROFILE.linkedin


def test_saved_answer_beats_claude():
    """A question the applicant already answered uses their answer."""
    profile = copy.deepcopy(PROFILE)
    profile.save_answer("How did you hear about this job?", "LinkedIn")
    answerer = Answerer(profile, claude_says("wrong", 100))
    answer = answerer.answer(FormField("question_1", "How did you hear about this job? ", "text"))
    assert (answer.value, answer.source) == ("LinkedIn", "saved")


def test_confident_claude_answer_is_used():
    """Claude's answer is used when it's sure and it's one of the options."""
    answer = Answerer(PROFILE, claude_says("No", 95)).answer(SPONSORSHIP)
    assert (answer.value, answer.source) == ("No", "claude")


def test_unsure_claude_answer_means_ask():
    """Below the threshold, the agent asks instead of guessing."""
    assert Answerer(PROFILE, claude_says("No", 60)).answer(SPONSORSHIP) is None


def test_answer_that_isnt_an_option_means_ask():
    """A dropdown answer has to be one of the dropdown's options."""
    assert Answerer(PROFILE, claude_says("Nope", 100)).answer(SPONSORSHIP) is None
