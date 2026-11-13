"""Tests for answering voluntary self-identification questions from the applicant's answers."""
import copy

from agent.answers.answerer import Answerer
from agent.applicant.profile import Profile
from agent.forms.form_field import FieldAnswer, FormField
from agent.forms.greenhouse_form import fields_from_api
from agent.settings import AGENT_DIR

PROFILE = Profile.load(AGENT_DIR / "applicant" / "example_profile.json")
# Greenhouse's wording, from SingleStore's application form
GENDER = FormField("gender", "Gender", "select",
                   options=["Male", "Female", "Decline To Self Identify"], profile_key="gender")
HISPANIC = FormField("hispanic_ethnicity", "Are you Hispanic/Latino?", "select",
                     options=["Yes", "No", "Decline To Self Identify"],
                     profile_key="hispanic_latino")
RACE = FormField("race", "Please identify your race", "select", profile_key="race", options=[
    "American Indian or Alaskan Native", "Asian", "Black or African American", "White",
    "Native Hawaiian or Other Pacific Islander", "Two or More Races", "Decline To Self Identify"])
VETERAN = FormField("veteran_status", "Veteran Status", "select", profile_key="veteran", options=[
    "I am not a protected veteran",
    "I identify as one or more of the classifications of a protected veteran",
    "I don't wish to answer"])
DISABILITY = FormField("disability_status", "Disability Status", "select",
                       profile_key="disability", options=[
                           "Yes, I have a disability, or have had one in the past",
                           "No, I do not have a disability and have not had one in the past",
                           "I do not want to answer"])


def no_claude(_form_field, _facts):
    """A Claude that never helps, so every answer here comes from the profile."""
    return FieldAnswer("", "claude", 0)


def answers(**self_id):
    """The value the agent puts in each self-ID box for these answers, or None to ask."""
    profile = copy.deepcopy(PROFILE)
    profile.eeo = "ask"
    for key, value in self_id.items():
        setattr(profile, key, value)
    answerer = Answerer(profile, no_claude)
    picked = [answerer.answer(form_field) for form_field in
              (GENDER, HISPANIC, RACE, VETERAN, DISABILITY)]
    return [answer.value if answer else None for answer in picked]


def test_each_answer_picks_the_forms_wording():
    """Each answer becomes the option the form words it as."""
    assert answers(gender="Female", hispanic_latino="No", race="American Indian or Alaska Native",
                   veteran="No", disability="Yes") == [
        "Female", "No", "American Indian or Alaskan Native", "I am not a protected veteran",
        "Yes, I have a disability, or have had one in the past"]
    assert answers(gender="Male", hispanic_latino="No", race="White", veteran="Yes",
                   disability="No")[2:] == [
        "White", "I identify as one or more of the classifications of a protected veteran",
        "No, I do not have a disability and have not had one in the past"]


def test_decline_picks_each_forms_decline_option():
    """"I don't wish to answer" finds each form's way of declining."""
    assert answers(gender="decline", hispanic_latino="decline", veteran="decline",
                   disability="decline") == [
        "Decline To Self Identify", "Decline To Self Identify", "Decline To Self Identify",
        "I don't wish to answer", "I do not want to answer"]


def test_unanswered_questions_are_asked():
    """No answer, and a form that doesn't offer the answer, both leave it to the applicant."""
    assert answers() == [None] * 5
    assert answers(gender="Non-binary")[0] is None  # this form only offers Male and Female


def test_hispanic_applicants_pick_hispanic_in_a_combined_race_list():
    """Forms that ask race in one list get "Hispanic or Latino"."""
    combined = FormField("race", "Race/Ethnicity", "select", options=[
        "Asian", "Hispanic or Latino", "White", "I prefer not to say"])
    profile = copy.deepcopy(PROFILE)
    profile.eeo, profile.hispanic_latino = "ask", "Yes"
    assert Answerer(profile, no_claude).answer(combined).value == "Hispanic or Latino"


def test_an_old_profile_with_eeo_decline_declines_everything():
    """Profile files from before still decline, even on unmarked fields."""
    profile = copy.deepcopy(PROFILE)
    profile.eeo = "decline"
    answerer = Answerer(profile, no_claude)
    assert answerer.answer(VETERAN).value == "I don't wish to answer"
    unmarked = FormField("question_9", "Gender identity", "select",
                         options=["Woman", "Man", "Prefer not to say"])
    assert answerer.answer(unmarked).value == "Prefer not to say"


def test_greenhouse_adds_the_hispanic_box_before_race():
    """The page asks Hispanic/Latino first and only shows race after "No"; the API omits it."""
    job = {"questions": [], "compliance": [{"type": "eeoc", "questions": [
        {"required": False, "label": "Race", "fields": [
            {"name": "race", "type": "multi_value_single_select",
             "values": [{"label": "Asian", "value": "2"}]}]},
        {"required": False, "label": "Gender", "fields": [
            {"name": "gender", "type": "multi_value_single_select",
             "values": [{"label": "Male", "value": "1"}]}]}]}]}
    fields = fields_from_api(job)
    assert [f.key for f in fields] == ["hispanic_ethnicity", "race", "gender"]
    assert [f.profile_key for f in fields] == ["hispanic_latino", "race", "gender"]
    assert fields[0].options == ["Yes", "No", "Decline To Self Identify"]
    assert not fields[0].required
